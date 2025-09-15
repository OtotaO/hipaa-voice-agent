#!/usr/bin/env python3

"""
Configuration Validation Script
Validates all configuration settings for HIPAA compliance
"""

import os
import sys
import re
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import requests
from cryptography.fernet import Fernet

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Color codes for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


class ConfigValidator:
    """Validates HIPAA Voice Agent configuration"""
    
    def __init__(self, env_file: str = "config/.env"):
        """
        Initialize validator
        
        Args:
            env_file: Path to environment file
        """
        self.env_file = env_file
        self.config = {}
        self.errors = []
        self.warnings = []
        self.info = []
        self.passed = 0
        self.failed = 0
        
    def load_config(self) -> bool:
        """
        Load configuration from .env file
        
        Returns:
            True if config loaded successfully
        """
        if not os.path.exists(self.env_file):
            self.errors.append(f"Configuration file not found: {self.env_file}")
            return False
        
        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            self.config[key.strip()] = value.strip()
            
            print(f"✓ Loaded {len(self.config)} configuration values")
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to load config: {e}")
            return False
    
    def validate_required(self) -> None:
        """Validate required configuration values"""
        print("\n1. REQUIRED SETTINGS")
        print("-" * 40)
        
        required = {
            # Twilio
            'TWILIO_ACCOUNT_SID': r'^AC[a-f0-9]{32}$',
            'TWILIO_AUTH_TOKEN': r'^[a-f0-9]{32}$',
            'TWILIO_HIPAA_PROJECT_ID': r'^PJ[a-f0-9]{32}$',
            'TWILIO_PHONE_NUMBER': r'^\+1[0-9]{10}$',
            
            # AWS
            'AWS_ACCESS_KEY_ID': r'^[A-Z0-9]{20}$',
            'AWS_SECRET_ACCESS_KEY': r'^[A-Za-z0-9/+=]{40}$',
            'AWS_REGION': r'^[a-z]{2}-[a-z]+-\d{1}$',
            
            # Security
            'MASTER_ENCRYPTION_KEY': r'^.{32,}$',
            'POSTGRES_PASSWORD': r'^.{12,}$',
            'REDIS_PASSWORD': r'^.{12,}$',
        }
        
        for key, pattern in required.items():
            value = self.config.get(key, '')
            
            if not value:
                self._fail(f"{key} is not set")
            elif value in ['your_value_here', 'change_me', 'default-key-change-me']:
                self._fail(f"{key} contains placeholder value")
            elif pattern and not re.match(pattern, value):
                self._fail(f"{key} format appears invalid")
            else:
                self._pass(f"{key} configured")
    
    def validate_hipaa(self) -> None:
        """Validate HIPAA-specific settings"""
        print("\n2. HIPAA COMPLIANCE SETTINGS")
        print("-" * 40)
        
        # Encryption
        if self.config.get('DB_ENCRYPT_PHI', 'false').lower() != 'true':
            self._fail("PHI encryption not enabled (DB_ENCRYPT_PHI)")
        else:
            self._pass("PHI encryption enabled")
        
        if self.config.get('AUDIT_LOG_ENCRYPTION', 'false').lower() != 'true':
            self._fail("Audit log encryption not enabled")
        else:
            self._pass("Audit log encryption enabled")
        
        # Audit
        if self.config.get('AUDIT_ENABLED', 'false').lower() != 'true':
            self._fail("Audit logging not enabled")
        else:
            self._pass("Audit logging enabled")
        
        retention = int(self.config.get('AUDIT_LOG_RETENTION_DAYS', '0'))
        if retention < 2555:  # 7 years
            self._fail(f"Audit retention ({retention} days) below 7-year requirement")
        else:
            self._pass(f"Audit retention adequate ({retention} days)")
        
        # PHI Protection
        if self.config.get('PHI_REDACTION_ENABLED', 'false').lower() != 'true':
            self._fail("PHI redaction not enabled")
        else:
            self._pass("PHI redaction enabled")
        
        # Call Recording
        if self.config.get('CALL_RECORDING_ENABLED', 'false').lower() == 'true':
            if self.config.get('CALL_RECORDING_ENCRYPTION', 'false').lower() != 'true':
                self._fail("Call recording enabled without encryption")
            else:
                self._warn("Call recording enabled (ensure proper consent)")
        else:
            self._pass("Call recording disabled (recommended)")
    
    def validate_security(self) -> None:
        """Validate security settings"""
        print("\n3. SECURITY SETTINGS")
        print("-" * 40)
        
        # TLS
        if self.config.get('PIPECAT_TLS_ENABLED', 'false').lower() != 'true':
            self._fail("TLS not enabled for Pipecat")
        else:
            self._pass("TLS enabled")
        
        # Database
        if self.config.get('POSTGRES_SSL_MODE') != 'require':
            self._fail("PostgreSQL SSL not required")
        else:
            self._pass("PostgreSQL SSL required")
        
        if not self.config.get('REDIS_PASSWORD'):
            self._fail("Redis password not set")
        else:
            self._pass("Redis password configured")
        
        # API Security
        if self.config.get('ENABLE_API_KEY_VALIDATION', 'false').lower() != 'true':
            self._warn("API key validation disabled")
        else:
            self._pass("API key validation enabled")
        
        # JWT
        if not self.config.get('JWT_SECRET'):
            self._warn("JWT secret not configured")
        else:
            if len(self.config.get('JWT_SECRET', '')) < 32:
                self._warn("JWT secret should be at least 32 characters")
            else:
                self._pass("JWT authentication configured")
    
    def validate_encryption_keys(self) -> None:
        """Validate encryption keys are properly formatted"""
        print("\n4. ENCRYPTION KEY VALIDATION")
        print("-" * 40)
        
        # Master key
        master_key = self.config.get('MASTER_ENCRYPTION_KEY', '')
        if master_key:
            try:
                # Check if it's a valid base64 key for Fernet
                if len(master_key) == 44:  # Base64 encoded 32 bytes
                    Fernet(master_key.encode() if isinstance(master_key, str) else master_key)
                    self._pass("Master encryption key format valid")
                else:
                    self._warn(f"Master key length ({len(master_key)}) may be incorrect")
            except Exception:
                self._fail("Master encryption key format invalid")
        
        # Data key
        data_key = self.config.get('DATA_ENCRYPTION_KEY', '')
        if data_key:
            try:
                if len(data_key) == 44:
                    Fernet(data_key.encode() if isinstance(data_key, str) else data_key)
                    self._pass("Data encryption key format valid")
                else:
                    self._warn(f"Data key length ({len(data_key)}) may be incorrect")
            except Exception:
                self._fail("Data encryption key format invalid")
    
    def validate_services(self) -> None:
        """Validate service configurations"""
        print("\n5. SERVICE CONFIGURATIONS")
        print("-" * 40)
        
        # LLM
        llm_endpoint = self.config.get('LLM_ENDPOINT', '')
        if not llm_endpoint:
            self._fail("LLM endpoint not configured")
        else:
            self._pass(f"LLM endpoint: {llm_endpoint}")
        
        # FHIR
        fhir_url = self.config.get('FHIR_BASE_URL', '')
        if not fhir_url:
            self._warn("FHIR base URL not configured")
        else:
            self._pass(f"FHIR URL: {fhir_url}")
        
        # Temporal
        temporal_host = self.config.get('TEMPORAL_HOST', '')
        if not temporal_host:
            self._warn("Temporal host not configured")
        else:
            self._pass(f"Temporal host: {temporal_host}")
    
    def validate_business_config(self) -> None:
        """Validate business configuration"""
        print("\n6. BUSINESS CONFIGURATION")
        print("-" * 40)
        
        # Business hours
        start = self.config.get('BUSINESS_HOURS_START', '')
        end = self.config.get('BUSINESS_HOURS_END', '')
        
        if start and end:
            self._info(f"Business hours: {start} - {end}")
        else:
            self._warn("Business hours not configured")
        
        # Timezone
        tz = self.config.get('BUSINESS_TIMEZONE', '')
        if tz:
            self._info(f"Timezone: {tz}")
        else:
            self._warn("Business timezone not configured")
        
        # Kentucky specific
        if self.config.get('STATE_JURISDICTION') == 'KY':
            self._info("Kentucky jurisdiction configured")
            if self.config.get('CONSENT_TYPE') == 'one_party':
                self._pass("One-party consent configured (KY)")
    
    def validate_network(self) -> None:
        """Validate network connectivity"""
        print("\n7. NETWORK CONNECTIVITY")
        print("-" * 40)
        
        # Check localhost services
        services = [
            ("API Health", "http://localhost:8081/health"),
            ("LLM Service", self.config.get('LLM_ENDPOINT', 'http://localhost:8000') + "/health"),
            ("Temporal", f"http://{self.config.get('TEMPORAL_HOST', 'localhost:7233')}/health"),
        ]
        
        for name, url in services:
            if url:
                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        self._pass(f"{name} reachable")
                    else:
                        self._warn(f"{name} returned status {response.status_code}")
                except requests.exceptions.ConnectionError:
                    self._info(f"{name} not reachable (service may not be running)")
                except Exception as e:
                    self._warn(f"{name} check failed: {e}")
    
    def check_file_permissions(self) -> None:
        """Check file permissions for security"""
        print("\n8. FILE PERMISSIONS")
        print("-" * 40)
        
        sensitive_files = [
            ('config/.env', 0o600),
            ('config/certs/server.key', 0o600),
            ('data/postgres', 0o700),
            ('data/logs/audit', 0o700),
        ]
        
        for filepath, expected_mode in sensitive_files:
            if os.path.exists(filepath):
                stat_info = os.stat(filepath)
                current_mode = stat_info.st_mode & 0o777
                
                if current_mode == expected_mode:
                    self._pass(f"{filepath} permissions correct ({oct(current_mode)})")
                elif current_mode > expected_mode:
                    self._fail(f"{filepath} permissions too permissive ({oct(current_mode)}, should be {oct(expected_mode)})")
                else:
                    self._warn(f"{filepath} permissions: {oct(current_mode)}")
            else:
                self._info(f"{filepath} does not exist")
    
    def _pass(self, message: str) -> None:
        """Record a passed check"""
        print(f"{GREEN}✓{NC} {message}")
        self.passed += 1
    
    def _fail(self, message: str) -> None:
        """Record a failed check"""
        print(f"{RED}✗{NC} {message}")
        self.errors.append(message)
        self.failed += 1
    
    def _warn(self, message: str) -> None:
        """Record a warning"""
        print(f"{YELLOW}⚠{NC} {message}")
        self.warnings.append(message)
    
    def _info(self, message: str) -> None:
        """Record info"""
        print(f"{BLUE}ℹ{NC} {message}")
        self.info.append(message)
    
    def generate_report(self) -> Dict:
        """
        Generate validation report
        
        Returns:
            Validation report dictionary
        """
        total = self.passed + self.failed
        score = (self.passed / total * 100) if total > 0 else 0
        
        return {
            'passed': self.passed,
            'failed': self.failed,
            'warnings': len(self.warnings),
            'score': round(score, 1),
            'compliant': self.failed == 0,
            'errors': self.errors,
            'warnings_list': self.warnings,
            'timestamp': os.popen('date -Iseconds').read().strip()
        }
    
    def run(self) -> bool:
        """
        Run all validations
        
        Returns:
            True if validation passed
        """
        print("="*50)
        print("HIPAA Voice Agent - Configuration Validation")
        print("="*50)
        
        if not self.load_config():
            return False
        
        # Run all validations
        self.validate_required()
        self.validate_hipaa()
        self.validate_security()
        self.validate_encryption_keys()
        self.validate_services()
        self.validate_business_config()
        self.validate_network()
        self.check_file_permissions()
        
        # Generate report
        report = self.generate_report()
        
        # Display summary
        print("\n" + "="*50)
        print("VALIDATION SUMMARY")
        print("="*50)
        print(f"{GREEN}Passed:{NC} {report['passed']}")
        print(f"{RED}Failed:{NC} {report['failed']}")
        print(f"{YELLOW}Warnings:{NC} {report['warnings']}")
        print(f"Score: {report['score']}%")
        
        if report['compliant']:
            print(f"\n{GREEN}✅ Configuration is HIPAA compliant!{NC}")
        else:
            print(f"\n{RED}❌ Configuration has {len(report['errors'])} critical issues:{NC}")
            for error in report['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(report['errors']) > 5:
                print(f"  ... and {len(report['errors']) - 5} more")
        
        if report['warnings'] > 0:
            print(f"\n{YELLOW}⚠️ {report['warnings']} warnings to review:{NC}")
            for warning in report['warnings_list'][:3]:
                print(f"  - {warning}")
        
        # Save report
        report_file = f"audits/config_validation_{report['timestamp'].replace(':', '')}.json"
        os.makedirs("audits", exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {report_file}")
        
        return report['compliant']


def main():
    """Main function"""
    validator = ConfigValidator()
    
    # Check for custom env file
    if len(sys.argv) > 1:
        validator.env_file = sys.argv[1]
    
    # Run validation
    success = validator.run()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
