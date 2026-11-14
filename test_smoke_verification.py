import duckdb

from scripts.verify_saved_tables import parquet_rows


def test_parquet_rows_checks_downloaded_content(tmp_path):
    path = tmp_path / "sample.parquet"
    with duckdb.connect(":memory:") as connection:
        connection.sql("SELECT 'north' AS region, 30 AS total UNION ALL SELECT 'south', 5").write_parquet(str(path))

    assert parquet_rows(path.read_bytes(), "SELECT region, total FROM dataset ORDER BY region") == [
        ("north", 30), ("south", 5),
    ]
