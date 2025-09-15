# 🎯 No-Hardware Implementation Checklist

## Profile: Built-in Mic + Speakers (Half-Duplex, Speaker-Safe)

### ✅ Completed Files
- `requirements_merged_no_hardware.yaml` - Full requirements with no-hardware overrides
- `pilot_acceptance_tests.jsonl` - 13 acceptance tests including speaker-safe scenarios
- `.env.no_hardware` - Environment configuration for no-hardware profile

## 🔧 Implementation Checklist

### Phase 1: Core Audio Pipeline (Week 1)

#### Push-to-Talk Implementation
- [ ] Implement keyboard PTT handler (Shift key default)
- [ ] Visual PTT indicator (recording light)
- [ ] PTT state management (pressed/released)
- [ ] Prevent ambient recording when PTT not active
- [ ] Test with multiple browsers (Chrome, Edge, Safari)

#### Half-Duplex Audio Control
- [ ] Implement TTS playback detection
- [ ] Block ASR during TTS playback
- [ ] Queue ASR attempts during TTS
- [ ] Show "System speaking..." indicator
- [ ] Test echo scenarios with built-in speakers

#### Speaker-Safe PHI Protection
- [ ] Implement PHI detector for TTS queue
- [ ] Block names/MRNs/DOBs from speaker output
- [ ] Show blocked PHI on screen only
- [ ] Log speaker-safe events for audit
- [ ] Implement "read PHI aloud" override command

### Phase 2: Safety Features (Week 2)

#### Confirmation System
- [ ] Medication confirmation flow
- [ ] Order confirmation flow
- [ ] Refill confirmation with last-visit check
- [ ] Visual + audio confirmation prompts
- [ ] Timeout handling (5 second default)

#### Provider Mode Toggle
- [ ] "Provider mode" voice command
- [ ] Visual indicator for mode status
- [ ] PHI readback allowed in provider mode
- [ ] Auto-revert to patient mode after timeout
- [ ] Audit mode switches

### Phase 3: Intent Processing (Week 3)

#### Core Intents (from intents_ranked.json)
- [ ] CreateSOAPNote - Ambient scribe
- [ ] AddToNoteSection - Section updates
- [ ] GenerateCodes - ICD-10/CPT
- [ ] RetrieveLabResults - Lab lookups
- [ ] RetrieveVitals - Vital trends
- [ ] CheckAllergies - Allergy verification
- [ ] GenerateAVS - Patient summaries
- [ ] CalculateMDM - E&M levels

#### Entity Resolution
- [ ] Medication name/dose/route/frequency
- [ ] Lab test names → LOINC codes
- [ ] Temporal reasoning (last 3, since July)
- [ ] Section detection (HPI, ROS, PE, etc.)

### Phase 4: Integration & Testing (Week 4)

#### Acceptance Testing
- [ ] Run all 13 tests from pilot_acceptance_tests.jsonl
- [ ] T001-T003: Outpatient URI scenario
- [ ] T004-T005: Inpatient rounding
- [ ] T006-T007: Cardiology follow-up
- [ ] T008-T009: Telehealth
- [ ] T010: MDM calculation
- [ ] T011-T012: Speaker-safe PHI
- [ ] T013: Echo control

#### Performance Validation
- [ ] ASR WER ≤ 8% with built-in mic
- [ ] E2E latency p95 ≤ 1700ms
- [ ] Confirmation response ≤ 5s
- [ ] No echo/feedback with speakers

## 📊 Success Metrics

### Must Pass (Go/No-Go)
- [ ] PTT works reliably
- [ ] No PHI over speakers (unless explicit)
- [ ] Half-duplex prevents echo
- [ ] All confirmations fire correctly
- [ ] Latency acceptable (<2s perceived)

### Should Pass (Quality)
- [ ] WER ≤ 8% in quiet room
- [ ] Provider satisfaction ≥ 7/10
- [ ] Time saved ≥ 5 min/encounter
- [ ] <3 corrections per note

### Nice to Have
- [ ] Multi-browser support
- [ ] Mobile browser support
- [ ] Background noise handling

## 🚀 Deployment Steps

### 1. Environment Setup
```bash
# Use no-hardware configuration
cp .env.no_hardware .env

# Verify settings
grep "PTT_REQUIRED" .env         # Should be true
grep "SPEAKER_SAFE" .env         # Should be true
grep "BARGE_IN" .env             # Should be false
```

### 2. Test Audio Pipeline
```python
# Run audio tests
python test_audio_pipeline.py --profile no_hardware

# Should test:
# - PTT activation
# - Half-duplex blocking
# - Speaker-safe PHI blocking
```

### 3. Run Acceptance Suite
```python
# Run acceptance tests
python run_acceptance_tests.py pilot_acceptance_tests.jsonl

# Expected: 13/13 pass
```

### 4. Pilot Deployment
```bash
# Deploy with monitoring
python app.py --config .env.no_hardware --monitor

# Watch for:
# - Echo events
# - PHI blocks
# - Confirmation timeouts
```

## ⚠️ Known Limitations

### Audio Quality
- Built-in mics pick up room noise
- Speaker output can echo without AEC
- Multiple speakers confuse diarization

### User Experience
- PTT adds friction vs always-on
- Half-duplex feels less natural
- Can't interrupt system

### Workarounds
- Position laptop away from noise
- Use PTT to control recording
- Wait for TTS to finish before speaking

## 📝 Training Points for Providers

### Essential Training (5 min)
1. **Hold Shift to talk** - Must hold while speaking
2. **Wait for system to finish** - Can't interrupt
3. **PHI won't play on speakers** - Look at screen
4. **Say "provider mode"** - To enable PHI audio
5. **Confirm medications** - Say "yes" or "no"

### Quick Reference Card
```
QUICK COMMANDS:
- Hold SHIFT → Talk
- "Provider mode" → Enable PHI audio
- "Patient mode" → Disable PHI audio
- "Read PHI aloud" → Override protection
- "Yes/No" → Confirm actions

TROUBLESHOOTING:
- Echo? → Move laptop, lower volume
- Not hearing? → Check screen for PHI
- Too slow? → Speak, then release Shift
```

## 🎯 Go-Live Criteria

### Technical Readiness
- [ ] All 13 acceptance tests pass
- [ ] Performance metrics met
- [ ] No critical bugs in pilot

### Clinical Readiness
- [ ] 3+ providers trained
- [ ] Quick reference cards distributed
- [ ] Support channel ready

### Compliance
- [ ] HIPAA officer approval
- [ ] Audit logging verified
- [ ] PHI protection confirmed

## Next Steps After Go-Live

1. **Week 1**: Monitor echo/feedback issues
2. **Week 2**: Gather provider feedback
3. **Week 3**: Tune ASR for environment
4. **Week 4**: Decide on headset upgrade

---

**Ready to implement?** Start with Phase 1 (PTT + Half-Duplex) and validate audio quality before proceeding.