# HTTP endpoints and shared processing used by app.worker.
# PostgreSQL owns metadata and run state; MinIO holds the CSV and Parquet bytes.

import json
import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, time
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

import duckdb
import psycopg
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from minio import Minio
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

from app.messaging import publish_processing_run
from app.query_executor import (
    MAX_PARQUET_BYTES,
    QueryError,
    execute_csv_query,
    execute_query,
    execute_saved_query,
)


class JsonLogFormatter(logging.Formatter):
    contextual_fields = (
        "correlation_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "upload_id",
        "dataset_id",
        "run_id",
        "outcome",
        "row_count",
    )

    def format(self, record):
        timestamp = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc,
        )

        payload = {
            "timestamp": timestamp.isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }

        for field in self.contextual_fields:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(
                record.exc_info
            )

        return json.dumps(
            payload,
            default=str,
        )


logger = logging.getLogger("platform.api")
logger.setLevel(logging.INFO)
logger.propagate = False

console_handler = logging.StreamHandler()
console_handler.setFormatter(JsonLogFormatter())

logger.handlers.clear()
logger.addHandler(console_handler)


def log_processing_event(
    *,
    level: int,
    event: str,
    correlation_id: str,
    upload_id: UUID,
    run_id: UUID | None = None,
    outcome: str | None = None,
    row_count: int | None = None,
):
    context = {
        "correlation_id": correlation_id,
        "upload_id": str(upload_id),
    }

    if run_id is not None:
        context["run_id"] = str(run_id)

    if outcome is not None:
        context["outcome"] = outcome

    if row_count is not None:
        context["row_count"] = row_count

    logger.log(
        level,
        event,
        extra=context,
    )


# Deployment environments supply credentials; address defaults support local study.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_RAW_BUCKET = os.getenv("MINIO_RAW_BUCKET", "raw")
MINIO_CURATED_BUCKET = os.getenv("MINIO_CURATED_BUCKET", "curated")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Uploads are buffered in memory, so reject files beyond the local demo's budget.
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

app = FastAPI()


@app.middleware("http")
async def add_correlation_id(
    request: Request,
    call_next,
):
    timer_started_at = monotonic()

    incoming_id = request.headers.get(
        "X-Correlation-ID"
    )

    try:
        correlation_id = (
            str(UUID(incoming_id))
            if incoming_id
            else str(uuid4())
        )
    except ValueError:
        correlation_id = str(uuid4())

    request.state.correlation_id = correlation_id

    response = await call_next(request)

    route = request.scope.get("route")
    path = getattr(
        route,
        "path",
        request.url.path,
    )

    duration_ms = round(
        (monotonic() - timer_started_at) * 1000,
        3,
    )

    logger.info(
        "http_request_completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    response.headers["X-Correlation-ID"] = (
        correlation_id
    )

    return response


# Keep identifiers in logs, not metric labels, to bound time-series cardinality.
# These metrics are process-local; PostgreSQL retains durable run history.
PROCESSING_RUNS = Counter(
    "platform_processing_runs_total",
    "Total number of completed processing runs.",
    ["outcome"],
)

PROCESSING_DURATION = Histogram(
    "platform_processing_duration_seconds",
    "Time spent processing an uploaded CSV.",
    ["outcome"],
)

PROCESSED_ROWS = Counter(
    "platform_processed_rows_total",
    "Total number of rows processed successfully.",
)

LAST_SUCCESSFUL_PROCESSING = Gauge(
    "platform_last_successful_processing_timestamp_seconds",
    "Unix timestamp of the latest successful processing run.",
)


class DatasetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class DatasetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class UploadResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    original_filename: str
    object_key: str
    content_type: str
    size_bytes: int
    created_at: datetime


class ProcessingResponse(BaseModel):
    run_id: UUID
    upload_id: UUID
    dataset_id: UUID
    status: str
    object_key: str
    format: str
    row_count: int
    validation_status: str

class ProcessingSubmissionResponse(BaseModel):
    run_id: UUID
    status: str

class ProcessingRunResponse(BaseModel):
    id: UUID
    upload_id: UUID
    status: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    row_count: int | None
    curated_object_key: str | None
    validation_status: str | None
    error_message: str | None


