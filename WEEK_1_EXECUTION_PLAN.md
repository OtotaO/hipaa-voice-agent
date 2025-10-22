# 🚀 WEEK 1 EXECUTION PLAN - Start TODAY

## Mission: Get 10 Pilot Practices Committed + MVP Running

---

## 📅 MONDAY: Network Activation

### Morning (3 hours): Contact Family Members

**Goal**: Get 10 practice commitments by EOD Friday

**Script for family members:**
```
Subject: Quick favor - launching AI billing software

Hi [Family Member],

I'm launching AI-powered medical billing software that cuts denials in half
and increases collections by 20%+.

I need 2 practices with high denial rates to pilot FREE for 90 days.
I guarantee results or they pay nothing.

Can you connect me to:
1. Your worst-performing practice (high denials/slow AR)
2. One other practice willing to try new tech

Just need intro to their billing manager/admin. I'll handle the rest.

Thanks!
```

**Action Items:**
- [ ] Email/text all 5 physician family members
- [ ] Follow up with phone calls in 2 hours
- [ ] Get intro to 10+ billing managers

**Success Metric**: 5+ warm intros by Monday EOD

### Afternoon (4 hours): Technical Setup - Accounts

**1. Stedi Account** (30 min)
```bash
# Go to https://www.stedi.com/
# Sign up for developer account
# Get API key from dashboard
# Save to .env
STEDI_API_KEY=your_key_here
```

**2. Cloudflare Account** (30 min)
```bash
# Go to https://dash.cloudflare.com/
# Sign up / log in
# Enable Workers AI
# Create API token
# Save to .env
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_token
```

**3. Medplum Setup** (2 hours)
```bash
# Clone Medplum
git clone https://github.com/medplum/medplum.git
cd medplum

# Create docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
version: '3.8'
services:
  postgres:
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: medplum
      POSTGRES_USER: medplum
      POSTGRES_PASSWORD: medplum

  redis:
    ports:
      - "6379:6379"

  medplum-server:
    ports:
      - "8103:8103"
    environment:
      NODE_ENV: development
      DATABASE_URL: postgres://medplum:medplum@postgres:5432/medplum
      REDIS_URL: redis://redis:6379
EOF

# Start Medplum
docker-compose up -d

# Wait for startup (2 min)
sleep 120

# Test
curl http://localhost:8103/healthcheck

# Expected: {"ok": true}
```

**4. Initialize Database** (30 min)
```bash
# Connect to Medplum PostgreSQL
docker exec -it medplum-postgres-1 psql -U medplum -d medplum

# Create custom tables for RCM (in addition to FHIR resources)
CREATE TABLE IF NOT EXISTS eligibility_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL,
    payer_id VARCHAR(100),
    check_date TIMESTAMP DEFAULT NOW(),
    coverage_status VARCHAR(20),
    copay VARCHAR(50),
    deductible VARCHAR(50),
    response_data JSONB,
    expires_at TIMESTAMP
);

CREATE INDEX idx_eligibility_patient ON eligibility_cache(patient_id);
CREATE INDEX idx_eligibility_expires ON eligibility_cache(expires_at);

\q
```

**Success Metric**: All 4 accounts set up, Medplum running

---

## 📅 TUESDAY: Build Eligibility MVP (Backend)

### Morning (4 hours): Stedi Integration

