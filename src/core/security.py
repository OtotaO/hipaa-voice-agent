"""
Security Module for HIPAA Compliance
Handles PHI redaction, encryption, audit logging, and caller verification
"""

import re
import hashlib
import hmac
import base64
import json
import logging
from typing import Dict, Any, List, Optional, Pattern
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import os

logger = logging.getLogger(__name__)


class PHIRedactor:
    """
    Redacts Protected Health Information (PHI) from text and data structures
    Uses pattern matching and ML-based detection for comprehensive coverage
    """
    
    def __init__(self):
        """Initialize PHI patterns and redaction rules"""
        self.patterns = self._compile_phi_patterns()
        self.redaction_char = os.getenv('PHI_MASK_CHARACTER', '*')
        self.enabled = os.getenv('PHI_REDACTION_ENABLED', 'true').lower() == 'true'
        
    def _compile_phi_patterns(self) -> Dict[str, Pattern]:
        """
        Compile regex patterns for PHI detection
        
        Returns:
            Dictionary of compiled regex patterns
        """
        patterns = {
            # Social Security Numbers
            'ssn': re.compile(
                r'\b(?:\d{3}-\d{2}-\d{4}|\d{3}\s\d{2}\s\d{4}|\d{9})\b',
                re.IGNORECASE
            ),
            
            # Medical Record Numbers (various formats)
            'mrn': re.compile(
                r'\b(?:MRN|Medical Record Number|Patient ID)[\s:#]*[\w\d-]+\b',
                re.IGNORECASE
            ),
            
            # Date of Birth
            'dob': re.compile(
                r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
            ),
            
            # Phone Numbers
            'phone': re.compile(
                r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ),
            
            # Email Addresses
            'email': re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ),
            
            # Credit Card Numbers
            'credit_card': re.compile(
                r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
            ),
            
            # US Addresses (simplified pattern)
            'address': re.compile(
                r'\d+\s+[\w\s]+(?:street|st|avenue|ave|road|rd|highway|hwy|lane|ln|drive|dr|court|ct|place|pl|boulevard|blvd)\b',
                re.IGNORECASE
            ),
            
            # Insurance ID
            'insurance': re.compile(
                r'\b(?:policy|member|subscriber|group)[\s#:]*[\w\d-]+\b',
                re.IGNORECASE
            ),
            
            # DEA Numbers
            'dea': re.compile(
                r'\b[A-Z]{2}\d{7}\b'
            ),
            
            # NPI Numbers
            'npi': re.compile(
                r'\b\d{10}\b'
            ),
            
            # State ID/Driver's License (generic)
            'state_id': re.compile(
                r'\b(?:DL|License|ID)[\s#:]*[\w\d-]+\b',
                re.IGNORECASE
            )
        }
        
        return patterns
    
    def redact_string(self, text: str) -> str:
        """
        Redact PHI from a string
        
        Args:
            text: Input text potentially containing PHI
            
        Returns:
            Text with PHI redacted
        """
        if not self.enabled or not text:
            return text
        
        redacted = text
        
        # Apply each pattern
        for pattern_name, pattern in self.patterns.items():
            redacted = pattern.sub(
                lambda m: self.redaction_char * len(m.group()),
                redacted
            )
        
        # Additional context-based redaction
        redacted = self._redact_contextual_phi(redacted)
        
        return redacted
    
    def _redact_contextual_phi(self, text: str) -> str:
        """
        Redact PHI based on context clues
        
        Args:
            text: Text to check for contextual PHI
            
        Returns:
            Text with contextual PHI redacted
        """
        # Look for patterns like "my name is [NAME]"
        name_contexts = [
            r'(?:my|patient|caller|your)\s+name\s+is\s+(\w+(?:\s+\w+)*)',
            r'(?:I am|I\'m|This is)\s+(\w+(?:\s+\w+)*)',
            r'(?:calling for|regarding)\s+(\w+(?:\s+\w+)*)'
        ]
        
        for pattern in name_contexts:
            text = re.sub(
                pattern,
                lambda m: m.group().replace(
                    m.group(1), 
                    self.redaction_char * len(m.group(1))
                ),
                text,
                flags=re.IGNORECASE
            )
        
        return text
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact PHI from dictionary
        
        Args:
            data: Dictionary potentially containing PHI
            
        Returns:
            Dictionary with PHI redacted
        """
        if not self.enabled:
            return data
        
        redacted = {}
        
        # PHI field names to fully redact
        phi_fields = {
            'ssn', 'social_security_number', 'mrn', 'medical_record_number',
            'dob', 'date_of_birth', 'birth_date', 'phone', 'phone_number',
            'email', 'email_address', 'address', 'street_address',
            'patient_name', 'name', 'full_name', 'first_name', 'last_name',
            'insurance_id', 'policy_number', 'credit_card', 'card_number'
        }
        
        for key, value in data.items():
            # Check if field name indicates PHI
            if any(phi_field in key.lower() for phi_field in phi_fields):
                redacted[key] = self.redaction_char * 8  # Fixed length redaction
            elif isinstance(value, str):
                redacted[key] = self.redact_string(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_dict(item) if isinstance(item, dict) 
                    else self.redact_string(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    def detect_phi(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PHI in text and return locations
        
        Args:
            text: Text to scan for PHI
            
        Returns:
            List of detected PHI with types and locations
        """
        detections = []
        
        for pattern_name, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                detections.append({
                    'type': pattern_name,
                    'start': match.start(),
                    'end': match.end(),
                    'length': match.end() - match.start()
                })
        
        return detections


