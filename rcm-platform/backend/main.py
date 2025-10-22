"""
RCM Platform - FastAPI Backend
AI-powered medical billing automation
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from services.eligibility import EligibilityService
from services.database import get_db_pool, close_db_pool
from services.audit import audit_log


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting RCM Platform API")
    await get_db_pool()
    yield
    # Shutdown
    logger.info("👋 Shutting down RCM Platform API")
    await close_db_pool()


# Initialize FastAPI
app = FastAPI(
    title="RCM Platform API",
    description="AI-powered medical billing automation platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Request/Response Models
# ============================================

class EligibilityCheckRequest(BaseModel):
    patient_id: str = Field(..., description="FHIR Patient resource ID")
    provider_npi: str = Field(..., description="Provider NPI number")


class EligibilityCheckResponse(BaseModel):
    status: str = Field(..., description="Coverage status: active, inactive, unknown")
    plan_name: Optional[str] = Field(None, description="Insurance plan name")
    copay: Optional[str] = Field(None, description="Office visit copay")
    deductible: Optional[str] = Field(None, description="Annual deductible")
    oop_max: Optional[str] = Field(None, description="Out-of-pocket maximum")
    cached: bool = Field(..., description="Whether result was from cache")
    check_date: datetime = Field(..., description="When check was performed")


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: dict


# ============================================
# Dependency Injection
# ============================================

def get_eligibility_service() -> EligibilityService:
    """Dependency for eligibility service"""
    stedi_api_key = os.getenv("STEDI_API_KEY")
    if not stedi_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STEDI_API_KEY not configured"
        )
    return EligibilityService(stedi_api_key)


# ============================================
# API Endpoints
# ============================================

@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "message": "RCM Platform API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Health check endpoint for monitoring"""
    from services.database import check_db_health
    from services.cache import check_redis_health

    db_healthy = await check_db_health()
    redis_healthy = await check_redis_health()

    return HealthResponse(
        status="healthy" if (db_healthy and redis_healthy) else "degraded",
        timestamp=datetime.now(),
        version="1.0.0",
        services={
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "stedi_api": "configured" if os.getenv("STEDI_API_KEY") else "not_configured"
        }
    )


@app.post(
    "/api/eligibility/check",
    response_model=EligibilityCheckResponse,
    tags=["eligibility"],
    summary="Check insurance eligibility"
)
async def check_eligibility(
    request: EligibilityCheckRequest,
    service: EligibilityService = Depends(get_eligibility_service)
):
    """
    Check patient insurance eligibility via Stedi API.

    Results are cached for 24 hours to reduce API costs.

    **Workflow:**
    1. Check cache for recent eligibility check
    2. If not cached, call Stedi API
    3. Parse and return results
    4. Cache for future requests

    **Returns:**
    - Coverage status (active/inactive)
    - Plan name
    - Copay, deductible, OOP max
    - Whether result was cached
    """

    try:
        # Log audit trail
        await audit_log(
            action="eligibility_check",
            resource_id=request.patient_id,
            metadata={"provider_npi": request.provider_npi}
        )

        # Check eligibility
        result = await service.check_eligibility(
            patient_id=request.patient_id,
            provider_npi=request.provider_npi
        )

        return EligibilityCheckResponse(**result)

    except ValueError as e:
        # Patient not found or invalid data
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Eligibility check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check eligibility: {str(e)}"
        )


@app.get("/api/eligibility/history/{patient_id}", tags=["eligibility"])
async def get_eligibility_history(patient_id: str, limit: int = 10):
    """Get eligibility check history for a patient"""
    from services.database import get_db_connection

    try:
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    check_date,
                    coverage_status,
                    plan_name,
                    copay,
                    deductible,
                    out_of_pocket_max
                FROM eligibility_cache
                WHERE patient_id = $1
                ORDER BY check_date DESC
                LIMIT $2
                """,
                patient_id,
                limit
            )

            return [dict(row) for row in rows]

    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch eligibility history"
        )


@app.post("/api/claims/scrub", tags=["claims"])
async def scrub_claim(claim_data: dict):
    """
    AI-powered claim scrubbing before submission.

    Uses Cloudflare Workers AI to check for:
    - CPT-ICD-10 medical necessity mismatch
    - Missing modifiers
    - Authorization requirements
    - Bundling issues
    """

    import httpx

    try:
        # Log audit
        await audit_log(
            action="claim_scrub",
            metadata={"cpt_codes": claim_data.get("cpt_codes", [])}
        )

        # Call Cloudflare Worker AI scrubber
        worker_url = os.getenv("CLOUDFLARE_WORKER_URL")
        if not worker_url:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="AI scrubber not configured. Set CLOUDFLARE_WORKER_URL"
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                worker_url,
                json=claim_data
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail="AI scrubber request failed"
                )

            result = response.json()

        # Log scrub result for training
        from services.database import log_scrub_result
        await log_scrub_result(claim_data, result)

        return result

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI scrubber timeout - try again"
        )
    except Exception as e:
        logger.error(f"Claim scrub failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scrub claim: {str(e)}"
        )


@app.get("/api/metrics/dashboard", tags=["metrics"])
async def get_dashboard_metrics(days: int = 30):
    """Get dashboard metrics for the specified number of days"""
    from services.database import get_db_connection

    try:
        async with get_db_connection() as conn:
            metrics = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_checks,
                    COUNT(DISTINCT patient_id) as unique_patients,
                    COUNT(*) FILTER (WHERE coverage_status = 'active') as active_coverage,
                    ROUND(AVG(confidence_score), 2) as avg_ai_confidence
                FROM eligibility_cache
                WHERE check_date > NOW() - INTERVAL '1 day' * $1
                """,
                days
            )

            scrub_metrics = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_scrubs,
                    COUNT(*) FILTER (WHERE ready_to_submit = true) as clean_claims,
                    COUNT(*) FILTER (WHERE ready_to_submit = false) as flagged_claims,
                    ROUND(AVG(confidence_score), 2) as avg_scrub_confidence
                FROM claim_scrub_logs
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                """,
                days
            )

            return {
                "eligibility": dict(metrics) if metrics else {},
                "claim_scrubber": dict(scrub_metrics) if scrub_metrics else {},
                "period_days": days
            }

    except Exception as e:
        logger.error(f"Failed to fetch metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch dashboard metrics"
        )


# ============================================
# Error Handlers
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