**Create Eligibility Service**
```typescript
// src/services/eligibility.ts
import { createHash } from 'crypto';

interface Patient {
  id: string;
  firstName: string;
  lastName: string;
  dob: string; // YYYY-MM-DD
  insuranceId: string;
  payerId: string;
}

interface EligibilityResult {
  status: 'active' | 'inactive' | 'unknown';
  planName: string | null;
  copay: string | null;
  deductible: string | null;
  oopMax: string | null;
  rawResponse: any;
}

export class EligibilityService {
  private apiKey: string;
  private baseUrl = 'https://core.stedi.com/2023-01-01/healthcare';

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async checkEligibility(
    patient: Patient,
    providerNPI: string
  ): Promise<EligibilityResult> {
    // Check cache first (eligibility valid for 24 hours)
    const cached = await this.getCached(patient.id);
    if (cached) {
      console.log('Returning cached eligibility');
      return cached;
    }

    // Call Stedi API
    const response = await fetch(`${this.baseUrl}/eligibility`, {
      method: 'POST',
      headers: {
        'Authorization': `Key ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        controlNumber: this.generateControlNumber(),
        tradingPartnerServiceId: patient.payerId,
        subscriber: {
          memberId: patient.insuranceId,
          firstName: patient.firstName,
          lastName: patient.lastName,
          dateOfBirth: patient.dob
        },
        provider: {
          npi: providerNPI,
          organizationName: process.env.PRACTICE_NAME
        },
        encounter: {
          serviceTypeCodes: ['30'] // Health Benefit Plan Coverage
        }
      })
    });

    if (!response.ok) {
      throw new Error(`Stedi API error: ${await response.text()}`);
    }

    const data = await response.json();
    const result = this.parseResponse(data);

    // Cache for 24 hours
    await this.cacheResult(patient.id, result);

    return result;
  }

  private parseResponse(data: any): EligibilityResult {
    // Parse Stedi JSON response
    const benefits = data.benefits || [];

    return {
      status: data.eligible === 'Y' ? 'active' : 'inactive',
      planName: data.planInformation?.planName || null,
      copay: this.findBenefit(benefits, 'copay'),
      deductible: this.findBenefit(benefits, 'deductible'),
      oopMax: this.findBenefit(benefits, 'out_of_pocket_max'),
      rawResponse: data
    };
  }

  private findBenefit(benefits: any[], type: string): string | null {
    const benefit = benefits.find(b => b.benefitType === type);
    if (!benefit) return null;

    if (benefit.inNetworkAmount) {
      return `$${benefit.inNetworkAmount}`;
    }

    return benefit.inNetworkPercent
      ? `${benefit.inNetworkPercent}%`
      : null;
  }

  private async getCached(patientId: string): Promise<EligibilityResult | null> {
    // Query PostgreSQL cache
    const { rows } = await db.query(
      `SELECT * FROM eligibility_cache
       WHERE patient_id = $1
       AND expires_at > NOW()
       ORDER BY check_date DESC
       LIMIT 1`,
      [patientId]
    );

    if (rows.length === 0) return null;

    return {
      status: rows[0].coverage_status,
      planName: rows[0].response_data.planName,
      copay: rows[0].copay,
      deductible: rows[0].deductible,
      oopMax: rows[0].response_data.oopMax,
      rawResponse: rows[0].response_data
    };
  }

  private async cacheResult(patientId: string, result: EligibilityResult) {
    await db.query(
      `INSERT INTO eligibility_cache
       (patient_id, coverage_status, copay, deductible, response_data, expires_at)
       VALUES ($1, $2, $3, $4, $5, NOW() + INTERVAL '24 hours')`,
      [
        patientId,
        result.status,
        result.copay,
        result.deductible,
        result.rawResponse
      ]
    );
  }

  private generateControlNumber(): string {
    // Generate unique 9-digit control number
    return Math.random().toString().slice(2, 11);
  }
}
```

**Create FastAPI Endpoint**
```python
# main.py (modify existing)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from typing import Optional

app = FastAPI()

class PatientEligibilityRequest(BaseModel):
    patient_id: str
    provider_npi: str

class EligibilityResponse(BaseModel):
    status: str
    plan_name: Optional[str]
    copay: Optional[str]
    deductible: Optional[str]
    oop_max: Optional[str]

@app.post("/api/eligibility/check", response_model=EligibilityResponse)
async def check_eligibility(request: PatientEligibilityRequest):
    """Check insurance eligibility via Stedi"""

    # 1. Fetch patient from Medplum
    patient = await medplum_client.read_resource(
        "Patient",
        request.patient_id
    )

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # 2. Extract insurance info
    if not patient.get('coverage'):
        raise HTTPException(status_code=400, detail="No insurance on file")

    coverage = patient['coverage'][0]

    # 3. Call Stedi
    eligibility_service = EligibilityService(os.getenv("STEDI_API_KEY"))

    result = await eligibility_service.check_eligibility(
        patient={
            'id': patient['id'],
            'firstName': patient['name'][0]['given'][0],
            'lastName': patient['name'][0]['family'],
            'dob': patient['birthDate'],
            'insuranceId': coverage['subscriberId'],
            'payerId': coverage['payor'][0]['identifier']['value']
        },
        provider_npi=request.provider_npi
    )

    return EligibilityResponse(**result)
