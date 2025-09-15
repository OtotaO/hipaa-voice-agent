"""
Medical Tools for Voice Agent
HIPAA-compliant tools for handling medical office operations
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, time
import re
import pytz
from dataclasses import dataclass

from src.services.fhir_client import FHIRClient
from src.core.security import PHIRedactor, AuditLogger

logger = logging.getLogger(__name__)


@dataclass
class AppointmentSlot:
    """Available appointment slot"""
    date: str
    time: str
    provider: Optional[str]
    type: str
    duration_minutes: int
    available: bool = True


class MedicalTools:
    """
    Medical office tools for the voice agent
    All tools ensure HIPAA compliance and proper audit trails
    """
    
    def __init__(self, fhir_client: FHIRClient):
        """
        Initialize medical tools
        
        Args:
            fhir_client: FHIR client instance
        """
        self.fhir = fhir_client
        self.phi_redactor = PHIRedactor()
        self.audit_logger = AuditLogger()
        
        # Business configuration
        self.business_hours = {
            'start': time(8, 0),  # 8:00 AM
            'end': time(17, 0),   # 5:00 PM
            'days': [0, 1, 2, 3, 4]  # Monday-Friday
        }
        
        self.appointment_types = {
            'new_patient': {'duration': 60, 'description': 'New Patient Visit'},
            'follow_up': {'duration': 30, 'description': 'Follow-up Visit'},
            'physical': {'duration': 45, 'description': 'Annual Physical'},
            'urgent': {'duration': 20, 'description': 'Urgent Care'},
            'telehealth': {'duration': 20, 'description': 'Telehealth Visit'},
            'lab_review': {'duration': 15, 'description': 'Lab Results Review'}
        }
        
        # Timezone configuration
        self.timezone = pytz.timezone(os.getenv('BUSINESS_TIMEZONE', 'America/New_York'))
        
        logger.info("Medical tools initialized")
    
    async def book_appointment(self,
                              patient_id: str,
                              appointment_type: str,
                              preferred_date: str,
                              preferred_time: Optional[str] = None,
                              reason: Optional[str] = None,
                              provider_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Book an appointment for a patient
        
        Args:
            patient_id: Patient identifier
            appointment_type: Type of appointment
            preferred_date: Requested date (YYYY-MM-DD)
            preferred_time: Requested time (HH:MM)
            reason: Reason for visit
            provider_id: Specific provider requested
            
        Returns:
            Booking result with confirmation details
        """
        try:
            # Validate appointment type
            if appointment_type not in self.appointment_types:
                return {
                    'success': False,
                    'message': f"Invalid appointment type. Available types: {', '.join(self.appointment_types.keys())}"
                }
            
            # Find available slot
            slot = await self._find_available_slot(
                preferred_date,
                preferred_time,
                appointment_type,
                provider_id
            )
            
            if not slot:
                # Suggest alternatives
                alternatives = await self._suggest_alternative_slots(
                    preferred_date,
                    appointment_type,
                    provider_id
                )
                
                return {
                    'success': False,
                    'message': 'Requested time not available',
                    'alternatives': alternatives
                }
            
            # Create appointment in FHIR
            appointment_data = {
                'status': 'booked',
                'appointmentType': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/v2-0276',
                        'code': appointment_type,
                        'display': self.appointment_types[appointment_type]['description']
                    }]
                },
                'description': self.phi_redactor.redact_string(reason) if reason else None,
                'start': f"{slot.date}T{slot.time}:00",
                'end': self._calculate_end_time(slot.date, slot.time, slot.duration_minutes),
                'participant': [
                    {
                        'actor': {'reference': f"Patient/{patient_id}"},
                        'required': 'required',
                        'status': 'accepted'
                    }
                ]
            }
            
            if provider_id:
                appointment_data['participant'].append({
                    'actor': {'reference': f"Practitioner/{provider_id}"},
                    'required': 'required',
                    'status': 'needs-action'
                })
            
            # Create appointment
            result = await self.fhir.create_appointment(appointment_data)
            
            # Log successful booking
            self.audit_logger.log_event(
                'appointment_booked',
                appointment_id=result['id'],
                patient_id=patient_id,
                appointment_type=appointment_type,
                date=slot.date,
                time=slot.time
            )
            
            return {
                'success': True,
                'message': f"Appointment confirmed for {slot.date} at {slot.time}",
                'appointment_id': result['id'],
                'confirmation_code': result['id'][:8].upper(),
                'details': {
                    'date': slot.date,
                    'time': slot.time,
                    'type': self.appointment_types[appointment_type]['description'],
                    'duration': slot.duration_minutes,
                    'provider': slot.provider
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to book appointment: {e}")
            return {
                'success': False,
                'message': 'Unable to book appointment at this time. Please try again.'
            }
    
    async def cancel_appointment(self, appointment_id: str, 
                                reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Cancel an appointment
        
        Args:
            appointment_id: Appointment identifier
            reason: Cancellation reason
            
        Returns:
            Cancellation result
        """
        try:
            # Update appointment status
            result = await self.fhir.update_appointment_status(appointment_id, 'cancelled')
            
            # Create communication record for cancellation
            if reason:
                communication_data = {
                    'status': 'completed',
                    'category': [{
                        'coding': [{
                            'system': 'http://terminology.hl7.org/CodeSystem/communication-category',
                            'code': 'notification'
                        }]
                    }],
                    'priority': 'routine',
                    'topic': {'text': 'Appointment Cancellation'},
                    'payload': [{
                        'contentString': f"Appointment cancelled. Reason: {self.phi_redactor.redact_string(reason)}"
                    }]
                }
                
                await self.fhir.create_communication(communication_data)
            
            # Log cancellation
            self.audit_logger.log_event(
                'appointment_cancelled',
                appointment_id=appointment_id,
                reason='patient_requested'
            )
            
            return {
                'success': True,
                'message': 'Appointment has been cancelled',
                'appointment_id': appointment_id
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel appointment: {e}")
            return {
                'success': False,
                'message': 'Unable to cancel appointment. Please try again.'
            }
    
    async def check_lab_results(self, patient_id: str, 
                               test_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Check lab results for a patient
        
        Args:
            patient_id: Patient identifier
            test_name: Specific test to check
            
        Returns:
            Lab results summary (following disclosure policies)
        """
        try:
            # Get recent observations
            observations = await self.fhir.get_observations(
                patient_id,
                category='laboratory',
                date=f"ge{(datetime.utcnow() - timedelta(days=30)).date().isoformat()}"
            )
            
            if not observations.get('entry'):
                return {
                    'success': True,
                    'has_results': False,
                    'message': 'No recent lab results available'
                }
            
            # Process results (following normal/abnormal policy)
            results_summary = []
            has_abnormal = False
            
            for entry in observations['entry']:
                observation = entry['resource']
                
                # Check if result is normal
                interpretation = observation.get('interpretation', [])
                is_normal = any(
                    coding.get('code') == 'N' 
                    for interp in interpretation 
                    for coding in interp.get('coding', [])
                )
                
                if not is_normal:
                    has_abnormal = True
                
                result_info = {
                    'test': observation.get('code', {}).get('text', 'Unknown test'),
                    'date': observation.get('effectiveDateTime', 'Unknown date'),
                    'status': 'normal' if is_normal else 'requires_review'
                }
                
                # Only include value for normal results
                if is_normal and observation.get('valueQuantity'):
                    result_info['value'] = f"{observation['valueQuantity'].get('value')} {observation['valueQuantity'].get('unit', '')}"
                
                results_summary.append(result_info)
            
            # Prepare response based on policy
            if has_abnormal:
                # Don't disclose abnormal values over phone
                return {
                    'success': True,
                    'has_results': True,
                    'requires_provider_review': True,
                    'message': 'Some results require provider review. Please schedule an appointment.',
                    'action_required': 'schedule_appointment'
                }
            else:
                # Can share normal results
                return {
                    'success': True,
                    'has_results': True,
                    'all_normal': True,
                    'message': 'All recent lab results are within normal limits',
                    'results': results_summary
                }
                
        except Exception as e:
            logger.error(f"Failed to check lab results: {e}")
            return {
                'success': False,
                'message': 'Unable to access lab results at this time'
            }
    
    async def request_prescription_refill(self,
                                         patient_id: str,
                                         medication_name: str,
                                         pharmacy: Optional[str] = None) -> Dict[str, Any]:
        """
        Request prescription refill (non-controlled substances only)
        
        Args:
            patient_id: Patient identifier
            medication_name: Name of medication
            pharmacy: Preferred pharmacy
            
        Returns:
            Refill request result
        """
        try:
            # Get active medications
            medications = await self.fhir.get_medication_requests(patient_id, status='active')
            
            # Find matching medication
            target_med = None
            for entry in medications.get('entry', []):
                med_request = entry['resource']
                med_text = med_request.get('medicationCodeableConcept', {}).get('text', '')
                
                if medication_name.lower() in med_text.lower():
                    target_med = med_request
                    break
            
            if not target_med:
                return {
                    'success': False,
                    'message': f"No active prescription found for {medication_name}"
                }
            
            # Check if controlled substance (simplified check)
            is_controlled = self._is_controlled_substance(medication_name)
            
            if is_controlled:
                return {
                    'success': False,
                    'message': 'Controlled substances require provider approval. Please schedule an appointment.',
                    'action_required': 'schedule_appointment'
                }
            
            # Check refills remaining
            dispense_request = target_med.get('dispenseRequest', {})
            refills_remaining = dispense_request.get('numberOfRepeatsAllowed', 0)
            
            if refills_remaining <= 0:
                return {
                    'success': False,
                    'message': 'No refills remaining. Provider review required.',
                    'action_required': 'provider_review'
                }
            
            # Create refill task
            task_data = {
                'status': 'requested',
                'intent': 'order',
                'priority': 'routine',
                'code': {
                    'coding': [{
                        'system': 'http://hl7.org/fhir/CodeSystem/task-code',
                        'code': 'refill-request'
                    }],
                    'text': 'Prescription Refill Request'
                },
                'description': f"Refill request for {medication_name}",
                'for': {'reference': f"Patient/{patient_id}"},
                'input': [
                    {
                        'type': {'text': 'Medication'},
                        'valueString': medication_name
                    },
                    {
                        'type': {'text': 'Original Prescription'},
                        'valueReference': {'reference': f"MedicationRequest/{target_med['id']}"}
                    }
                ]
            }
            
            if pharmacy:
                task_data['input'].append({
                    'type': {'text': 'Pharmacy'},
                    'valueString': pharmacy
                })
            
            result = await self.fhir.create_task(task_data)
            
            # Log refill request
            self.audit_logger.log_event(
                'refill_requested',
                patient_id=patient_id,
                medication=medication_name,
                task_id=result['id']
            )
            
            return {
                'success': True,
                'message': f"Refill request submitted for {medication_name}. Processing within 24-48 hours.",
                'reference_number': result['id'][:8].upper(),
                'estimated_ready': (datetime.utcnow() + timedelta(days=2)).strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Failed to request refill: {e}")
            return {
                'success': False,
                'message': 'Unable to process refill request. Please try again.'
            }
    
    async def leave_message_for_provider(self,
                                        patient_id: str,
                                        provider_name: Optional[str],
                                        message: str,
                                        urgency: str = 'routine') -> Dict[str, Any]:
        """
        Leave a message for healthcare provider
        
        Args:
            patient_id: Patient identifier
            provider_name: Target provider name
            message: Message content
            urgency: Message urgency (routine, urgent)
            
        Returns:
            Message submission result
        """
        try:
            # Redact PHI from message
            redacted_message = self.phi_redactor.redact_string(message)
            
            # Create communication resource
            communication_data = {
                'status': 'completed',
                'category': [{
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/communication-category',
                        'code': 'instruction'
                    }]
                }],
                'priority': urgency,
                'subject': {'reference': f"Patient/{patient_id}"},
                'topic': {'text': f"Message for {provider_name or 'Provider'}"},
                'payload': [{
                    'contentString': redacted_message
                }],
                'sent': datetime.utcnow().isoformat()
            }
            
            if provider_name:
                communication_data['recipient'] = [{'display': provider_name}]
            
            result = await self.fhir.create_communication(communication_data)
            
            # Create task for provider review
            task_data = {
                'status': 'requested',
                'intent': 'order',
                'priority': urgency,
                'code': {
                    'text': 'Provider Message Review'
                },
                'description': f"Patient message requires review",
                'for': {'reference': f"Patient/{patient_id}"},
                'focus': {'reference': f"Communication/{result['id']}"}
            }
            
            task_result = await self.fhir.create_task(task_data)
            
            # Log message creation
            self.audit_logger.log_event(
                'provider_message_created',
                patient_id=patient_id,
                communication_id=result['id'],
                task_id=task_result['id'],
                urgency=urgency
            )
            
            # Determine response based on urgency
            if urgency == 'urgent':
                response_time = "within 4 hours during business hours"
            else:
                response_time = "within 1-2 business days"
            
            return {
                'success': True,
                'message': f"Message recorded. Provider will respond {response_time}.",
                'reference_number': result['id'][:8].upper()
            }
            
        except Exception as e:
            logger.error(f"Failed to leave message: {e}")
            return {
                'success': False,
                'message': 'Unable to record message. Please try again.'
            }
    
    async def get_office_information(self, info_type: str) -> Dict[str, Any]:
        """
        Get general office information
        
        Args:
            info_type: Type of information (hours, location, services, etc.)
            
        Returns:
            Requested information
        """
        info_map = {
            'hours': {
                'monday_friday': '8:00 AM - 5:00 PM',
                'saturday': 'Closed',
                'sunday': 'Closed',
                'holidays': 'Closed on major holidays'
            },
            'location': {
                'address': os.getenv('OFFICE_ADDRESS', '123 Medical Center Dr'),
                'city': os.getenv('OFFICE_CITY', 'Louisville'),
                'state': 'KY',
                'zip': os.getenv('OFFICE_ZIP', '40202'),
                'phone': os.getenv('OFFICE_PHONE', '502-555-0100')
            },
            'services': [
                'Primary Care',
                'Annual Physicals',
                'Preventive Care',
                'Chronic Disease Management',
                'Minor Procedures',
                'Lab Services',
                'Telehealth Visits'
            ],
            'insurance': [
                'Medicare',
                'Medicaid',
                'Most major insurance plans',
                'Please call to verify specific coverage'
            ],
            'emergency': {
                'message': 'For medical emergencies, hang up and dial 911',
                'after_hours': 'For urgent after-hours needs, call our on-call service',
                'nearest_er': 'Nearest ER: University Hospital, 530 S Jackson St'
            }
        }
        
        if info_type in info_map:
            return {
                'success': True,
                'info_type': info_type,
                'data': info_map[info_type]
            }
        else:
            return {
                'success': False,
                'message': f"Unknown information type: {info_type}",
                'available_types': list(info_map.keys())
            }
    
    async def _find_available_slot(self,
                                  date_str: str,
                                  time_str: Optional[str],
                                  appointment_type: str,
                                  provider_id: Optional[str]) -> Optional[AppointmentSlot]:
        """
        Find available appointment slot
        
        Args:
            date_str: Date to check
            time_str: Preferred time
            appointment_type: Type of appointment
            provider_id: Specific provider
            
        Returns:
            Available slot or None
        """
        # Parse date
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return None
        
        # Check if date is valid (not in past, not weekend for now)
        if target_date < datetime.utcnow().date():
            return None
        
        if target_date.weekday() not in self.business_hours['days']:
            return None
        
        # Get appointment duration
        duration = self.appointment_types[appointment_type]['duration']
        
        # If specific time requested, check availability
        if time_str:
            try:
                target_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                return None
            
            # Check if time is within business hours
            if not (self.business_hours['start'] <= target_time <= self.business_hours['end']):
                return None
            
            # Check for conflicts (simplified - would query actual schedule)
            if await self._is_slot_available(target_date, target_time, duration, provider_id):
                return AppointmentSlot(
                    date=date_str,
                    time=time_str,
                    provider=provider_id,
                    type=appointment_type,
                    duration_minutes=duration
                )
        else:
            # Find next available slot
            slots = await self._get_available_slots(target_date, appointment_type, provider_id)
            if slots:
                return slots[0]
        
        return None
    
    async def _is_slot_available(self, date: datetime.date, 
                                time: datetime.time,
                                duration: int,
                                provider_id: Optional[str]) -> bool:
        """
        Check if specific slot is available
        
        Args:
            date: Date to check
            time: Time to check
            duration: Appointment duration in minutes
            provider_id: Provider to check
            
        Returns:
            True if slot is available
        """
        # Query existing appointments
        start_datetime = datetime.combine(date, time)
        end_datetime = start_datetime + timedelta(minutes=duration)
        
        # Search for conflicting appointments
        params = {
            'date': f"ge{start_datetime.isoformat()}",
            'date': f"le{end_datetime.isoformat()}",
            'status': 'booked,pending,proposed'
        }
        
        if provider_id:
            params['practitioner'] = f"Practitioner/{provider_id}"
        
        conflicts = await self.fhir.search_appointments(**params)
        
        return len(conflicts.get('entry', [])) == 0
    
    async def _get_available_slots(self, date: datetime.date,
                                  appointment_type: str,
                                  provider_id: Optional[str],
                                  max_slots: int = 5) -> List[AppointmentSlot]:
        """
        Get available slots for a date
        
        Args:
            date: Date to check
            appointment_type: Type of appointment
            provider_id: Specific provider
            max_slots: Maximum slots to return
            
        Returns:
            List of available slots
        """
        slots = []
        duration = self.appointment_types[appointment_type]['duration']
        
        # Generate time slots (every 30 minutes for simplicity)
        current_time = self.business_hours['start']
        end_time = self.business_hours['end']
        
        while current_time < end_time and len(slots) < max_slots:
            if await self._is_slot_available(date, current_time, duration, provider_id):
                slots.append(AppointmentSlot(
                    date=date.isoformat(),
                    time=current_time.strftime('%H:%M'),
                    provider=provider_id,
                    type=appointment_type,
                    duration_minutes=duration
                ))
            
            # Move to next slot
            current_datetime = datetime.combine(date, current_time)
            current_datetime += timedelta(minutes=30)
            current_time = current_datetime.time()
        
        return slots
    
    async def _suggest_alternative_slots(self, preferred_date: str,
                                        appointment_type: str,
                                        provider_id: Optional[str],
                                        days_to_check: int = 7) -> List[Dict[str, Any]]:
        """
        Suggest alternative appointment slots
        
        Args:
            preferred_date: Originally requested date
            appointment_type: Type of appointment
            provider_id: Specific provider
            days_to_check: Number of days to check
            
        Returns:
            List of alternative slots
        """
        alternatives = []
        
        try:
            start_date = datetime.strptime(preferred_date, '%Y-%m-%d').date()
        except ValueError:
            start_date = datetime.utcnow().date()
        
        for days_offset in range(1, days_to_check + 1):
            check_date = start_date + timedelta(days=days_offset)
            
            # Skip weekends
            if check_date.weekday() not in self.business_hours['days']:
                continue
            
            slots = await self._get_available_slots(
                check_date,
                appointment_type,
                provider_id,
                max_slots=2
            )
            
            for slot in slots:
                alternatives.append({
                    'date': slot.date,
                    'time': slot.time,
                    'day_name': check_date.strftime('%A')
                })
            
            if len(alternatives) >= 3:
                break
        
        return alternatives
    
    def _is_controlled_substance(self, medication_name: str) -> bool:
        """
        Check if medication is a controlled substance
        
        Args:
            medication_name: Name of medication
            
        Returns:
            True if controlled substance
        """
        # Simplified check - in production, use proper drug database
        controlled_keywords = [
            'oxycodone', 'hydrocodone', 'morphine', 'fentanyl',
            'adderall', 'ritalin', 'xanax', 'valium', 'ativan',
            'ambien', 'tramadol', 'codeine'
        ]
        
        med_lower = medication_name.lower()
        return any(keyword in med_lower for keyword in controlled_keywords)
    
    def _calculate_end_time(self, date_str: str, time_str: str, 
                          duration_minutes: int) -> str:
        """
        Calculate appointment end time
        
        Args:
            date_str: Date string
            time_str: Start time string
            duration_minutes: Duration in minutes
            
        Returns:
            End time in ISO format
        """
        start = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        end = start + timedelta(minutes=duration_minutes)
        return end.isoformat()


import os  # Add this import at the top of the file