class QueryRequest(BaseModel):
    """Preview input; SQL execution restrictions are enforced by the executor."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(min_length=1, max_length=10000)
    max_rows: int = Field(default=100, ge=1, le=1000, strict=True)


class QueryResponse(BaseModel):
    """Rows follow column order, preserving even duplicate SQL column names."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int = Field(ge=0)
    truncated: bool


class CsvQueryRequest(BaseModel):
    """Full query export; no preview row limit or saved-table name."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(min_length=1, max_length=10000)


class SaveQueryTableRequest(BaseModel):
    """Save the query result, independently of the preview's row limit."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sql: str = Field(min_length=1, max_length=10000)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class SavedTableResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    source_run_id: UUID | None
    source_table_id: UUID | None
    query_sql: str
    object_key: str
    row_count: int
    size_bytes: int
    created_at: datetime


@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Returns 200 OK if the service is running.
    """
    # Process health only: database connectivity has a separate endpoint.
    return {"status": "healthy"}


def get_db_connection():
    """
    Create a connection to PostgreSQL.
    Raises an exception if the database is not reachable.
    """
    try:
        conn = psycopg.connect(DATABASE_URL)
        return conn
    except psycopg.OperationalError as e:
        raise Exception(f"Database connection failed: {e}")


def insert_dataset(dataset: DatasetCreate):
    """
    Insert a dataset registration and return the created database record.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO datasets (name, description)
                VALUES (%s, %s)
                RETURNING id, name, description, created_at;
                """,
                (dataset.name, dataset.description),
            )
            return cursor.fetchone()

def dataset_exists(dataset_id: UUID) -> bool:
    """
    Return whether the requested dataset exists.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM datasets WHERE id = %s);",
                (dataset_id,),
            )
            return cursor.fetchone()[0]

@app.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=201,
)
def create_dataset(dataset: DatasetCreate):
    """
    Register a logical dataset in PostgreSQL.
    """
    try:
        return insert_dataset(dataset)
    except UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="A dataset with this name already exists.",
        )
    except Exception:
        logger.exception("Dataset registration failed")
        raise HTTPException(
            status_code=500,
            detail="Dataset registration failed.",
        )

def get_minio_client():
    """
    Create a client for S3-compatible object storage.
    """
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )

def download_raw_object(object_key: str) -> bytes:
    """
    Download a raw object from MinIO and return its bytes.
    """
    response = get_minio_client().get_object(
        MINIO_RAW_BUCKET,
        object_key,
    )

    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def download_query_artifact(object_key: str) -> bytes:
    """Read a curated artifact without downloading an unbounded object."""
    return download_bounded_object(
        MINIO_CURATED_BUCKET, object_key, MAX_PARQUET_BYTES,
        "Dataset exceeds the 20 MiB query input limit.",
    )


def download_bounded_object(
    bucket: str,
    object_key: str,
    max_bytes: int,
    size_error: str,
) -> bytes:
    """Read at most the size limit plus one byte and always release the response."""
    response = get_minio_client().get_object(
        bucket,
        object_key,
    )
    try:
        content = response.read(max_bytes + 1)
    finally:
        try:
            response.close()
        finally:
            response.release_conn()

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=size_error,
        )
    return content


def convert_csv_to_parquet(csv_content: bytes) -> tuple[bytes, int]:
    """
    Convert CSV bytes into Parquet bytes and return the row count.
    """
    csv_content = csv_content.removeprefix(b"\xef\xbb\xbf")

    with TemporaryDirectory() as temporary_directory:
        input_path = Path(temporary_directory) / "input.csv"
        output_path = Path(temporary_directory) / "output.parquet"

        input_path.write_bytes(csv_content)

        with duckdb.connect() as connection:
            connection.execute(
                """
                CREATE TEMP TABLE processed_data AS
                SELECT *
                FROM read_csv_auto(?, strict_mode = false);
                """,
                [str(input_path)],
            )

            row_count = connection.execute(
                "SELECT COUNT(*) FROM processed_data;"
            ).fetchone()[0]

            connection.table("processed_data").write_parquet(
                str(output_path)
            )

        parquet_content = output_path.read_bytes()

    return parquet_content, row_count


