"""
Main FastAPI Application
WebSocket server for Twilio Media Streams and HTTP endpoints
"""

import os
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import hashlib
import hmac
import base64

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from src.core.agent import HIPAAVoiceAgent
from src.core.compliance import HIPAACompliance
from src.core.security import AuditLogger
from src.workflows.temporal_client import TemporalClient

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="HIPAA Voice Agent API",
    description="HIPAA-compliant voice AI system for medical offices",
    version="1.0.0",
    docs_url=None if os.getenv('ENVIRONMENT') == 'production' else "/docs",
    redoc_url=None if os.getenv('ENVIRONMENT') == 'production' else "/redoc"
)

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
)

# CORS middleware (configure carefully for production)
if os.getenv('CORS_ENABLED', 'false').lower() == 'true':
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv('CORS_ORIGINS', '').split(','),
        allow_methods=os.getenv('CORS_METHODS', 'GET,POST').split(','),
        allow_headers=os.getenv('CORS_HEADERS', 'Content-Type,Authorization').split(','),
        allow_credentials=False
    )

# Initialize services
agent = HIPAAVoiceAgent()
compliance = HIPAACompliance()
audit_logger = AuditLogger()
temporal_client = TemporalClient()

# Security
security = HTTPBearer()


# ===== Request/Response Models =====

class TwilioWebhookRequest(BaseModel):
    """Twilio webhook request model"""
    CallSid: str
    From: str
    To: str
    CallStatus: str
    Direction: str
    AccountSid: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str
    compliance_check: bool


class ComplianceReport(BaseModel):
    """Compliance status report"""
    compliant: bool
    timestamp: str
    violations: list
    checks: dict


# ===== Helper Functions =====

def verify_twilio_signature(request: Request, body: bytes) -> bool:
    """
    Verify Twilio webhook signature
    
    Args:
        request: FastAPI request object
        body: Request body bytes
        
    Returns:
        True if signature is valid
    """
    if os.getenv('TWILIO_SIGNATURE_VALIDATION', 'true').lower() != 'true':
        return True  # Skip validation in development
    
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    signature = request.headers.get('X-Twilio-Signature', '')
    
    if not signature or not auth_token:
        return False
    
    # Build the URL
    url = str(request.url)
    
    # If POST, sort parameters and append to URL
    if request.method == 'POST':
        params = []
        if body:
            try:
                data = body.decode('utf-8')
                for param in data.split('&'):
                    if '=' in param:
                        params.append(tuple(param.split('=', 1)))
                params.sort()
                for key, value in params:
                    url += key + value
            except Exception:
                return False
    
    # Compute signature
    computed = base64.b64encode(
        hmac.new(
            auth_token.encode('utf-8'),
            url.encode('utf-8'),
            hashlib.sha1
        ).digest()
    ).decode('utf-8')
    
    return computed == signature


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Verify API key for non-Twilio endpoints
    
    Args:
        credentials: Bearer token credentials
        
    Returns:
        True if API key is valid
    """
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


# ===== Endpoints =====

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Health status and compliance check
    """
    compliance_report = compliance.get_compliance_report()
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        compliance_check=compliance_report['compliant']
    )


@app.get("/compliance", response_model=ComplianceReport)
async def compliance_check(authorized: bool = Depends(verify_api_key)):
    """
    Get HIPAA compliance status report
    
    Returns:
        Detailed compliance report
    """
    report = compliance.get_compliance_report()
    
    return ComplianceReport(
        compliant=report['compliant'],
        timestamp=report['timestamp'],
        violations=report['violations'],
        checks=report['checks']
    )


