"""
HIPAA Audit Logging
Tracks all actions for compliance
"""

from datetime import datetime
from typing import Optional, Dict
from loguru import logger

from .database import get_db_connection


async def audit_log(
    action: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict] = None,
    response_status: Optional[int] = None
):
    """
    Log action to audit trail

    Args:
        action: Action performed (e.g., "eligibility_check", "claim_submit")
        user_id: User who performed action
        resource_type: Type of resource (e.g., "Patient", "Claim")
        resource_id: ID of resource
        ip_address: Client IP address
        user_agent: Client user agent
        metadata: Additional metadata as JSON
        response_status: HTTP response status
    """

    try:
        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO audit_log (
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    ip_address,
                    user_agent,
                    request_data,
                    response_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                action,
                resource_type,
                resource_id,
                ip_address,
                user_agent,
                metadata or {},
                response_status
            )

        logger.debug(f"Audit log: {action} for {resource_type}/{resource_id}")

    except Exception as e:
        # Don't fail requests if audit logging fails
        logger.error(f"Audit log failed: {e}")


async def get_audit_trail(
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100
) -> list:
    """
    Retrieve audit trail

    Args:
        resource_id: Filter by resource ID
        action: Filter by action type
        limit: Max number of records

    Returns:
        List of audit log entries
    """

    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    param_count = 0

    if resource_id:
        param_count += 1
        query += f" AND resource_id = ${param_count}"
        params.append(resource_id)

    if action:
        param_count += 1
        query += f" AND action = ${param_count}"
        params.append(action)

    param_count += 1
    query += f" ORDER BY created_at DESC LIMIT ${param_count}"
    params.append(limit)

    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to fetch audit trail: {e}")
        return []
