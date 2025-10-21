# 🏥 Revenue Cycle Management Platform - Occam's Razor Architecture

## Executive Summary

**You're pivoting from a voice documentation tool to a full RCM platform.** This is a 6-12 month rebuild, not an extension of the current codebase.

## The 11 RCM Workflows You Need

### 1. **Eligibility & Benefits Check**
- Real-time insurance verification before appointments
- Coverage details, copay/deductible information
- **API**: Eligible API or pVerify ($0.14/check via Waystar)

### 2. **Data Entry & Patient Demographics**
- Patient registration and demographic capture
- Insurance card scanning (OCR)
- **Tech**: FastAPI + React frontend + OCR.space API

### 3. **Referral & Authorization**
- Prior authorization tracking and submission
- Referral management workflow
- **API**: Availity Prior Auth API

### 4. **Charge Posting**
- Capture CPT/HCPCS codes from encounters
- Link to fee schedules
- **Tech**: Internal database with CPT code library

### 5. **Claim Submission**
- Generate X12 837 professional/institutional claims
- Submit to clearinghouse
- **API**: Waystar or Availity Clearinghouse API

### 6. **Clearinghouse Denials**
- Parse 277CA claim acknowledgment responses
- Identify submission errors (bad NPI, invalid codes)
- **Tech**: Parse clearinghouse API responses

### 7. **Payment Posting**
- Process 835 ERA (Electronic Remittance Advice)
- Auto-post payments to patient accounts
- **API**: Waystar ERA API or Availity

### 8. **Denial Management**
- Track denied claims (reasons: medical necessity, coding, etc.)
- Workflow for corrections and resubmission
- **Tech**: Internal workflow engine + Temporal

### 9. **Secondary Filing**
- Identify secondary payers after primary payment
- Auto-generate secondary claims
- **API**: Waystar crossover claims

### 10. **Accounts Receivable**
- Aging reports (30/60/90/120+ days)
- Patient balance tracking
- **Tech**: PostgreSQL + reporting dashboard

### 11. **Appeal Procedure**
- Track appeal deadlines by payer
- Generate appeal letters with supporting documentation
- **Tech**: Workflow engine + document generation

