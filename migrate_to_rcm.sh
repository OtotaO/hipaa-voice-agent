#!/bin/bash
# Migration Script: Voice Agent → RCM Platform
# Run this if you decide to pivot to RCM

set -e  # Exit on error

echo "🔄 Starting migration from Voice Agent to RCM Platform..."
echo ""

# Confirm with user
read -p "This will archive voice agent files and create RCM structure. Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 1
fi

# 1. Create archive directory
echo "📦 Creating archive directory..."
mkdir -p archive/voice-agent

# 2. Archive voice-specific files
echo "🗃️  Archiving voice agent files..."
mv app.py archive/voice-agent/ 2>/dev/null || echo "  app.py already moved"
mv medical_scribe.py archive/voice-agent/ 2>/dev/null || echo "  medical_scribe.py already moved"
mv intent_router.py archive/voice-agent/ 2>/dev/null || echo "  intent_router.py already moved"
mv READY_TO_TEST.md archive/voice-agent/ 2>/dev/null || echo "  READY_TO_TEST.md already moved"
mv MANUAL_TESTING_GUIDE.md archive/voice-agent/ 2>/dev/null || echo "  MANUAL_TESTING_GUIDE.md already moved"
mv NO_HARDWARE_IMPLEMENTATION.md archive/voice-agent/ 2>/dev/null || echo "  NO_HARDWARE_IMPLEMENTATION.md already moved"
mv FIXES_APPLIED.md archive/voice-agent/ 2>/dev/null || echo "  FIXES_APPLIED.md already moved"
mv COMPLETE.md archive/voice-agent/ 2>/dev/null || echo "  COMPLETE.md already moved"
mv PROJECT_SUMMARY.md archive/voice-agent/ 2>/dev/null || echo "  PROJECT_SUMMARY.md already moved"

# 3. Delete irrelevant files
echo "🗑️  Removing voice-specific test files..."
rm -f test_utterances.txt 2>/dev/null || true
rm -f intents_ranked.json 2>/dev/null || true
rm -f hardware_cost_estimates.json 2>/dev/null || true
rm -f pilot_acceptance_tests.jsonl 2>/dev/null || true
rm -f test_scenarios.py 2>/dev/null || true
rm -f test_system.py 2>/dev/null || true
rm -f test_harness.py 2>/dev/null || true

# 4. Create new RCM directory structure
echo "📁 Creating RCM directory structure..."
mkdir -p src/rcm
mkdir -p frontend/src/components
mkdir -p migrations
mkdir -p tests/rcm

# 5. Create placeholder files
echo "📝 Creating RCM module files..."

# Create __init__.py
cat > src/rcm/__init__.py << 'EOF'
"""
Revenue Cycle Management Platform
Core modules for medical billing workflow automation
"""

from .eligibility import EligibilityService
from .models import Patient, EligibilityCheck, Claim, Payment

__all__ = [
    "EligibilityService",
    "Patient",
    "EligibilityCheck",
    "Claim",
    "Payment"
]
EOF

# Create models.py skeleton
cat > src/rcm/models.py << 'EOF'
"""
SQLAlchemy models for RCM platform
"""

from sqlalchemy import Column, String, DateTime, Date, DECIMAL, Integer, ARRAY, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class Patient(Base):
    """Patient demographic and insurance information"""
    __tablename__ = 'patients'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    dob = Column(Date, nullable=False)
    gender = Column(String(10))
    ssn_last4 = Column(String(4))
    insurance_id = Column(String(50))
    insurance_payer = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EligibilityCheck(Base):
    """Insurance eligibility verification history"""
    __tablename__ = 'eligibility_checks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    check_date = Column(DateTime, nullable=False)
    payer = Column(String(100))
    status = Column(String(20))  # active, inactive, pending
    plan_name = Column(String(255))
    copay = Column(String(50))
    deductible = Column(String(50))
    out_of_pocket_max = Column(String(50))
    response_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

class Claim(Base):
    """Insurance claims"""
    __tablename__ = 'claims'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), nullable=False)
    claim_number = Column(String(50), unique=True)
    submission_date = Column(DateTime)
    payer = Column(String(100))
    total_charges = Column(DECIMAL(10, 2))
    status = Column(String(50))
    clearinghouse_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(Base):
    """Payment posting from ERAs"""
    __tablename__ = 'payments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), nullable=False)
    payment_date = Column(Date)
    paid_amount = Column(DECIMAL(10, 2))
    adjustment_amount = Column(DECIMAL(10, 2))
    adjustment_reason = Column(String(255))
    era_id = Column(String(100))
    posted_at = Column(DateTime, default=datetime.utcnow)
EOF

# Create eligibility.py skeleton
cat > src/rcm/eligibility.py << 'EOF'
"""
Eligibility verification service using Eligible API
"""

