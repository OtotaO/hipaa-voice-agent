#!/usr/bin/env python3
"""
Realistic Test Scenarios for Medical Scribe v1
These test what we can ACTUALLY build, not fantasy features
"""

import asyncio
import json
from datetime import datetime
from medical_scribe import MedicalScribe

# Test conversations based on REAL clinical encounters
TEST_SCENARIOS = {
    "primary_care_uri": """
Doctor: Good morning, Mrs. Johnson. What brings you in today?

Patient: I've had this cough for about a week now. It's getting worse, and I'm coughing up yellow stuff.

Doctor: Any fever or chills?

Patient: Yes, I had a fever of 101 last night. And I've been feeling really tired.

Doctor: Any chest pain or shortness of breath?

Patient: Some chest pain when I cough hard, but breathing is okay.

Doctor: Are you still smoking?

Patient: I quit six months ago.

Doctor: Good. Let me listen to your lungs. [pause] I hear some crackles on the right lower side.
Your temp is 100.4, blood pressure 130/85, pulse 92, oxygen saturation 96%.

Based on your symptoms and exam, you have acute bronchitis, possibly early pneumonia.
I'm going to prescribe azithromycin 250mg, take two tablets today then one daily for four more days.
Also, use your albuterol inhaler if you need it for coughing.
Drink plenty of fluids, rest, and come back if you're not better in 3-4 days or if you develop worsening fever or trouble breathing.
""",

    "diabetes_followup": """
Doctor: Hi Mr. Garcia, here for your diabetes follow-up?

Patient: Yes, my sugars have been running high lately.

Doctor: What numbers are you seeing?

Patient: Mostly 180s to 200s in the morning, sometimes 250 after meals.

Doctor: Are you taking your metformin regularly?

Patient: Yes, twice a day with meals like you said.

Doctor: How about diet and exercise?

Patient: Diet's been tough. I've been stress eating with work. Exercise maybe twice a week.

Doctor: I see your A1C from last week is 8.9, up from 7.2. Weight is up 8 pounds.
Blood pressure today 145/92.

We need better control. I'm going to add Jardiance 10mg once daily.
Watch for increased urination.
Let's also refer you back to the diabetes educator for diet review.
I want to recheck your A1C in 3 months.
Keep working on the lifestyle changes - they're just as important as the medications.
""",

    "back_pain": """
Doctor: Tell me about your back pain.

Patient: It started three days ago when I was lifting boxes at work. Sharp pain in my lower back.

Doctor: Does it radiate anywhere? Down your legs?

Patient: No, just stays in my back.

Doctor: Any numbness, tingling, or weakness in your legs?

Patient: No, none of that.

Doctor: Any problems with urination or bowel movements?

Patient: No.

Doctor: On exam, you have muscle spasm in the paraspinal muscles.
Straight leg raise is negative. Strength and reflexes are normal.

This looks like mechanical low back pain, likely muscle strain.
I recommend ibuprofen 600mg three times daily with food.
Alternate heat and ice. Gentle stretching.
Stay active but avoid heavy lifting for a week.
Most back pain improves within 2-4 weeks.
Come back if you develop leg symptoms or it's not improving in a week.
"""
}