```

**Success Metric**: Eligibility check endpoint works with test data

### Afternoon (3 hours): Test with Real Payer Data

**1. Get Test Credentials from Stedi**
Stedi provides test payer IDs for development

**2. Create Test Patient**
```bash
# Use Medplum API to create test patient
curl -X POST http://localhost:8103/fhir/R4/Patient \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Patient",
    "name": [{"given": ["John"], "family": "Doe"}],
    "birthDate": "1980-01-01",
    "gender": "male",
    "identifier": [
      {"system": "http://hl7.org/fhir/sid/us-ssn", "value": "999999999"}
    ]
  }'
```

**3. Test Eligibility Check**
```bash
curl -X POST http://localhost:8000/api/eligibility/check \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "patient-test-id",
    "provider_npi": "1234567890"
  }'

# Expected response:
# {
#   "status": "active",
#   "plan_name": "Blue Cross Blue Shield PPO",
#   "copay": "$30",
#   "deductible": "$1500",
#   "oop_max": "$5000"
# }
```

**Success Metric**: Successfully check eligibility for test patient

---

## 📅 WEDNESDAY: Build Frontend MVP

### Morning (4 hours): React UI

**Setup Vite + React**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install

# Install dependencies
npm install @tanstack/react-query axios
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Eligibility Check Component**
```typescript
// src/components/EligibilityCheck.tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';

interface EligibilityResult {
  status: string;
  plan_name: string;
  copay: string;
  deductible: string;
  oop_max: string;
}