def upload_curated_object(
    object_key: str,
    parquet_content: bytes,
) -> None:
    """
    Store a generated Parquet object in the curated MinIO bucket.
    """
    get_minio_client().put_object(
        MINIO_CURATED_BUCKET,
        object_key,
        BytesIO(parquet_content),
        length=len(parquet_content),
        content_type="application/vnd.apache.parquet",
    )


def insert_upload(
    upload_id: UUID,
    dataset_id: UUID,
    original_filename: str,
    object_key: str,
    content_type: str,
    size_bytes: int,
):
    """
    Record a stored object and return its upload metadata.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO uploads (
                    id,
                    dataset_id,
                    original_filename,
                    object_key,
                    content_type,
                    size_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    dataset_id,
                    original_filename,
                    object_key,
                    content_type,
                    size_bytes,
                    created_at;
                """,
                (
                    upload_id,
                    dataset_id,
                    original_filename,
                    object_key,
                    content_type,
                    size_bytes,
                ),
            )
            return cursor.fetchone()


def get_upload(upload_id: UUID):
    """
    Return metadata for one uploaded raw object.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    dataset_id,
                    original_filename,
                    object_key,
                    content_type,
                    size_bytes,
                    created_at
                FROM uploads
                WHERE id = %s;
                """,
                (upload_id,),
            )
            return cursor.fetchone()


def create_processing_run(upload_id: UUID):
    """
    Create and return a queued processing record.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO processing_runs (
                    upload_id,
                    status
                )
                VALUES (%s, 'queued')
                RETURNING
                    id,
                    upload_id,
                    status,
                    created_at,
                    started_at;
                """,
                (upload_id,),
            )
            return cursor.fetchone()

def claim_processing_run(run_id: UUID):
    """Start a run only if it is still queued."""
    # One conditional UPDATE avoids a read-then-write race between consumers.
    # Only the caller receiving a row from RETURNING may execute this run.
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE processing_runs
                SET
                    status = 'running',
                    started_at = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND status = 'queued'
                RETURNING
                    id,
                    upload_id,
                    status,
                    created_at,
                    started_at;
                """,
                (run_id,),
            )
            return cursor.fetchone()

def complete_processing_run(
    run_id: UUID,
    row_count: int,
    curated_object_key: str,
):
    """
    Mark a running processing record as successfully completed.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE processing_runs
                SET
                    status = 'succeeded',
                    completed_at = CURRENT_TIMESTAMP,
                    row_count = %s,
                    curated_object_key = %s,
                    validation_status = 'passed',
                    error_message = NULL
                WHERE id = %s
                  AND status = 'running'
                RETURNING
                    id,
                    upload_id,
                    status,
                    started_at,
                    completed_at,
                    row_count,
                    curated_object_key,
                    validation_status,
                    error_message;
                """,
                (
                    row_count,
                    curated_object_key,
                    run_id,
                ),
            )
            return cursor.fetchone()


def fail_processing_run(
    run_id: UUID,
    error_message: str,
    validation_failed: bool = False,
):
    """
    Mark a running processing record as failed.
    """
    validation_status = (
        "failed" if validation_failed else None
    )

    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                UPDATE processing_runs
                SET
                    status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    row_count = NULL,
                    curated_object_key = NULL,
                    validation_status = %s,
                    error_message = %s
                WHERE id = %s
                  AND status = 'running'
                RETURNING
                    id,
                    upload_id,
                    status,
                    started_at,
                    completed_at,
                    row_count,
                    curated_object_key,
                    validation_status,
                    error_message;
                """,
                (
                    validation_status,
                    error_message,
                    run_id,
                ),
            )
            return cursor.fetchone()

def try_to_record_processing_failure(
    run_id: UUID,
    error_message: str,
    validation_failed: bool = False,
) -> None:
    """
    Attempt to record a failure without hiding the original error.
    """
    try:
        failed_run = fail_processing_run(
            run_id=run_id,
            error_message=error_message,
            validation_failed=validation_failed,
        )

        if failed_run is None:
            logger.error(
                "Processing run could not transition to failed",
                extra={"run_id": str(run_id)},
            )
    except Exception:
        logger.exception(
            "Processing failure could not be recorded",
            extra={"run_id": str(run_id)},
        )

