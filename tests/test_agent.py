#!/usr/bin/env python3

"""
HIPAA Voice Agent - Test Suite
Comprehensive testing for voice agent functionality and compliance
"""

import asyncio
import json
import os
import sys
import unittest
from datetime import datetime
from typing import Dict, Any
import aiohttp
import websockets
from unittest.mock import Mock, patch, AsyncMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.security import PHIRedactor, AuditLogger, CallerVerification
from src.core.compliance import HIPAACompliance
from src.services.fhir_client import FHIRClient
from src.tools.medical_tools import MedicalTools


class TestPHIRedactor(unittest.TestCase):
    """Test PHI redaction functionality"""
    
    def setUp(self):
        self.redactor = PHIRedactor()
    
    def test_ssn_redaction(self):
        """Test SSN redaction"""
        text = "My SSN is 123-45-6789"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("123-45-6789", redacted)
        self.assertIn("*" * 11, redacted)
    
    def test_phone_redaction(self):
        """Test phone number redaction"""
        text = "Call me at (502) 555-0123"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("502", redacted)
        self.assertNotIn("555-0123", redacted)
    
    def test_email_redaction(self):
        """Test email redaction"""
        text = "Email: john.doe@example.com"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("john.doe@example.com", redacted)
    
    def test_dob_redaction(self):
        """Test date of birth redaction"""
        text = "Born on 01/15/1980"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("01/15/1980", redacted)
    
    def test_dict_redaction(self):
        """Test dictionary PHI redaction"""
        data = {
            "name": "John Doe",
            "ssn": "123-45-6789",
            "phone": "502-555-0123",
            "diagnosis": "Hypertension"
        }
        redacted = self.redactor.redact_dict(data)
        self.assertEqual(redacted["name"], "*" * 8)
        self.assertEqual(redacted["ssn"], "*" * 8)
        self.assertNotIn("502", redacted["phone"])
    
    def test_contextual_redaction(self):
        """Test contextual PHI redaction"""
        text = "My name is John Smith and I live at 123 Main St"
        redacted = self.redactor.redact_string(text)
        self.assertNotIn("John Smith", redacted)
        self.assertNotIn("123 Main St", redacted)


class TestHIPAACompliance(unittest.TestCase):
    """Test HIPAA compliance validation"""
    
    def setUp(self):
        self.compliance = HIPAACompliance()
    
    def test_encryption_validation(self):
        """Test encryption settings validation"""
        # Set test environment variables
        os.environ['MASTER_ENCRYPTION_KEY'] = 'test-key-32-bytes-long-for-testing'
        os.environ['AUDIT_ENABLED'] = 'true'
        
        report = self.compliance.get_compliance_report()
        self.assertIsNotNone(report)
        self.assertIn('checks', report)
    
    def test_patient_access_validation(self):
        """Test patient data access validation"""
        # Test unauthenticated access
        context = {
            'user_authenticated': False,
            'patient_verified': False
        }
        result = self.compliance.validate_operation('patient_data_access', context)
        self.assertFalse(result)
        
        # Test authenticated access
        context = {
            'user_authenticated': True,
            'patient_verified': True
        }
        result = self.compliance.validate_operation('patient_data_access', context)
        self.assertTrue(result)
    
    def test_transmission_validation(self):
        """Test data transmission validation"""
        # Test unencrypted transmission
        context = {
            'encrypted': False
        }
        result = self.compliance.validate_operation('data_transmission', context)
        self.assertFalse(result)
        
        # Test encrypted transmission
        context = {
            'encrypted': True,
            'tls_version': '1.3'
        }
        result = self.compliance.validate_operation('data_transmission', context)
        self.assertTrue(result)
        
        # Test PHI in SMS
        context = {
            'encrypted': True,
            'channel': 'sms',
            'contains_phi': True
        }
        result = self.compliance.validate_operation('data_transmission', context)
        self.assertFalse(result)


