# 🚀 RCM Platform - Practical Implementation Plan

## Occam's Razor Approach: Start with ONE Workflow

**Don't build all 11 workflows at once.** Start with the highest-value, lowest-complexity workflow and prove it works.

## Phase 1: Eligibility Verification MVP (Week 1-2)

### Why Start Here?
- **Immediate value**: Every practice checks eligibility 20-50x daily
- **Simple workflow**: Input patient info → API call → Display results
- **Low risk**: Read-only operation, no claim submission
- **Fast feedback**: Can demo to billing managers in days

### Week 1: Core Infrastructure

#### Day 1-2: Database & API Setup
```bash
# 1. Create PostgreSQL database
CREATE DATABASE rcm_platform;

# Tables needed:
# - patients (demographics, insurance info)
# - eligibility_checks (history of verifications)
# - users (practice staff accounts)
```

**Files to Create:**
```
src/rcm/
├── __init__.py
├── models.py              # SQLAlchemy models
├── eligibility.py         # Eligible API integration
├── database.py            # Database connection
└── schemas.py             # Pydantic validation schemas

migrations/
└── 001_initial_schema.sql
```

**Code Structure:**
```python
# src/rcm/models.py
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Patient(Base):
    __tablename__ = 'patients'

    id = Column(String, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)
    dob = Column(DateTime)
    gender = Column(String)
    ssn_last4 = Column(String)  # Only last 4 for security
    insurance_id = Column(String)
    insurance_payer = Column(String)

class EligibilityCheck(Base):
    __tablename__ = 'eligibility_checks'

    id = Column(String, primary_key=True)
    patient_id = Column(String)
    check_date = Column(DateTime)
    payer = Column(String)
    status = Column(String)  # active, inactive, pending
    response_data = Column(JSON)  # Full API response
    copay = Column(String)
    deductible = Column(String)
    out_of_pocket_max = Column(String)
```

#### Day 3-4: Eligible API Integration

**Sign up**: https://eligible.com (has free developer tier)

**Implementation:**
```python
# src/rcm/eligibility.py
import httpx
from datetime import datetime
from typing import Dict, Optional

class EligibilityService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://gds.eligibleapi.com/v1.5"

    async def check_coverage(
        self,
        member_id: str,
        payer_id: str,
        first_name: str,
        last_name: str,
        dob: str,  # YYYY-MM-DD
        provider_npi: str
    ) -> Dict:
        """Check real-time eligibility"""

        payload = {
            "service_type": ["30"],  # Health benefit coverage
            "member": {
                "id": member_id,
                "first_name": first_name,
                "last_name": last_name,
                "dob": dob
            },
            "provider": {
                "npi": provider_npi,
                "organization_name": "Your Practice Name"
            },
            "payer": {
                "id": payer_id
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/coverage/all.json",
                json=payload,
                headers=headers
            )

            if response.status_code == 200:
                return self._parse_response(response.json())
            else:
                raise Exception(f"Eligibility check failed: {response.text}")

    def _parse_response(self, data: Dict) -> Dict:
        """Extract key information from Eligible API response"""

        result = {
            "status": "active" if data.get("eligible") == "yes" else "inactive",
            "plan_name": data.get("plan", {}).get("plan_name"),
            "copay": self._extract_copay(data),
            "deductible": self._extract_deductible(data),
            "out_of_pocket_max": self._extract_oop_max(data),
            "coverage_details": data.get("coverage", []),
            "raw_response": data
        }

        return result

    def _extract_copay(self, data: Dict) -> Optional[str]:
        """Extract copay from response"""
        for service in data.get("coverage", []):
            if service.get("service_type") == "30":  # Office visit
                copay = service.get("copay_in_network")
                if copay:
                    return f"${copay['amount']}"
        return None

    # Similar methods for deductible and OOP max...
```

#### Day 5: FastAPI Endpoints

```python
# src/main.py (modify existing)
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from src.rcm.eligibility import EligibilityService
from src.rcm.models import Patient, EligibilityCheck
from src.rcm.database import get_db
from datetime import datetime
import uuid

app = FastAPI(title="RCM Platform")

# Keep existing security imports from voice agent
from src.core.security import get_current_user

@app.post("/api/eligibility/check")
async def check_eligibility(
    patient_id: str,
    provider_npi: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Check insurance eligibility for a patient"""

    # 1. Fetch patient from database
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # 2. Call Eligible API
    eligibility_service = EligibilityService(api_key=settings.ELIGIBLE_API_KEY)

    try:
        result = await eligibility_service.check_coverage(
            member_id=patient.insurance_id,
            payer_id=patient.insurance_payer,
            first_name=patient.first_name,
            last_name=patient.last_name,
            dob=patient.dob.strftime("%Y-%m-%d"),
            provider_npi=provider_npi
        )

        # 3. Save to database
        check = EligibilityCheck(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            check_date=datetime.now(),
            payer=patient.insurance_payer,
            status=result["status"],
            response_data=result["raw_response"],
            copay=result["copay"],
            deductible=result["deductible"],
            out_of_pocket_max=result["out_of_pocket_max"]
        )
        db.add(check)
        db.commit()

        # 4. Return result
        return {
            "status": result["status"],
            "plan_name": result["plan_name"],
            "copay": result["copay"],
            "deductible": result["deductible"],
            "out_of_pocket_max": result["out_of_pocket_max"],
            "check_id": check.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/patients")
async def create_patient(
    first_name: str,
    last_name: str,
    dob: str,
    gender: str,
    insurance_id: str,
    insurance_payer: str,
    db: Session = Depends(get_db)
):
    """Create new patient record"""

    patient = Patient(
        id=str(uuid.uuid4()),
        first_name=first_name,
        last_name=last_name,
        dob=datetime.strptime(dob, "%Y-%m-%d"),
        gender=gender,
        insurance_id=insurance_id,
        insurance_payer=insurance_payer
    )

    db.add(patient)
    db.commit()

    return {"patient_id": patient.id, "message": "Patient created"}
```

