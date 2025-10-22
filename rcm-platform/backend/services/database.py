"""
Database connection and utilities
Uses asyncpg for PostgreSQL
"""

import os
from contextlib import asynccontextmanager
import asyncpg
from loguru import logger


# Global connection pool
_db_pool = None


async def get_db_pool():
    """Get or create database connection pool"""
    global _db_pool

    if _db_pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not set in environment")

        logger.info("Creating database connection pool")

        _db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
            timeout=30
        )

        logger.info("Database pool created successfully")

    return _db_pool


async def close_db_pool():
    """Close database connection pool"""
    global _db_pool

    if _db_pool:
        logger.info("Closing database connection pool")
        await _db_pool.close()
        _db_pool = None


@asynccontextmanager
async def get_db_connection():
    """
    Context manager for database connections

    Usage:
        async with get_db_connection() as conn:
            result = await conn.fetchrow("SELECT * FROM table")
    """
    pool = await get_db_pool()

    async with pool.acquire() as connection:
        yield connection


async def check_db_health() -> bool:
    """Check database connectivity"""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def log_scrub_result(claim_data: dict, scrub_result: dict):
    """Log AI claim scrub results for training data"""

    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO claim_scrub_logs (
                claim_data,
                scrub_result,
                ready_to_submit,
                confidence_score,
                errors_found,
                warnings_found
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            claim_data,
            scrub_result,
            scrub_result.get("ready", False),
            scrub_result.get("confidence", 0.0),
            scrub_result.get("errors", []),
            scrub_result.get("warnings", [])
        )

    logger.debug(f"Logged scrub result: ready={scrub_result.get('ready')}")
