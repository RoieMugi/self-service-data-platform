"""Live local smoke test; retains one sample dataset/run and two saved tables.

Run with the Compose API and worker running:
    python scripts/verify_saved_tables.py
"""

import json
import time
from uuid import uuid4

import httpx


def main():
    label = f"session20-{uuid4().hex[:8]}"
    with httpx.Client(base_url="http://localhost:8000", timeout=30) as client:
        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()

        dataset = post("/datasets", json={"name": label})
        upload = post(f"/datasets/{dataset['id']}/uploads", files={
            "file": ("sales.csv", b"region,amount\nnorth,10\nnorth,20\nsouth,5\n", "text/csv"),
        })
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

        sql = "SELECT region, SUM(amount) AS total FROM dataset GROUP BY region ORDER BY region"
        preview = post(f"/processing-runs/{run_id}/query", json={"sql": sql, "max_rows": 1})
        assert preview["rows"] == [["north", 30]] and preview["truncated"]
        request = {"name": f"{label}-regions", "sql": sql}
        saved = post(f"/processing-runs/{run_id}/tables", json=request)
        assert saved["row_count"] == 2
        table_id = saved["id"]
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
