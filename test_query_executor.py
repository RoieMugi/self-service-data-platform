import subprocess

import duckdb
import pytest

from app import query_executor
from app.query_executor import QueryError, execute_query
from app.query_executor import execute_saved_query


@pytest.fixture
def parquet_content(tmp_path):
    # Real Parquet and child execution exercise engine restrictions beyond mocks.
    path = tmp_path / "source.parquet"
    with duckdb.connect() as connection:
        connection.execute("CREATE TABLE sales AS SELECT * FROM (VALUES ('north', 10), ('north', 20), ('south', 5)) t(region, amount)")
        connection.table("sales").write_parquet(str(path))
    return path.read_bytes()


def test_aggregate_and_preview_truncation(parquet_content):
    result = execute_query(parquet_content, "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region", 1)
    assert result == {
        "columns": ["region", "total"],
        "rows": [["north", 30]],
        "row_count": 1,
        "truncated": True,
    }


def test_empty_result_keeps_columns(parquet_content):
    assert execute_query(parquet_content, "SELECT region FROM dataset WHERE false") == {
        "columns": ["region"], "rows": [], "row_count": 0, "truncated": False,
    }


@pytest.mark.parametrize("sql", [
    "DROP TABLE dataset",
    "SELECT 1; SELECT 2",
    "COPY dataset TO 'escape.csv'",
    "SET enable_external_access = true",
    "SELECT * FROM read_text('request.json')",
    "SELECT * FROM read_csv('https://example.com/data.csv')",
])
def test_rejects_writes_multiple_statements_and_external_reads(parquet_content, sql):
    with pytest.raises(QueryError):
        execute_query(parquet_content, sql)


def test_rejects_oversized_response(parquet_content):
    with pytest.raises(QueryError, match="1 MiB"):
        execute_query(parquet_content, "SELECT repeat('x', 1100000)")


def test_timeout_is_a_controlled_error(parquet_content, monkeypatch):
    # Deterministically test error translation; this does not measure real deadlines.
    def expire(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(query_executor.subprocess, "run", expire)
    with pytest.raises(QueryError, match="execution limit"):
        execute_query(parquet_content, "SELECT * FROM dataset")


def test_saved_result_can_be_queried_again(parquet_content):
    saved, count = execute_saved_query(parquet_content, "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region")
    assert count == 2
    assert execute_query(saved, "SELECT * FROM dataset ORDER BY region")["rows"] == [["north", 30], ["south", 5]]


def test_save_is_not_limited_to_preview_rows(parquet_content):
    saved, count = execute_saved_query(parquet_content, "SELECT i FROM range(1500) t(i)")
    assert count == 1500
    assert execute_query(saved, "SELECT COUNT(*) FROM dataset")["rows"] == [[1500]]


def test_empty_saved_table_retains_schema(parquet_content):
    saved, count = execute_saved_query(parquet_content, "SELECT region FROM dataset WHERE false")
    assert count == 0
    assert execute_query(saved, "SELECT * FROM dataset")["columns"] == ["region"]


@pytest.mark.parametrize("sql", [
    "SELECT * FROM range(100001)",
    "SELECT amount AS x, region AS x FROM dataset",
    "DROP TABLE dataset",
    "SELECT * FROM read_text('request.json')",
    "SELECT 1; SELECT 2",
])
def test_save_rejects_overflow_ambiguous_columns_and_unsafe_sql(parquet_content, sql):
    with pytest.raises(QueryError):
        execute_saved_query(parquet_content, sql)
