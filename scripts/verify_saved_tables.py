"""Live local smoke test; retains one sample dataset/run and two saved tables.

Run with the Compose API and worker running:
    python scripts/verify_saved_tables.py
"""

import csv
import json
import os
import time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import duckdb
import httpx


def parquet_rows(content, sql):
    with TemporaryDirectory() as directory:
        path = Path(directory) / "download.parquet"
        path.write_bytes(content)
        with duckdb.connect(":memory:") as connection:
            connection.read_parquet(str(path)).create_view("dataset")
            return connection.execute(sql).fetchall()


def main():
    label = f"smoke-{uuid4().hex[:8]}"
    with httpx.Client(base_url=os.getenv("PLATFORM_API_URL", "http://localhost:8000"), timeout=30) as client:
        deadline = time.monotonic() + 60
        while True:
            try:
                health = client.get("/db-health")
                if health.status_code == 200:
                    break
            except httpx.RequestError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("API and database did not become ready")
            time.sleep(1)

        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            if response.is_error:
                raise RuntimeError(f"POST {path} returned {response.status_code}: {response.text}")
            return response.json()

        dataset = post("/datasets", json={"name": label})
        source_csv = b"region,amount\nnorth,10\nnorth,20\nsouth,5\n"
        upload = post(f"/datasets/{dataset['id']}/uploads", files={
            "file": ("sales.csv", source_csv, "text/csv"),
        })
        raw = client.get(f"/uploads/{upload['id']}/download")
        raw.raise_for_status()
        assert raw.content == source_csv
        run = post(f"/uploads/{upload['id']}/process")
        run_id = run["run_id"]
        deadline = time.monotonic() + 30
        while True:
            response = client.get(f"/processing-runs/{run_id}")
            response.raise_for_status()
            state = response.json()
            if state["status"] in ("succeeded", "failed"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Run did not finish: {run_id}")
            time.sleep(0.5)
        assert state["status"] == "succeeded", state
        output = client.get(f"/processing-runs/{run_id}/download")
        output.raise_for_status()
        assert parquet_rows(output.content, "SELECT region, amount FROM dataset ORDER BY region, amount") == [
            ("north", 10), ("north", 20), ("south", 5),
        ]

        sql = "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region"
        preview = post(f"/processing-runs/{run_id}/query", json={"sql": sql, "max_rows": 1})
        assert preview["rows"] == [["north", 30]] and preview["truncated"]
        request = {"name": f"{label}-regions", "sql": sql}
        saved = post(f"/processing-runs/{run_id}/tables", json=request)
        assert saved["row_count"] == 2
        table_id = saved["id"]
        table_file = client.get(f"/tables/{table_id}/download")
        table_file.raise_for_status()
        assert parquet_rows(table_file.content, "SELECT region, total FROM dataset ORDER BY region") == [
            ("north", 30), ("south", 5),
        ]
        exported = client.post(f"/tables/{table_id}/query/csv", json={"sql": "SELECT region, total FROM dataset ORDER BY region"})
        exported.raise_for_status()
        csv_rows = list(csv.reader(StringIO(exported.content.decode("utf-8"), newline="")))
        assert csv_rows[0] == ["region", "total"], csv_rows
        assert [(region, Decimal(total)) for region, total in csv_rows[1:]] == [
            ("north", Decimal(30)), ("south", Decimal(5)),
        ], csv_rows
        result = post(f"/tables/{table_id}/query", json={"sql": "SELECT * FROM dataset ORDER BY region"})
        assert result["rows"] == [["north", 30], ["south", 5]]
        assert client.get(f"/tables/{table_id}").json()["name"] == request["name"]
        listed = client.get("/tables")
        listed.raise_for_status()
        assert table_id in [item["id"] for item in listed.json()]
        assert client.post(f"/processing-runs/{run_id}/tables", json=request).status_code == 409
        assert client.post(f"/tables/{table_id}/query", json={"sql": "DROP TABLE dataset"}).status_code == 422
        derived = post(f"/tables/{table_id}/tables", json={
            "name": f"{label}-total", "sql": "SELECT SUM(total) AS grand_total FROM dataset",
        })
        assert derived["source_table_id"] == table_id
        assert post(f"/tables/{derived['id']}/query", json={"sql": "SELECT * FROM dataset"})["rows"] == [[35]]
        # Verify the original result remains readable after duplicate cleanup.
        assert post(f"/tables/{table_id}/query", json={"sql": "SELECT COUNT(*) FROM dataset"})["rows"] == [[2]]
        print(json.dumps({
            "status": "passed", "dataset_id": dataset["id"], "run_id": run_id,
            "saved_table_id": table_id, "derived_table_id": derived["id"],
            "saved_table_name": saved["name"],
        }, indent=2))


if __name__ == "__main__":
    main()