### Week 2: Frontend UI

#### Simple React Form

```typescript
// frontend/src/components/EligibilityCheck.tsx
import React, { useState } from 'react';
import axios from 'axios';

interface EligibilityResult {
  status: string;
  plan_name: string;
  copay: string;
  deductible: string;
  out_of_pocket_max: string;
}

export function EligibilityCheck() {
  const [patientId, setPatientId] = useState('');
  const [providerNPI, setProviderNPI] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EligibilityResult | null>(null);

  const handleCheck = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/eligibility/check', {
        patient_id: patientId,
        provider_npi: providerNPI
      });
      setResult(response.data);
    } catch (error) {
      alert('Eligibility check failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-2xl font-bold mb-6">Insurance Eligibility Check</h2>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium">Patient ID</label>
          <input
            type="text"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            className="mt-1 block w-full border rounded-md p-2"
          />
        </div>

        <div>
          <label className="block text-sm font-medium">Provider NPI</label>
          <input
            type="text"
            value={providerNPI}
            onChange={(e) => setProviderNPI(e.target.value)}
            className="mt-1 block w-full border rounded-md p-2"
          />
        </div>

        <button
          onClick={handleCheck}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700"
        >
          {loading ? 'Checking...' : 'Check Eligibility'}
        </button>
      </div>

      {result && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
          <h3 className="text-lg font-semibold mb-3">Results</h3>
          <dl className="grid grid-cols-2 gap-3">
            <div>
              <dt className="text-sm text-gray-600">Status</dt>
              <dd className="font-medium">{result.status}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-600">Plan</dt>
              <dd className="font-medium">{result.plan_name}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-600">Copay</dt>
              <dd className="font-medium">{result.copay || 'N/A'}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-600">Deductible</dt>
              <dd className="font-medium">{result.deductible || 'N/A'}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  );
}
```

### Testing the MVP

**Week 2, Day 6-7: Real-World Testing**

1. **Get test insurance info** from Eligible API docs
2. **Create 5 test patients** with different payers
3. **Run eligibility checks**
4. **Time the process**: Should be <5 seconds end-to-end
5. **Show to 3 medical billing staff** and get feedback

## Phase 2: Add Charge Posting (Week 3-4)

### Only Build If Phase 1 Succeeds

**Success criteria for Phase 1:**
- ✅ Eligibility check completes in <5 seconds
- ✅ Results are accurate (compare to manual payer checks)
- ✅ Billing staff say "this saves time"
- ✅ At least 2 practices commit to pilot

### Week 3: CPT Code Database

```sql
-- migrations/002_cpt_codes.sql
CREATE TABLE cpt_codes (
    code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL,
    category VARCHAR(100),
    base_fee DECIMAL(10, 2)
);

CREATE TABLE charges (
    id UUID PRIMARY KEY,
    patient_id UUID REFERENCES patients(id),
    encounter_date DATE NOT NULL,
    cpt_code VARCHAR(5) REFERENCES cpt_codes(code),
    units INTEGER DEFAULT 1,
    fee DECIMAL(10, 2),
    diagnosis_codes TEXT[],  -- Array of ICD-10 codes
    posted_by UUID REFERENCES users(id),
    posted_at TIMESTAMP DEFAULT NOW()
);
```

Load CPT codes from CMS fee schedule or purchase from AAPC.

### Week 4: Charge Entry UI

Simple form to post charges after encounter:
- Patient selector (autocomplete)
- CPT code search
- ICD-10 diagnosis linking
- Save to database

## Phase 3: Claim Submission (Week 5-8)

### Week 5-6: Waystar Integration

**Sign up**: https://www.waystar.com (contact for developer account)

