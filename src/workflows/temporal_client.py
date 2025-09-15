"""
Temporal Workflow Client
Manages durable workflows for HIPAA-compliant operations
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import uuid

from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy

from src.core.security import PHIRedactor, AuditLogger
from src.services.fhir_client import FHIRClient

logger = logging.getLogger(__name__)


# ===== Workflow Data Classes =====

@dataclass
class AppointmentConfirmationData:
    """Data for appointment confirmation workflow"""
    appointment_id: str
    patient_id: str
    appointment_date: str
    appointment_time: str
    confirmation_method: str = 'sms'  # sms, email, or both


@dataclass
class RefillProcessingData:
    """Data for prescription refill workflow"""
    task_id: str
    patient_id: str
    medication_name: str
    prescription_id: str
    pharmacy: Optional[str] = None


@dataclass
class MessageReviewData:
    """Data for provider message review workflow"""
    communication_id: str
    task_id: str
    patient_id: str
    provider_name: Optional[str] = None
    urgency: str = 'routine'


@dataclass
class PriorAuthData:
    """Data for prior authorization workflow"""
    patient_id: str
    medication_name: str
    diagnosis_codes: List[str]
    payer_id: str
    provider_id: str


# ===== Activities =====

class MedicalActivities:
    """
    Temporal activities for medical workflows
    Each activity is a single, atomic operation
    """
    
    def __init__(self):
        """Initialize activities with required services"""
        self.fhir_client = FHIRClient()
        self.phi_redactor = PHIRedactor()
        self.audit_logger = AuditLogger()
    
    @activity.defn
    async def send_appointment_reminder(self, data: AppointmentConfirmationData) -> Dict[str, Any]:
        """
        Send appointment reminder to patient
        
        Args:
            data: Appointment confirmation data
            
        Returns:
            Result of reminder sending
        """
        try:
            # Get appointment details from FHIR
            appointment = await self.fhir_client.get_appointment(data.appointment_id)
            
            # Prepare reminder message (no PHI in SMS/email)
            message = f"Appointment reminder: {data.appointment_date} at {data.appointment_time}. Reply C to confirm or R to reschedule."
            
            # Send via configured method (mock implementation)
            if data.confirmation_method in ['sms', 'both']:
                # Send SMS (would integrate with Twilio)
                logger.info(f"SMS reminder sent for appointment {data.appointment_id}")
            
            if data.confirmation_method in ['email', 'both']:
                # Send email (would integrate with email service)
                logger.info(f"Email reminder sent for appointment {data.appointment_id}")
            
            # Log activity
            self.audit_logger.log_event(
                'appointment_reminder_sent',
                appointment_id=data.appointment_id,
                method=data.confirmation_method
            )
            
            return {
                'success': True,
                'reminder_sent': datetime.utcnow().isoformat(),
                'method': data.confirmation_method
            }
            
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @activity.defn
    async def check_appointment_confirmation(self, appointment_id: str) -> Dict[str, Any]:
        """
        Check if appointment has been confirmed
        
        Args:
            appointment_id: Appointment identifier
            
        Returns:
            Confirmation status
        """
        try:
            appointment = await self.fhir_client.get_appointment(appointment_id)
            
            # Check participant status
            for participant in appointment.get('participant', []):
                if 'Patient' in participant.get('actor', {}).get('reference', ''):
                    status = participant.get('status')
                    return {
                        'confirmed': status == 'accepted',
                        'status': status
                    }
            
            return {
                'confirmed': False,
                'status': 'unknown'
            }
            
        except Exception as e:
            logger.error(f"Failed to check confirmation: {e}")
            return {
                'confirmed': False,
                'error': str(e)
            }
    
    @activity.defn
    async def process_refill_request(self, data: RefillProcessingData) -> Dict[str, Any]:
        """
        Process prescription refill request
        
        Args:
            data: Refill processing data
            
        Returns:
            Processing result
        """
        try:
            # Update task status to in-progress
            await self.fhir_client.update_task_status(data.task_id, 'in-progress')
            
            # Verify prescription details
            # In production, would check:
            # - Refills remaining
            # - Last fill date
            # - Drug interactions
            # - Insurance coverage
            
            # Create new prescription if approved
            new_prescription = {
                'status': 'active',
                'intent': 'order',
                'medicationCodeableConcept': {
                    'text': data.medication_name
                },
                'subject': {'reference': f"Patient/{data.patient_id}"},
                'authoredOn': datetime.utcnow().isoformat(),
                'dispenseRequest': {
                    'numberOfRepeatsAllowed': 3,
                    'quantity': {
                        'value': 30,
                        'unit': 'tablets'
                    },
                    'expectedSupplyDuration': {
                        'value': 30,
                        'unit': 'days'
                    }
                }
            }
            
            if data.pharmacy:
                new_prescription['dispenseRequest']['performer'] = {
                    'display': data.pharmacy
                }
            
            result = await self.fhir_client.create_medication_request(new_prescription)
            
            # Update task status
            await self.fhir_client.update_task_status(data.task_id, 'completed')
            
            # Log processing
            self.audit_logger.log_event(
                'refill_processed',
                task_id=data.task_id,
                prescription_id=result['id']
            )
            
            return {
                'success': True,
                'prescription_id': result['id'],
                'status': 'approved'
            }
            
        except Exception as e:
            logger.error(f"Failed to process refill: {e}")
            await self.fhir_client.update_task_status(data.task_id, 'failed')
            return {
                'success': False,
                'error': str(e)
            }
    
    @activity.defn
    async def notify_provider(self, data: MessageReviewData) -> Dict[str, Any]:
        """
        Notify provider of pending message
        
        Args:
            data: Message review data
            
        Returns:
            Notification result
        """
        try:
            # In production, would send notification via:
            # - Secure messaging system
            # - Provider portal
            # - Pager for urgent messages
            
            if data.urgency == 'urgent':
                # Send urgent notification
                logger.info(f"Urgent notification sent for message {data.communication_id}")
                notification_method = 'pager'
            else:
                # Queue for routine review
                logger.info(f"Message queued for review: {data.communication_id}")
                notification_method = 'queue'
            
            # Log notification
            self.audit_logger.log_event(
                'provider_notified',
                communication_id=data.communication_id,
                method=notification_method,
                urgency=data.urgency
            )
            
            return {
                'success': True,
                'notified': datetime.utcnow().isoformat(),
                'method': notification_method
            }
            
        except Exception as e:
            logger.error(f"Failed to notify provider: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @activity.defn
    async def submit_prior_auth(self, data: PriorAuthData) -> Dict[str, Any]:
        """
        Submit prior authorization to payer
        
        Args:
            data: Prior authorization data
            
        Returns:
            Submission result
        """
        try:
            # In production, would:
            # - Connect to payer API/portal
            # - Submit clinical documentation
            # - Include diagnosis codes and medical necessity
            
            # Mock submission
            auth_request = {
                'patient_id': data.patient_id,
                'medication': data.medication_name,
                'diagnosis_codes': data.diagnosis_codes,
                'payer': data.payer_id,
                'provider': data.provider_id,
                'submitted': datetime.utcnow().isoformat(),
                'reference_number': str(uuid.uuid4())[:8].upper()
            }
            
            # Log submission
            self.audit_logger.log_event(
                'prior_auth_submitted',
                **auth_request
            )
            
            return {
                'success': True,
                'reference_number': auth_request['reference_number'],
                'status': 'pending',
                'estimated_response': (datetime.utcnow() + timedelta(days=3)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to submit prior auth: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# ===== Workflows =====

@workflow.defn
class AppointmentConfirmationWorkflow:
    """
    Workflow for appointment confirmation process
    Sends reminders and tracks confirmations
    """
    
    @workflow.run
    async def run(self, data: AppointmentConfirmationData) -> Dict[str, Any]:
        """
        Execute appointment confirmation workflow
        
        Args:
            data: Appointment confirmation data
            
        Returns:
            Workflow result
        """
        # Calculate when to send reminder (24 hours before)
        appointment_datetime = datetime.fromisoformat(f"{data.appointment_date}T{data.appointment_time}")
        reminder_time = appointment_datetime - timedelta(hours=24)
        
        # Wait until reminder time
        await workflow.sleep_until(reminder_time)
        
        # Send reminder
        reminder_result = await workflow.execute_activity(
            MedicalActivities.send_appointment_reminder,
            data,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not reminder_result['success']:
            return {
                'success': False,
                'error': 'Failed to send reminder'
            }
        
        # Wait for confirmation (up to 4 hours)
        confirmation_deadline = datetime.utcnow() + timedelta(hours=4)
        confirmed = False
        
        while datetime.utcnow() < confirmation_deadline:
            # Check confirmation status
            status = await workflow.execute_activity(
                MedicalActivities.check_appointment_confirmation,
                data.appointment_id,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            if status.get('confirmed'):
                confirmed = True
                break
            
            # Wait 30 minutes before checking again
            await workflow.sleep(timedelta(minutes=30))
        
        # Send second reminder if not confirmed
        if not confirmed:
            # Send final reminder 4 hours before appointment
            final_reminder_time = appointment_datetime - timedelta(hours=4)
            if datetime.utcnow() < final_reminder_time:
                await workflow.sleep_until(final_reminder_time)
                
                await workflow.execute_activity(
                    MedicalActivities.send_appointment_reminder,
                    data,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3)
                )
        
        return {
            'success': True,
            'confirmed': confirmed,
            'reminders_sent': 2 if not confirmed else 1
        }


@workflow.defn
class RefillProcessingWorkflow:
    """
    Workflow for prescription refill processing
    Handles approval, pharmacy notification, and patient updates
    """
    
    @workflow.run
    async def run(self, data: RefillProcessingData) -> Dict[str, Any]:
        """
        Execute refill processing workflow
        
        Args:
            data: Refill processing data
            
        Returns:
            Workflow result
        """
        # Process refill request
        result = await workflow.execute_activity(
            MedicalActivities.process_refill_request,
            data,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10)
            )
        )
        
        if not result['success']:
            return {
                'success': False,
                'error': result.get('error', 'Processing failed')
            }
        
        # In production, would also:
        # - Send to pharmacy
        # - Notify patient
        # - Update insurance
        
        return {
            'success': True,
            'prescription_id': result['prescription_id'],
            'status': 'completed'
        }


@workflow.defn
class ProviderMessageReviewWorkflow:
    """
    Workflow for provider message review
    Ensures timely response to patient messages
    """
    
    @workflow.run
    async def run(self, data: MessageReviewData) -> Dict[str, Any]:
        """
        Execute provider message review workflow
        
        Args:
            data: Message review data
            
        Returns:
            Workflow result
        """
        # Notify provider
        notification_result = await workflow.execute_activity(
            MedicalActivities.notify_provider,
            data,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not notification_result['success']:
            return {
                'success': False,
                'error': 'Failed to notify provider'
            }
        
        # Set response deadline based on urgency
        if data.urgency == 'urgent':
            response_deadline = datetime.utcnow() + timedelta(hours=4)
        else:
            response_deadline = datetime.utcnow() + timedelta(days=2)
        
        # Wait for response or escalate
        await workflow.sleep_until(response_deadline)
        
        # Check if message was addressed
        # In production, would check task status
        # For now, we'll assume it needs escalation
        
        # Escalate if not addressed
        escalation_data = MessageReviewData(
            communication_id=data.communication_id,
            task_id=data.task_id,
            patient_id=data.patient_id,
            provider_name="On-Call Provider",
            urgency='urgent'
        )
        
        await workflow.execute_activity(
            MedicalActivities.notify_provider,
            escalation_data,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        return {
            'success': True,
            'escalated': True,
            'response_deadline': response_deadline.isoformat()
        }


@workflow.defn
class PriorAuthorizationWorkflow:
    """
    Workflow for prior authorization processing
    Handles submission, follow-up, and status tracking
    """
    
    @workflow.run
    async def run(self, data: PriorAuthData) -> Dict[str, Any]:
        """
        Execute prior authorization workflow
        
        Args:
            data: Prior authorization data
            
        Returns:
            Workflow result
        """
        # Submit prior authorization
        submission_result = await workflow.execute_activity(
            MedicalActivities.submit_prior_auth,
            data,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not submission_result['success']:
            return {
                'success': False,
                'error': 'Failed to submit prior authorization'
            }
        
        # Wait for response (mock - in production would poll or receive webhook)
        await workflow.sleep(timedelta(days=3))
        
        # Check status
        # In production, would query payer API
        status = 'approved'  # Mock approval
        
        # Notify provider and patient of decision
        # In production, would send notifications
        
        return {
            'success': True,
            'reference_number': submission_result['reference_number'],
            'status': status,
            'completed': datetime.utcnow().isoformat()
        }


# ===== Client =====

class TemporalClient:
    """
    Client for interacting with Temporal workflows
    """
    
    def __init__(self):
        """Initialize Temporal client"""
        self.host = os.getenv('TEMPORAL_HOST', 'localhost:7233')
        self.namespace = os.getenv('TEMPORAL_NAMESPACE', 'medical')
        self.task_queue = os.getenv('TEMPORAL_TASK_QUEUE', 'voice-agent-tasks')
        self.client = None
        self.worker = None
        
        logger.info(f"Temporal client initialized for {self.host}")
    
    async def connect(self):
        """Connect to Temporal server"""
        if not self.client:
            self.client = await Client.connect(self.host, namespace=self.namespace)
            logger.info("Connected to Temporal server")
    
    async def start_workflow(self, workflow_type: str, data: Dict[str, Any]) -> str:
        """
        Start a workflow
        
        Args:
            workflow_type: Type of workflow to start
            data: Workflow input data
            
        Returns:
            Workflow ID
        """
        if not self.client:
            await self.connect()
        
        workflow_id = f"{workflow_type}-{uuid.uuid4()}"
        
        workflow_map = {
            'appointment_confirmation': (AppointmentConfirmationWorkflow, AppointmentConfirmationData),
            'refill_processing': (RefillProcessingWorkflow, RefillProcessingData),
            'provider_message_review': (ProviderMessageReviewWorkflow, MessageReviewData),
            'prior_authorization': (PriorAuthorizationWorkflow, PriorAuthData)
        }
        
        if workflow_type not in workflow_map:
            raise ValueError(f"Unknown workflow type: {workflow_type}")
        
        workflow_class, data_class = workflow_map[workflow_type]
        workflow_data = data_class(**data)
        
        handle = await self.client.start_workflow(
            workflow_class.run,
            workflow_data,
            id=workflow_id,
            task_queue=self.task_queue
        )
        
        logger.info(f"Started workflow {workflow_id} of type {workflow_type}")
        return workflow_id
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow status
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow status information
        """
        if not self.client:
            await self.connect()
        
        handle = self.client.get_workflow_handle(workflow_id)
        
        try:
            result = await handle.result()
            return {
                'status': 'completed',
                'result': result
            }
        except Exception as e:
            # Check if still running
            try:
                await handle.describe()
                return {
                    'status': 'running'
                }
            except Exception:
                return {
                    'status': 'failed',
                    'error': str(e)
                }
    
    async def start_worker(self):
        """Start Temporal worker to process workflows"""
        if not self.client:
            await self.connect()
        
        activities = MedicalActivities()
        
        self.worker = Worker(
            self.client,
            task_queue=self.task_queue,
            workflows=[
                AppointmentConfirmationWorkflow,
                RefillProcessingWorkflow,
                ProviderMessageReviewWorkflow,
                PriorAuthorizationWorkflow
            ],
            activities=[
                activities.send_appointment_reminder,
                activities.check_appointment_confirmation,
                activities.process_refill_request,
                activities.notify_provider,
                activities.submit_prior_auth
            ]
        )
        
        logger.info(f"Starting Temporal worker on task queue: {self.task_queue}")
        await self.worker.run()
    
    async def shutdown(self):
        """Shutdown Temporal client and worker"""
        if self.worker:
            await self.worker.shutdown()
        if self.client:
            await self.client.close()
        logger.info("Temporal client shutdown complete")
