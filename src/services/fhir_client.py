"""
FHIR R4 Client for EHR Integration
HIPAA-compliant interface to FHIR servers
"""

import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import base64
from urllib.parse import urljoin
import os

from src.core.security import PHIRedactor, EncryptionService

logger = logging.getLogger(__name__)


class FHIRClient:
    """
    FHIR R4 client with HIPAA compliance
    Handles authentication, encryption, and audit logging
    """
    
    def __init__(self):
        """Initialize FHIR client with configuration"""
        self.base_url = os.getenv('FHIR_BASE_URL')
        self.tenant_id = os.getenv('FHIR_TENANT_ID')
        self.client_id = os.getenv('FHIR_CLIENT_ID')
        self.client_secret = os.getenv('FHIR_CLIENT_SECRET')
        self.auth_type = os.getenv('FHIR_AUTH_TYPE', 'oauth2')
        self.token_endpoint = os.getenv('FHIR_TOKEN_ENDPOINT')
        
        # Security services
        self.phi_redactor = PHIRedactor()
        self.encryption = EncryptionService()
        
        # Token management
        self.access_token = None
        self.token_expiry = None
        
        # Session configuration
        self.timeout = int(os.getenv('FHIR_TIMEOUT', 30))
        self.max_retries = int(os.getenv('FHIR_MAX_RETRIES', 3))
        self.verify_ssl = os.getenv('FHIR_VERIFY_SSL', 'true').lower() == 'true'
        
        # Initialize session
        self.session = None
        
        logger.info("FHIR client initialized")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def initialize(self):
        """Initialize HTTP session and authenticate"""
        if not self.session:
            connector = aiohttp.TCPConnector(
                ssl=self.verify_ssl,
                limit=100,
                limit_per_host=30
            )
            
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            
            # Authenticate if needed
            if self.auth_type == 'oauth2':
                await self._authenticate_oauth2()
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _authenticate_oauth2(self):
        """
        Authenticate using OAuth2 client credentials
        """
        try:
            if not self.token_endpoint:
                logger.error("Token endpoint not configured")
                return
            
            # Prepare OAuth2 request
            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': os.getenv('FHIR_SCOPE', 'launch patient/*.read patient/*.write')
            }
            
            async with self.session.post(
                self.token_endpoint,
                data=auth_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data.get('access_token')
                    expires_in = token_data.get('expires_in', 3600)
                    self.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                    logger.info("FHIR authentication successful")
                else:
                    logger.error(f"FHIR authentication failed: {response.status}")
                    
        except Exception as e:
            logger.error(f"OAuth2 authentication error: {e}")
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if self.auth_type == 'oauth2':
            if not self.access_token or \
               (self.token_expiry and datetime.utcnow() >= self.token_expiry):
                await self._authenticate_oauth2()
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authentication
        
        Returns:
            Headers dictionary
        """
        headers = {
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        
        if self.auth_type == 'oauth2' and self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        elif self.auth_type == 'basic':
            credentials = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            headers['Authorization'] = f'Basic {credentials}'
        
        return headers
    
    async def _request(self, method: str, endpoint: str, 
                      data: Optional[Dict] = None,
                      params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make FHIR API request with retry logic
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request body
            params: Query parameters
            
        Returns:
            Response data
        """
        if not self.session:
            await self.initialize()
        
        await self._ensure_authenticated()
        
        url = urljoin(self.base_url, endpoint)
        headers = self._get_headers()
        
        # Redact PHI from logs
        log_data = self.phi_redactor.redact_dict(data) if data else None
        logger.debug(f"FHIR request: {method} {endpoint}")
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                async with self.session.request(
                    method,
                    url,
                    headers=headers,
                    json=data,
                    params=params
                ) as response:
                    response_data = await response.json()
                    
                    if response.status >= 200 and response.status < 300:
                        return response_data
                    elif response.status == 401:
                        # Re-authenticate and retry
                        await self._authenticate_oauth2()
                        headers = self._get_headers()
                    else:
                        logger.error(f"FHIR request failed: {response.status}")
                        if attempt == self.max_retries - 1:
                            raise Exception(f"FHIR request failed: {response.status}")
                            
            except asyncio.TimeoutError:
                logger.error(f"FHIR request timeout (attempt {attempt + 1})")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.error(f"FHIR request error: {e}")
                if attempt == self.max_retries - 1:
                    raise
                    
            # Wait before retry
            await asyncio.sleep(2 ** attempt)
        
        raise Exception("FHIR request failed after all retries")
    
    # ===== Patient Resources =====
    
    async def get_patient(self, patient_id: str) -> Dict[str, Any]:
        """
        Retrieve patient resource
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Patient resource
        """
        endpoint = f"Patient/{patient_id}"
        return await self._request('GET', endpoint)
    
    async def search_patients(self, **kwargs) -> Dict[str, Any]:
        """
        Search for patients
        
        Args:
            **kwargs: Search parameters (name, birthdate, identifier, etc.)
            
        Returns:
            Bundle of patient resources
        """
        endpoint = "Patient"
        params = {k: v for k, v in kwargs.items() if v is not None}
        return await self._request('GET', endpoint, params=params)
    
    async def create_patient(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new patient resource
        
        Args:
            patient_data: Patient resource data
            
        Returns:
            Created patient resource
        """
        endpoint = "Patient"
        patient_data['resourceType'] = 'Patient'
        return await self._request('POST', endpoint, data=patient_data)
    
    async def update_patient(self, patient_id: str, 
                           patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update patient resource
        
        Args:
            patient_id: Patient identifier
            patient_data: Updated patient data
            
        Returns:
            Updated patient resource
        """
        endpoint = f"Patient/{patient_id}"
        patient_data['resourceType'] = 'Patient'
        patient_data['id'] = patient_id
        return await self._request('PUT', endpoint, data=patient_data)
    
    # ===== Appointment Resources =====
    
    async def create_appointment(self, appointment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create appointment resource
        
        Args:
            appointment_data: Appointment details
            
        Returns:
            Created appointment resource
        """
        endpoint = "Appointment"
        appointment_data['resourceType'] = 'Appointment'
        
        # Ensure required fields
        if 'status' not in appointment_data:
            appointment_data['status'] = 'proposed'
        
        return await self._request('POST', endpoint, data=appointment_data)
    
    async def get_appointment(self, appointment_id: str) -> Dict[str, Any]:
        """
        Retrieve appointment resource
        
        Args:
            appointment_id: Appointment identifier
            
        Returns:
            Appointment resource
        """
        endpoint = f"Appointment/{appointment_id}"
        return await self._request('GET', endpoint)
    
    async def search_appointments(self, **kwargs) -> Dict[str, Any]:
        """
        Search appointments
        
        Args:
            **kwargs: Search parameters (patient, date, status, etc.)
            
        Returns:
            Bundle of appointment resources
        """
        endpoint = "Appointment"
        params = {k: v for k, v in kwargs.items() if v is not None}
        return await self._request('GET', endpoint, params=params)
    
    async def update_appointment_status(self, appointment_id: str, 
                                       status: str) -> Dict[str, Any]:
        """
        Update appointment status
        
        Args:
            appointment_id: Appointment identifier
            status: New status (proposed, pending, booked, arrived, fulfilled, cancelled, noshow)
            
        Returns:
            Updated appointment resource
        """
        # Get current appointment
        appointment = await self.get_appointment(appointment_id)
        
        # Update status
        appointment['status'] = status
        
        endpoint = f"Appointment/{appointment_id}"
        return await self._request('PUT', endpoint, data=appointment)
    
    # ===== Communication Resources =====
    
    async def create_communication(self, communication_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create communication resource (for messages)
        
        Args:
            communication_data: Communication details
            
        Returns:
            Created communication resource
        """
        endpoint = "Communication"
        communication_data['resourceType'] = 'Communication'
        
        # Set defaults
        if 'status' not in communication_data:
            communication_data['status'] = 'completed'
        if 'sent' not in communication_data:
            communication_data['sent'] = datetime.utcnow().isoformat()
        
        return await self._request('POST', endpoint, data=communication_data)
    
    async def get_communications(self, patient_id: str) -> Dict[str, Any]:
        """
        Get communications for a patient
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Bundle of communication resources
        """
        endpoint = "Communication"
        params = {'subject': f"Patient/{patient_id}"}
        return await self._request('GET', endpoint, params=params)
    
    # ===== Task Resources =====
    
    async def create_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create task resource (for workflow items)
        
        Args:
            task_data: Task details
            
        Returns:
            Created task resource
        """
        endpoint = "Task"
        task_data['resourceType'] = 'Task'
        
        # Set defaults
        if 'status' not in task_data:
            task_data['status'] = 'requested'
        if 'intent' not in task_data:
            task_data['intent'] = 'order'
        if 'authoredOn' not in task_data:
            task_data['authoredOn'] = datetime.utcnow().isoformat()
        
        return await self._request('POST', endpoint, data=task_data)
    
    async def update_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """
        Update task status
        
        Args:
            task_id: Task identifier
            status: New status (draft, requested, received, accepted, ready, 
                   in-progress, completed, cancelled, failed)
            
        Returns:
            Updated task resource
        """
        # Get current task
        task = await self.get_task(task_id)
        
        # Update status
        task['status'] = status
        
        endpoint = f"Task/{task_id}"
        return await self._request('PUT', endpoint, data=task)
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Retrieve task resource
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task resource
        """
        endpoint = f"Task/{task_id}"
        return await self._request('GET', endpoint)
    
    # ===== Observation Resources (for lab results) =====
    
    async def get_observations(self, patient_id: str, 
                              category: Optional[str] = None,
                              code: Optional[str] = None,
                              date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get observations (lab results, vitals) for a patient
        
        Args:
            patient_id: Patient identifier
            category: Category filter (laboratory, vital-signs, etc.)
            code: LOINC code filter
            date: Date filter
            
        Returns:
            Bundle of observation resources
        """
        endpoint = "Observation"
        params = {
            'subject': f"Patient/{patient_id}",
            'category': category,
            'code': code,
            'date': date
        }
        params = {k: v for k, v in params.items() if v is not None}
        return await self._request('GET', endpoint, params=params)
    
    async def get_latest_observation(self, patient_id: str, 
                                    code: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent observation for a specific code
        
        Args:
            patient_id: Patient identifier
            code: LOINC code
            
        Returns:
            Most recent observation or None
        """
        params = {
            'subject': f"Patient/{patient_id}",
            'code': code,
            '_sort': '-date',
            '_count': 1
        }
        
        endpoint = "Observation"
        result = await self._request('GET', endpoint, params=params)
        
        if result.get('entry'):
            return result['entry'][0]['resource']
        return None
    
    # ===== MedicationRequest Resources =====
    
    async def get_medication_requests(self, patient_id: str,
                                     status: Optional[str] = None) -> Dict[str, Any]:
        """
        Get medication requests (prescriptions) for a patient
        
        Args:
            patient_id: Patient identifier
            status: Status filter (active, completed, cancelled, etc.)
            
        Returns:
            Bundle of medication request resources
        """
        endpoint = "MedicationRequest"
        params = {
            'subject': f"Patient/{patient_id}",
            'status': status
        }
        params = {k: v for k, v in params.items() if v is not None}
        return await self._request('GET', endpoint, params=params)
    
    async def create_medication_request(self, 
                                       medication_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create medication request (prescription)
        
        Args:
            medication_data: Medication request details
            
        Returns:
            Created medication request resource
        """
        endpoint = "MedicationRequest"
        medication_data['resourceType'] = 'MedicationRequest'
        
        # Set required fields
        if 'status' not in medication_data:
            medication_data['status'] = 'draft'
        if 'intent' not in medication_data:
            medication_data['intent'] = 'order'
        if 'authoredOn' not in medication_data:
            medication_data['authoredOn'] = datetime.utcnow().isoformat()
        
        return await self._request('POST', endpoint, data=medication_data)
    
    # ===== Bundle Operations =====
    
    async def execute_transaction(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute FHIR transaction bundle
        
        Args:
            bundle: Transaction bundle with multiple operations
            
        Returns:
            Transaction response bundle
        """
        bundle['resourceType'] = 'Bundle'
        bundle['type'] = 'transaction'
        
        return await self._request('POST', '', data=bundle)
    
    # ===== Utility Methods =====
    
    async def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """
        Get comprehensive patient summary
        
        Args:
            patient_id: Patient identifier
            
        Returns:
            Patient summary with demographics, appointments, medications, etc.
        """
        summary = {}
        
        # Get patient demographics
        try:
            summary['patient'] = await self.get_patient(patient_id)
        except Exception as e:
            logger.error(f"Failed to get patient demographics: {e}")
            summary['patient'] = None
        
        # Get upcoming appointments
        try:
            appointments = await self.search_appointments(
                patient=f"Patient/{patient_id}",
                date=f"ge{datetime.utcnow().date().isoformat()}",
                _sort='date',
                _count=5
            )
            summary['upcoming_appointments'] = appointments.get('entry', [])
        except Exception as e:
            logger.error(f"Failed to get appointments: {e}")
            summary['upcoming_appointments'] = []
        
        # Get active medications
        try:
            medications = await self.get_medication_requests(patient_id, status='active')
            summary['active_medications'] = medications.get('entry', [])
        except Exception as e:
            logger.error(f"Failed to get medications: {e}")
            summary['active_medications'] = []
        
        # Get recent observations
        try:
            observations = await self.get_observations(
                patient_id,
                date=f"ge{(datetime.utcnow() - timedelta(days=90)).date().isoformat()}"
            )
            summary['recent_observations'] = observations.get('entry', [])
        except Exception as e:
            logger.error(f"Failed to get observations: {e}")
            summary['recent_observations'] = []
        
        return summary
    
    async def verify_patient_identity(self, name: str, dob: str, 
                                     mrn: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Verify patient identity for authentication
        
        Args:
            name: Patient name
            dob: Date of birth
            mrn: Medical record number (optional)
            
        Returns:
            Patient resource if verified, None otherwise
        """
        try:
            # Search by name and birthdate
            params = {
                'name': name,
                'birthdate': dob
            }
            
            if mrn:
                params['identifier'] = mrn
            
            result = await self.search_patients(**params)
            
            if result.get('entry') and len(result['entry']) == 1:
                # Exactly one match - verified
                return result['entry'][0]['resource']
            elif result.get('entry') and len(result['entry']) > 1:
                # Multiple matches - need more specific criteria
                logger.warning(f"Multiple patients match criteria: {name}, {dob}")
                return None
            else:
                # No matches
                return None
                
        except Exception as e:
            logger.error(f"Patient verification error: {e}")
            return None
