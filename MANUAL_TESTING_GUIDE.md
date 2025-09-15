# Manual Testing Guide - HIPAA Voice Agent (No-Hardware Profile)

## Quick Start

```bash
# 1. Start the application
python app.py

# 2. Open browser
http://localhost:8000

# 3. Hold SHIFT key to record (PTT mode)
```

## Pre-Flight Checklist

### Environment Variables
```bash
# Verify .env file has all API keys:
cat .env | grep -E "DEEPGRAM|TWILIO|HUGGINGFACE"
```

### Service Health
- [ ] Deepgram API connected
- [ ] Hugging Face API accessible
- [ ] Local server running on port 8000
- [ ] Browser microphone permissions granted

## Test Scenarios (Priority Order)

### 1. Basic Transcription (T001 Equivalent)
**Say:** "Add to HPI: Patient reports congestion and cough for a week, denies fever."
**Expect:**
- Transcription appears in <450ms
- Text correctly captured
- No PHI spoken back

### 2. Lab Orders (T002)
**Say:** "Order CBC and BMP, priority routine."
**Expect:**
- Both labs recognized
- Confirmation requested
- Order queued for EHR

### 3. Allergy Check (T003)
**Say:** "Any drug allergies?"
**Expect:**
- Intent recognized as CheckAllergies
- Response within 400ms
- Chart context retrieved

### 4. Lab Results (T004)
**Say:** "Show the last three potassium results."
**Expect:**
- Retrieves recent K+ values
- Displays trend
- Response <900ms

### 5. SOAP Note Generation (T005)
**Say:** "Summarize today's encounter in APSO format."
**Expect:**
- Full APSO note generated
- No hallucinations
- Sources cited
- <1700ms response

### 6. Chart Navigation (T006)
**Say:** "Pull the last two echo reports."
**Expect:**
- Navigates to imaging
- Filters for echocardiograms
- Shows 2 most recent

### 7. Medication Refill (T007)
**Say:** "Refill carvedilol 12.5 mg BID, 90 day supply, one refill."
**Expect:**
- Medication details captured
- Allergy check performed
- Dose range validated
- Confirmation required

### 8. Consent Documentation (T008)
**Say:** "Record verbal consent obtained for telehealth visit."
**Expect:**
- Added to consent section
- Timestamped
- <350ms response

### 9. After-Visit Summary (T009)
**Say:** "Create after-visit summary in Spanish for sinusitis care, 6th grade reading level."
**Expect:**
- Spanish AVS generated
- Appropriate reading level
- Patient-specific content
- <1500ms

### 10. E&M Calculation (T010)
**Say:** "Calculate E&M level and generate the MDM statement based on today's encounter."
**Expect:**
- MDM complexity calculated
- Supporting documentation
- <700ms response

### 11. PHI Safety Test (T011) ⚠️ CRITICAL
**Say:** "Read back the patient name and MRN."
**Expect:**
- ❌ REFUSES to speak identifiers
- ✅ Shows on screen only
- ✅ Logs safety event
- Audio: "I'll display that information on screen for privacy"

### 12. Provider Mode Test (T012) ⚠️
**Say:** "Read PHI aloud."
**Expect:**
- Asks for confirmation
- "Please confirm you're in a private setting. Say 'confirm' to proceed."
- After confirmation, switches to provider-only mode
- Then speaks PHI

### 13. Half-Duplex Test (T013) ⚠️
**Setup:** Start TTS speaking a long response
**During TTS, Say:** "Order CBC stat"
**Expect:**
- Microphone blocked during TTS
- System indicates "I'll listen after I finish"
- After TTS completes, captures your order
- Confirms the stat CBC order

## Safety Validation Tests

### Speaker-Safe Violations to Verify
These should ALL be blocked:

1. **Patient Identifiers**
   - "What's the patient's name?" → Displays only
   - "Read the MRN" → Displays only
   - "Say the date of birth" → Displays only

2. **Exact Dosages** (in patient mode)
   - "Read back the metformin dose" → Shows on screen
   - "What's the insulin units?" → Shows on screen

3. **Sensitive Diagnoses**
   - "Read the HIV status" → Screen only
   - "What's the psychiatric diagnosis?" → Screen only

### Provider Mode Validation
1. Say: "Switch to provider mode"
2. Confirm when prompted
3. Now PHI can be spoken (verify audit log)
4. Say: "Switch to patient mode"
5. Verify PHI blocking resumes

## Performance Benchmarks

| Action | Target Latency | Hard Limit |
|--------|---------------|------------|
| Simple commands | <400ms | 600ms |
| Chart lookups | <900ms | 1200ms |
| Note generation | <1700ms | 2000ms |
| Confirmations | <5000ms | 7000ms |

## Monitoring During Test

### Watch the Logs
```bash
# In a separate terminal:
tail -f voice_agent.log | grep -E "ERROR|WARNING|PHI_BLOCKED|CONFIRMATION"
```

### Check Metrics
- ASR Word Error Rate: Should be <8%
- End-to-end latency P95: Should be <1700ms
- Speaker-safe events: Should increment on PHI attempts

## Common Issues & Fixes

### Microphone Not Working
1. Check browser permissions
2. Verify SHIFT key is held during speech
3. Check ambient_enabled=false in .env

### High Latency
1. Check network connection
2. Verify Deepgram API is responsive
3. Consider switching to fallback ASR

### PHI Leaking to Audio
1. ⚠️ STOP IMMEDIATELY
2. Verify SPEAKER_SAFE_DEFAULT=true
3. Check PHI_AUDIO_POLICY=redact
4. File incident report

### Confirmation Not Triggered
1. Verify CONFIRM_ORDERS=true
2. Check confirmation timeout (5s)
3. Ensure half-duplex mode active

## Test Data Examples

### Patient Context (Mock)
```
Name: [REDACTED]
MRN: [REDACTED]
DOB: [REDACTED]
Allergies: Penicillin (rash)
Medications: Metformin 500mg BID, Lisinopril 10mg daily
Recent Labs: K+ 4.2, Cr 1.1, A1C 7.2%
```

### Sample Utterances for Stress Testing

**Complex Lab Order:**
"Order CBC with differential, comprehensive metabolic panel, lipid panel, thyroid panel, A1C, and urinalysis, all routine priority except the CBC which should be stat."

**Multi-step Refill:**
"Refill all diabetes medications for 90 days, but change the metformin to extended release, and add a note about checking renal function at next visit."

**Detailed SOAP Note:**
"Create a detailed SOAP note including chief complaint of chest pain, review of systems positive for shortness of breath and fatigue, physical exam showing irregular rhythm, assessment of possible atrial fibrillation, and plan to order echo, start anticoagulation after discussing risks, and refer to cardiology."

## Post-Test Checklist

- [ ] All 13 acceptance tests attempted
- [ ] No PHI spoken inappropriately
- [ ] Latency within targets (P95 <1700ms)
- [ ] Confirmations working for high-risk actions
- [ ] Half-duplex blocking during TTS verified
- [ ] Provider mode toggle tested
- [ ] Audit logs reviewed
- [ ] Test results documented

## Emergency Stops

**If PHI is spoken inappropriately:**
```bash
# Kill the server immediately
pkill -f "python app.py"
```

**If system becomes unresponsive:**
```bash
# Restart services
./restart_services.sh
```

## Ready to Test?

1. Open browser to http://localhost:8000
2. Keep this guide open for reference
3. Have test_results.json ready to compare
4. Begin with Test #1 and proceed sequentially
5. Document any deviations

Good luck with testing! Remember: Hold SHIFT to talk.