## Occam's Razor Architecture (Simplest That Works)

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│  Patient Demographics | Eligibility | Claims Dashboard  │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              FastAPI Application Server                 │
│  - REST API endpoints for each RCM workflow             │
│  - Authentication & Authorization (JWT)                 │
│  - HIPAA-compliant audit logging                        │
└─────────────────────┬───────────────────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
│ Eligible  │  │  Waystar  │  │ Availity  │
│    API    │  │Clearinghouse│  │   API     │
│(Eligibility)│ │  (Claims) │  │(Prior Auth)│
└───────────┘  └───────────┘  └───────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
│PostgreSQL │  │  Temporal │  │   Redis   │
│ (Patient/ │  │ (Workflows)│  │  (Cache)  │
│Claims DB) │  │           │  │           │
└───────────┘  └───────────┘  └───────────┘
```

## What You Can Salvage From Current Codebase

### ✅ Reusable (30% of current code)
- **src/core/security.py** - HIPAA compliance, encryption, PHI protection
- **src/core/compliance.py** - Audit logging, data retention
- **src/workflows/temporal_client.py** - Workflow engine for denials/appeals
- **src/services/fhir_client.py** - Could pull patient demographics from EHR
- **FastAPI structure** - HTTP server foundation

### ❌ Not Reusable (70% of current code)
- **app.py** - Voice recording UI (not needed)
- **medical_scribe.py** - Transcription/SOAP notes (different product)
- **intent_router.py** - Voice intent routing (not applicable)
- **Deepgram/Hugging Face integrations** - Wrong domain

## Technology Stack (Occam's Razor)

### Core Infrastructure
- **Backend**: FastAPI (Python) - Keep existing
- **Database**: PostgreSQL - Store patients, claims, payments
- **Cache**: Redis - Session management, API rate limiting
- **Workflows**: Temporal - Manage denial follow-ups, appeal deadlines
- **Queue**: Celery + Redis - Async claim submissions

### Critical APIs (Pick ONE Clearinghouse)
- **Eligibility**: Eligible API or pVerify (~$0.14/check)
- **Clearinghouse**: Waystar ($0.11/claim) OR Availity
  - **Recommendation**: Waystar (98% clean claims rate, modern API)
- **Prior Auth**: Availity Prior Authorization API
- **OCR**: OCR.space or Google Vision API (insurance card scanning)

### Frontend
- **UI Framework**: React + TypeScript
- **Component Library**: Shadcn UI or Ant Design (medical billing UIs)
- **State Management**: React Query (server state) + Zustand (client state)

### Security & Compliance
- **Authentication**: Auth0 or Keycloak (HIPAA-compliant SSO)
- **Encryption**: Keep existing from src/core/security.py
- **Audit Logging**: Keep existing from src/core/compliance.py

## Implementation Roadmap

### **Phase 1: Foundation (Weeks 1-4)**
1. **Database schema** for patients, claims, payments, denials
2. **API integration** with Waystar (eligibility + claims)
3. **Basic UI** for patient demographics and eligibility check
4. **Authentication** and user management

**Deliverable**: Can check eligibility and create patient records

### **Phase 2: Claims Workflow (Weeks 5-8)**
1. **Charge posting** UI (CPT code entry)
2. **837 claim generation** via Waystar API
3. **Claim status tracking** (submitted → pending → paid/denied)
4. **277CA parsing** for submission acknowledgments

**Deliverable**: Can submit professional claims and track status

### **Phase 3: Payments & Denials (Weeks 9-12)**
1. **835 ERA processing** (payment posting automation)
2. **Denial management** workflow (identify, categorize, queue)
3. **Secondary claim** auto-generation
4. **AR aging reports** (30/60/90/120+)

**Deliverable**: Can post payments and manage denials

### **Phase 4: Advanced Features (Weeks 13-20)**
1. **Prior authorization** submission and tracking
2. **Appeal workflows** with Temporal (deadline tracking)
3. **Reporting dashboard** (KPIs: clean claim rate, days in AR, denial rate)
4. **Patient statements** generation

**Deliverable**: Full RCM platform

### **Phase 5: Optimization (Weeks 21-24)**
1. **AI-powered coding** suggestions (from encounter notes)
2. **Automated denial prevention** (scrub claims before submission)
3. **Predictive analytics** (which claims likely to deny)
4. **EHR integration** (Epic, Athena, eClinicalWorks)

**Deliverable**: Production-ready with competitive features

## Honest Cost Estimates

### Development (6 months, 2 developers)
- **Salaries**: $60K × 2 × 6 months = $60K
- **APIs**:
  - Waystar setup: $1,000
  - Eligible API: $500/month × 6 = $3,000
  - OCR.space: $200/month × 6 = $1,200
- **Infrastructure**: AWS ~$500/month × 6 = $3,000
- **Total Development**: ~$67,200

### Ongoing Costs (Per 1,000 Claims/Month)
- **Waystar**: 1,000 × $0.11 = $110/month
- **Eligible**: 1,500 eligibility checks × $0.14 = $210/month
- **ERA processing**: 1,000 × $0.04 = $40/month
- **Infrastructure**: $500/month
- **Total**: ~$860/month per 1,000 claims

### Revenue Model
- **SaaS Pricing**: $500-800/provider/month (industry standard)
- **Transaction Pricing**: 3-5% of collections (alternative model)
- **Breakeven**: ~25-30 providers at $600/month

## Competitive Landscape

### You're Competing Against:
- **Kareo** - $160/provider/month, basic RCM
- **AdvancedMD** - $429/month, full-featured
- **Athenahealth** - 4-6% of collections, enterprise
- **DrChrono** - $199/month, mobile-first

### Your Differentiation:
1. **Modern API-first** architecture (easier integrations)
2. **AI-powered** denial prevention and coding assistance
3. **Transparent pricing** (vs. % of collections)
4. **Better UX** (most RCM software has 2010-era interfaces)

## The Brutal Reality Check

### This Is NOT a 2-Week Project
- **Minimum viable**: 3 months (eligibility + claims + payments)
- **Production-ready**: 6 months (add denials, appeals, reporting)
- **Competitive**: 12 months (add AI, predictive analytics, integrations)

### Regulatory Hurdles
- **HIPAA compliance** (you have foundation from current code)
- **X12 EDI standards** (handled by Waystar/Availity APIs)
- **State regulations** (varies by state for billing practices)
- **Payer contracts** (clearinghouse handles most of this)

### Capital Requirements
- **Development**: $60-100K for MVP
- **Sales/Marketing**: $50K+ to acquire first 50 customers
- **Working capital**: $20K for API costs during growth
- **Total**: $150-200K minimum

## What From Voice Agent Can Transfer

### Keep These Files:
```
src/core/security.py          → PHI protection, encryption
src/core/compliance.py        → Audit logging
src/workflows/temporal_client.py → Denial/appeal workflows
src/services/fhir_client.py   → EHR integration (later phase)
```

### Archive/Delete:
```
app.py                        → Voice recording (wrong product)
medical_scribe.py             → Transcription (wrong domain)
intent_router.py              → Voice intents (not applicable)
test_utterances.txt           → Voice testing (not needed)
```

### New Files Needed:
```
src/rcm/eligibility.py        → Eligible API integration
src/rcm/claims.py             → Waystar claim submission
src/rcm/payments.py           → ERA processing
src/rcm/denials.py            → Denial management workflow
src/rcm/appeals.py            → Appeal procedure tracking
src/rcm/ar.py                 → Accounts receivable reports
```

## Decision Matrix

### Should You Build This?

**✅ Build It If:**
- You have $150K+ in funding or savings
- You have 6-12 months runway
- You have RCM domain expertise or a strong advisor
- You can get 5-10 beta practices committed

**❌ Don't Build If:**
- You need revenue in <6 months
- You don't understand medical billing workflows
- You can't afford ongoing API costs (~$1K-2K/month)
- You're building alone (need at least 2 developers)

## My Recommendation

### Option A: Pivot Fully to RCM (High Risk, High Reward)
1. **Archive** the voice agent code
2. **Focus** 100% on RCM platform
3. **Start** with Phase 1 (eligibility + demographics)
4. **Get** 3-5 beta practices committed upfront
5. **Timeline**: 6 months to revenue

### Option B: Build RCM Voice Assistant (Hybrid)
Keep some voice agent DNA:
- Voice-driven **charge capture** ("Order CBC" → auto-post charge)
- Voice-powered **demographic entry** (reduce data entry)
- AI **coding assistant** (ambient notes → CPT codes)

This differentiates you but adds complexity.

### Option C: Stay Focused on Clinical Documentation
Don't pivot. Double down on the medical scribe:
- Get 5-10 doctors using it THIS MONTH
- Measure time savings (must be >5 min/visit)
- Prove value before building anything else

## Next Steps (If You Choose RCM)

1. **This Week**: Pick ONE workflow (I recommend eligibility checking)
2. **Day 1**: Sign up for Eligible API (has free trial)
3. **Day 2**: Build simple UI: patient demographics → eligibility check
4. **Day 3**: Test with real insurance cards (yours, family, friends)
5. **Week 2**: Show to 3 medical billing managers, get feedback
6. **Week 3**: Decide if their feedback justifies 6 months of work

## The Bottom Line

You have **30% reusable code** (security, compliance, workflows) but need to **rebuild 70%** for RCM. This is a **6-month, $150K minimum** endeavor.

**My advice**: Pick ONE workflow (eligibility or claims), build it in 2 weeks, and validate demand before committing to the full platform.

Building all 11 workflows at once is **not** Occam's Razor—it's a recipe for scope creep and failure.

---

**Ready to commit to RCM? Or should we refocus on the voice agent?**