def read_and_validate_csv(file: UploadFile):
    """
    Validate the uploaded file and return its name, content type, and bytes.
    """
    # Admission checks only; the worker parses the CSV and validates data rows.
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Only CSV files are supported.",
        )

    content = file.file.read(MAX_UPLOAD_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The uploaded file exceeds the 10 MiB limit.",
        )

    content_type = file.content_type or "text/csv"

    return filename, content_type, content

def get_processing_run(run_id: UUID):
    """
    Return one processing run by its UUID.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    upload_id,
                    status,
                    created_at,
                    started_at,
                    completed_at,
                    row_count,
                    curated_object_key,
                    validation_status,
                    error_message
                FROM processing_runs
                WHERE id = %s;
                """,
                (run_id,),
            )
            return cursor.fetchone()

@app.post(
    "/datasets/{dataset_id}/uploads",
    response_model=UploadResponse,
    status_code=201,
)
def upload_dataset_file(
    dataset_id: UUID,
    file: UploadFile = File(...),
):
    """
    Store a CSV in MinIO and record its metadata in PostgreSQL.
    """
    try:
        exists = dataset_exists(dataset_id)
    except Exception:
        logger.exception("Dataset lookup failed")
        raise HTTPException(
            status_code=500,
            detail="Dataset lookup failed.",
        )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    filename, content_type, content = read_and_validate_csv(file)

    upload_id = uuid4()
    object_key = f"{dataset_id}/{upload_id}/{filename}"
    minio_client = get_minio_client()

    try:
        minio_client.put_object(
            MINIO_RAW_BUCKET,
            object_key,
            BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
    except Exception:
        logger.exception("Object upload failed")
        raise HTTPException(
            status_code=503,
            detail="Object storage is unavailable.",
        )

    try:
        return insert_upload(
            upload_id=upload_id,
            dataset_id=dataset_id,
            original_filename=filename,
            object_key=object_key,
            content_type=content_type,
            size_bytes=len(content),
        )
    except Exception:
        logger.exception("Upload metadata insert failed")

        # Best-effort compensation across two stores, not an atomic rollback.
        # This path cannot distinguish a rejected insert from a lost commit reply;
        # cleanup can leave a dangling row if the database actually committed.
        try:
            minio_client.remove_object(MINIO_RAW_BUCKET, object_key)
        except Exception:
            logger.exception(
                "Failed to remove orphaned object: %s",
                object_key,
            )

        raise HTTPException(
            status_code=500,
            detail="Upload registration failed.",
        )

def record_processing_metrics(
    outcome: str,
    timer_started_at: float,
    row_count: int | None = None,
):
    duration = monotonic() - timer_started_at

    PROCESSING_RUNS.labels(outcome=outcome).inc()
    PROCESSING_DURATION.labels(outcome=outcome).observe(
        duration
    )

    if outcome == "succeeded":
        PROCESSED_ROWS.inc(row_count or 0)
        LAST_SUCCESSFUL_PROCESSING.set(time())


class ProcessingError(Exception):
    # Shared execution reports domain outcomes; the API maps them to HTTP status.
    def __init__(self, outcome: str, message: str):
        super().__init__(message)
        self.outcome = outcome
        self.message = message


@app.post(
    "/uploads/{upload_id}/process",
    response_model=ProcessingSubmissionResponse,
    status_code=202,
)
def process_upload(
    upload_id: UUID,
    request: Request,
):
    try:
        return submit_processing(
            upload_id=upload_id,
            correlation_id=request.state.correlation_id,
        )
    except ProcessingError as exc:
        status_code = {
            "validation_failed": 422,
            "storage_failed": 503,
            "internal_failed": 500,
            "upload_not_found": 404,
            "submission_failed": 503,
        }.get(exc.outcome, 500)

        raise HTTPException(
            status_code=status_code,
            detail=exc.message,
        ) from exc


def submit_processing(
    upload_id: UUID,
    correlation_id: str,
):
    """Validate the upload, create a queued run, and publish it."""
    try:
        upload = get_upload(upload_id)
    except Exception:
        logger.exception("Upload lookup failed")
        raise ProcessingError(
            outcome="internal_failed",
            message="Upload lookup failed.",
        )

    if upload is None:
        raise ProcessingError(
            outcome="upload_not_found",
            message="Upload not found.",
        )

    timer_started_at = monotonic()

    try:
        processing_run = create_processing_run(upload_id)
    except Exception:
        logger.exception(
            "Processing run creation failed",
            extra={"upload_id": str(upload_id)},
        )
        log_processing_event(
            level=logging.ERROR,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            outcome="internal_failed",
        )
        record_processing_metrics(
            outcome="internal_failed",
            timer_started_at=timer_started_at,
        )
        raise ProcessingError(
            outcome="internal_failed",
            message="Processing run creation failed.",
        )

    # The database commit and broker publish are separate operations. Without an
    # outbox, a failure between them can leave a queued row with no message.
    try:
        publish_processing_run(
            run_id=processing_run["id"],
            correlation_id=correlation_id,
        )
    except Exception:
        # A missing confirmation does not prove delivery failed. Preserve the run
        # and return its ID so the caller can inspect state before resubmitting.
        logger.exception(
            "Processing run publication failed",
            extra={
                "run_id": str(processing_run["id"]),
                "correlation_id": correlation_id,
            },
        )
        raise ProcessingError(
            outcome="submission_failed",
            message=(
                "Processing submission could not be confirmed. "
                f"Check processing run {processing_run['id']} before retrying."
            ),
        )

    return ProcessingSubmissionResponse(
        run_id=processing_run["id"],
        status="queued",
    )


def execute_processing(
    run_id: UUID,
    correlation_id: str,
):
    """Claim and process an existing queued run."""
    timer_started_at = monotonic()

    try:
        claimed_run = claim_processing_run(run_id)
    except Exception:
        logger.exception(
            "Processing run claim failed",
            extra={"run_id": str(run_id)},
        )
        raise ProcessingError(
            outcome="internal_failed",
            message="Processing run claim failed.",
        )

    # Terminal duplicates need no work. A running row is not reclaimed here:
    # there is no lease or automatic recovery for an interrupted execution.
    if claimed_run is None:
        existing_run = get_processing_run(run_id)

        if existing_run is not None and existing_run["status"] in ("succeeded", "failed"):
            logger.info(
                "Skipping terminal processing run",
                extra={
                    "run_id": str(run_id),
                    "status": existing_run["status"],
                },
            )
            return

        raise ProcessingError(
            outcome="internal_failed",
            message="Processing run is not available to start.",
        )

    upload_id = claimed_run["upload_id"]

    try:
        upload = get_upload(upload_id)
        if upload is None:
            raise RuntimeError("The run's upload was not found.")
    except Exception:
        logger.exception(
            "Processing upload lookup failed",
            extra={"run_id": str(run_id)},
        )
        try_to_record_processing_failure(
            run_id=run_id,
            error_message="Processing upload lookup failed.",
        )
        log_processing_event(
            level=logging.ERROR,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            run_id=run_id,
            outcome="internal_failed",
        )
        record_processing_metrics(
            outcome="internal_failed",
            timer_started_at=timer_started_at,
        )
        raise ProcessingError(
            outcome="internal_failed",
            message="Processing upload lookup failed.",
        )

    log_processing_event(
        level=logging.INFO,
        event="processing_started",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
    )

    try:
        csv_content = download_raw_object(
            upload["object_key"]
        )
    except Exception:
        logger.exception(
            "Raw object download failed",
            extra={
                "run_id": str(run_id),
                "upload_id": str(upload_id),
            },
        )

        try_to_record_processing_failure(
            run_id=run_id,
            error_message=(
                "Raw object storage is unavailable."
            ),
        )

        log_processing_event(
            level=logging.ERROR,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            run_id=run_id,
            outcome="storage_failed",
        )

        record_processing_metrics(
            outcome="storage_failed",
            timer_started_at=timer_started_at,
        )
        raise ProcessingError(
            outcome="storage_failed",
            message="Raw object storage is unavailable.",
        )

    try:
        parquet_content, row_count = (
            convert_csv_to_parquet(csv_content)
        )

        if row_count == 0:
            try_to_record_processing_failure(
                run_id=run_id,
                error_message=(
                    "The uploaded CSV contains no data rows."
                ),
                validation_failed=True,
            )

            log_processing_event(
                level=logging.WARNING,
                event="processing_failed",
                correlation_id=correlation_id,
                upload_id=upload_id,
                run_id=run_id,
                outcome="validation_failed",
            )

            record_processing_metrics(
                outcome="validation_failed",
                timer_started_at=timer_started_at,
            )
            raise ProcessingError(
                outcome="validation_failed",
                message="The uploaded CSV contains no data rows.",
            )

    except duckdb.Error:
        logger.exception("CSV-to-Parquet conversion failed")

        try_to_record_processing_failure(
            run_id=run_id,
            error_message=(
                "The uploaded CSV could not be processed."
            ),
            validation_failed=True,
        )

        log_processing_event(
            level=logging.WARNING,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            run_id=run_id,
            outcome="validation_failed",
        )
        record_processing_metrics(
            outcome="validation_failed",
            timer_started_at=timer_started_at,
        )
        raise ProcessingError(
            outcome="validation_failed",
            message="The uploaded CSV could not be processed.",
        )

    # Give each processing run its own output path.
    curated_object_key = (
        f'{upload["dataset_id"]}/'
        f'{upload["id"]}/'
        f"{run_id}/"
        "data.parquet"
    )
    try:
        upload_curated_object(
            curated_object_key,
            parquet_content,
        )
    except Exception:
        logger.exception("Curated object upload failed")

        try_to_record_processing_failure(
            run_id=run_id,
            error_message=(
                "Curated object storage is unavailable."
            ),
        )

        log_processing_event(
            level=logging.ERROR,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            run_id=run_id,
            outcome="storage_failed",
        )

        record_processing_metrics(
            outcome="storage_failed",
            timer_started_at=timer_started_at,
        )
        raise ProcessingError(
            outcome="storage_failed",
            message="Curated object storage is unavailable.",
        )

    # Record success only after storing the artifact. If this update fails, the
    # object may exist without a confirmed terminal run; the worker rereads state.
    try:
        completed_run = complete_processing_run(
            run_id=run_id,
            row_count=row_count,
            curated_object_key=curated_object_key,
        )

        if completed_run is None:
            raise RuntimeError(
                "The processing run was not in the running state."
            )
    except Exception:
        logger.exception(
            "Processing result tracking failed",
            extra={
                "run_id": str(run_id),
                "upload_id": str(upload_id),
            },
        )

        log_processing_event(
            level=logging.ERROR,
            event="processing_failed",
            correlation_id=correlation_id,
            upload_id=upload_id,
            run_id=run_id,
            outcome="internal_failed",
        )

        record_processing_metrics(
            outcome="internal_failed",
            timer_started_at=timer_started_at,
        )

        raise ProcessingError(
            outcome="internal_failed",
            message="Processing result tracking failed.",
        )

    record_processing_metrics(
        outcome="succeeded",
        timer_started_at=timer_started_at,
        row_count=row_count,
    )

    log_processing_event(
        level=logging.INFO,
        event="processing_succeeded",
        correlation_id=correlation_id,
        upload_id=upload_id,
        run_id=run_id,
        outcome="succeeded",
        row_count=row_count,
    )
    return {
        "run_id": run_id,
        "upload_id": upload_id,
        "dataset_id": upload["dataset_id"],
        "status": completed_run["status"],
        "object_key": curated_object_key,
        "format": "parquet",
        "row_count": row_count,
        "validation_status": completed_run[
            "validation_status"
        ],
    }


@app.get("/db-health")
def db_health_check():
    """
    Database health check endpoint.
    Returns 200 if connected, 500 if the database is unreachable.
    """
    # Connectivity check only; it does not verify schema or other dependencies.
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "healthy", "database": "connected"}
    except Exception:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "error": "database unavailable",
            },
        )