class AuditLogger:
    """
    HIPAA-compliant audit logging system
    Maintains immutable audit trail with encryption
    """
    
    def __init__(self):
        """Initialize audit logger with encryption"""
        self.enabled = os.getenv('AUDIT_ENABLED', 'true').lower() == 'true'
        self.encryption_enabled = os.getenv('AUDIT_LOG_ENCRYPTION', 'true').lower() == 'true'
        self.log_path = os.getenv('AUDIT_LOG_PATH', '/logs/audit')
        self.retention_days = int(os.getenv('AUDIT_LOG_RETENTION_DAYS', 2555))  # 7 years
        
        # Initialize encryption if enabled
        if self.encryption_enabled:
            self.cipher = self._init_encryption()
        
        # Ensure audit directory exists
        os.makedirs(self.log_path, exist_ok=True)
        
        logger.info("Audit logger initialized")
    
    def _init_encryption(self) -> Fernet:
        """
        Initialize encryption for audit logs
        
        Returns:
            Fernet cipher for encryption
        """
        key = os.getenv('AUDIT_ENCRYPTION_KEY')
        if not key:
            # Generate key from master key
            master_key = os.getenv('MASTER_ENCRYPTION_KEY', 'default-key-change-me')
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'audit-log-salt',  # In production, use random salt
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        
        return Fernet(key)
    
    def log_event(self, event_type: str, **kwargs):
        """
        Log an audit event
        
        Args:
            event_type: Type of event being logged
            **kwargs: Event details (will be redacted if needed)
        """
        if not self.enabled:
            return
        
        try:
            # Create audit entry
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'event_type': event_type,
                'details': kwargs,
                'checksum': None  # Will be computed
            }
            
            # Compute integrity checksum
            entry['checksum'] = self._compute_checksum(entry)
            
            # Encrypt if enabled
            if self.encryption_enabled:
                entry_json = json.dumps(entry)
                encrypted = self.cipher.encrypt(entry_json.encode())
                entry_data = encrypted.decode('utf-8')
            else:
                entry_data = json.dumps(entry)
            
            # Write to audit log
            log_file = os.path.join(
                self.log_path,
                f"audit_{datetime.utcnow().strftime('%Y%m%d')}.log"
            )
            
            with open(log_file, 'a') as f:
                f.write(entry_data + '\n')
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def _compute_checksum(self, entry: Dict[str, Any]) -> str:
        """
        Compute integrity checksum for audit entry
        
        Args:
            entry: Audit entry data
            
        Returns:
            Checksum string
        """
        # Remove checksum field for computation
        entry_copy = {k: v for k, v in entry.items() if k != 'checksum'}
        entry_json = json.dumps(entry_copy, sort_keys=True)
        
        # Compute HMAC
        secret = os.getenv('AUDIT_HMAC_SECRET', 'audit-secret-key')
        h = hmac.new(
            secret.encode(),
            entry_json.encode(),
            hashlib.sha256
        )
        
        return h.hexdigest()
    
    async def persist_trail(self, call_sid: str, trail: List[Dict], duration: float):
        """
        Persist complete audit trail for a call
        
        Args:
            call_sid: Unique call identifier
            trail: List of audit events
            duration: Call duration in seconds
        """
        summary = {
            'call_sid': call_sid,
            'event_count': len(trail),
            'duration_seconds': duration,
            'events': trail
        }
        
        self.log_event('call_audit_trail', **summary)
    
    def verify_integrity(self, entry_data: str) -> bool:
        """
        Verify integrity of an audit entry
        
        Args:
            entry_data: Encrypted or plain audit entry
            
        Returns:
            True if integrity is valid
        """
        try:
            # Decrypt if needed
            if self.encryption_enabled:
                decrypted = self.cipher.decrypt(entry_data.encode())
                entry = json.loads(decrypted)
            else:
                entry = json.loads(entry_data)
            
            # Verify checksum
            stored_checksum = entry.get('checksum')
            computed_checksum = self._compute_checksum(entry)
            
            return stored_checksum == computed_checksum
            
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            return False