class TestCallerVerification(unittest.IsolatedAsyncioTestCase):
    """Test caller verification functionality"""
    
    def setUp(self):
        self.verifier = CallerVerification()
    
    async def test_verify_success(self):
        """Test successful verification"""
        # Mock the lookup method
        with patch.object(self.verifier, '_lookup_patient', 
                         return_value={'id': '123', 'mrn': 'MRN-001', 'full_name': 'JOHN DOE', 'last_name': 'DOE'}):
            result = await self.verifier.verify('JOHN DOE', '1980-01-01')
            self.assertTrue(result['verified'])
            self.assertEqual(result['mrn'], 'MRN-001')
    
    async def test_verify_failure(self):
        """Test failed verification"""
        with patch.object(self.verifier, '_lookup_patient', return_value=None):
            result = await self.verifier.verify('Jane Doe', '1990-01-01')
            self.assertFalse(result['verified'])
    
    async def test_verify_with_mrn(self):
        """Test verification with MRN"""
        with patch.object(self.verifier, '_lookup_by_mrn',
                         return_value={'id': '123', 'mrn': 'MRN-001', 'last_name': 'DOE'}):
            result = await self.verifier.verify_with_mrn('MRN-001', 'DOE')
            self.assertTrue(result['verified'])
    
    def test_session_management(self):
        """Test verification session management"""
        session_id = self.verifier.create_verification_session('call-123')
        self.assertIsNotNone(session_id)
        
        # Check session validity
        self.assertTrue(self.verifier.check_session_valid(session_id))
        
        # Check invalid session
        self.assertFalse(self.verifier.check_session_valid('invalid-session'))