@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

@app.get(
    "/processing-runs/{run_id}",
    response_model=ProcessingRunResponse,
    status_code=200,
)
def read_processing_run(run_id: UUID):
    """
    Return the current state of one processing run.
    """
    try:
        processing_run = get_processing_run(run_id)
    except Exception:
        logger.exception(
            "Processing run lookup failed",
            extra={"run_id": str(run_id)},
        )
        raise HTTPException(
            status_code=500,
            detail="Processing run lookup failed.",
        )

    if processing_run is None:
        raise HTTPException(
            status_code=404,
            detail="Processing run not found.",
        )

    return processing_run


@app.post(
    "/processing-runs/{run_id}/query",
    response_model=QueryResponse,
    status_code=200,
)
def query_processing_run(run_id: UUID, query: QueryRequest):
    """Preview a successful run's Parquet output using SELECT over dataset.

    This does not save a new table. The executor's deadline covers its child
    process, not the preceding database lookup or object download.
    """
    return preview_artifact(processing_artifact_key(run_id), query)


def processing_artifact_key(run_id: UUID) -> str:
    # Resolve file locations from metadata rather than caller-supplied paths.
    processing_run = read_processing_run(run_id)
    if processing_run["status"] != "succeeded":
        raise HTTPException(
            status_code=409,
            detail="Only succeeded processing runs can be queried.",
        )
    object_key = processing_run["curated_object_key"]
    if not object_key:
        raise HTTPException(
            status_code=409,
            detail="Processing run has no curated artifact.",
        )
    return object_key


