# 🔄 Migration Plan: Voice Agent → RCM Platform

## Executive Summary

**Reusable**: 30% of current codebase (security, workflows, infrastructure)
**New Development**: 70% (RCM-specific logic)
**Timeline**: 2 weeks for eligibility MVP, 6 months for full platform

## File-by-File Analysis

### ✅ KEEP - Reusable Components (30%)

#### Security & Compliance Layer
```
src/core/security.py          ✅ KEEP (100% reusable)
- PHI encryption/decryption
- JWT token validation
- Audit logging hooks
- Access control

src/core/compliance.py        ✅ KEEP (100% reusable)
- HIPAA audit trail
- Data retention policies
- Immutable logging
- 7-year retention enforcement
```

**Why**: RCM platform needs same HIPAA compliance as voice agent

#### Workflow Engine
```
src/workflows/temporal_client.py  ✅ KEEP (80% reusable)
- Durable workflow orchestration
- Retry logic
- State management
```

**Modifications Needed**:
- Rename workflows from "appointment confirmation" to "denial follow-up"
- Add "appeal deadline tracking" workflow
- Add "secondary claim submission" workflow

#### Infrastructure
```
docker-compose.yml            ✅ KEEP (modify)
- PostgreSQL (already configured)
- Redis (already configured)
- Temporal (already configured)

.env.example                  ✅ KEEP (add RCM API keys)
requirements.txt              ✅ KEEP (update dependencies)
```

#### FHIR Integration (Phase 3+)
```
src/services/fhir_client.py   ✅ KEEP (for later)
- Pull patient demographics from EHR
- Retrieve encounter data
- Sync diagnosis codes
```

**Note**: Not needed for MVP (Weeks 1-2), but valuable for Phase 3 when integrating with practice EHRs

#### Testing Infrastructure
```
tests/                        ✅ KEEP (rewrite tests)
- Test structure is good
- Replace voice tests with RCM tests
```

### ⚠️ ARCHIVE - Not Applicable to RCM

#### Voice/Audio Processing
```
app.py                        ⚠️ ARCHIVE
- Web-based voice recording UI
- Audio processing logic
- WebSocket handling for audio streams

medical_scribe.py             ⚠️ ARCHIVE
- Deepgram ASR integration
- SOAP note generation from transcripts
- Medical note parsing

intent_router.py              ⚠️ ARCHIVE
- Voice intent classification
- Entity extraction from spoken commands
- Confidence scoring
```

**Why Archive (Not Delete)**:
- May repurpose for "voice-driven charge entry" in Phase 5
- Good reference for building voice-powered RCM assistant
- Keep in `archive/` directory

#### Documentation
```
READY_TO_TEST.md              ⚠️ ARCHIVE
MANUAL_TESTING_GUIDE.md       ⚠️ ARCHIVE
NO_HARDWARE_IMPLEMENTATION.md ⚠️ ARCHIVE
REALITY_CHECK.md              ✅ KEEP (good wisdom)
ACCEPTANCE_CRITERIA.md        ✅ KEEP (adapt for RCM)
```

### ❌ DELETE - Completely Irrelevant

```
test_utterances.txt           ❌ DELETE
intents_ranked.json           ❌ DELETE
hardware_cost_estimates.json  ❌ DELETE
pilot_acceptance_tests.jsonl  ❌ DELETE (voice-specific tests)
test_scenarios.py             ❌ DELETE (voice scenarios)
```

## Migration Script

```bash
#!/bin/bash
# migrate_to_rcm.sh

# 1. Create archive directory
mkdir -p archive/voice-agent

# 2. Archive voice-specific files
mv app.py archive/voice-agent/
mv medical_scribe.py archive/voice-agent/
mv intent_router.py archive/voice-agent/
mv READY_TO_TEST.md archive/voice-agent/
mv MANUAL_TESTING_GUIDE.md archive/voice-agent/
mv NO_HARDWARE_IMPLEMENTATION.md archive/voice-agent/
mv test_utterances.txt archive/voice-agent/
mv intents_ranked.json archive/voice-agent/
mv pilot_acceptance_tests.jsonl archive/voice-agent/

# 3. Delete truly irrelevant files
rm -f hardware_cost_estimates.json
rm -f test_scenarios.py
rm -f test_system.py
rm -f test_harness.py

# 4. Create new RCM directory structure
mkdir -p src/rcm/{eligibility,claims,payments,denials,appeals}
mkdir -p frontend/src/components
mkdir -p migrations
mkdir -p tests/rcm

# 5. Keep core infrastructure
# (no action needed - already in src/core, src/workflows)

# 6. Update documentation
mv README.md archive/voice-agent/README.old.md
cp RCM_ARCHITECTURE.md README.md

echo "Migration complete!"
echo "- Voice agent files archived in archive/voice-agent/"
echo "- Core security/compliance kept in src/core/"
echo "- New RCM structure created in src/rcm/"
```

