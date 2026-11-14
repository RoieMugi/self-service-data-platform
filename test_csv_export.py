import csv
from io import StringIO
from unittest.mock import Mock
from uuid import UUID

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.main as main
from app import query_executor


ID = UUID("aa20d66f-aa0e-4784-bbe0-7b6e5334e0d2")
client = TestClient(main.app)


@pytest.fixture
def parquet(tmp_path):
    path = tmp_path / "source.parquet"
    with duckdb.connect() as connection:
        connection.sql("SELECT 1 AS id, 'Alice' AS name, 150.25 AS amount").write_parquet(str(path))
    return path.read_bytes()


def parse(content):
    # An independent CSV reader checks DuckDB's output, including quoting/newlines.
    return list(csv.reader(StringIO(content.decode("utf-8"), newline="")))


def test_csv_has_all_rows_beyond_preview_limit(parquet):
    content, count = query_executor.execute_csv_query(parquet, "SELECT i FROM range(1500) t(i) ORDER BY i")
    rows = parse(content)
    assert count == 1500
    assert rows[0] == ["i"] and rows[-1] == ["1499"]
    assert len(rows) == 1501


def test_csv_quotes_special_values_preserves_unicode_and_decimal(parquet):
    content, count = query_executor.execute_csv_query(parquet,
        "SELECT 'a,b' AS comma, 'say \"hello\"' AS quote, 'first' || chr(10) || 'second' AS multiline, 'שלום' AS unicode, amount, NULL AS missing FROM dataset")
    assert count == 1
    assert parse(content) == [
        ["comma", "quote", "multiline", "unicode", "amount", "missing"],
        ["a,b", 'say "hello"', "first\nsecond", "שלום", "150.25", ""],
    ]


def test_empty_csv_retains_headers(parquet):
    content, count = query_executor.execute_csv_query(parquet, "SELECT id, name FROM dataset WHERE false")
    assert count == 0
    assert parse(content) == [["id", "name"]]


@pytest.mark.parametrize("sql", [
    "DROP TABLE dataset", "SELECT 1; SELECT 2",
    "SELECT * FROM read_text('request.json')",
    "SELECT * FROM range(100001)", "SELECT 1 AS x, 2 AS x",
    "SELECT repeat('x', 21000000) AS large",
])
def test_csv_rejects_disallowed_queries_and_overflow(parquet, sql):
    with pytest.raises(query_executor.QueryError):
        query_executor.execute_csv_query(parquet, sql)


@pytest.fixture
def dependencies(monkeypatch):
    run = Mock(return_value={"status": "succeeded", "curated_object_key": "run.parquet"})
    table = Mock(return_value={"object_key": "table.parquet"})
    download = Mock(return_value=b"source")
    export = Mock(return_value=(b"amount\n150\n", 1))
    insert = Mock(side_effect=AssertionError("CSV export must not register a table"))
    upload = Mock(side_effect=AssertionError("CSV export must not upload an artifact"))
    monkeypatch.setattr(main, "get_processing_run", run)
    monkeypatch.setattr(main, "get_saved_table", table)
    monkeypatch.setattr(main, "download_query_artifact", download)
    monkeypatch.setattr(main, "execute_csv_query", export)
    monkeypatch.setattr(main, "insert_saved_table", insert)
    monkeypatch.setattr(main, "upload_curated_object", upload)
    return run, table, download, export, insert, upload


@pytest.mark.parametrize("resource,key", [("processing-runs", "run.parquet"), ("tables", "table.parquet")])
def test_csv_routes_return_attachments_without_persisting(dependencies, resource, key):
    _, _, download, export, insert, upload = dependencies
    response = client.post(f"/{resource}/{ID}/query/csv", json={"sql": "SELECT amount FROM dataset"})
    assert response.status_code == 200
    assert response.content == b"amount\n150\n"
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="query-{ID}.csv"'
    assert response.headers["x-row-count"] == "1"
    assert "x-correlation-id" in response.headers
    download.assert_called_once_with(key)
    export.assert_called_once_with(b"source", "SELECT amount FROM dataset")
    insert.assert_not_called()
    upload.assert_not_called()


@pytest.mark.parametrize("resource", ["processing-runs", "tables"])
@pytest.mark.parametrize("body", [{"sql": " "}, {"sql": "SELECT 1", "max_rows": 10}, {"sql": "x" * 10001}])
def test_csv_input_validation(dependencies, resource, body):
    assert client.post(f"/{resource}/{ID}/query/csv", json=body).status_code == 422
    dependencies[2].assert_not_called()
    dependencies[3].assert_not_called()


@pytest.mark.parametrize("resource,index", [("processing-runs", 0), ("tables", 1)])
def test_missing_source(dependencies, resource, index):
    dependencies[index].return_value = None
    assert client.post(f"/{resource}/{ID}/query/csv", json={"sql": "SELECT 1"}).status_code == 404
    dependencies[2].assert_not_called()


def test_unfinished_run_cannot_export(dependencies):
    dependencies[0].return_value = {"status": "queued"}
    assert client.post(f"/processing-runs/{ID}/query/csv", json={"sql": "SELECT 1"}).status_code == 409
    dependencies[2].assert_not_called()


@pytest.mark.parametrize("error,status", [(query_executor.QueryError("Export limit exceeded"), 422), (OSError("private details"), 500)])
def test_csv_errors_are_not_file_attachments(dependencies, error, status):
    dependencies[3].side_effect = error
    response = client.post(f"/tables/{ID}/query/csv", json={"sql": "SELECT 1"})
    assert response.status_code == status
    assert "content-disposition" not in response.headers
    assert "private details" not in response.text


def test_real_csv_executor_through_api(dependencies, parquet, monkeypatch):
    dependencies[2].return_value = parquet
    monkeypatch.setattr(main, "execute_csv_query", query_executor.execute_csv_query)
    response = client.post(f"/tables/{ID}/query/csv", json={"sql": "SELECT name, amount FROM dataset"})
    assert response.status_code == 200
    assert parse(response.content) == [["name", "amount"], ["Alice", "150.25"]]


def test_openapi_describes_csv_response():
    schema = client.get("/openapi.json").json()
    for resource, parameter in [("tables", "table_id"), ("processing-runs", "run_id")]:
        content = schema["paths"][f"/{resource}/{{{parameter}}}/query/csv"]["post"]["responses"]["200"]["content"]
        assert "text/csv" in content and "application/json" not in content