def load_query_artifact(object_key: str) -> bytes:
    try:
        return download_query_artifact(object_key)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "Query artifact download failed",
        )
        raise HTTPException(
            status_code=503,
            detail="Query artifact could not be retrieved.",
        )


def preview_artifact(object_key: str, query: QueryRequest):
    parquet_content = load_query_artifact(object_key)
    try:
        return execute_query(parquet_content, query.sql, query.max_rows)
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception(
            "Query execution failed",
        )
        raise HTTPException(
            status_code=500,
            detail="Query execution failed.",
        )


def get_saved_table(table_id: UUID):
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute("SELECT * FROM saved_tables WHERE id = %s", (table_id,))
            return cursor.fetchone()


@app.get("/tables/{table_id}", response_model=SavedTableResponse)
def read_saved_table(table_id: UUID):
    try:
        table = get_saved_table(table_id)
    except Exception:
        logger.exception("Saved table lookup failed")
        raise HTTPException(status_code=503, detail="Table catalog unavailable.")
    if table is None:
        raise HTTPException(status_code=404, detail="Saved table not found.")
    return table


@app.get("/tables", response_model=list[SavedTableResponse])
def list_saved_tables(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM saved_tables ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                return cursor.fetchall()
    except Exception:
        logger.exception("Saved table listing failed")
        raise HTTPException(status_code=503, detail="Table catalog unavailable.")


@app.post("/tables/{table_id}/query", response_model=QueryResponse)
def query_saved_table(table_id: UUID, query: QueryRequest):
    table = read_saved_table(table_id)
    return preview_artifact(table["object_key"], query)


@app.get("/tables/{table_id}/download")
def download_saved_table(table_id: UUID):
    table = read_saved_table(table_id)
    content = load_query_artifact(table["object_key"])

    return Response(
        content=content,
        media_type="application/vnd.apache.parquet",
        headers={
            "Content-Disposition": f'attachment; filename="{table_id}.parquet"'
        },
    )


@app.get("/uploads/{upload_id}/download")
def download_uploaded_csv(upload_id: UUID):
    """Return the original CSV bytes, without processing or changing the upload."""
    try:
        upload = get_upload(upload_id)
    except Exception:
        logger.exception("Upload download lookup failed")
        raise HTTPException(status_code=503, detail="Upload metadata unavailable.")
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    try:
        content = download_bounded_object(
            MINIO_RAW_BUCKET, upload["object_key"], MAX_UPLOAD_SIZE,
            "Upload exceeds the 10 MiB download limit.",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Raw upload download failed")
        raise HTTPException(status_code=503, detail="Uploaded file could not be retrieved.")

    # Remove path components/control characters; encode the Unicode filename as
    # a header parameter and keep an ASCII UUID fallback for older clients.
    name = (upload["original_filename"] or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable()).strip()
    if not name or name in (".", ".."):
        name = f"{upload_id}.csv"
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{upload_id}.csv"; '
                f"filename*=UTF-8''{quote(name, safe='')}"
            ),
        },
    )