**Implementation:**
```python
# src/rcm/claims.py
import httpx
from typing import List, Dict

class ClaimService:
    def __init__(self, api_key: str, practice_npi: str):
        self.api_key = api_key
        self.practice_npi = practice_npi
        self.base_url = "https://api.waystar.com/v1"

    async def submit_claim(
        self,
        patient: Patient,
        charges: List[Charge],
        diagnoses: List[str]
    ) -> Dict:
        """Submit professional claim (837P)"""

        # Waystar handles 837 generation from structured data
        claim_data = {
            "claim_type": "professional",
            "patient": {
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "dob": patient.dob.isoformat(),
                "gender": patient.gender,
                "member_id": patient.insurance_id
            },
            "provider": {
                "npi": self.practice_npi,
                "tax_id": "XX-XXXXXXX"  # Practice TIN
            },
            "payer": {
                "id": patient.insurance_payer
            },
            "charges": [
                {
                    "cpt_code": charge.cpt_code,
                    "units": charge.units,
                    "charge_amount": str(charge.fee),
                    "diagnosis_pointers": [1, 2]  # Links to diagnoses
                }
                for charge in charges
            ],
            "diagnoses": [
                {"code": dx, "qualifier": "ABK"} for dx in diagnoses
            ]
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/claims",
                json=claim_data,
                headers=headers
            )

            if response.status_code == 201:
                return response.json()
            else:
                raise Exception(f"Claim submission failed: {response.text}")
```

### Week 7-8: Claim Dashboard

Build UI to:
- View submitted claims
- Track status (pending, accepted, denied)
- Show clearinghouse responses
- Alert on rejections

## Phase 4: Payment Posting (Week 9-12)

### ERA (835) Processing

Waystar provides webhook for when ERA arrives:

```python
@app.post("/webhooks/waystar/era")
async def process_era(era_data: Dict):
    """Process Electronic Remittance Advice from Waystar"""

    for payment in era_data["payments"]:
        claim_id = payment["claim_id"]
        paid_amount = payment["paid_amount"]
        adjustments = payment["adjustments"]

        # Post payment to patient account
        # Update claim status
        # Handle denials/adjustments
```

## Simplified Roadmap Summary

| Phase | Weeks | Workflow | Value |
|-------|-------|----------|-------|
| 1 | 1-2 | Eligibility Check | Saves 10 min/day |
| 2 | 3-4 | Charge Posting | Organizes encounter billing |
| 3 | 5-8 | Claim Submission | Automates claims |
| 4 | 9-12 | Payment Posting | Automates reconciliation |
| 5 | 13-16 | Denials | Reduces lost revenue |
| 6 | 17-20 | Appeals & AR | Complete RCM loop |

## What Files to Keep vs. Delete

### Keep (Reuse from Voice Agent)
```
src/core/
  ├── security.py        → Encryption, PHI protection
  ├── compliance.py      → Audit logging
  └── __init__.py

src/workflows/
  └── temporal_client.py → For denial follow-ups later

.env.example             → Modify for RCM APIs
requirements.txt         → Update dependencies
docker-compose.yml       → Keep PostgreSQL/Redis
```

### Delete (Not Applicable)
```
app.py                   → Voice recording UI
medical_scribe.py        → Transcription
intent_router.py         → Voice intents
test_utterances.txt      → Voice testing
READY_TO_TEST.md        → Voice agent docs
```

### Create New
```
src/rcm/
  ├── eligibility.py     → Eligible API
  ├── claims.py          → Waystar claims
  ├── payments.py        → ERA processing
  ├── models.py          → SQLAlchemy models
  └── schemas.py         → Pydantic validation

frontend/
  ├── src/
  │   ├── components/
  │   │   ├── EligibilityCheck.tsx
  │   │   ├── ChargeEntry.tsx
  │   │   └── ClaimDashboard.tsx
  │   └── App.tsx
  └── package.json

migrations/
  ├── 001_initial_schema.sql
  ├── 002_cpt_codes.sql
  └── 003_claims.sql
```

## Updated requirements.txt

```txt
# Core
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0

# Database
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
alembic==1.12.1

# APIs
httpx==0.25.2
pydantic==2.5.0

# Security (keep from voice agent)
cryptography==41.0.7
python-jose[cryptography]==3.3.0

# Workflows (keep for Phase 5)
temporallib==1.3.0

# Task queue
celery==5.3.4
redis==5.0.1

# Utilities
loguru==0.7.2
```

## Next Immediate Steps

1. **Today**: Decide if you're committing to RCM pivot
2. **Tomorrow**: Sign up for Eligible API developer account
3. **Day 3**: Create database schema for patients + eligibility checks
4. **Day 4-5**: Build eligibility check endpoint
5. **Day 6-7**: Build simple UI and test with real data
6. **Week 2**: Show to 3 billing managers, get feedback
7. **Week 3**: Go/No-Go decision based on feedback

## The Critical Question

**Can you get 5 medical practices to commit to a 3-month pilot?**

If yes → Build the MVP in 2 weeks and start the pilot
If no → Don't build, you'll waste 6 months

---

**This is Occam's Razor: Start with ONE workflow, prove value, then expand.**
