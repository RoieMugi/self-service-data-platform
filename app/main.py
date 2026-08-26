import logging
import os
from datetime import datetime
from uuid import UUID, uuid4
from minio import Minio


import psycopg
from fastapi import FastAPI, HTTPException, UploadFile, File
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field
from io import BytesIO

logger = logging.getLogger(__name__)


# Read the DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "platform_minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "platform_minio_password")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "raw")
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
            MINIO_BUCKET,
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
            minio_client.remove_object(MINIO_BUCKET, object_key)
        except Exception:
            logger.exception(
                "Failed to remove orphaned object: %s",
                object_key,
            )

        raise HTTPException(
            status_code=500,
            detail="Upload registration failed.",
        )


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