@app.get("/processing-runs/{run_id}/download")
def download_processing_output(run_id: UUID):
    """Return a succeeded run's existing Parquet output without rerunning it."""
    object_key = processing_artifact_key(run_id)
    content = load_query_artifact(object_key)
    return Response(
        content=content,
        media_type="application/vnd.apache.parquet",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.parquet"'},
    )


def export_query_csv(object_key: str, query: CsvQueryRequest, source_id: UUID):
    content = load_query_artifact(object_key)
    try:
        csv_content, row_count = execute_csv_query(content, query.sql)
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("CSV query export failed")
        raise HTTPException(status_code=500, detail="CSV query export failed.")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="query-{source_id}.csv"',
            "X-Row-Count": str(row_count),
        },
    )


@app.post(
    "/processing-runs/{run_id}/query/csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV query result"}},
)
def export_processing_query(run_id: UUID, query: CsvQueryRequest):
    """Download full bounded query results without saving a table."""
    return export_query_csv(processing_artifact_key(run_id), query, run_id)


@app.post(
    "/tables/{table_id}/query/csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "CSV query result"}},
)
def export_saved_table_query(table_id: UUID, query: CsvQueryRequest):
    """Export a SELECT over the selected saved table as CSV."""
    table = read_saved_table(table_id)
    return export_query_csv(table["object_key"], query, table_id)