## Updated Project Structure

```
hipaa-voice-agent/           → Rename to rcm-platform/
├── src/
│   ├── core/                ✅ KEPT
│   │   ├── security.py      (PHI protection, encryption)
│   │   └── compliance.py    (audit logging)
│   ├── workflows/           ✅ KEPT
│   │   └── temporal_client.py  (durable workflows)
│   ├── services/            ✅ KEPT
│   │   └── fhir_client.py   (for Phase 3+)
│   └── rcm/                 🆕 NEW
│       ├── __init__.py
│       ├── models.py        (SQLAlchemy: Patient, Claim, Payment)
│       ├── schemas.py       (Pydantic validation)
│       ├── eligibility.py   (Eligible API integration)
│       ├── claims.py        (Waystar claim submission)
│       ├── payments.py      (ERA processing)
│       ├── denials.py       (denial management workflow)
│       └── appeals.py       (appeal tracking)
│
├── frontend/                🆕 NEW
│   ├── src/
│   │   ├── components/
│   │   │   ├── EligibilityCheck.tsx
│   │   │   ├── PatientForm.tsx
│   │   │   ├── ChargeEntry.tsx
│   │   │   ├── ClaimDashboard.tsx
│   │   │   └── DenialQueue.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── migrations/              🆕 NEW
│   ├── 001_initial_schema.sql
│   ├── 002_cpt_codes.sql
│   └── 003_claims.sql
│
├── tests/                   ✅ KEPT (rewrite)
│   └── rcm/
│       ├── test_eligibility.py
│       ├── test_claims.py
│       └── test_payments.py
│
├── archive/                 🆕 NEW
│   └── voice-agent/         (old files)
│       ├── app.py
│       ├── medical_scribe.py
│       └── ...
│
├── config/                  ✅ KEPT
├── docker/                  ✅ KEPT
├── docker-compose.yml       ✅ KEPT (modify services)
├── requirements.txt         ✅ KEPT (update deps)
├── .env.example             ✅ KEPT (add RCM API keys)
├── README.md                🆕 REPLACE (RCM_ARCHITECTURE.md)
└── Makefile                 ✅ KEPT (update targets)
```

## Dependencies Update

### Remove (Voice Agent Specific)
```diff
- deepgram-sdk==3.0.0
- pyaudio==0.2.14
- huggingface-hub==0.20.1
- transformers==4.36.2
- torch==2.1.2
```

### Keep (Reusable)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
cryptography==41.0.7        # Security
python-jose[cryptography]==3.3.0  # Auth
loguru==0.7.2               # Logging
```

### Add (RCM Specific)
```diff
+ sqlalchemy==2.0.23         # ORM for patient/claim data
+ psycopg2-binary==2.9.9     # PostgreSQL driver
+ alembic==1.12.1            # Database migrations
+ httpx==0.25.2              # HTTP client for APIs
+ celery==5.3.4              # Task queue for async claim submission
+ redis==5.0.1               # Celery backend + caching
```

## Environment Variables Update

### Remove
```diff
- DEEPGRAM_API_KEY
- HUGGINGFACE_API_KEY
- TWILIO_ACCOUNT_SID (keep if adding voice later)
- TWILIO_AUTH_TOKEN
```

### Add
```diff
+ # RCM APIs
+ ELIGIBLE_API_KEY=your_eligible_api_key
+ WAYSTAR_API_KEY=your_waystar_api_key
+ WAYSTAR_PRACTICE_NPI=1234567890
+ WAYSTAR_TAX_ID=XX-XXXXXXX

+ # Database
+ DATABASE_URL=postgresql://user:pass@localhost/rcm_platform

+ # Redis
+ REDIS_URL=redis://localhost:6379/0

+ # Practice Info
+ PRACTICE_NAME=Your Medical Practice
+ PRACTICE_ADDRESS=123 Main St, City, ST 12345
```

## Database Schema

### New Tables Needed

```sql
-- migrations/001_initial_schema.sql

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL,  -- admin, biller, provider
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    check_date TIMESTAMP NOT NULL,
    payer VARCHAR(100),
    status VARCHAR(20),  -- active, inactive, pending
    plan_name VARCHAR(255),
    copay VARCHAR(50),
    deductible VARCHAR(50),
    out_of_pocket_max VARCHAR(50),
    response_data JSONB,  -- Full API response
    created_by UUID REFERENCES users(id)
);

CREATE TABLE cpt_codes (
    code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL,
    category VARCHAR(100),
    base_fee DECIMAL(10, 2)
);

