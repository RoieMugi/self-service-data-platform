"""Queue integration contracts, without a live broker or database."""

import json
from unittest.mock import Mock, call
from uuid import UUID

import pika
import pytest
from fastapi.testclient import TestClient

import app.main as api
import app.messaging as messaging
import app.worker as worker


RUN_ID = UUID("79d674f8-9a9b-4b31-8951-31c381b21429")
UPLOAD_ID = UUID("cd49f308-e39e-4d87-a7f0-f72f75bde678")
CORRELATION_ID = "0b87b403-bccc-4e92-a496-d41c27d18f42"
BODY = json.dumps({
    "run_id": str(RUN_ID), "correlation_id": CORRELATION_ID,
}).encode("utf-8")


@pytest.fixture
def submission(monkeypatch):
    dependencies = Mock()
    dependencies.get_upload.return_value = {"id": UPLOAD_ID}
    dependencies.create_processing_run.return_value = {"id": RUN_ID}
    for name in (
        "get_upload", "create_processing_run", "publish_pending_run",
        "execute_processing", "try_to_record_processing_failure",
    ):
        monkeypatch.setattr(api, name, getattr(dependencies, name))
    return dependencies


def submit():
    return TestClient(api.app).post(
        f"/uploads/{UPLOAD_ID}/process",
        headers={"X-Correlation-ID": CORRELATION_ID},
    )


def test_submission_publishes_existing_run_without_execution(submission):
    response = submit()
    assert response.status_code == 202
    assert response.json() == {"run_id": str(RUN_ID), "status": "queued"}
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert submission.mock_calls == [
        call.get_upload(UPLOAD_ID),
        call.create_processing_run(UPLOAD_ID, CORRELATION_ID),
        call.publish_pending_run(RUN_ID),
    ]


def test_submission_publish_failure_preserves_run(submission):
    submission.publish_pending_run.side_effect = RuntimeError("Confirmation lost")
    response = submit()
    assert response.status_code == 202
    assert response.json()["run_id"] == str(RUN_ID)
    submission.create_processing_run.assert_called_once_with(UPLOAD_ID, CORRELATION_ID)
    submission.execute_processing.assert_not_called()
    submission.try_to_record_processing_failure.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "lookup", "creation"])
def test_submission_does_not_publish_when_preparation_fails(submission, failure):
    if failure == "missing":
        submission.get_upload.return_value = None
    elif failure == "lookup":
        submission.get_upload.side_effect = RuntimeError("Database unavailable")
    else:
        submission.create_processing_run.side_effect = RuntimeError("Insert failed")
    response = submit()
    assert response.status_code == (404 if failure == "missing" else 500)
    submission.publish_pending_run.assert_not_called()
    submission.execute_processing.assert_not_called()
    if failure != "creation":
        submission.create_processing_run.assert_not_called()


@pytest.fixture
def broker(monkeypatch):
    connection = Mock(is_open=True)
    monkeypatch.setenv("RABBITMQ_QUEUE", "processing_runs")
    monkeypatch.setattr(messaging, "open_broker_connection", Mock(return_value=connection))
    return connection


def test_publisher_sends_persistent_routable_message_with_confirmation(broker):
    messaging.publish_processing_run(RUN_ID, CORRELATION_ID)
    channel = broker.channel.return_value
    channel.queue_declare.assert_called_once_with(queue="processing_runs", durable=True)
    channel.confirm_delivery.assert_called_once_with()
    channel.basic_publish.assert_called_once()
    sent = channel.basic_publish.call_args.kwargs
    assert sent["exchange"] == ""
    assert sent["routing_key"] == "processing_runs"
    assert sent["mandatory"] is True
    assert json.loads(sent["body"]) == json.loads(BODY)
    properties = sent["properties"]
    assert properties.delivery_mode == 2
    assert properties.content_type == "application/json"
    assert properties.message_id == str(RUN_ID)
    assert properties.correlation_id == CORRELATION_ID
    assert [item[0] for item in channel.mock_calls] == [
        "queue_declare", "confirm_delivery", "basic_publish",
    ]
    broker.close.assert_called_once_with()


@pytest.mark.parametrize("stage", ["queue_declare", "confirm_delivery", "basic_publish"])
def test_publisher_propagates_failure_and_closes_connection(broker, stage):
    error = RuntimeError("Broker operation failed")
    getattr(broker.channel.return_value, stage).side_effect = error
    with pytest.raises(RuntimeError) as caught:
        messaging.publish_processing_run(RUN_ID, CORRELATION_ID)
    assert caught.value is error
    broker.close.assert_called_once_with()


@pytest.mark.parametrize("error", [
    pika.exceptions.UnroutableError([]), pika.exceptions.NackError([]),
])
def test_publisher_surfaces_broker_rejection(broker, error):
    broker.channel.return_value.basic_publish.side_effect = error
    with pytest.raises(type(error)):
        messaging.publish_processing_run(RUN_ID, CORRELATION_ID)
    broker.close.assert_called_once_with()