def insert_saved_table(
    table_id,
    request,
    object_key,
    row_count,
    size_bytes,
    source_run_id,
    source_table_id,
):
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """INSERT INTO saved_tables
                   (id, name, description, source_run_id, source_table_id,
                    query_sql, object_key, row_count, size_bytes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (table_id, request.name, request.description, source_run_id,
                 source_table_id, request.sql, object_key, row_count, size_bytes),
            )
            return cursor.fetchone()


def save_query_table(
    object_key: str,
    request: SaveQueryTableRequest,
    *,
    source_run_id: UUID | None = None,
    source_table_id: UUID | None = None,
):
    # Persist a standalone Parquet snapshot; later reads do not rerun query_sql.
    content = load_query_artifact(object_key)
    try:
        parquet, row_count = execute_saved_query(content, request.sql)
    except QueryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        logger.exception("Saved query execution failed")
        raise HTTPException(status_code=500, detail="Saved query execution failed.")

    table_id = uuid4()
    output_key = f"tables/{table_id}/data.parquet"
    try:
        upload_curated_object(output_key, parquet)
    except Exception:
        logger.exception("Saved table upload failed", extra={"table_id": str(table_id)})
        raise HTTPException(status_code=503, detail="Saved table could not be stored.")

    try:
        return insert_saved_table(
            table_id, request, output_key, row_count,
            len(parquet), source_run_id, source_table_id,
        )
    except UniqueViolation:
        # PostgreSQL rejected this insert: it is safe to remove only our new object.
        try:
            get_minio_client().remove_object(MINIO_CURATED_BUCKET, output_key)
        except Exception:
            logger.exception("Unregistered table cleanup failed", extra={"table_id": str(table_id)})
        raise HTTPException(status_code=409, detail="A saved table with that name already exists.")
    except Exception:
        # A lost commit response is ambiguous. Preserve the object in case the row
        # committed; deleting it could corrupt a successfully registered table.
        logger.exception("Saved table registration uncertain", extra={"table_id": str(table_id)})
        raise HTTPException(status_code=503, detail={
            "message": "Table registration could not be confirmed. Check this table ID before retrying.",
            "table_id": str(table_id),
        })


@app.post(
    "/processing-runs/{run_id}/tables",
    response_model=SavedTableResponse,
    status_code=201,
)
def save_processing_run_table(run_id: UUID, request: SaveQueryTableRequest):
    return save_query_table(processing_artifact_key(run_id), request, source_run_id=run_id)


@app.post(
    "/tables/{table_id}/tables",
    response_model=SavedTableResponse,
    status_code=201,
)
def save_derived_table(table_id: UUID, request: SaveQueryTableRequest):
    source = read_saved_table(table_id)
    return save_query_table(source["object_key"], request, source_table_id=table_id)
