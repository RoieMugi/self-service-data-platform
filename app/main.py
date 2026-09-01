import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import duckdb
import psycopg
from fastapi import FastAPI, File, HTTPException, UploadFile
from minio import Minio
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


# Read the DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "platform_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "platform_minio_password")
MINIO_RAW_BUCKET = os.getenv("MINIO_RAW_BUCKET", "raw")
MINIO_CURATED_BUCKET = os.getenv("MINIO_CURATED_BUCKET", "curated")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# Max size for files- for this project I placed limitations
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

app = FastAPI()


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


class ProcessingRunResponse(BaseModel):
    id: UUID
    upload_id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None
    row_count: int | None
    curated_object_key: str | None
    validation_status: str | None
    error_message: str | None


@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Returns 200 OK if the service is running.
    """
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
    Create and return a running processing record.
    """
    with get_db_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                INSERT INTO processing_runs (
                    upload_id,
                    status
                )
                VALUES (%s, 'running')
                RETURNING
                    id,
                    upload_id,
                    status,
                    started_at;
                """,
                (upload_id,),
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


@app.post(
    "/uploads/{upload_id}/process",
    response_model=ProcessingResponse,
    status_code=200,
)
def process_upload(upload_id: UUID):
    """
    Convert one raw CSV upload into curated Parquet.
    """
    try:
        upload = get_upload(upload_id)
    except Exception:
        logger.exception("Upload lookup failed")
        raise HTTPException(
            status_code=500,
            detail="Upload lookup failed.",
        )

    if upload is None:
        raise HTTPException(
            status_code=404,
            detail="Upload not found.",
        )

    try:
        processing_run = create_processing_run(upload_id)
    except Exception:
        logger.exception(
            "Processing run creation failed",
            extra={"upload_id": str(upload_id)},
        )
        raise HTTPException(
            status_code=500,
            detail="Processing run creation failed.",
        )

    run_id = processing_run["id"]
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

        raise HTTPException(
            status_code=503,
            detail="Raw object storage is unavailable.",
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

            raise HTTPException(
                status_code=422,
                detail=(
                    "The uploaded CSV contains no data rows."
                ),
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

        raise HTTPException(
            status_code=422,
            detail="The uploaded CSV could not be processed.",
        )

    curated_object_key = (
        f'{upload["dataset_id"]}/'
        f'{upload["id"]}/'
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

        raise HTTPException(
            status_code=503,
            detail="Curated object storage is unavailable.",
        )

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
        raise HTTPException(
            status_code=500,
            detail="Processing result tracking failed.",
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