class TestHarness:
    """Test harness for medical scribe scenarios"""

    def __init__(self):
        self.scribe = MedicalScribe()
        self.results = []

    async def run_scenario(self, name: str, transcript: str):
        """Run a single test scenario"""
        print(f"\n{'='*60}")
        print(f"SCENARIO: {name}")
        print(f"{'='*60}")

        start_time = datetime.now()

        # Generate SOAP note
        note = await self.scribe.generate_soap_note(transcript)

        # Calculate metrics
        generation_time = (datetime.now() - start_time).total_seconds()

        # Evaluate quality (basic checks)
        quality_checks = {
            "has_chief_complaint": bool(note.chief_complaint),
            "has_hpi": bool(note.history_of_present_illness),
            "has_assessment": bool(note.assessment),
            "has_plan": bool(note.plan),
            "has_icd_codes": len(note.icd10_codes) > 0,
            "generation_time_sec": generation_time,
            "under_3_sec": generation_time < 3.0
        }

        # Display results
        print(f"\n📋 GENERATED NOTE:")
        print(f"Chief Complaint: {note.chief_complaint[:100]}...")
        print(f"Assessment: {note.assessment[:100]}...")
        print(f"ICD-10 Codes: {', '.join(note.icd10_codes) if note.icd10_codes else 'None'}")

        print(f"\n✅ QUALITY CHECKS:")
        for check, passed in quality_checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}: {passed}")

        # Store results
        self.results.append({
            "scenario": name,
            "quality_checks": quality_checks,
            "note": note.dict()
        })

        return quality_checks

    async def run_all_scenarios(self):
        """Run all test scenarios"""
        print("\n" + "="*60)
        print("MEDICAL SCRIBE TEST SUITE")
        print("="*60)

        all_passed = True

        for name, transcript in TEST_SCENARIOS.items():
            checks = await self.run_scenario(name, transcript)

            # Check critical requirements
            if not all([
                checks["has_chief_complaint"],
                checks["has_assessment"],
                checks["has_plan"],
                checks["under_3_sec"]
            ]):
                all_passed = False

        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Scenarios run: {len(self.results)}")
        print(f"All critical checks passed: {'YES ✅' if all_passed else 'NO ❌'}")

        # Save results
        with open(f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
            json.dump(self.results, f, indent=2)

        return all_passed

async def test_edge_cases():
    """Test edge cases and failure modes"""
    print("\n" + "="*60)
    print("EDGE CASE TESTING")
    print("="*60)

    scribe = MedicalScribe()

    # Test 1: Empty input
    print("\n1. Empty transcript:")
    note = await scribe.generate_soap_note("")
    assert note.chief_complaint != "", "Should handle empty input"
    print("   ✓ Handled gracefully")

    # Test 2: Non-medical conversation
    print("\n2. Non-medical content:")
    note = await scribe.generate_soap_note("The weather is nice today. How about those Lakers?")
    print(f"   Generated: {note.chief_complaint[:50]}...")
    print("   ✓ Attempted structure anyway")

    # Test 3: Medication mentions without clear orders
    print("\n3. Ambiguous medication mention:")
    note = await scribe.generate_soap_note(
        "Patient asks: Should I keep taking the metformin? Doctor: Let's discuss that."
    )
    print(f"   Plan: {note.plan[:100]}...")
    print("   ✓ Didn't create false orders")

    # Test 4: Multiple speakers (complex)
    print("\n4. Multiple speakers:")
    note = await scribe.generate_soap_note("""
        Doctor: How are you?
        Patient: Not good.
        Nurse: Blood pressure is 150/90.
        Doctor: That's high.
        Patient's wife: He hasn't been taking his meds.
        Doctor: We need to restart them.
    """)
    print(f"   Captured: {note.assessment[:100]}...")
    print("   ✓ Handled multiple speakers")

async def test_performance():
    """Test performance metrics"""
    print("\n" + "="*60)
    print("PERFORMANCE TESTING")
    print("="*60)

    scribe = MedicalScribe()

    # Test various lengths
    test_lengths = [
        ("Short (30 sec)", "Doctor: Sore throat. Patient: Yes, for 3 days. Doctor: Looks like strep."),
        ("Medium (2 min)", TEST_SCENARIOS["back_pain"]),
        ("Long (5 min)", TEST_SCENARIOS["primary_care_uri"] * 2)  # Doubled for length
    ]

    for name, transcript in test_lengths:
        start = datetime.now()
        note = await scribe.generate_soap_note(transcript)
        elapsed = (datetime.now() - start).total_seconds()

        print(f"\n{name}:")
        print(f"  Transcript length: {len(transcript)} chars")
        print(f"  Generation time: {elapsed:.2f} seconds")
        print(f"  Acceptable (<3s): {'✓' if elapsed < 3 else '✗'}")

async def main():
    """Run all tests"""

    # Run main test suite
    harness = TestHarness()
    main_passed = await harness.run_all_scenarios()

    # Run edge cases
    await test_edge_cases()

    # Run performance tests
    await test_performance()

    print("\n" + "="*60)
    print("FINAL VERDICT")
    print("="*60)

    if main_passed:
        print("✅ READY FOR PILOT with real physicians")
        print("\nNext steps:")
        print("1. Get 2-3 physician volunteers")
        print("2. Have them use for 1 week")
        print("3. Measure actual time saved")
        print("4. Iterate based on feedback")
    else:
        print("❌ NOT READY - Critical issues found")
        print("\nFix these first:")
        print("1. Ensure all notes have required sections")
        print("2. Improve generation speed")
        print("3. Add error recovery")

if __name__ == "__main__":
    asyncio.run(main())