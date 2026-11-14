"""Read-only comparison of PostgreSQL references and MinIO objects.

Run inside the API container: docker compose exec api python scripts/audit_objects.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import MINIO_CURATED_BUCKET, MINIO_RAW_BUCKET, get_db_connection, get_minio_client


def inventory():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT object_key FROM uploads")
            raw = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT curated_object_key FROM processing_runs WHERE curated_object_key IS NOT NULL")
            curated = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT object_key FROM saved_tables")
            curated.update(row[0] for row in cursor.fetchall())

    client = get_minio_client()
    report = {}
    for bucket, referenced in ((MINIO_RAW_BUCKET, raw), (MINIO_CURATED_BUCKET, curated)):
        stored = {item.object_name for item in client.list_objects(bucket, recursive=True)}
        report[bucket] = {
            "referenced_missing": sorted(referenced - stored),
            "unreferenced_stored": sorted(stored - referenced),
        }
    return report


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2))
