"""Bounded previews over one Parquet artifact; no storage or HTTP dependencies."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


MAX_PARQUET_BYTES = 20 * 1024 * 1024
MAX_RESULT_BYTES = 1024 * 1024
QUERY_TIMEOUT_SECONDS = 10
MAX_SAVED_ROWS = 100000


class QueryError(Exception):
    """A controlled query failure suitable for later HTTP error translation."""


def execute_query(parquet_content: bytes, sql: str, max_rows: int = 100) -> dict:
    return _execute(parquet_content, sql, max_rows, save=False)


def execute_saved_query(parquet_content: bytes, sql: str) -> tuple[bytes, int]:
    """Return a complete bounded Parquet result, never a truncated preview."""
    return _execute(parquet_content, sql, 100, save=True)


def execute_csv_query(parquet_content: bytes, sql: str) -> tuple[bytes, int]:
    """Export the full bounded SELECT result as UTF-8 CSV with column headers."""
    return _execute(parquet_content, sql, 100, save=True, csv_export=True)


def _execute(
    parquet_content: bytes,
    sql: str,
    max_rows: int,
    *,
    save: bool,
    csv_export: bool = False,
):
    """Preview rows; the deadline includes child startup, loading and encoding.

    DuckDB's memory setting is an engine limit, not an OS process memory cap.
    This is a local learning executor, not an isolation boundary for public SQL.
    """
    if not parquet_content or len(parquet_content) > MAX_PARQUET_BYTES:
        raise QueryError("Dataset must contain between 1 byte and 20 MiB.")
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 10000:
        raise QueryError("SQL must contain between 1 and 10000 characters.")
    if type(max_rows) is not int or not 1 <= max_rows <= 1000:
        raise QueryError("Preview limit must be an integer from 1 to 1000.")

    with TemporaryDirectory(prefix="platform-query-") as directory:
        work = Path(directory)
        (work / "dataset.parquet").write_bytes(parquet_content)
        (work / "request.json").write_text(
            json.dumps({
                "sql": sql,
                "max_rows": max_rows,
                "save": save,
                "csv_export": csv_export,
            }),
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(Path(__file__).resolve()), str(work)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=QUERY_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise QueryError("Query exceeded the 10-second execution limit.") from exc
        except OSError as exc:
            raise QueryError("Query process could not be started.") from exc

        output = work / "result.json"
        if completed.returncode != 0 or not output.exists():
            raise QueryError("Query process failed.")
        if output.stat().st_size > MAX_RESULT_BYTES:
            raise QueryError("Query result exceeds the 1 MiB response limit.")
        result = json.loads(output.read_text(encoding="utf-8"))
        if "error" in result:
            raise QueryError(result["error"])
        if save:
            artifact = work / ("result.csv" if csv_export else "saved.parquet")
            if not artifact.exists() or artifact.stat().st_size > MAX_PARQUET_BYTES:
                raise QueryError("Export exceeds the 20 MiB limit or is missing.")
            return artifact.read_bytes(), result["row_count"]
        return result


def _run_preview(work: Path) -> dict:
    import duckdb

    request = json.loads((work / "request.json").read_text(encoding="utf-8"))
    artifact = work / ("result.csv" if request.get("csv_export") else "saved.parquet")
    with duckdb.connect(config={
        "memory_limit": "256MB",
        "threads": "1",
        "max_temp_directory_size": "0B",
        "autoload_known_extensions": "false",
        "autoinstall_known_extensions": "false",
        "allow_community_extensions": "false",
    }) as connection:
        # Only this application-owned path is read before external access is closed.
        connection.execute(
            "CREATE TEMP TABLE dataset AS SELECT * FROM read_parquet(?)",
            [str(work / "dataset.parquet")],
        )
        if request.get("save"):
            # Only this generated output path is permitted for our artifact writer.
            connection.execute("SET allowed_paths = ?", [[str(artifact)]])
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
        statements = connection.extract_statements(request["sql"])
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise QueryError("Provide exactly one read-only SELECT query.")

        if request.get("save"):
            relation = connection.sql(request["sql"])
            # Parquet needs unambiguous column names for subsequent queries.
            names = relation.columns
            if len({name.lower() for name in names}) != len(names):
                raise QueryError("Export columns must have unique names; use SQL aliases.")
            relation.limit(MAX_SAVED_ROWS + 1).create("saved_result")
            row_count = connection.execute("SELECT COUNT(*) FROM saved_result").fetchone()[0]
            if row_count > MAX_SAVED_ROWS:
                raise QueryError("Export exceeds the 100000-row limit; narrow the query.")
            if request.get("csv_export"):
                connection.table("saved_result").write_csv(str(artifact), header=True)
            else:
                connection.table("saved_result").write_parquet(str(artifact))
            if artifact.stat().st_size > MAX_PARQUET_BYTES:
                raise QueryError("Export exceeds the 20 MiB limit.")
            return {"row_count": row_count}

        cursor = connection.execute(statements[0])
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchmany(request["max_rows"] + 1)
        truncated = len(rows) > request["max_rows"]
        rows = rows[:request["max_rows"]]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }


def _main(work: Path) -> None:
    try:
        result = _run_preview(work)
        # Dates, decimals, UUIDs and other non-JSON scalar values use strings.
        encoded = json.dumps(result, default=str, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_RESULT_BYTES:
            raise QueryError("Query result exceeds the 1 MiB response limit.")
    except QueryError as exc:
        encoded = json.dumps({"error": str(exc)})
    except Exception:
        # Do not return engine diagnostics containing local paths or data values.
        encoded = json.dumps({"error": "Query could not be executed within the allowed access and resource limits; check SQL and column names."})
    (work / "result.json").write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    _main(Path(sys.argv[1]))