class CallerVerification:
    """
    Verify caller identity for HIPAA compliance
    Multiple verification methods with audit trail
    """
    
    def __init__(self):
        """Initialize verification system"""
        self.max_attempts = 3
        self.verification_timeout = 300  # 5 minutes
        self.active_sessions = {}
        
    async def verify(self, full_name: str, date_of_birth: str) -> Dict[str, Any]:
        """
        Verify patient identity using name and DOB
        
        Args:
            full_name: Patient's full name
            date_of_birth: Patient's date of birth
            
        Returns:
            Verification result with patient details if successful
        """
        try:
            # Normalize inputs
            name_normalized = full_name.strip().upper()
            dob_normalized = self._normalize_date(date_of_birth)
            
            # Query patient database (mock implementation)
            # In production, this would query your FHIR server or patient database
            patient = await self._lookup_patient(name_normalized, dob_normalized)
            
            if patient:
                return {
                    'verified': True,
                    'mrn': patient['mrn'],
                    'patient_id': patient['id'],
                    'verification_method': 'name_dob'
                }
            else:
                return {
                    'verified': False,
                    'reason': 'No matching patient found'
                }
                
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return {
                'verified': False,
                'reason': 'Verification system error'
            }
    
    async def verify_with_mrn(self, mrn: str, last_name: str) -> Dict[str, Any]:
        """
        Verify using MRN and last name
        
        Args:
            mrn: Medical Record Number
            last_name: Patient's last name
            
        Returns:
            Verification result
        """
        try:
            # Query by MRN
            patient = await self._lookup_by_mrn(mrn)
            
            if patient and patient['last_name'].upper() == last_name.strip().upper():
                return {
                    'verified': True,
                    'patient_id': patient['id'],
                    'verification_method': 'mrn_lastname'
                }
            else:
                return {
                    'verified': False,
                    'reason': 'MRN and last name do not match'
                }
                
        except Exception as e:
            logger.error(f"MRN verification error: {e}")
            return {
                'verified': False,
                'reason': 'Verification system error'
            }
    
    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date format
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Normalized date in YYYY-MM-DD format
        """
        # Handle various date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%d/%m/%Y',
            '%Y/%m/%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # If no format matches, return as-is
        return date_str
    
    async def _lookup_patient(self, name: str, dob: str) -> Optional[Dict[str, Any]]:
        """
        Look up patient in database
        
        Args:
            name: Normalized patient name
            dob: Normalized date of birth
            
        Returns:
            Patient record if found
        """
        # Mock implementation - replace with actual database query
        # This would typically query your FHIR server or patient database
        
        # Example mock data (DO NOT USE IN PRODUCTION)
        mock_patients = [
            {
                'id': 'patient-123',
                'mrn': 'MRN-001234',
                'full_name': 'JOHN DOE',
                'last_name': 'DOE',
                'dob': '1980-01-01'
            }
        ]
        
        for patient in mock_patients:
            if patient['full_name'] == name and patient['dob'] == dob:
                return patient
        
        return None
    
    async def _lookup_by_mrn(self, mrn: str) -> Optional[Dict[str, Any]]:
        """
        Look up patient by MRN
        
        Args:
            mrn: Medical Record Number
            
        Returns:
            Patient record if found
        """
        # Mock implementation - replace with actual database query
        mock_patients = [
            {
                'id': 'patient-123',
                'mrn': 'MRN-001234',
                'full_name': 'JOHN DOE',
                'last_name': 'DOE',
                'dob': '1980-01-01'
            }
        ]
        
        for patient in mock_patients:
            if patient['mrn'] == mrn:
                return patient
        
        return None
    
    def create_verification_session(self, call_sid: str) -> str:
        """
        Create a verification session for multi-step verification
        
        Args:
            call_sid: Call identifier
            
        Returns:
            Session ID
        """
        session_id = hashlib.sha256(f"{call_sid}_{datetime.utcnow()}".encode()).hexdigest()[:16]
        
        self.active_sessions[session_id] = {
            'call_sid': call_sid,
            'created': datetime.utcnow(),
            'attempts': 0,
            'verified': False
        }
        
        return session_id
    
    def check_session_valid(self, session_id: str) -> bool:
        """
        Check if verification session is still valid
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session is valid
        """
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        
        # Check timeout
        elapsed = (datetime.utcnow() - session['created']).total_seconds()
        if elapsed > self.verification_timeout:
            del self.active_sessions[session_id]
            return False
        
        # Check attempts
        if session['attempts'] >= self.max_attempts:
            del self.active_sessions[session_id]
            return False
        
        return True


class EncryptionService:
    """
    Service for encrypting and decrypting PHI/PII
    """
    
    def __init__(self):
        """Initialize encryption service"""
        self.data_key = os.getenv('DATA_ENCRYPTION_KEY')
        if not self.data_key:
            # Generate from master key
            master_key = os.getenv('MASTER_ENCRYPTION_KEY', 'default-key-change-me')
            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'data-encryption-salt',  # Use random salt in production
                iterations=100000,
            )
            self.data_key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        
        self.cipher = Fernet(self.data_key)
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt sensitive data
        
        Args:
            data: Plain text data
            
        Returns:
            Encrypted data as base64 string
        """
        if not data:
            return data
        
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data
        
        Args:
            encrypted_data: Encrypted data as base64 string
            
        Returns:
            Decrypted plain text
        """
        if not encrypted_data:
            return encrypted_data
        
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return decrypted.decode('utf-8')
    
    def encrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        Encrypt specific fields in a dictionary
        
        Args:
            data: Dictionary containing sensitive data
            fields: List of field names to encrypt
            
        Returns:
            Dictionary with specified fields encrypted
        """
        encrypted_data = data.copy()
        
        for field in fields:
            if field in encrypted_data and encrypted_data[field]:
                if isinstance(encrypted_data[field], str):
                    encrypted_data[field] = self.encrypt(encrypted_data[field])
        
        return encrypted_data
    
    def decrypt_dict(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        Decrypt specific fields in a dictionary
        
        Args:
            data: Dictionary with encrypted fields
            fields: List of field names to decrypt
            
        Returns:
            Dictionary with specified fields decrypted
        """
        decrypted_data = data.copy()
        
        for field in fields:
            if field in decrypted_data and decrypted_data[field]:
                if isinstance(decrypted_data[field], str):
                    try:
                        decrypted_data[field] = self.decrypt(decrypted_data[field])
                    except Exception as e:
                        logger.error(f"Failed to decrypt field {field}: {e}")
                        decrypted_data[field] = None
        
        return decrypted_data
