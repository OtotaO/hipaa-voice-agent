"""
FHIR Bridge API
Provides a simplified interface to FHIR servers with HIPAA compliance
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os

from services.fhir_client import FHIRClient
from core.security import PHIRedactor, AuditLogger

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FHIR Bridge API",
    description="HIPAA-compliant FHIR integration service",
    version="1.0.0"
)

# Security
security = HTTPBearer()

# Initialize services
fhir_client = FHIRClient()
phi_redactor = PHIRedactor()
audit_logger = AuditLogger()


# Request/Response Models
class PatientSearchRequest(BaseModel):
    """Patient search parameters"""
    name: Optional[str] = None
    birthdate: Optional[str] = None
    identifier: Optional[str] = None


class AppointmentRequest(BaseModel):
    """Appointment creation request"""
    patient_id: str
    practitioner_id: Optional[str] = None
    start: str
    end: str
    appointment_type: str
    description: Optional[str] = None


class ObservationSearchRequest(BaseModel):
    """Observation search parameters"""
    patient_id: str
    category: Optional[str] = None
    code: Optional[str] = None
    date: Optional[str] = None


# Helper Functions
def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API key"""
    if os.getenv('ENABLE_API_KEY_VALIDATION', 'true').lower() != 'true':
        return True
    
    api_key = credentials.credentials
    valid_keys = os.getenv('API_KEYS', '').split(',')
    
    if not api_key or api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return True


# Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FHIR Bridge",
        "version": "1.0.0"
    }


@app.post("/api/patients/search")
async def search_patients(
    request: PatientSearchRequest,
    authorized: bool = Depends(verify_api_key)
):
    """
    Search for patients
    
    Args:
        request: Search parameters
        
    Returns:
        List of matching patients (PHI redacted)
    """
    try:
        async with fhir_client as client:
            results = await client.search_patients(
                name=request.name,
                birthdate=request.birthdate,
                identifier=request.identifier
            )
        
        # Redact PHI from response
        if results.get('entry'):
            for entry in results['entry']:
                if 'resource' in entry:
                    entry['resource'] = phi_redactor.redact_dict(entry['resource'])
        
        # Log search
        audit_logger.log_event(
            'patient_search',
            criteria=request.dict(),
            results_count=len(results.get('entry', []))
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Patient search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/api/patients/{patient_id}")
async def get_patient(
    patient_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """
    Get patient details
    
    Args:
        patient_id: Patient identifier
        
    Returns:
        Patient resource (PHI redacted based on access level)
    """
    try:
        async with fhir_client as client:
            patient = await client.get_patient(patient_id)
        
        # Redact sensitive fields
        patient = phi_redactor.redact_dict(patient)
        
        # Log access
        audit_logger.log_event(
            'patient_access',
            patient_id=patient_id
        )
        
        return patient
        
    except Exception as e:
        logger.error(f"Get patient error: {e}")
        raise HTTPException(status_code=404, detail="Patient not found")


@app.post("/api/appointments")
async def create_appointment(
    request: AppointmentRequest,
    authorized: bool = Depends(verify_api_key)
):
    """
    Create appointment
    
    Args:
        request: Appointment details
        
    Returns:
        Created appointment resource
    """
    try:
        appointment_data = {
            'status': 'proposed',
            'start': request.start,
            'end': request.end,
            'participant': [
                {
                    'actor': {'reference': f"Patient/{request.patient_id}"},
                    'status': 'needs-action'
                }
            ]
        }
        
        if request.practitioner_id:
            appointment_data['participant'].append({
                'actor': {'reference': f"Practitioner/{request.practitioner_id}"},
                'status': 'needs-action'
            })
        
        if request.appointment_type:
            appointment_data['appointmentType'] = {
                'text': request.appointment_type
            }
        
        if request.description:
            # Redact PHI from description
            appointment_data['description'] = phi_redactor.redact_string(request.description)
        
        async with fhir_client as client:
            result = await client.create_appointment(appointment_data)
        
        # Log appointment creation
        audit_logger.log_event(
            'appointment_created',
            appointment_id=result.get('id'),
            patient_id=request.patient_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Create appointment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create appointment")


@app.get("/api/appointments/{appointment_id}")
async def get_appointment(
    appointment_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """
    Get appointment details
    
    Args:
        appointment_id: Appointment identifier
        
    Returns:
        Appointment resource
    """
    try:
        async with fhir_client as client:
            appointment = await client.get_appointment(appointment_id)
        
        # Log access
        audit_logger.log_event(
            'appointment_access',
            appointment_id=appointment_id
        )
        
        return appointment
        
    except Exception as e:
        logger.error(f"Get appointment error: {e}")
        raise HTTPException(status_code=404, detail="Appointment not found")


@app.post("/api/observations/search")
async def search_observations(
    request: ObservationSearchRequest,
    authorized: bool = Depends(verify_api_key)
):
    """
    Search observations (lab results, vitals)
    
    Args:
        request: Search parameters
        
    Returns:
        List of observations
    """
    try:
        async with fhir_client as client:
            results = await client.get_observations(
                patient_id=request.patient_id,
                category=request.category,
                code=request.code,
                date=request.date
            )
        
        # Apply normal/abnormal policy
        if results.get('entry'):
            for entry in results['entry']:
                observation = entry.get('resource', {})
                
                # Check if abnormal
                interpretation = observation.get('interpretation', [])
                is_normal = any(
                    coding.get('code') == 'N'
                    for interp in interpretation
                    for coding in interp.get('coding', [])
                )
                
                # If abnormal, remove value
                if not is_normal and 'valueQuantity' in observation:
                    observation['valueQuantity'] = {
                        'status': 'Requires provider review'
                    }
        
        # Log access
        audit_logger.log_event(
            'observation_search',
            patient_id=request.patient_id,
            category=request.category,
            results_count=len(results.get('entry', []))
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Observation search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/api/patients/{patient_id}/summary")
async def get_patient_summary(
    patient_id: str,
    authorized: bool = Depends(verify_api_key)
):
    """
    Get comprehensive patient summary
    
    Args:
        patient_id: Patient identifier
        
    Returns:
        Patient summary with appointments, medications, observations
    """
    try:
        async with fhir_client as client:
            summary = await client.get_patient_summary(patient_id)
        
        # Redact PHI from summary
        if 'patient' in summary and summary['patient']:
            summary['patient'] = phi_redactor.redact_dict(summary['patient'])
        
        # Log access
        audit_logger.log_event(
            'patient_summary_access',
            patient_id=patient_id
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Get patient summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get summary")


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize FHIR client on startup"""
    logger.info("FHIR Bridge API starting...")
    await fhir_client.initialize()
    logger.info("FHIR Bridge API ready")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    logger.info("FHIR Bridge API shutting down...")
    await fhir_client.close()
    logger.info("FHIR Bridge API shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
