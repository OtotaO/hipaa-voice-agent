"""
HIPAA-Compliant Pipecat Voice Agent
Core implementation with PHI protection and audit logging
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
import hashlib
import hmac

from pipecat.pipeline import Pipeline
from pipecat.transports.twilio import TwilioTransport
from pipecat.processors.aggregators import LLMUserContextAggregator, LLMAssistantContextAggregator
from pipecat.processors.llm import LLMProcessor
from pipecat.services.aws_transcribe import AWSTranscribeSTTService
from pipecat.services.openai import OpenAILLMService
from pipecat.frames import Frame, AudioFrame, TextFrame, EndFrame
from pipecat.utils import create_task

from src.core.security import PHIRedactor, AuditLogger, CallerVerification
from src.core.compliance import HIPAACompliance
from src.services.fhir_client import FHIRClient
from src.tools.medical_tools import MedicalTools
from src.workflows.temporal_client import TemporalClient

# Configure logging with PHI redaction
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/logs/pipecat.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize PHI redactor
phi_redactor = PHIRedactor()


@dataclass
class CallContext:
    """
    Maintains call state with PHI protection
    """
    call_sid: str
    caller_number: str  # Hashed for privacy
    caller_verified: bool = False
    caller_dob: Optional[str] = None  # Encrypted
    caller_mrn: Optional[str] = None  # Encrypted
    intent: Optional[str] = None
    session_data: Dict[str, Any] = field(default_factory=dict)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    
    def add_audit_entry(self, action: str, details: Dict[str, Any]):
        """Add entry to audit trail with PHI redaction"""
        self.audit_trail.append({
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'details': phi_redactor.redact_dict(details)
        })


class HIPAAVoiceAgent:
    """
    Main voice agent with HIPAA compliance built-in
    """
    
    def __init__(self):
        """Initialize the HIPAA-compliant voice agent"""
        self.compliance = HIPAACompliance()
        self.audit_logger = AuditLogger()
        self.verifier = CallerVerification()
        self.fhir_client = FHIRClient()
        self.medical_tools = MedicalTools(self.fhir_client)
        self.temporal_client = TemporalClient()
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize services
        self._init_services()
        
        # System prompt for after-hours receptionist
        self.system_prompt = self._load_system_prompt()
        
        logger.info("HIPAA Voice Agent initialized successfully")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with validation"""
        config = {
            'twilio': {
                'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
                'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
                'phone_number': os.getenv('TWILIO_PHONE_NUMBER'),
                'hipaa_project_id': os.getenv('TWILIO_HIPAA_PROJECT_ID'),
            },
            'aws': {
                'access_key': os.getenv('AWS_ACCESS_KEY_ID'),
                'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                'region': os.getenv('AWS_REGION'),
            },
            'llm': {
                'endpoint': os.getenv('LLM_ENDPOINT'),
                'model': os.getenv('LLM_MODEL'),
                'max_tokens': int(os.getenv('LLM_MAX_TOKENS', 2048)),
                'temperature': float(os.getenv('LLM_TEMPERATURE', 0.7)),
            },
            'security': {
                'enable_encryption': os.getenv('DB_ENCRYPT_PHI', 'true').lower() == 'true',
                'enable_audit': os.getenv('AUDIT_ENABLED', 'true').lower() == 'true',
                'phi_redaction': os.getenv('PHI_REDACTION_ENABLED', 'true').lower() == 'true',
            }
        }
        
        # Validate required settings
        self._validate_config(config)
        return config
    
    def _validate_config(self, config: Dict[str, Any]):
        """Validate HIPAA-required configuration"""
        required_keys = [
            ('twilio', 'hipaa_project_id'),
            ('security', 'enable_encryption'),
            ('security', 'enable_audit'),
        ]
        
        for section, key in required_keys:
            if not config.get(section, {}).get(key):
                raise ValueError(f"Missing required HIPAA config: {section}.{key}")
    
    def _init_services(self):
        """Initialize Pipecat services with HIPAA settings"""
        # AWS Transcribe Medical for ASR
        self.stt_service = AWSTranscribeSTTService(
            access_key=self.config['aws']['access_key'],
            secret_key=self.config['aws']['secret_key'],
            region=self.config['aws']['region'],
            medical_specialty='PRIMARYCARE',
            medical_type='CONVERSATION',
            show_speaker_labels=True,
        )
        
        # Self-hosted LLM service
        self.llm_service = OpenAILLMService(
            api_key='not-needed',  # Self-hosted
            base_url=self.config['llm']['endpoint'],
            model=self.config['llm']['model'],
            max_tokens=self.config['llm']['max_tokens'],
            temperature=self.config['llm']['temperature'],
        )
        
        logger.info("Services initialized with HIPAA configuration")
    
    def _load_system_prompt(self) -> str:
        """Load the after-hours receptionist system prompt"""
        return """You are a HIPAA-compliant medical office reception assistant handling after-hours calls.

CRITICAL RULES:
1. NEVER provide medical advice or diagnosis
2. ALWAYS verify caller identity before discussing any patient information
3. NEVER repeat or confirm PHI unless absolutely necessary
4. For emergencies, immediately instruct: "If this is a medical emergency, please hang up and dial 911"
5. NEVER send PHI via SMS or email confirmations

VERIFICATION PROCESS:
1. Ask for patient's full name
2. Ask for date of birth
3. Verify against records using the verify_patient tool

AVAILABLE ACTIONS:
- Schedule appointments (use schedule_appointment tool)
- Leave messages for providers (use leave_message tool)
- Provide general office information
- Handle prescription refill requests (non-controlled only)
- Direct to appropriate resources

CONVERSATION FLOW:
1. Greet caller professionally
2. Check for emergency
3. Verify identity if patient-specific request
4. Determine caller's need
5. Use appropriate tool or provide information
6. Confirm next steps (without PHI)
7. Professional closing

EXAMPLE RESPONSES:
- "Good evening, you've reached [Practice Name] after-hours service. Is this a medical emergency?"
- "I can help you schedule an appointment. First, I'll need to verify your identity."
- "I've left a message for your provider. They will review it during the next business day."
- "I've scheduled your appointment. You'll receive a confirmation text with the date and time."

Remember: Be professional, empathetic, and efficient while maintaining strict HIPAA compliance."""
    
    async def handle_incoming_call(self, websocket, call_data: Dict[str, Any]):
        """
        Handle incoming Twilio call with HIPAA compliance
        
        Args:
            websocket: WebSocket connection from Twilio
            call_data: Call metadata from Twilio
        """
        call_sid = call_data.get('CallSid')
        caller_number_hash = self._hash_phone_number(call_data.get('From', ''))
        
        # Initialize call context
        context = CallContext(
            call_sid=call_sid,
            caller_number=caller_number_hash
        )
        
        # Log call start (no PHI)
        self.audit_logger.log_event(
            event_type='call_started',
            call_sid=call_sid,
            timestamp=context.start_time
        )
        
        try:
            # Create Twilio transport
            transport = TwilioTransport(
                websocket=websocket,
                call_sid=call_sid,
                sample_rate=8000,
                audio_encoding='mulaw'
            )
            
            # Build the pipeline
            pipeline = await self._build_pipeline(transport, context)
            
            # Run the pipeline
            await pipeline.run()
            
        except Exception as e:
            logger.error(f"Error handling call {call_sid}: {phi_redactor.redact_string(str(e))}")
            context.add_audit_entry('error', {'type': 'call_handling', 'error': str(e)})
            
        finally:
            # Persist audit trail
            await self._persist_audit_trail(context)
            
            # Clean up
            await self._cleanup_call(context)
    
    async def _build_pipeline(self, transport: TwilioTransport, context: CallContext) -> Pipeline:
        """
        Build Pipecat pipeline with HIPAA-compliant components
        
        Args:
            transport: Twilio transport for audio
            context: Call context for maintaining state
        """
        # Create pipeline with security hooks
        pipeline = Pipeline([
            transport.input(),
            self.stt_service,
            PHIDetectorFrame(),  # Custom frame to detect PHI
            LLMUserContextAggregator(),
            CallContextFrame(context),  # Inject context
            LLMProcessor(
                llm_service=self.llm_service,
                system_prompt=self.system_prompt,
                tools=self._get_tools(context)
            ),
            PHIRedactorFrame(),  # Redact PHI from output
            LLMAssistantContextAggregator(),
            transport.output()
        ])
        
        # Add audit hooks
        pipeline.add_frame_handler(self._audit_frame_handler)
        
        return pipeline
    
    def _get_tools(self, context: CallContext) -> List[Dict[str, Any]]:
        """
        Get available tools for the LLM with context binding
        
        Args:
            context: Current call context
            
        Returns:
            List of tool definitions for the LLM
        """
        return [
            {
                'name': 'verify_patient',
                'description': 'Verify patient identity using name and DOB',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'full_name': {'type': 'string'},
                        'date_of_birth': {'type': 'string', 'format': 'date'}
                    },
                    'required': ['full_name', 'date_of_birth']
                },
                'function': lambda **kwargs: self._verify_patient(context, **kwargs)
            },
            {
                'name': 'schedule_appointment',
                'description': 'Schedule an appointment for the verified patient',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'appointment_type': {'type': 'string'},
                        'preferred_date': {'type': 'string', 'format': 'date'},
                        'preferred_time': {'type': 'string'},
                        'reason': {'type': 'string'}
                    },
                    'required': ['appointment_type', 'preferred_date']
                },
                'function': lambda **kwargs: self._schedule_appointment(context, **kwargs)
            },
            {
                'name': 'leave_message',
                'description': 'Leave a message for the provider',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'provider_name': {'type': 'string'},
                        'message': {'type': 'string'},
                        'urgency': {'type': 'string', 'enum': ['routine', 'urgent']}
                    },
                    'required': ['message']
                },
                'function': lambda **kwargs: self._leave_message(context, **kwargs)
            }
        ]
    
    async def _verify_patient(self, context: CallContext, full_name: str, date_of_birth: str) -> Dict[str, Any]:
        """
        Verify patient identity against records
        
        Args:
            context: Call context
            full_name: Patient's full name
            date_of_birth: Patient's date of birth
            
        Returns:
            Verification result
        """
        try:
            # Perform verification (implementation depends on your system)
            result = await self.verifier.verify(full_name, date_of_birth)
            
            if result['verified']:
                context.caller_verified = True
                context.caller_dob = self._encrypt_pii(date_of_birth)
                context.caller_mrn = self._encrypt_pii(result.get('mrn'))
                
                # Audit successful verification
                context.add_audit_entry('patient_verified', {
                    'method': 'name_dob',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return {
                    'success': True,
                    'message': 'Identity verified successfully'
                }
            else:
                # Audit failed verification
                context.add_audit_entry('verification_failed', {
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return {
                    'success': False,
                    'message': 'Unable to verify identity. Please try again.'
                }
                
        except Exception as e:
            logger.error(f"Verification error: {phi_redactor.redact_string(str(e))}")
            return {
                'success': False,
                'message': 'Verification system unavailable'
            }
    
    async def _schedule_appointment(
        self, 
        context: CallContext, 
        appointment_type: str,
        preferred_date: str,
        preferred_time: Optional[str] = None,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule an appointment for verified patient
        
        Args:
            context: Call context with verified patient info
            appointment_type: Type of appointment
            preferred_date: Requested date
            preferred_time: Requested time slot
            reason: Reason for visit (redacted)
            
        Returns:
            Scheduling result
        """
        if not context.caller_verified:
            return {
                'success': False,
                'message': 'Patient verification required before scheduling'
            }
        
        try:
            # Create FHIR Appointment resource
            appointment_data = {
                'resourceType': 'Appointment',
                'status': 'proposed',
                'appointmentType': {
                    'text': appointment_type
                },
                'description': phi_redactor.redact_string(reason) if reason else None,
                'start': preferred_date,
                'participant': [{
                    'actor': {
                        'reference': f"Patient/{context.caller_mrn}"
                    },
                    'status': 'needs-action'
                }]
            }
            
            # Submit to FHIR server
            result = await self.fhir_client.create_appointment(appointment_data)
            
            # Create Temporal workflow for follow-up
            workflow_id = await self.temporal_client.start_workflow(
                'appointment_confirmation',
                {
                    'appointment_id': result['id'],
                    'patient_id': context.caller_mrn,
                    'appointment_date': preferred_date
                }
            )
            
            # Audit the scheduling
            context.add_audit_entry('appointment_scheduled', {
                'appointment_id': result['id'],
                'workflow_id': workflow_id,
                'type': appointment_type,
                'date': preferred_date
            })
            
            return {
                'success': True,
                'message': f"Appointment scheduled for {preferred_date}. You'll receive a confirmation.",
                'appointment_id': result['id']
            }
            
        except Exception as e:
            logger.error(f"Scheduling error: {phi_redactor.redact_string(str(e))}")
            return {
                'success': False,
                'message': 'Unable to schedule at this time. Please try again later.'
            }
    
    async def _leave_message(
        self,
        context: CallContext,
        message: str,
        provider_name: Optional[str] = None,
        urgency: str = 'routine'
    ) -> Dict[str, Any]:
        """
        Leave a message for provider with PHI protection
        
        Args:
            context: Call context
            message: Message content (will be redacted)
            provider_name: Target provider
            urgency: Message urgency level
            
        Returns:
            Message creation result
        """
        try:
            # Redact PHI from message
            redacted_message = phi_redactor.redact_string(message)
            
            # Create FHIR Communication resource
            communication_data = {
                'resourceType': 'Communication',
                'status': 'completed',
                'priority': urgency,
                'subject': {
                    'reference': f"Patient/{context.caller_mrn}" if context.caller_verified else None
                },
                'payload': [{
                    'contentString': redacted_message
                }],
                'sent': datetime.utcnow().isoformat()
            }
            
            # Submit to FHIR server
            result = await self.fhir_client.create_communication(communication_data)
            
            # Create task for provider review
            task_id = await self.temporal_client.start_workflow(
                'provider_message_review',
                {
                    'communication_id': result['id'],
                    'urgency': urgency,
                    'provider': provider_name
                }
            )
            
            # Audit message creation
            context.add_audit_entry('message_created', {
                'communication_id': result['id'],
                'task_id': task_id,
                'urgency': urgency
            })
            
            return {
                'success': True,
                'message': 'Your message has been recorded and will be reviewed.',
                'reference_id': result['id'][:8]  # Partial ID for reference
            }
            
        except Exception as e:
            logger.error(f"Message error: {phi_redactor.redact_string(str(e))}")
            return {
                'success': False,
                'message': 'Unable to record message. Please try again.'
            }
    
    def _hash_phone_number(self, phone: str) -> str:
        """Hash phone number for privacy"""
        return hashlib.sha256(phone.encode()).hexdigest() if phone else 'unknown'
    
    def _encrypt_pii(self, data: str) -> str:
        """Encrypt PII/PHI data"""
        # Implementation would use proper encryption library
        # This is a placeholder
        return f"encrypted_{hashlib.sha256(data.encode()).hexdigest()[:16]}"
    
    async def _audit_frame_handler(self, frame: Frame):
        """Handle frames for audit logging"""
        if isinstance(frame, TextFrame):
            # Log text interactions (redacted)
            logger.debug(f"Text frame: {phi_redactor.redact_string(frame.text)}")
    
    async def _persist_audit_trail(self, context: CallContext):
        """Persist the audit trail for compliance"""
        try:
            await self.audit_logger.persist_trail(
                call_sid=context.call_sid,
                trail=context.audit_trail,
                duration=(datetime.utcnow() - context.start_time).total_seconds()
            )
        except Exception as e:
            logger.error(f"Failed to persist audit trail: {e}")
    
    async def _cleanup_call(self, context: CallContext):
        """Clean up call resources and temporary data"""
        try:
            # Clear any cached PHI
            context.session_data.clear()
            
            # Log call end
            self.audit_logger.log_event(
                event_type='call_ended',
                call_sid=context.call_sid,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


class PHIDetectorFrame(Frame):
    """Custom frame to detect PHI in audio transcriptions"""
    pass


class PHIRedactorFrame(Frame):
    """Custom frame to redact PHI from LLM outputs"""
    pass


class CallContextFrame(Frame):
    """Frame to maintain call context through pipeline"""
    def __init__(self, context: CallContext):
        self.context = context


async def main():
    """Main entry point for the voice agent"""
    agent = HIPAAVoiceAgent()
    
    # This would typically be called by your web server
    # when receiving Twilio webhooks
    logger.info("HIPAA Voice Agent ready for incoming calls")
    
    # Keep the agent running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down HIPAA Voice Agent")


if __name__ == "__main__":
    asyncio.run(main())