CREATE TABLE charges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    encounter_date DATE NOT NULL,
    cpt_code VARCHAR(5) REFERENCES cpt_codes(code),
    units INTEGER DEFAULT 1,
    fee DECIMAL(10, 2),
    diagnosis_codes TEXT[],  -- ICD-10 codes
    posted_by UUID REFERENCES users(id),
    posted_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(id),
    claim_number VARCHAR(50) UNIQUE,
    submission_date TIMESTAMP,
    payer VARCHAR(100),
    total_charges DECIMAL(10, 2),
    status VARCHAR(50),  -- submitted, accepted, denied, paid
    clearinghouse_id VARCHAR(100),  -- Waystar claim ID
    submitted_by UUID REFERENCES users(id)
);

CREATE TABLE claim_charges (
    claim_id UUID REFERENCES claims(id),
    charge_id UUID REFERENCES charges(id),
    PRIMARY KEY (claim_id, charge_id)
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID REFERENCES claims(id),
    payment_date DATE,
    paid_amount DECIMAL(10, 2),
    adjustment_amount DECIMAL(10, 2),
    adjustment_reason VARCHAR(255),
    era_id VARCHAR(100),  -- 835 ERA reference
    posted_by UUID REFERENCES users(id),
    posted_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE denials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID REFERENCES claims(id),
    denial_date DATE,
    denial_code VARCHAR(10),
    denial_reason TEXT,
    status VARCHAR(50),  -- pending, corrected, appealed, written_off
    assigned_to UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE appeals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    denial_id UUID REFERENCES denials(id),
    appeal_date DATE,
    appeal_deadline DATE,
    status VARCHAR(50),  -- pending, submitted, won, lost
    notes TEXT,
    created_by UUID REFERENCES users(id)
);
```

## Docker Compose Updates

```yaml
version: '3.8'

services:
  # KEEP - Already configured
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: rcm_platform  # Changed from hipaa_voice_agent
      POSTGRES_USER: rcm_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d  # Auto-run migrations

  # KEEP - Already configured
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}

  # KEEP - For workflows
  temporal:
    image: temporalio/auto-setup:latest
    environment:
      - DB=postgresql
      - DB_PORT=5432
      - POSTGRES_USER=rcm_user
      - POSTGRES_PWD=${POSTGRES_PASSWORD}
    depends_on:
      - postgres

  # NEW - RCM API server
  api:
    build: .
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://rcm_user:${POSTGRES_PASSWORD}@postgres/rcm_platform
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - postgres
      - redis

  # NEW - Celery worker for async tasks
  celery:
    build: .
    command: celery -A src.tasks worker --loglevel=info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://rcm_user:${POSTGRES_PASSWORD}@postgres/rcm_platform
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
```

## Step-by-Step Migration Process

### Day 1: Backup and Archive
```bash
# 1. Create git branch
git checkout -b feature/rcm-pivot

# 2. Create archive
mkdir -p archive/voice-agent
git mv app.py medical_scribe.py intent_router.py archive/voice-agent/

# 3. Commit archive
git commit -m "Archive voice agent files before RCM pivot"
```

### Day 2: Create New Structure
```bash
# 1. Run migration script
bash migrate_to_rcm.sh

# 2. Create RCM modules
touch src/rcm/{__init__.py,models.py,schemas.py,eligibility.py}

# 3. Create migrations
cp migrations/001_initial_schema.sql migrations/

# 4. Update requirements.txt
# (manual edit)

# 5. Commit structure
git add .
git commit -m "Create RCM platform structure"
```

### Day 3: Update Configuration
```bash
# 1. Update .env.example
# Add ELIGIBLE_API_KEY, WAYSTAR_API_KEY, etc.

# 2. Update docker-compose.yml
# Change database name, add new services

# 3. Update README.md
cp RCM_ARCHITECTURE.md README.md

# 4. Commit config
git commit -am "Update configuration for RCM platform"
```

### Day 4-7: Build Eligibility MVP
- Implement src/rcm/eligibility.py
- Create API endpoints in src/main.py
- Build simple React frontend
- Test with real Eligible API account

## Risk Mitigation

### What If You Need to Revert?
```bash
# All voice agent code is in archive/
# Can always restore:
git checkout main
# Or copy files back from archive/voice-agent/
```

### Hybrid Approach
Keep BOTH codebases:
```
rcm-platform/              # Main RCM product
├── src/rcm/              # Billing features
└── src/voice/            # Voice features (from archive)
    ├── scribe.py
    └── charge_capture.py  # Voice-driven charge entry
```

This lets you build "voice-powered RCM" later.

## Summary

| Component | Status | Action |
|-----------|--------|--------|
| Security/Compliance | ✅ Keep | Reuse 100% |
| Workflows | ✅ Keep | Adapt for RCM |
| Database | ✅ Keep | New schema |
| Voice/Audio | ⚠️ Archive | Save for later |
| Documentation | ⚠️ Archive | Replace with RCM docs |
| Tests | ✅ Keep | Rewrite for RCM |

**Net Result**: 30% reusable, 70% new development required.

---

**Ready to execute migration? Run `bash migrate_to_rcm.sh` to start.**
