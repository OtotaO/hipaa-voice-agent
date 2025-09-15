"""
HIPAA Compliance Module
Ensures all operations meet HIPAA technical safeguards
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ComplianceConfig:
    """HIPAA compliance configuration"""
    # Encryption requirements
    encryption_required: bool = True
    encryption_algorithm: str = "AES-256"
    
    # Audit requirements
    audit_enabled: bool = True
    audit_retention_years: int = 7
    
    # Access control
    session_timeout_minutes: int = 15
    max_login_attempts: int = 3
    password_complexity_required: bool = True
    mfa_required: bool = True
    
    # Data handling
    phi_redaction_enabled: bool = True
    data_minimization: bool = True
    
    # Transmission security
    tls_required: bool = True
    tls_min_version: str = "1.2"
    
    # Backup and recovery
    backup_encryption_required: bool = True
    backup_retention_days: int = 30
    
    # Business Associate Agreements
    baa_required_services: List[str] = None
    
    def __post_init__(self):
        if self.baa_required_services is None:
            self.baa_required_services = [
                'twilio', 'aws', 'azure', 'google_cloud'
            ]


class HIPAACompliance:
    """
    Central HIPAA compliance manager
    Validates and enforces HIPAA requirements across the system
    """
    
    def __init__(self, config: Optional[ComplianceConfig] = None):
        """
        Initialize HIPAA compliance manager
        
        Args:
            config: Compliance configuration
        """
        self.config = config or ComplianceConfig()
        self.violations = []
        self._validate_environment()
        
        logger.info("HIPAA Compliance manager initialized")
    
    def _validate_environment(self):
        """Validate environment meets HIPAA requirements"""
        validations = [
            self._check_encryption_settings(),
            self._check_audit_settings(),
            self._check_baa_configuration(),
            self._check_network_security(),
            self._check_access_controls(),
            self._check_data_retention()
        ]
        
        failed = [v for v in validations if not v['passed']]
        
        if failed:
            logger.warning(f"HIPAA validation warnings: {len(failed)} items need attention")
            for item in failed:
                logger.warning(f"- {item['check']}: {item['message']}")
    
    def _check_encryption_settings(self) -> Dict[str, Any]:
        """Validate encryption configuration"""
        passed = True
        messages = []
        
        # Check master encryption key
        if not os.getenv('MASTER_ENCRYPTION_KEY') or \
           os.getenv('MASTER_ENCRYPTION_KEY') == 'default-key-change-me':
            passed = False
            messages.append("Master encryption key not properly configured")
        
        # Check data encryption key
        if not os.getenv('DATA_ENCRYPTION_KEY'):
            messages.append("Data encryption key not set (will derive from master)")
        
        # Check TLS settings
        if os.getenv('PIPECAT_TLS_ENABLED', 'true').lower() != 'true':
            passed = False
            messages.append("TLS is not enabled for Pipecat")
        
        return {
            'check': 'Encryption Settings',
            'passed': passed,
            'message': '; '.join(messages) if messages else 'OK'
        }
    
    def _check_audit_settings(self) -> Dict[str, Any]:
        """Validate audit configuration"""
        passed = True
        messages = []
        
        if os.getenv('AUDIT_ENABLED', 'true').lower() != 'true':
            passed = False
            messages.append("Audit logging is disabled")
        
        retention_days = int(os.getenv('AUDIT_LOG_RETENTION_DAYS', 2555))
        if retention_days < 2555:  # 7 years in days
            passed = False
            messages.append(f"Audit retention ({retention_days} days) less than 7 years")
        
        if os.getenv('AUDIT_LOG_ENCRYPTION', 'true').lower() != 'true':
            passed = False
            messages.append("Audit log encryption is disabled")
        
        return {
            'check': 'Audit Settings',
            'passed': passed,
            'message': '; '.join(messages) if messages else 'OK'
        }
    
    def _check_baa_configuration(self) -> Dict[str, Any]:
        """Check Business Associate Agreement configuration"""
        messages = []
        
        # Check for required BAA configurations
        if not os.getenv('TWILIO_HIPAA_PROJECT_ID'):
            messages.append("Twilio HIPAA Project ID not configured")
        
        # Note: Can't actually verify BAAs are signed, just configuration
        messages.append("Ensure BAAs are executed with all service providers")
        
        return {
            'check': 'BAA Configuration',
            'passed': len(messages) <= 1,  # Only the reminder message
            'message': '; '.join(messages)
        }
    
    def _check_network_security(self) -> Dict[str, Any]:
        """Validate network security settings"""
        passed = True
        messages = []
        
        # Check Redis security
        if not os.getenv('REDIS_PASSWORD'):
            passed = False
            messages.append("Redis password not set")
        
        # Check PostgreSQL SSL
        if os.getenv('POSTGRES_SSL_MODE') != 'require':
            passed = False
            messages.append("PostgreSQL SSL not required")
        
        # Check API security
        if os.getenv('ENABLE_API_KEY_VALIDATION', 'true').lower() != 'true':
            passed = False
            messages.append("API key validation disabled")
        
        return {
            'check': 'Network Security',
            'passed': passed,
            'message': '; '.join(messages) if messages else 'OK'
        }
    
    def _check_access_controls(self) -> Dict[str, Any]:
        """Validate access control settings"""
        messages = []
        
        # Check session timeout
        timeout = int(os.getenv('PIPECAT_CONNECTION_TIMEOUT', 300))
        if timeout > 900:  # 15 minutes
            messages.append(f"Session timeout ({timeout}s) exceeds recommended 15 minutes")
        
        # Check JWT configuration
        if not os.getenv('JWT_SECRET'):
            messages.append("JWT secret not configured")
        
        return {
            'check': 'Access Controls',
            'passed': len(messages) == 0,
            'message': '; '.join(messages) if messages else 'OK'
        }
    
    def _check_data_retention(self) -> Dict[str, Any]:
        """Validate data retention policies"""
        messages = []
        
        # Check call recording settings
        if os.getenv('CALL_RECORDING_ENABLED', 'false').lower() == 'true':
            retention = int(os.getenv('CALL_RECORDING_RETENTION_DAYS', 7))
            if retention > 30:
                messages.append(f"Call recordings retained for {retention} days")
            
            if os.getenv('CALL_RECORDING_ENCRYPTION', 'true').lower() != 'true':
                messages.append("Call recordings not encrypted")
        
        # Check backup settings
        if os.getenv('BACKUP_ENCRYPTION', 'true').lower() != 'true':
            messages.append("Backups not encrypted")
        
        return {
            'check': 'Data Retention',
            'passed': len(messages) == 0,
            'message': '; '.join(messages) if messages else 'OK'
        }
    
    def validate_operation(self, operation: str, context: Dict[str, Any]) -> bool:
        """
        Validate an operation meets HIPAA requirements
        
        Args:
            operation: Operation being performed
            context: Operation context
            
        Returns:
            True if operation is compliant
        """
        validators = {
            'patient_data_access': self._validate_patient_access,
            'data_transmission': self._validate_transmission,
            'data_storage': self._validate_storage,
            'audit_access': self._validate_audit_access
        }
        
        validator = validators.get(operation)
        if validator:
            return validator(context)
        
        # Default to allowing if no specific validator
        return True
    
    def _validate_patient_access(self, context: Dict[str, Any]) -> bool:
        """
        Validate patient data access
        
        Args:
            context: Access context
            
        Returns:
            True if access is compliant
        """
        # Check user is authenticated
        if not context.get('user_authenticated'):
            self._add_violation('Unauthenticated patient data access attempt')
            return False
        
        # Check patient verification
        if not context.get('patient_verified'):
            self._add_violation('Patient data access without verification')
            return False
        
        # Check minimum necessary rule
        if context.get('bulk_access') and not context.get('bulk_justified'):
            self._add_violation('Bulk data access without justification')
            return False
        
        return True
    
    def _validate_transmission(self, context: Dict[str, Any]) -> bool:
        """
        Validate data transmission security
        
        Args:
            context: Transmission context
            
        Returns:
            True if transmission is compliant
        """
        # Check encryption
        if not context.get('encrypted'):
            self._add_violation('Unencrypted data transmission')
            return False
        
        # Check TLS version
        tls_version = context.get('tls_version', '')
        if tls_version and float(tls_version) < float(self.config.tls_min_version):
            self._add_violation(f'TLS version {tls_version} below minimum')
            return False
        
        # Check for PHI in insecure channels
        if context.get('channel') in ['sms', 'email'] and context.get('contains_phi'):
            self._add_violation('PHI transmitted via insecure channel')
            return False
        
        return True
    
    def _validate_storage(self, context: Dict[str, Any]) -> bool:
        """
        Validate data storage compliance
        
        Args:
            context: Storage context
            
        Returns:
            True if storage is compliant
        """
        # Check encryption at rest
        if not context.get('encrypted_at_rest'):
            self._add_violation('Data stored without encryption')
            return False
        
        # Check retention policy
        if context.get('indefinite_retention'):
            self._add_violation('No retention policy defined')
            return False
        
        return True
    
    def _validate_audit_access(self, context: Dict[str, Any]) -> bool:
        """
        Validate audit log access
        
        Args:
            context: Access context
            
        Returns:
            True if access is compliant
        """
        # Only authorized personnel should access audit logs
        if not context.get('authorized_auditor'):
            self._add_violation('Unauthorized audit log access')
            return False
        
        return True
    
    def _add_violation(self, violation: str):
        """
        Record a compliance violation
        
        Args:
            violation: Description of the violation
        """
        self.violations.append({
            'timestamp': datetime.utcnow().isoformat(),
            'violation': violation
        })
        logger.error(f"HIPAA Compliance Violation: {violation}")
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance status report
        
        Returns:
            Compliance report dictionary
        """
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'compliant': len(self.violations) == 0,
            'violations': self.violations,
            'checks': {
                'encryption': self._check_encryption_settings(),
                'audit': self._check_audit_settings(),
                'baa': self._check_baa_configuration(),
                'network': self._check_network_security(),
                'access': self._check_access_controls(),
                'retention': self._check_data_retention()
            }
        }
    
    def enforce_minimum_necessary(self, requested_fields: List[str], 
                                 context: Dict[str, Any]) -> List[str]:
        """
        Apply minimum necessary rule to data access
        
        Args:
            requested_fields: Fields requested
            context: Access context
            
        Returns:
            Filtered list of allowed fields
        """
        # Define sensitive fields
        sensitive_fields = {
            'ssn', 'full_ssn', 'credit_card', 'bank_account',
            'psychotherapy_notes', 'substance_abuse_records'
        }
        
        # Check if user has specific need for sensitive fields
        if not context.get('elevated_access'):
            requested_fields = [f for f in requested_fields 
                              if f not in sensitive_fields]
        
        # Log access for audit
        logger.info(f"Minimum necessary filter applied: {len(requested_fields)} fields allowed")
        
        return requested_fields
    
    def generate_breach_notification(self, breach_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate breach notification per HIPAA requirements
        
        Args:
            breach_details: Details of the breach
            
        Returns:
            Breach notification details
        """
        notification = {
            'breach_id': breach_details.get('id'),
            'discovered_date': datetime.utcnow().isoformat(),
            'affected_individuals': breach_details.get('affected_count', 0),
            'type_of_phi': breach_details.get('phi_types', []),
            'description': breach_details.get('description'),
            'mitigation_steps': breach_details.get('mitigation', []),
            'notification_required': {
                'individuals': breach_details.get('affected_count', 0) > 0,
                'hhs': breach_details.get('affected_count', 0) >= 500,
                'media': breach_details.get('affected_count', 0) >= 500,
                'timeline': '60 days' if breach_details.get('affected_count', 0) < 500 else 'immediately'
            }
        }
        
        # Log breach
        logger.critical(f"BREACH NOTIFICATION GENERATED: {notification['breach_id']}")
        
        return notification


class RiskAssessment:
    """
    HIPAA Security Risk Assessment
    Identifies and evaluates potential risks to PHI
    """
    
    def __init__(self):
        """Initialize risk assessment module"""
        self.risk_factors = []
        self.risk_score = 0
        self.last_assessment = None
    
    def assess_call_risk(self, call_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risk level for a specific call
        
        Args:
            call_context: Call details and context
            
        Returns:
            Risk assessment results
        """
        risks = []
        risk_level = 'low'
        
        # Check verification status
        if not call_context.get('caller_verified'):
            risks.append({
                'factor': 'unverified_caller',
                'severity': 'medium',
                'mitigation': 'Require identity verification'
            })
        
        # Check call duration
        duration = call_context.get('duration', 0)
        if duration > 1800:  # 30 minutes
            risks.append({
                'factor': 'extended_call',
                'severity': 'low',
                'mitigation': 'Consider call time limits'
            })
        
        # Check data access patterns
        if call_context.get('bulk_data_requested'):
            risks.append({
                'factor': 'bulk_data_access',
                'severity': 'high',
                'mitigation': 'Apply minimum necessary rule'
            })
        
        # Check time of call
        call_hour = datetime.fromisoformat(call_context.get('timestamp', datetime.utcnow().isoformat())).hour
        if call_hour < 6 or call_hour > 22:
            risks.append({
                'factor': 'unusual_hours',
                'severity': 'low',
                'mitigation': 'Flag for review'
            })
        
        # Determine overall risk level
        high_risks = [r for r in risks if r['severity'] == 'high']
        medium_risks = [r for r in risks if r['severity'] == 'medium']
        
        if high_risks:
            risk_level = 'high'
        elif len(medium_risks) >= 2:
            risk_level = 'medium'
        
        return {
            'risk_level': risk_level,
            'risk_factors': risks,
            'recommended_actions': [r['mitigation'] for r in risks],
            'assessment_timestamp': datetime.utcnow().isoformat()
        }
    
    def perform_system_assessment(self) -> Dict[str, Any]:
        """
        Perform comprehensive system risk assessment
        
        Returns:
            System risk assessment report
        """
        assessments = []
        
        # Physical safeguards
        assessments.append(self._assess_physical_safeguards())
        
        # Administrative safeguards
        assessments.append(self._assess_administrative_safeguards())
        
        # Technical safeguards
        assessments.append(self._assess_technical_safeguards())
        
        # Calculate overall risk score
        total_score = sum(a['score'] for a in assessments)
        max_score = len(assessments) * 100
        risk_percentage = (total_score / max_score) * 100
        
        self.risk_score = risk_percentage
        self.last_assessment = datetime.utcnow()
        
        return {
            'assessment_date': self.last_assessment.isoformat(),
            'overall_risk_score': risk_percentage,
            'risk_level': self._calculate_risk_level(risk_percentage),
            'categories': assessments,
            'recommendations': self._generate_recommendations(assessments)
        }
    
    def _assess_physical_safeguards(self) -> Dict[str, Any]:
        """Assess physical security measures"""
        score = 70  # Base score
        findings = []
        
        # Check if running in secure environment
        if os.getenv('ENVIRONMENT') != 'production':
            score -= 10
            findings.append('Not running in production environment')
        
        # Check backup encryption
        if os.getenv('BACKUP_ENCRYPTION', 'true').lower() != 'true':
            score -= 20
            findings.append('Backup encryption not enabled')
        
        return {
            'category': 'Physical Safeguards',
            'score': max(0, score),
            'findings': findings
        }
    
    def _assess_administrative_safeguards(self) -> Dict[str, Any]:
        """Assess administrative controls"""
        score = 80  # Base score
        findings = []
        
        # Check audit logging
        if os.getenv('AUDIT_ENABLED', 'true').lower() != 'true':
            score -= 30
            findings.append('Audit logging disabled')
        
        # Check training (can't really check, but note it)
        findings.append('Ensure staff HIPAA training is current')
        
        return {
            'category': 'Administrative Safeguards',
            'score': max(0, score),
            'findings': findings
        }
    
    def _assess_technical_safeguards(self) -> Dict[str, Any]:
        """Assess technical security measures"""
        score = 90  # Base score
        findings = []
        
        # Check encryption
        if not os.getenv('MASTER_ENCRYPTION_KEY'):
            score -= 30
            findings.append('Master encryption key not configured')
        
        # Check TLS
        if os.getenv('PIPECAT_TLS_ENABLED', 'true').lower() != 'true':
            score -= 20
            findings.append('TLS not enabled')
        
        # Check PHI redaction
        if os.getenv('PHI_REDACTION_ENABLED', 'true').lower() != 'true':
            score -= 15
            findings.append('PHI redaction disabled')
        
        return {
            'category': 'Technical Safeguards',
            'score': max(0, score),
            'findings': findings
        }
    
    def _calculate_risk_level(self, score: float) -> str:
        """Calculate risk level from score"""
        if score >= 80:
            return 'low'
        elif score >= 60:
            return 'medium'
        else:
            return 'high'
    
    def _generate_recommendations(self, assessments: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on assessment"""
        recommendations = []
        
        for assessment in assessments:
            if assessment['score'] < 70:
                recommendations.append(f"Improve {assessment['category']}")
            
            for finding in assessment['findings']:
                if 'not enabled' in finding.lower() or 'disabled' in finding.lower():
                    recommendations.append(f"Enable {finding.split()[0]}")
        
        return recommendations