def test_worker_acknowledges_only_after_execution(monkeypatch):
    channel = Mock()

    def execute(**kwargs):
        channel.basic_ack.assert_not_called()

    execution = Mock(side_effect=execute)
    monkeypatch.setattr(worker, "execute_processing", execution)
    worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)
    execution.assert_called_once_with(run_id=RUN_ID, correlation_id=CORRELATION_ID)
    channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.basic_reject.assert_not_called()


@pytest.fixture
def unclaimed_run(monkeypatch):
    """Use real execution while isolating database and processing effects."""
    dependencies = Mock()
    dependencies.claim_processing_run.return_value = None
    dependencies.get_processing_run.return_value = {
        "id": RUN_ID, "status": "succeeded",
    }
    for name in (
        "claim_processing_run", "get_processing_run", "create_processing_run",
        "get_upload", "download_raw_object", "convert_csv_to_parquet",
        "upload_curated_object", "complete_processing_run",
        "try_to_record_processing_failure", "record_processing_metrics",
    ):
        monkeypatch.setattr(api, name, getattr(dependencies, name))
    monkeypatch.setattr(worker, "get_processing_run", dependencies.get_processing_run)
    return dependencies


@pytest.mark.parametrize("status", ["succeeded", "failed"])
def test_worker_acknowledges_terminal_run_without_reprocessing(unclaimed_run, status):
    unclaimed_run.get_processing_run.return_value = {
        "id": RUN_ID, "status": status,
    }
    channel = Mock()

    # Repeated deliveries of the same run must each be handled safely.
    for delivery_tag in (7, 8):
        worker.handle_processing_message(
            channel, Mock(delivery_tag=delivery_tag), None, BODY,
        )

    assert unclaimed_run.mock_calls == [
        call.claim_processing_run(RUN_ID),
        call.get_processing_run(RUN_ID),
        call.claim_processing_run(RUN_ID),
        call.get_processing_run(RUN_ID),
    ]
    assert channel.mock_calls == [
        call.basic_ack(delivery_tag=7),
        call.basic_ack(delivery_tag=8),
    ]


@pytest.mark.parametrize("status", [None, "queued", "running"])
def test_worker_does_not_acknowledge_other_unclaimed_runs(unclaimed_run, status):
    """Missing and nonterminal runs must not be acknowledged after a refused claim."""
    unclaimed_run.get_processing_run.return_value = (
        None if status is None else {"id": RUN_ID, "status": status}
    )
    channel = Mock()

    with pytest.raises(api.ProcessingError, match="not available to start"):
        worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)

    assert unclaimed_run.mock_calls == [
        call.claim_processing_run(RUN_ID),
        call.get_processing_run(RUN_ID),
        call.get_processing_run(RUN_ID),
    ]
    assert channel.mock_calls == []


def test_worker_acknowledges_duplicate_with_recoverable_running_lease(unclaimed_run):
    unclaimed_run.get_processing_run.return_value = {
        "id": RUN_ID, "status": "running", "lease_expires_at": "future",
    }
    channel = Mock()
    worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)
    channel.basic_ack.assert_called_once_with(delivery_tag=7)


def test_worker_does_not_acknowledge_when_run_lookup_fails(unclaimed_run):
    error = RuntimeError("Database unavailable")
    unclaimed_run.get_processing_run.side_effect = error
    channel = Mock()

    with pytest.raises(RuntimeError) as caught:
        worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)

    assert caught.value is error
    assert unclaimed_run.mock_calls == [
        call.claim_processing_run(RUN_ID),
        call.get_processing_run(RUN_ID),
    ]
    assert channel.mock_calls == []


@pytest.mark.parametrize("body", [
    b"not json", b"\xff", b"[]", b"null", b"{}",
    b'{"run_id": "invalid", "correlation_id": "invalid"}',
    json.dumps({"run_id": str(RUN_ID), "correlation_id": "invalid"}).encode(),
    json.dumps({"run_id": None, "correlation_id": CORRELATION_ID}).encode(),
])
def test_worker_discards_malformed_message_without_execution(monkeypatch, body):
    execution = Mock()
    monkeypatch.setattr(worker, "execute_processing", execution)
    channel = Mock()
    worker.handle_processing_message(channel, Mock(delivery_tag=7), None, body)
    execution.assert_not_called()
    channel.basic_reject.assert_called_once_with(delivery_tag=7, requeue=False)
    channel.basic_ack.assert_not_called()


@pytest.mark.parametrize("error", [
    RuntimeError("Unexpected failure"),
    api.ProcessingError("validation_failed", "Invalid CSV"),
    api.ProcessingError("storage_failed", "Storage unavailable"),
])
@pytest.mark.parametrize("status", [None, "queued", "running"])
def test_worker_stops_without_acknowledging_execution_failure(monkeypatch, error, status):
    """An exception without a confirmed terminal outcome must not settle delivery."""
    monkeypatch.setattr(worker, "execute_processing", Mock(side_effect=error))
    lookup = Mock(return_value=None if status is None else {"status": status})
    monkeypatch.setattr(worker, "get_processing_run", lookup)
    channel = Mock()
    with pytest.raises(type(error)) as caught:
        worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)
    assert caught.value is error
    channel.basic_ack.assert_not_called()
    channel.basic_reject.assert_not_called()
    if isinstance(error, api.ProcessingError):
        lookup.assert_called_once_with(RUN_ID)
    else:
        lookup.assert_not_called()


