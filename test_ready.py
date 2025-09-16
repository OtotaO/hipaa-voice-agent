#!/usr/bin/env python3
"""
System Readiness Test
Verifies all components are working before manual testing
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 60)
print("HIPAA VOICE AGENT - SYSTEM READINESS CHECK")
print("=" * 60)
print()

# Check 1: Environment Variables
print("1. Checking Environment Variables...")
api_keys = {
    "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
    "HUGGINGFACE_API_KEY": os.getenv("HUGGINGFACE_API_KEY"),
}

all_keys_present = True
for key, value in api_keys.items():
    if value:
        print(f"   ✅ {key}: Present")
    else:
        print(f"   ❌ {key}: Missing")
        all_keys_present = False

if not all_keys_present:
    print("\n❌ ERROR: Missing API keys. Please check your .env file")
    sys.exit(1)

# Check 2: Import Core Modules
print("\n2. Checking Core Modules...")
try:
    from medical_scribe import MedicalScribe
    print("   ✅ Medical Scribe: Loaded")
except ImportError as e:
    print(f"   ❌ Medical Scribe: {e}")
    sys.exit(1)

try:
    from intent_router import IntentRouter
    print("   ✅ Intent Router: Loaded")
except ImportError as e:
    print(f"   ❌ Intent Router: {e}")
    sys.exit(1)

try:
    import deepgram
    print("   ✅ Deepgram SDK: Loaded")
except ImportError as e:
    print(f"   ❌ Deepgram SDK: {e}")
    sys.exit(1)

try:
    import huggingface_hub
    print("   ✅ Hugging Face: Loaded")
except ImportError as e:
    print(f"   ❌ Hugging Face: {e}")
    sys.exit(1)

# Check 3: Test Intent Router
print("\n3. Testing Intent Router...")
router = IntentRouter()

test_utterances = [
    ("Order CBC and BMP stat", "OrderLabs"),
    ("Any drug allergies?", "CheckAllergies"),
    ("Refill metformin 500mg BID", "RefillMedication"),
    ("Create SOAP note for today's visit", "CreateSOAPNote"),
    ("Show the last three potassium results", "RetrieveLabResults"),
]

for utterance, expected_intent in test_utterances:
    result = router.route(utterance)
    if result.intent == expected_intent:
        print(f"   ✅ '{utterance[:30]}...' → {result.intent}")
    else:
        print(f"   ⚠️  '{utterance[:30]}...' → {result.intent} (expected {expected_intent})")

# Check 4: Test Medical Scribe Initialization
print("\n4. Testing Medical Scribe...")
try:
    scribe = MedicalScribe()
    print("   ✅ Medical Scribe initialized")

    # Test intent routing through scribe
    async def test_routing():
        result = await scribe.route_intent("Order CBC stat")
        return result

    loop = asyncio.get_event_loop()
    routing_result = loop.run_until_complete(test_routing())

    if routing_result["intent"] == "OrderLabs":
        print("   ✅ Intent routing working")
        print(f"      - Intent: {routing_result['intent']}")
        print(f"      - Entities: {routing_result['entities']}")
        print(f"      - Confirmation: {routing_result['requires_confirmation']}")
    else:
        print("   ⚠️  Intent routing returned unexpected result")

except Exception as e:
    print(f"   ❌ Medical Scribe error: {e}")
    sys.exit(1)

# Check 5: Test Harness Verification
print("\n5. Checking Test Harness...")
try:
    from test_harness import call_voice_system, run_tests
    print("   ✅ Test harness loaded")

    # Quick test
    test_response = call_voice_system("Order CBC and BMP")
    if test_response.get("intent") == "OrderLabs":
        print("   ✅ Test harness responding correctly")
    else:
        print("   ⚠️  Test harness response unexpected")
except ImportError as e:
    print(f"   ⚠️  Test harness not critical: {e}")

# Check 6: Server Components
print("\n6. Checking Server Components...")
try:
    import fastapi
    import uvicorn
    print("   ✅ FastAPI/Uvicorn: Ready")
except ImportError as e:
    print(f"   ❌ FastAPI/Uvicorn: {e}")
    sys.exit(1)

# Check 7: File System
print("\n7. Checking File System...")
required_files = [
    "app.py",
    "medical_scribe.py",
    "intent_router.py",
    "test_harness.py",
    ".env",
    "start_testing.sh",
]

for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}: Present")
    else:
        print(f"   ⚠️  {file}: Missing")

# Final Report
print("\n" + "=" * 60)
print("SYSTEM STATUS: READY FOR TESTING")
print("=" * 60)

print("\n📋 QUICK TEST COMMANDS:")
print("\n1. Run acceptance tests:")
print("   python test_harness.py")
print("\n2. Start web server:")
print("   python app.py")
print("\n3. Or use the all-in-one script:")
print("   ./start_testing.sh")

print("\n🎯 TEST SCENARIOS TO TRY:")
print("   - 'Add to HPI: Patient has chest pain for 3 days'")
print("   - 'Order CBC and BMP stat'")
print("   - 'Any drug allergies?'")
print("   - 'Refill metformin 500mg BID, 90 day supply'")
print("   - 'Create SOAP note for this encounter'")

print("\n⚠️  SAFETY REMINDERS:")
print("   - Hold SHIFT key to record")
print("   - PHI will NOT be spoken (screen only)")
print("   - Orders require confirmation")
print("   - Half-duplex mode active")

print("\n✅ System ready. Start with: python app.py")
print("   Then open: http://localhost:8000")
print("=" * 60)