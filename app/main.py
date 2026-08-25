import logging
import os
from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger(__name__)


# Read the DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dbname")


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
