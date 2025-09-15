#!/usr/bin/env python3
"""
Medical Scribe - Real ambient clinical documentation
Records doctor-patient conversations and generates SOAP notes
"""

import os
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional, List
import base64
import io
import wave

from deepgram import DeepgramClient, PrerecordedOptions, FileSource
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logger.add("logs/medical_scribe.log", rotation="1 day", retention="7 days")

class ClinicalNote(BaseModel):
    """Structured clinical note"""
    encounter_id: str
    timestamp: str
    chief_complaint: str
    history_of_present_illness: str
    review_of_systems: str
    physical_exam: str
    assessment: str
    plan: str
    icd10_codes: List[str] = []
    cpt_codes: List[str] = []
    follow_up: str = ""

class MedicalScribe:
    """
    Production medical scribe system
    - Records conversations
    - Transcribes with Deepgram Medical
    - Generates SOAP notes with Hugging Face
    """

    def __init__(self):
        # Initialize Deepgram
        self.deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.deepgram_key:
            raise ValueError("DEEPGRAM_API_KEY not found in environment")
        self.deepgram = DeepgramClient(self.deepgram_key)

        # Initialize Hugging Face
        self.hf_token = os.getenv("HUGGINGFACE_API_KEY")
        if not self.hf_token:
            raise ValueError("HUGGINGFACE_API_KEY not found in environment")

        # Use Mistral 7B Instruct for medical notes (fast and good)
        self.hf_client = InferenceClient(
            model="mistralai/Mistral-7B-Instruct-v0.2",
            token=self.hf_token
        )

        logger.info("Medical Scribe initialized successfully")

    async def transcribe_audio(self, audio_data: bytes, medical_specialty: str = "primary_care") -> Dict:
        """
        Transcribe audio using Deepgram Medical

        Args:
            audio_data: WAV audio bytes
            medical_specialty: Medical specialty for better accuracy

        Returns:
            Transcription with timestamps and confidence
        """
        try:
            logger.info(f"Transcribing {len(audio_data)} bytes of audio")

            # Configure Deepgram for medical transcription
            options = PrerecordedOptions(
                model="nova-2-medical",  # Medical model for better accuracy
                language="en-US",
                smart_format=True,
                punctuate=True,
                paragraphs=True,
                utterances=True,
                diarize=True,  # Speaker detection
                intents=False,
                topics=False,
                sentiment=False
            )

            # Create audio source
            source = {"buffer": audio_data, "mimetype": "audio/wav"}

            # Transcribe
            response = self.deepgram.listen.prerecorded.v("1").transcribe_file(
                source,
                options
            )

            # Extract transcript
            transcript = response.results.channels[0].alternatives[0].transcript
            confidence = response.results.channels[0].alternatives[0].confidence

            # Extract speaker segments if available
            utterances = []
            if hasattr(response.results, 'utterances'):
                for utterance in response.results.utterances:
                    utterances.append({
                        "speaker": utterance.speaker,
                        "text": utterance.transcript,
                        "start": utterance.start,
                        "end": utterance.end
                    })

            result = {
                "transcript": transcript,
                "confidence": confidence,
                "utterances": utterances,
                "duration": response.metadata.duration if hasattr(response.metadata, 'duration') else 0
            }

            logger.info(f"Transcription complete. Confidence: {confidence:.2%}")
            return result

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            # Return basic result even on error
            return {
                "transcript": "[Transcription failed - using fallback]",
                "confidence": 0.0,
                "utterances": [],
                "error": str(e)
            }

    async def generate_soap_note(self, transcript: str) -> ClinicalNote:
        """
        Generate SOAP note from transcript using Hugging Face

        Args:
            transcript: The conversation transcript

        Returns:
            Structured clinical note
        """
        try:
            logger.info("Generating SOAP note from transcript")

            # Create prompt for medical note generation
            prompt = f"""<s>[INST] You are a medical scribe. Convert this doctor-patient conversation into a structured SOAP note.

CONVERSATION:
{transcript}

Generate a professional SOAP note with these sections:
1. CHIEF COMPLAINT: Main reason for visit (one line)
2. HISTORY OF PRESENT ILLNESS: Detailed history
3. REVIEW OF SYSTEMS: Relevant systems reviewed
4. PHYSICAL EXAM: Examination findings
5. ASSESSMENT: Clinical assessment
6. PLAN: Treatment plan
7. ICD-10 CODES: Relevant diagnosis codes
8. CPT CODES: Relevant procedure codes
9. FOLLOW-UP: Next steps

Format as JSON with these exact keys: chief_complaint, history_of_present_illness, review_of_systems, physical_exam, assessment, plan, icd10_codes, cpt_codes, follow_up[/INST]"""

            # Generate response
            response = self.hf_client.text_generation(
                prompt,
                max_new_tokens=1500,
                temperature=0.3,  # Lower temperature for more consistent medical notes
                top_p=0.9,
                do_sample=True
            )

            # Parse the response to extract JSON
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                try:
                    note_data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    # If JSON parsing fails, create structured note from text
                    note_data = self._parse_text_to_soap(response)
            else:
                note_data = self._parse_text_to_soap(response)

            # Create clinical note
            note = ClinicalNote(
                encounter_id=f"ENC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                chief_complaint=note_data.get("chief_complaint", ""),
                history_of_present_illness=note_data.get("history_of_present_illness", ""),
                review_of_systems=note_data.get("review_of_systems", ""),
                physical_exam=note_data.get("physical_exam", ""),
                assessment=note_data.get("assessment", ""),
                plan=note_data.get("plan", ""),
                icd10_codes=note_data.get("icd10_codes", []),
                cpt_codes=note_data.get("cpt_codes", []),
                follow_up=note_data.get("follow_up", "")
            )

            logger.info(f"SOAP note generated for encounter {note.encounter_id}")
            return note

        except Exception as e:
            logger.error(f"Error generating SOAP note: {e}")
            # Return basic note structure on error
            return ClinicalNote(
                encounter_id=f"ENC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                chief_complaint="Error generating note - manual review required",
                history_of_present_illness=transcript[:500] if transcript else "",
                review_of_systems="",
                physical_exam="",
                assessment="",
                plan="",
                icd10_codes=[],
                cpt_codes=[],
                follow_up=""
            )

    def _parse_text_to_soap(self, text: str) -> Dict:
        """
        Parse free text into SOAP structure
        """
        sections = {
            "chief_complaint": "",
            "history_of_present_illness": "",
            "review_of_systems": "",
            "physical_exam": "",
            "assessment": "",
            "plan": "",
            "icd10_codes": [],
            "cpt_codes": [],
            "follow_up": ""
        }

        # Try to extract sections from text
        text_lower = text.lower()

        # Look for section headers
        for section in sections.keys():
            section_formatted = section.replace("_", " ").upper()
            if section_formatted in text:
                # Extract text after this section header
                start = text.index(section_formatted) + len(section_formatted)
                # Find next section or end
                next_section_pos = len(text)
                for other_section in sections.keys():
                    other_formatted = other_section.replace("_", " ").upper()
                    if other_formatted in text[start:]:
                        pos = text.index(other_formatted, start)
                        if pos < next_section_pos:
                            next_section_pos = pos

                content = text[start:next_section_pos].strip()

                if section.endswith("_codes"):
                    # Extract codes as list
                    codes = re.findall(r'[A-Z]\d{2,}\.?\d*', content)
                    sections[section] = codes
                else:
                    sections[section] = content.strip(": \n")

        return sections

    async def process_encounter(self, audio_data: bytes) -> Dict:
        """
        Complete pipeline: audio -> transcript -> SOAP note

        Args:
            audio_data: WAV audio bytes

        Returns:
            Complete encounter documentation
        """
        logger.info("Processing new encounter")

        # Step 1: Transcribe
        transcription = await self.transcribe_audio(audio_data)

        # Step 2: Generate SOAP note
        soap_note = await self.generate_soap_note(transcription["transcript"])

        # Step 3: Combine results
        result = {
            "encounter_id": soap_note.encounter_id,
            "timestamp": soap_note.timestamp,
            "transcription": transcription,
            "soap_note": soap_note.dict(),
            "processing_time": datetime.now().isoformat()
        }

        # Save to file for review
        output_file = f"encounters/{soap_note.encounter_id}.json"
        os.makedirs("encounters", exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        logger.info(f"Encounter processed and saved to {output_file}")
        return result


# Test function
async def test_with_sample():
    """Test with a sample medical conversation"""

    # Sample conversation (you can replace with actual audio)
    sample_transcript = """
    Doctor: Good morning, Mrs. Johnson. What brings you in today?

    Patient: Hi doctor, I've been having this terrible headache for the past three days. It's mostly on the right side of my head.

    Doctor: I see. Can you describe the pain? Is it throbbing, sharp, or constant?

    Patient: It's throbbing, and it gets worse when I move around. I also feel nauseous sometimes.

    Doctor: Have you had any visual changes or sensitivity to light?

    Patient: Yes, bright lights really bother me when the headache is bad.

    Doctor: Any recent stress or changes in your routine? How's your sleep been?

    Patient: Work has been very stressful lately, and I've only been sleeping about 4-5 hours a night.

    Doctor: Let me examine you. I'm checking your blood pressure... 130 over 85, slightly elevated.
    Pupils are equal and reactive. No neck stiffness.
    Based on your symptoms, this appears to be a migraine headache, likely triggered by stress and lack of sleep.

    I'm going to prescribe sumatriptan for acute migraine relief. Take it as soon as you feel a migraine starting.
    Also, I want you to focus on stress management and getting at least 7-8 hours of sleep.
    Let's follow up in two weeks to see how you're doing.
    """

    scribe = MedicalScribe()

    # For testing, we'll skip audio and use the transcript directly
    note = await scribe.generate_soap_note(sample_transcript)

    print("\n" + "="*60)
    print("GENERATED CLINICAL NOTE")
    print("="*60)
    print(f"Encounter ID: {note.encounter_id}")
    print(f"Timestamp: {note.timestamp}")
    print(f"\nCHIEF COMPLAINT:\n{note.chief_complaint}")
    print(f"\nHPI:\n{note.history_of_present_illness}")
    print(f"\nASSESSMENT:\n{note.assessment}")
    print(f"\nPLAN:\n{note.plan}")
    if note.icd10_codes:
        print(f"\nICD-10 CODES: {', '.join(note.icd10_codes)}")
    print("="*60)


if __name__ == "__main__":
    # Run test
    asyncio.run(test_with_sample())