import httpx
from typing import Dict, Optional
from datetime import datetime

class EligibilityService:
    """Real-time insurance eligibility verification"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://gds.eligibleapi.com/v1.5"

    async def check_coverage(
        self,
        member_id: str,
        payer_id: str,
        first_name: str,
        last_name: str,
        dob: str,
        provider_npi: str
    ) -> Dict:
        """
        Check insurance eligibility

        Args:
            member_id: Insurance member ID
            payer_id: Payer identifier
            first_name: Patient first name
            last_name: Patient last name
            dob: Date of birth (YYYY-MM-DD)
            provider_npi: Provider NPI

        Returns:
            Dict with eligibility status, copay, deductible, etc.
        """

        # TODO: Implement Eligible API integration
        # See RCM_IMPLEMENTATION_PLAN.md for complete code

        raise NotImplementedError("Eligible API integration pending")
EOF

# 6. Create initial database migration
echo "🗄️  Creating initial database schema..."
cat > migrations/001_initial_schema.sql << 'EOF'
-- RCM Platform Initial Schema
-- Run with: psql -U rcm_user -d rcm_platform -f migrations/001_initial_schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    dob DATE NOT NULL,
    gender VARCHAR(10),
    ssn_last4 VARCHAR(4),
    insurance_id VARCHAR(50),
    insurance_payer VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE eligibility_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id UUID REFERENCES patients(id),
    check_date TIMESTAMP NOT NULL,
    payer VARCHAR(100),
    status VARCHAR(20),
    plan_name VARCHAR(255),
    copay VARCHAR(50),
    deductible VARCHAR(50),
    out_of_pocket_max VARCHAR(50),
    response_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_eligibility_patient ON eligibility_checks(patient_id);
CREATE INDEX idx_eligibility_date ON eligibility_checks(check_date);

-- Future tables (add in subsequent migrations):
-- CREATE TABLE claims (...);
-- CREATE TABLE payments (...);
-- CREATE TABLE denials (...);
-- CREATE TABLE appeals (...);
EOF

# 7. Update requirements.txt
echo "📦 Updating dependencies..."
cat > requirements.txt << 'EOF'
# Core Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
python-multipart==0.0.6

# Database
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# HTTP Client
httpx==0.25.2

# Data Validation
pydantic==2.5.0

# Security (kept from voice agent)
cryptography==41.0.7
python-jose[cryptography]==3.3.0

# Task Queue (for Phase 2+)
celery==5.3.4
redis==5.0.1

# Workflows (kept from voice agent)
# temporallib==1.3.0

# Utilities
loguru==0.7.2
aiofiles==23.2.1
EOF

# 8. Update .env.example
echo "⚙️  Updating environment configuration..."
cat > .env.example << 'EOF'
# RCM Platform Configuration

# Database
DATABASE_URL=postgresql://rcm_user:your_password@localhost/rcm_platform

# Redis (for caching and Celery)
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_redis_password

# RCM APIs
ELIGIBLE_API_KEY=your_eligible_api_key_here
WAYSTAR_API_KEY=your_waystar_api_key_here
WAYSTAR_PRACTICE_NPI=1234567890
WAYSTAR_TAX_ID=XX-XXXXXXX

# Practice Information
PRACTICE_NAME=Your Medical Practice
PRACTICE_ADDRESS=123 Main St, City, ST 12345

# Security
SECRET_KEY=your_secret_key_here
MASTER_ENCRYPTION_KEY=your_encryption_key_base64

# Server
HOST=0.0.0.0
PORT=8000

# Logging
LOG_LEVEL=INFO
EOF

# 9. Update README
echo "📖 Updating README..."
cp RCM_ARCHITECTURE.md README.md

# 10. Create git commit
echo "💾 Creating git commit..."
git add . 2>/dev/null || true
git status

echo ""
echo "✅ Migration complete!"
echo ""
echo "📋 Next Steps:"
echo "  1. Review changes: git status"
echo "  2. Commit changes: git commit -m 'Migrate to RCM platform'"
echo "  3. Install dependencies: pip install -r requirements.txt"
echo "  4. Set up database: docker-compose up -d postgres"
echo "  5. Run migrations: psql -U rcm_user -d rcm_platform -f migrations/001_initial_schema.sql"
echo "  6. Sign up for Eligible API: https://eligible.com/developers"
echo "  7. Follow RCM_IMPLEMENTATION_PLAN.md to build eligibility MVP"
echo ""
echo "📁 Project structure:"
echo "  src/rcm/          - RCM business logic"
echo "  migrations/       - Database schemas"
echo "  archive/          - Voice agent files (preserved)"
echo ""
echo "🎯 Goal: Build eligibility check MVP in 2 weeks"
echo "📖 Read: RCM_IMPLEMENTATION_PLAN.md for detailed steps"