@app.post("/webhooks/twilio/voice")
async def twilio_voice_webhook(request: Request):
    """
    Handle Twilio voice webhook for incoming calls
    
    Args:
        request: Incoming webhook request
        
    Returns:
        TwiML response for call handling
    """
    # Get request body
    body = await request.body()
    
    # Verify Twilio signature
    if not verify_twilio_signature(request, body):
        logger.warning("Invalid Twilio signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse request
    try:
        form_data = await request.form()
        call_data = {key: value for key, value in form_data.items()}
    except Exception as e:
        logger.error(f"Failed to parse webhook data: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
    
    # Log call start
    audit_logger.log_event(
        'incoming_call',
        call_sid=call_data.get('CallSid'),
        from_number_hash=hashlib.sha256(
            call_data.get('From', '').encode()
        ).hexdigest()
    )
    
    # Generate TwiML response to connect to WebSocket
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Thank you for calling. Connecting you to our automated assistant.</Say>
    <Connect>
        <Stream url="wss://{request.headers.get('host')}/ws/{call_data.get('CallSid')}">
            <Parameter name="CallSid" value="{call_data.get('CallSid')}" />
            <Parameter name="AccountSid" value="{call_data.get('AccountSid')}" />
            <Parameter name="From" value="{call_data.get('From')}" />
            <Parameter name="To" value="{call_data.get('To')}" />
        </Stream>
    </Connect>
</Response>"""
    
    return JSONResponse(
        content=twiml_response,
        media_type="application/xml"
    )


@app.post("/webhooks/twilio/status")
async def twilio_status_webhook(request: Request):
    """
    Handle Twilio call status updates
    
    Args:
        request: Status webhook request
        
    Returns:
        Acknowledgment response
    """
    # Get request body
    body = await request.body()
    
    # Verify signature
    if not verify_twilio_signature(request, body):
        logger.warning("Invalid Twilio signature for status webhook")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse status update
    try:
        form_data = await request.form()
        status_data = {key: value for key, value in form_data.items()}
    except Exception as e:
        logger.error(f"Failed to parse status data: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")
    
    # Log status update
    audit_logger.log_event(
        'call_status_update',
        call_sid=status_data.get('CallSid'),
        status=status_data.get('CallStatus'),
        duration=status_data.get('CallDuration')
    )
    
    # Handle specific statuses
    call_status = status_data.get('CallStatus')
    if call_status == 'completed':
        # Trigger post-call workflows
        asyncio.create_task(handle_call_completed(status_data))
    
    return {"status": "acknowledged"}


@app.websocket("/ws/{call_sid}")
async def websocket_endpoint(websocket: WebSocket, call_sid: str):
    """
    WebSocket endpoint for Twilio Media Streams
    
    Args:
        websocket: WebSocket connection
        call_sid: Twilio call SID
    """
    await websocket.accept()
    
    logger.info(f"WebSocket connected for call {call_sid}")
    
    # Initialize call metadata
    call_metadata = {
        'call_sid': call_sid,
        'connected_at': datetime.utcnow().isoformat(),
        'stream_sid': None
    }
    
    try:
        # Handle incoming messages
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event_type = data.get('event')
            
            if event_type == 'connected':
                # Stream connected event
                logger.info(f"Media stream connected for call {call_sid}")
                call_metadata['stream_sid'] = data.get('streamSid')
                
            elif event_type == 'start':
                # Stream started event
                stream_data = data.get('start', {})
                call_metadata['media_format'] = stream_data.get('mediaFormat')
                call_metadata['call_data'] = stream_data.get('customParameters', {})
                
                # Start handling the call with the agent
                asyncio.create_task(
                    agent.handle_incoming_call(websocket, call_metadata)
                )
                
            elif event_type == 'media':
                # Media payload (audio data)
                # This is handled by the agent's pipeline
                pass
                
            elif event_type == 'stop':
                # Stream stopped
                logger.info(f"Media stream stopped for call {call_sid}")
                break
                
            elif event_type == 'mark':
                # Mark event (custom event)
                mark_data = data.get('mark', {})
                logger.debug(f"Mark event received: {mark_data}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error for call {call_sid}: {e}")
    finally:
        # Clean up
        audit_logger.log_event(
            'websocket_closed',
            call_sid=call_sid,
            duration=(datetime.utcnow() - datetime.fromisoformat(
                call_metadata['connected_at']
            )).total_seconds()
        )


@app.post("/api/appointments/schedule")
async def schedule_appointment(
    request: Request,
    authorized: bool = Depends(verify_api_key)
):
    """
    API endpoint to schedule appointments
    
    Args:
        request: Appointment scheduling request
        
    Returns:
        Scheduling result
    """
    try:
        data = await request.json()
        
        # Validate required fields
        required = ['patient_id', 'appointment_type', 'preferred_date']
        for field in required:
            if field not in data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Use medical tools to book appointment
        from src.tools.medical_tools import MedicalTools
        from src.services.fhir_client import FHIRClient
        
        async with FHIRClient() as fhir:
            tools = MedicalTools(fhir)
            result = await tools.book_appointment(**data)
        
        if result['success']:
            # Start confirmation workflow
            await temporal_client.start_workflow(
                'appointment_confirmation',
                {
                    'appointment_id': result['appointment_id'],
                    'patient_id': data['patient_id'],
                    'appointment_date': result['details']['date'],
                    'appointment_time': result['details']['time']
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to schedule appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/messages/provider")
async def leave_provider_message(
    request: Request,
    authorized: bool = Depends(verify_api_key)
):
    """
    API endpoint to leave message for provider
    
    Args:
        request: Message request
        
    Returns:
        Message submission result
    """
    try:
        data = await request.json()
        
        # Validate required fields
        required = ['patient_id', 'message']
        for field in required:
            if field not in data:
                raise HTTPException(
                    status_code=400,
                    detail=f"Missing required field: {field}"
                )
        
        # Use medical tools to leave message
        from src.tools.medical_tools import MedicalTools
        from src.services.fhir_client import FHIRClient
        
        async with FHIRClient() as fhir:
            tools = MedicalTools(fhir)
            result = await tools.leave_message_for_provider(**data)
        
        if result['success']:
            # Start review workflow
            await temporal_client.start_workflow(
                'provider_message_review',
                {
                    'communication_id': result.get('reference_number'),
                    'task_id': f"task-{result.get('reference_number')}",
                    'patient_id': data['patient_id'],
                    'provider_name': data.get('provider_name'),
                    'urgency': data.get('urgency', 'routine')
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to leave message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Helper Functions =====

async def handle_call_completed(call_data: Dict[str, Any]):
    """
    Handle post-call processing
    
    Args:
        call_data: Call completion data
    """
    try:
        # Log call completion
        audit_logger.log_event(
            'call_completed',
            call_sid=call_data.get('CallSid'),
            duration=call_data.get('CallDuration'),
            status=call_data.get('CallStatus')
        )
        
        # Trigger any follow-up workflows
        # For example, send call summary, update records, etc.
        
    except Exception as e:
        logger.error(f"Error in post-call processing: {e}")


# ===== Startup/Shutdown Events =====

@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logger.info("Starting HIPAA Voice Agent API")
    
    # Connect to Temporal
    await temporal_client.connect()
    
    # Verify compliance
    report = compliance.get_compliance_report()
    if not report['compliant']:
        logger.warning(f"Compliance issues detected: {report['violations']}")
    
    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger.info("Shutting down HIPAA Voice Agent API")
    
    # Close connections
    await temporal_client.shutdown()
    
    logger.info("Shutdown complete")


# ===== Main Entry Point =====

if __name__ == "__main__":
    # Run with uvicorn for production
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8080,
        workers=int(os.getenv('WORKERS', 2)),
        loop="uvloop",
        access_log=True,
        use_colors=False,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": os.getenv('LOG_LEVEL', 'INFO'),
                "handlers": ["default"],
            },
        }
    )