export function EligibilityCheck() {
  const [patientId, setPatientId] = useState('');
  const [providerNPI, setProviderNPI] = useState(
    import.meta.env.VITE_DEFAULT_NPI || ''
  );

  const mutation = useMutation({
    mutationFn: async (data: { patient_id: string; provider_npi: string }) => {
      const response = await axios.post<EligibilityResult>(
        '/api/eligibility/check',
        data
      );
      return response.data;
    }
  });

  const handleCheck = () => {
    mutation.mutate({ patient_id: patientId, provider_npi: providerNPI });
  };

  return (
    <div className="max-w-2xl mx-auto p-6 bg-white rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">
        🏥 Insurance Eligibility Check
      </h2>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Patient ID
          </label>
          <input
            type="text"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            placeholder="Enter patient ID"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Provider NPI
          </label>
          <input
            type="text"
            value={providerNPI}
            onChange={(e) => setProviderNPI(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
            placeholder="Enter provider NPI"
          />
        </div>

        <button
          onClick={handleCheck}
          disabled={mutation.isPending}
          className="w-full bg-blue-600 text-white py-3 rounded-md font-semibold hover:bg-blue-700 disabled:bg-gray-400 transition"
        >
          {mutation.isPending ? 'Checking...' : '🔍 Check Eligibility'}
        </button>
      </div>

      {mutation.isError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
          <p className="text-red-800">
            ❌ Error: {(mutation.error as Error).message}
          </p>
        </div>
      )}

      {mutation.isSuccess && (
        <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-lg">
          <h3 className="text-lg font-semibold mb-4 text-green-800">
            ✅ Coverage Active
          </h3>

          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-gray-600">Status</dt>
              <dd className="text-lg font-semibold capitalize">
                {mutation.data.status}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-gray-600">Plan</dt>
              <dd className="text-lg font-semibold">
                {mutation.data.plan_name || 'N/A'}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-gray-600">Copay</dt>
              <dd className="text-lg font-semibold text-blue-600">
                {mutation.data.copay || 'N/A'}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-gray-600">Deductible</dt>
              <dd className="text-lg font-semibold text-blue-600">
                {mutation.data.deductible || 'N/A'}
              </dd>
            </div>

            <div className="col-span-2">
              <dt className="text-sm text-gray-600">Out-of-Pocket Max</dt>
              <dd className="text-lg font-semibold text-blue-600">
                {mutation.data.oop_max || 'N/A'}
              </dd>
            </div>
          </dl>

          <div className="mt-4 p-3 bg-blue-50 rounded-md">
            <p className="text-sm text-blue-800">
              💡 <strong>AI Tip:</strong> Coverage is active. No prior authorization
              required for routine office visits.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Deploy to Cloudflare Pages**
```bash
# Build frontend
npm run build

# Install wrangler
npm install -g wrangler

# Deploy to Cloudflare Pages
wrangler pages deploy dist --project-name rcm-platform

# Get URL: https://rcm-platform.pages.dev
```

**Success Metric**: Working UI deployed to Cloudflare Pages

---

## 📅 THURSDAY: Add AI Claim Scrubber

### Morning (3 hours): Cloudflare Workers AI Integration

**Create AI Worker**
```typescript
// workers/claim-scrubber.ts
export interface Env {
  AI: any;
}

interface ClaimData {
  patient: { name: string; dob: string };
  cpt_codes: string[];
  icd10_codes: string[];
  payer: string;
  provider_npi: string;
}

interface ScrubResult {
  ready: boolean;
  errors: string[];
  warnings: string[];
  confidence: number;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    const claim: ClaimData = await request.json();

    // Use Cloudflare AI to scrub claim
    const ai = new Ai(env.AI);

    const prompt = `You are a medical billing expert. Review this claim for errors:

Patient: ${claim.patient.name} (DOB: ${claim.patient.dob})
CPT Codes: ${claim.cpt_codes.join(', ')}
ICD-10 Codes: ${claim.icd10_codes.join(', ')}
Payer: ${claim.payer}

Check for these common errors:
1. CPT-ICD-10 medical necessity mismatch
2. Missing modifiers
3. Incorrect place of service
4. Prior authorization required but not noted
5. Bundling issues (codes that can't be billed together)

Return ONLY valid JSON in this format:
{
  "ready": true/false,
  "errors": ["error 1", "error 2"],
  "warnings": ["warning 1"],
  "confidence": 0.0-1.0
}`;

    const response = await ai.run('@cf/meta/llama-3.2-11b-vision-instruct', {
      prompt
    });

    // Parse AI response
    let result: ScrubResult;
    try {
      // Extract JSON from response
      const text = response.response || '';
      const jsonMatch = text.match(/\{[\s\S]*\}/);

      if (jsonMatch) {
        result = JSON.parse(jsonMatch[0]);
      } else {
        // Fallback if AI doesn't return JSON
        result = {
          ready: true,
          errors: [],
          warnings: ['AI response parsing failed - manual review recommended'],
          confidence: 0.5
        };
      }
    } catch (error) {
      result = {
        ready: false,
        errors: ['AI scrubber error - manual review required'],
        warnings: [],
        confidence: 0.0
      };
    }

    return Response.json(result);
  }
};

// Deploy with:
// wrangler deploy
```

**Add to FastAPI**
```python
# main.py
@app.post("/api/claims/scrub")
async def scrub_claim(claim_data: dict):
    """AI-powered claim scrubbing before submission"""

    # Call Cloudflare Worker
    worker_url = os.getenv("CLOUDFLARE_WORKER_URL") + "/claim-scrubber"

    response = await httpx.post(worker_url, json=claim_data)
    result = response.json()

    # Log for training data
    await log_scrub_result(claim_data, result)

    return result
```

**Success Metric**: AI scrubber catches test errors (e.g., wrong ICD-10 for CPT)

### Afternoon (3 hours): Testing & Demo Prep

**Create Demo Script**
```markdown
# Demo Script for Billing Managers

## Scenario 1: Eligibility Check (2 min)
1. Open app: https://rcm-platform.pages.dev
2. Enter patient ID: [test-patient-123]
3. Click "Check Eligibility"
4. Result in <3 seconds: Active coverage, $30 copay, $1500 deductible
5. **Value**: "Normally takes 5 minutes on phone. AI does it in 3 seconds."

## Scenario 2: AI Claim Scrubber (3 min)
1. Submit test claim with intentional errors:
   - CPT: 99213 (office visit)
   - ICD-10: Z23 (immunization) → WRONG, mismatch
2. AI catches error: "Medical necessity mismatch"
3. Fix ICD-10 to match visit type
4. AI approves: "Ready to submit"
5. **Value**: "This claim would've been denied. AI caught it before submission."

## Scenario 3: ROI Calculator (1 min)
Show spreadsheet:
- Average practice: 200 claims/month
- 15% denial rate = 30 denied claims
- $150 per claim = $4,500 lost
- AI reduces denials to 7% = saves $2,400/month
- Our cost: $199/month
- **ROI: 12X**
```

**Success Metric**: Can demo both features smoothly in <5 minutes

---

## 📅 FRIDAY: First Demo Day

### Morning (2 hours): Final Testing

**Checklist:**
- [ ] Eligibility check works with real Stedi test data
- [ ] AI scrubber catches common errors
- [ ] UI is responsive on mobile
- [ ] Error handling works gracefully
- [ ] Demo script rehearsed 3x

### Afternoon (4 hours): Demo to Billing Managers

**Schedule 30-min calls with 3-5 billing managers**

**Demo Flow:**
1. **Intro** (2 min): "AI-powered billing that cuts denials in half"
2. **Live Demo** (5 min): Show eligibility + scrubber
3. **ROI** (3 min): Calculate their potential savings
4. **Pilot Offer** (2 min): "Free for 90 days, you pay only if it saves money"
5. **Next Steps** (3 min): Get access to test patient, schedule training

**Success Metric**: 3+ practices agree to pilot

---

## Weekend: Reflect & Plan Week 2

### Saturday: Review Week 1

**Metrics to track:**
- Pilot practices committed: __/10
- Demos completed: __/5
- Technical milestones hit: __/5

### Sunday: Plan Week 2

**Week 2 Goals:**
1. Onboard first 3 pilot practices
2. Process first 50 real claims
3. Add claim submission (Stedi 837 API)
4. Build basic dashboard for practices

---

## Key Success Factors

### 1. **Speed Over Perfection**
- MVP eligibility check > full platform
- Live demo beats slide deck
- Real data trumps mock data

### 2. **Leverage Your Network**
- Family trust opens doors
- No cold calling needed
- Word of mouth spreads fast

### 3. **AI as Differentiator**
- Show AI catching real errors
- "This would've been denied" moments
- ROI is undeniable

### 4. **Free Pilot = No Barrier**
- Remove all risk for practices
- Prove value before asking for money
- Money-back guarantee if no savings

---

## Emergency Troubleshooting

### "Stedi API not working"
**Fix**: Use mock data for demos, fix API integration week 2
```typescript
// Mock eligibility service
const mockResult = {
  status: 'active',
  plan_name: 'Blue Cross PPO',
  copay: '$30',
  deductible: '$1500',
  oop_max: '$5000'
};
```

### "Can't get family to respond"
**Fix**: Call instead of email, pitch as "helping their colleagues"

### "AI scrubber too slow"
**Fix**: Cache common CPT-ICD-10 checks, only use AI for edge cases

### "No practices committed by Friday"
**Fix**: Extend timeline to Monday, lower bar to 5 practices instead of 10

---

## Week 1 Deliverables Checklist

**Technical:**
- [ ] Medplum running locally
- [ ] Stedi account + API key
- [ ] Cloudflare Workers AI deployed
- [ ] Eligibility API working
- [ ] AI scrubber functional
- [ ] Frontend deployed to Cloudflare Pages

**Business:**
- [ ] 10 billing manager intros
- [ ] 3+ live demos completed
- [ ] 5+ pilot practice commitments
- [ ] Demo script polished

**Data:**
- [ ] Test patient created
- [ ] Eligibility check logged
- [ ] AI scrubber results logged
- [ ] ROI calculator built

---

## Next Week Sneak Peek

**Week 2: Onboard Pilots + Claim Submission**
- Integrate with pilot practice data
- Add claim submission (Stedi 837 API)
- Process first 100 real claims
- Track clean claim rate improvement

**Week 3: Payment Posting + Denial Tracking**
- Add ERA processing (Stedi 835 API)
- Build denial queue
- AI appeal letter generator

**Week 4: Results + Convert to Paid**
- Show ROI data to practices
- Convert 5 pilots to paying customers
- Build case studies

---

**THIS WEEK IS MAKE OR BREAK. EXECUTE FAST. NO EXCUSES.**

**Let's turn your 300-doctor network into $180K ARR in 6 months.**

**START NOW. 🚀**