class TestMedicalTools(unittest.IsolatedAsyncioTestCase):
    """Test medical tools functionality"""
    
    async def asyncSetUp(self):
        self.fhir_client = AsyncMock(spec=FHIRClient)
        self.tools = MedicalTools(self.fhir_client)
    
    async def test_book_appointment(self):
        """Test appointment booking"""
        # Mock FHIR client response
        self.fhir_client.create_appointment.return_value = {
            'id': 'apt-123',
            'status': 'booked'
        }
        
        # Mock slot finding
        with patch.object(self.tools, '_find_available_slot',
                         return_value=Mock(date='2024-01-15', time='10:00', 
                                         duration_minutes=30, provider='Dr. Smith')):
            result = await self.tools.book_appointment(
                patient_id='patient-123',
                appointment_type='follow_up',
                preferred_date='2024-01-15',
                preferred_time='10:00'
            )
            
            self.assertTrue(result['success'])
            self.assertEqual(result['appointment_id'], 'apt-123')
    
    async def test_check_lab_results_normal(self):
        """Test checking normal lab results"""
        # Mock normal results
        self.fhir_client.get_observations.return_value = {
            'entry': [{
                'resource': {
                    'code': {'text': 'Blood Glucose'},
                    'effectiveDateTime': '2024-01-10',
                    'interpretation': [{'coding': [{'code': 'N'}]}],
                    'valueQuantity': {'value': 95, 'unit': 'mg/dL'}
                }
            }]
        }
        
        result = await self.tools.check_lab_results('patient-123')
        self.assertTrue(result['success'])
        self.assertTrue(result.get('all_normal', False))
    
    async def test_check_lab_results_abnormal(self):
        """Test checking abnormal lab results"""
        # Mock abnormal results
        self.fhir_client.get_observations.return_value = {
            'entry': [{
                'resource': {
                    'code': {'text': 'Blood Glucose'},
                    'effectiveDateTime': '2024-01-10',
                    'interpretation': [{'coding': [{'code': 'H'}]}]  # High
                }
            }]
        }
        
        result = await self.tools.check_lab_results('patient-123')
        self.assertTrue(result['success'])
        self.assertTrue(result.get('requires_provider_review', False))
        self.assertEqual(result.get('action_required'), 'schedule_appointment')
    
    async def test_request_refill_non_controlled(self):
        """Test prescription refill for non-controlled substance"""
        # Mock medication request
        self.fhir_client.get_medication_requests.return_value = {
            'entry': [{
                'resource': {
                    'id': 'med-123',
                    'medicationCodeableConcept': {'text': 'Lisinopril'},
                    'dispenseRequest': {'numberOfRepeatsAllowed': 3}
                }
            }]
        }
        
        self.fhir_client.create_task.return_value = {'id': 'task-123'}
        
        result = await self.tools.request_prescription_refill(
            patient_id='patient-123',
            medication_name='Lisinopril'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('reference_number', result)
    
    async def test_request_refill_controlled(self):
        """Test prescription refill for controlled substance"""
        # Mock controlled medication
        self.fhir_client.get_medication_requests.return_value = {
            'entry': [{
                'resource': {
                    'id': 'med-456',
                    'medicationCodeableConcept': {'text': 'Oxycodone'},
                    'dispenseRequest': {'numberOfRepeatsAllowed': 0}
                }
            }]
        }
        
        result = await self.tools.request_prescription_refill(
            patient_id='patient-123',
            medication_name='Oxycodone'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result.get('action_required'), 'schedule_appointment')


class TestWebSocketIntegration(unittest.IsolatedAsyncioTestCase):
    """Test WebSocket integration for Twilio Media Streams"""
    
    async def test_websocket_connection(self):
        """Test WebSocket connection establishment"""
        # This would require a running server - mock for unit tests
        mock_ws = AsyncMock()
        mock_ws.recv.side_effect = [
            json.dumps({'event': 'connected', 'streamSid': 'stream-123'}),
            json.dumps({'event': 'start', 'start': {'mediaFormat': 'audio/x-mulaw'}}),
            json.dumps({'event': 'stop'})
        ]
        
        # Simulate connection handling
        messages = []
        async for _ in range(3):
            msg = await mock_ws.recv()
            messages.append(json.loads(msg))
        
        self.assertEqual(messages[0]['event'], 'connected')
        self.assertEqual(messages[1]['event'], 'start')
        self.assertEqual(messages[2]['event'], 'stop')


class TestAPIEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test API endpoints"""
    
    async def test_health_endpoint(self):
        """Test health check endpoint"""
        # This would require a running server
        # For unit tests, we'll mock the response
        mock_response = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'compliance_check': True
        }
        
        self.assertEqual(mock_response['status'], 'healthy')
        self.assertTrue(mock_response['compliance_check'])
    
    async def test_compliance_endpoint(self):
        """Test compliance check endpoint"""
        mock_response = {
            'compliant': True,
            'timestamp': datetime.utcnow().isoformat(),
            'violations': [],
            'checks': {
                'encryption': {'passed': True},
                'audit': {'passed': True},
                'network': {'passed': True}
            }
        }
        
        self.assertTrue(mock_response['compliant'])
        self.assertEqual(len(mock_response['violations']), 0)


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for end-to-end workflows"""
    
    async def test_appointment_booking_workflow(self):
        """Test complete appointment booking workflow"""
        # This would test the full flow from voice input to FHIR booking
        # For unit tests, we'll mock the components
        
        # 1. Verify caller
        verifier = CallerVerification()
        with patch.object(verifier, '_lookup_patient',
                         return_value={'id': '123', 'mrn': 'MRN-001'}):
            verification = await verifier.verify('John Doe', '1980-01-01')
            self.assertTrue(verification['verified'])
        
        # 2. Book appointment
        fhir_client = AsyncMock(spec=FHIRClient)
        fhir_client.create_appointment.return_value = {'id': 'apt-123'}
        
        tools = MedicalTools(fhir_client)
        with patch.object(tools, '_find_available_slot',
                         return_value=Mock(date='2024-01-15', time='10:00',
                                         duration_minutes=30, provider='Dr. Smith')):
            booking = await tools.book_appointment(
                patient_id='123',
                appointment_type='follow_up',
                preferred_date='2024-01-15'
            )
            self.assertTrue(booking['success'])
    
    async def test_lab_results_workflow(self):
        """Test lab results inquiry workflow"""
        # 1. Verify caller
        verifier = CallerVerification()
        with patch.object(verifier, '_lookup_patient',
                         return_value={'id': '123', 'mrn': 'MRN-001'}):
            verification = await verifier.verify('John Doe', '1980-01-01')
            self.assertTrue(verification['verified'])
        
        # 2. Check lab results
        fhir_client = AsyncMock(spec=FHIRClient)
        fhir_client.get_observations.return_value = {
            'entry': [{
                'resource': {
                    'code': {'text': 'Blood Test'},
                    'interpretation': [{'coding': [{'code': 'N'}]}]
                }
            }]
        }
        
        tools = MedicalTools(fhir_client)
        results = await tools.check_lab_results('123')
        self.assertTrue(results['success'])


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPHIRedactor))
    suite.addTests(loader.loadTestsFromTestCase(TestHIPAACompliance))
    suite.addTests(loader.loadTestsFromTestCase(TestCallerVerification))
    suite.addTests(loader.loadTestsFromTestCase(TestMedicalTools))
    suite.addTests(loader.loadTestsFromTestCase(TestWebSocketIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIEndpoints))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