@pytest.mark.parametrize("status", ["succeeded", "failed"])
@pytest.mark.parametrize("outcome", ["validation_failed", "storage_failed", "internal_failed"])
def test_worker_acknowledges_confirmed_terminal_outcome_after_error(monkeypatch, status, outcome):
    events = Mock()
    events.execute.side_effect = api.ProcessingError(outcome, "Processing failed")
    events.lookup.return_value = {"id": RUN_ID, "status": status}
    monkeypatch.setattr(worker, "execute_processing", events.execute)
    monkeypatch.setattr(worker, "get_processing_run", events.lookup)

    worker.handle_processing_message(events.channel, Mock(delivery_tag=7), None, BODY)

    assert events.mock_calls == [
        call.execute(run_id=RUN_ID, correlation_id=CORRELATION_ID),
        call.lookup(RUN_ID),
        call.channel.basic_ack(delivery_tag=7),
    ]


def test_worker_leaves_message_unacknowledged_when_error_recovery_lookup_fails(monkeypatch):
    monkeypatch.setattr(worker, "execute_processing", Mock(
        side_effect=api.ProcessingError("validation_failed", "Invalid CSV"),
    ))
    lookup_error = RuntimeError("Database unavailable")
    lookup = Mock(side_effect=lookup_error)
    monkeypatch.setattr(worker, "get_processing_run", lookup)
    channel = Mock()

    with pytest.raises(RuntimeError) as caught:
        worker.handle_processing_message(channel, Mock(delivery_tag=7), None, BODY)

    assert caught.value is lookup_error
    lookup.assert_called_once_with(RUN_ID)
    assert channel.mock_calls == []


def test_consumer_continues_after_recorded_processing_failure(monkeypatch):
    monkeypatch.setattr(worker, "start_http_server", Mock())
    monkeypatch.setenv("RABBITMQ_QUEUE", "processing_runs")
    connection = Mock(is_open=True)
    channel = connection.channel.return_value
    monkeypatch.setattr(worker, "open_broker_connection", Mock(return_value=connection))
    execution = Mock(side_effect=[
        api.ProcessingError("validation_failed", "Invalid CSV"), None,
    ])
    monkeypatch.setattr(worker, "execute_processing", execution)
    lookup = Mock(return_value={"id": RUN_ID, "status": "failed"})
    monkeypatch.setattr(worker, "get_processing_run", lookup)
    next_run_id = UUID("211b6ac8-1110-4f45-9304-0bcdca568173")
    next_body = json.dumps({
        "run_id": str(next_run_id), "correlation_id": CORRELATION_ID,
    }).encode()

    def consume():
        callback = channel.basic_consume.call_args.kwargs["on_message_callback"]
        callback(channel, Mock(delivery_tag=7), None, BODY)
        callback(channel, Mock(delivery_tag=8), None, next_body)

    channel.start_consuming.side_effect = consume
    worker.main()

    assert execution.call_args_list == [
        call(run_id=RUN_ID, correlation_id=CORRELATION_ID),
        call(run_id=next_run_id, correlation_id=CORRELATION_ID),
    ]
    lookup.assert_called_once_with(RUN_ID)
    assert channel.basic_ack.call_args_list == [
        call(delivery_tag=7), call(delivery_tag=8),
    ]
    channel.basic_reject.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("execution_fails", [False, True])
def test_consumer_uses_manual_ack_and_closes_on_exit(monkeypatch, execution_fails):
    fake_metrics_server = Mock()
    monkeypatch.setattr(worker, "start_http_server", fake_metrics_server)
    connection = Mock(is_open=True)
    channel = connection.channel.return_value
    monkeypatch.setenv("RABBITMQ_QUEUE", "processing_runs")
    monkeypatch.setattr(worker, "open_broker_connection", Mock(return_value=connection))
    execution = Mock(side_effect=RuntimeError("Execution failed") if execution_fails else None)
    monkeypatch.setattr(worker, "execute_processing", execution)

    def consume():
        options = channel.basic_consume.call_args.kwargs
        assert options["auto_ack"] is False
        options["on_message_callback"](channel, Mock(delivery_tag=7), None, BODY)

    channel.start_consuming.side_effect = consume
    if execution_fails:
        with pytest.raises(RuntimeError, match="Execution failed"):
            worker.main()
        channel.basic_ack.assert_not_called()
    else:
        worker.main()
        channel.basic_ack.assert_called_once_with(delivery_tag=7)
    channel.queue_declare.assert_called_once_with(queue="processing_runs", durable=True)
    channel.basic_qos.assert_called_once_with(prefetch_count=1)
    assert channel.basic_consume.call_args.kwargs["queue"] == "processing_runs"
    connection.close.assert_called_once_with()
