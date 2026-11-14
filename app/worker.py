import json
import logging
import os
from uuid import UUID

from prometheus_client import start_http_server

from app.main import ProcessingError, execute_processing, get_processing_run
from app.messaging import open_broker_connection

logger = logging.getLogger(__name__)


def decode_processing_message(body: bytes):
    message = json.loads(body)

    if not isinstance(message, dict):
        raise ValueError("Processing message must be a JSON object.")

    run_id = UUID(message["run_id"])
    correlation_id = str(UUID(message["correlation_id"]))

    return run_id, correlation_id


def handle_processing_message(channel, method, properties, body):
    try:
        run_id, correlation_id = decode_processing_message(body)
    except (ValueError, KeyError, TypeError, AttributeError):
        # Retrying cannot repair the payload. No dead-letter queue is configured,
        # so rejecting without requeue discards this message.
        logger.exception("Rejecting malformed processing message")
        channel.basic_reject(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )
        return

    try:
        execute_processing(
            run_id=run_id,
            correlation_id=correlation_id,
        )
    except ProcessingError:
        # An exception alone does not prove the failure was saved. Acknowledge
        # only a terminal database outcome, including already-completed duplicates.
        stored_run = get_processing_run(run_id)

        if stored_run is not None and (
            stored_run["status"] in ("succeeded", "failed")
            or (stored_run["status"] == "running" and stored_run.get("lease_expires_at") is not None)
        ):
            logger.info(
                "Acknowledging recorded terminal outcome",
                extra={
                    "run_id": str(run_id),
                    "status": stored_run["status"],
                    "correlation_id": correlation_id,
                },
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Stop consumption with delivery unsettled when durable state is uncertain.
        raise
    except Exception:
        logger.exception(
            "Worker execution stopped; message remains unacknowledged",
            extra={
                "run_id": str(run_id),
                "correlation_id": correlation_id,
            },
        )
        raise

    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    start_http_server(8001)
    connection = open_broker_connection()

    try:
        channel = connection.channel()
        queue_name = os.environ["RABBITMQ_QUEUE"]

        channel.queue_declare(queue=queue_name, durable=True)
        # One outstanding delivery bounds work held by this synchronous consumer.
        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(
            queue=queue_name,
            on_message_callback=handle_processing_message,
            auto_ack=False,
        )

        logger.info("Worker waiting for processing messages")
        channel.start_consuming()
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
