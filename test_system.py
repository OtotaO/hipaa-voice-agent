#!/usr/bin/env python3
"""
Test the medical scribe system
"""

import asyncio
import os
from medical_scribe import MedicalScribe
from dotenv import load_dotenv

load_dotenv()

async def test_transcription_and_note_generation():
    """Test the complete pipeline with a sample conversation"""

    print("\n" + "="*60)
    print("MEDICAL SCRIBE SYSTEM TEST")
    print("="*60)

    # Sample medical conversation
    test_conversation = """
    Doctor: Good morning, Mr. Smith. What brings you in today?

    Patient: Hi doctor, I've been having chest pain for the past two days. It's been really concerning me.

    Doctor: I understand your concern. Can you describe the pain? Where exactly is it located?

    Patient: It's in the center of my chest, kind of a pressure feeling. It gets worse when I walk up stairs.

    Doctor: Does the pain radiate anywhere? To your arms, jaw, or back?

    Patient: Sometimes it goes to my left shoulder, yes.

    Doctor: Any shortness of breath, nausea, or sweating with the pain?

    Patient: I do get a bit short of breath when the pain is bad. No nausea though.

    Doctor: Do you have any history of heart problems? High blood pressure, high cholesterol?

    Patient: My cholesterol was a bit high last year. I'm on atorvastatin 20mg daily. My father had a heart attack at 65.

    Doctor: Are you a smoker? Any diabetes?

    Patient: I quit smoking 5 years ago. No diabetes, but I'm probably 30 pounds overweight.

    Doctor: Let me examine you. Your blood pressure is 145 over 90, slightly elevated.
    Heart rate is 88, regular rhythm. I'm hearing a slight murmur on auscultation.
    Your EKG shows some ST segment changes that concern me.

    Given your symptoms, risk factors, and EKG findings, I'm concerned about possible unstable angina.
    We need to admit you for further cardiac workup including troponin levels, stress test, and possibly cardiac catheterization.
    I'm going to start you on aspirin 325mg now, and we'll add a beta blocker for rate control.
    We'll also increase your statin dose.

    Do you have any questions?

    Patient: Will I need surgery?

    Doctor: Let's see what the tests show first. We'll take excellent care of you.
    """

    # Initialize the scribe
    print("\n1. Initializing Medical Scribe...")
    scribe = MedicalScribe()
    print("   ✓ Scribe initialized")

    # Test note generation
    print("\n2. Generating SOAP note from conversation...")
    note = await scribe.generate_soap_note(test_conversation)
    print("   ✓ SOAP note generated")

    # Display results
    print("\n3. Generated Clinical Documentation:")
    print("-" * 40)
    print(f"Encounter ID: {note.encounter_id}")
    print(f"Timestamp: {note.timestamp}")
    print(f"\n📋 CHIEF COMPLAINT:")
    print(f"   {note.chief_complaint}")
    print(f"\n📋 HISTORY OF PRESENT ILLNESS:")
    print(f"   {note.history_of_present_illness}")
    print(f"\n📋 PHYSICAL EXAM:")
    print(f"   {note.physical_exam}")
    print(f"\n📋 ASSESSMENT:")
    print(f"   {note.assessment}")
    print(f"\n📋 PLAN:")
    print(f"   {note.plan}")

    if note.icd10_codes:
        print(f"\n📋 ICD-10 CODES:")
        for code in note.icd10_codes:
            print(f"   • {code}")

    if note.cpt_codes:
        print(f"\n📋 CPT CODES:")
        for code in note.cpt_codes:
            print(f"   • {code}")

    print("\n" + "="*60)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("="*60)

    # Test API connectivity
    print("\n4. Testing API Connectivity:")
    print("-" * 40)

    # Test Deepgram
    try:
        if os.getenv("DEEPGRAM_API_KEY"):
            print("   ✓ Deepgram API key found")
        else:
            print("   ✗ Deepgram API key missing")
    except:
        print("   ✗ Error checking Deepgram")

    # Test Hugging Face
    try:
        if os.getenv("HUGGINGFACE_API_KEY"):
            print("   ✓ Hugging Face API key found")
        else:
            print("   ✗ Hugging Face API key missing")
    except:
        print("   ✗ Error checking Hugging Face")

    print("\n" + "="*60)
    print("\nNEXT STEPS:")
    print("1. Run the web server: python app.py")
    print("2. Open browser to: http://localhost:8000")
    print("3. Click microphone to record a conversation")
    print("4. Get instant SOAP note generation")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_transcription_and_note_generation())