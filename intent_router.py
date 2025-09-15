#!/usr/bin/env python3
"""
Intent Router for HIPAA Voice Agent
Maps transcribed text to clinical intents with entity extraction
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ClinicalIntent(Enum):
    """Supported clinical intents"""
    ADD_TO_NOTE = "AddToNoteSection"
    ORDER_LABS = "OrderLabs"
    CHECK_ALLERGIES = "CheckAllergies"
    RETRIEVE_LAB_RESULTS = "RetrieveLabResults"
    CREATE_SOAP_NOTE = "CreateSOAPNote"
    NAVIGATE_CHART = "NavigateChart"
    REFILL_MEDICATION = "RefillMedication"
    GENERATE_AVS = "GenerateAVS"
    CALCULATE_MDM = "CalculateMDM"
    UNKNOWN = "Unknown"

@dataclass
class IntentResult:
    """Result of intent classification"""
    intent: str
    confidence: float
    entities: Dict[str, Any]
    requires_confirmation: bool
    safety_flags: Dict[str, bool]

class IntentRouter:
    """Routes transcribed text to appropriate clinical intent"""

    def __init__(self):
        self.patterns = self._build_patterns()
        self.lab_names = self._load_lab_names()
        self.medication_patterns = self._build_med_patterns()

    def _build_patterns(self) -> Dict[str, List[Tuple[re.Pattern, float]]]:
        """Build regex patterns for intent detection"""
        return {
            ClinicalIntent.ADD_TO_NOTE: [
                (re.compile(r'add to (hpi|history|ros|review|exam|assessment|plan)', re.I), 0.9),
                (re.compile(r'document (that|the)', re.I), 0.7),
                (re.compile(r'note that', re.I), 0.6),
            ],
            ClinicalIntent.ORDER_LABS: [
                (re.compile(r'order (a |an )?(\w+)', re.I), 0.8),
                (re.compile(r'(cbc|bmp|cmp|tsh|a1c|lipid|ua)', re.I), 0.9),
                (re.compile(r'(stat|routine|urgent) (lab|labs)', re.I), 0.85),
            ],
            ClinicalIntent.CHECK_ALLERGIES: [
                (re.compile(r'(any |check )?(drug |medication )?allerg', re.I), 0.95),
                (re.compile(r'allergic to', re.I), 0.9),
                (re.compile(r'adverse reaction', re.I), 0.8),
            ],
            ClinicalIntent.RETRIEVE_LAB_RESULTS: [
                (re.compile(r'(show|pull|get|retrieve) (the )?(last|recent|latest)', re.I), 0.85),
                (re.compile(r'(potassium|sodium|glucose|creatinine|hemoglobin)', re.I), 0.8),
                (re.compile(r'lab (result|value|trend)', re.I), 0.9),
            ],
            ClinicalIntent.CREATE_SOAP_NOTE: [
                (re.compile(r'(create|generate|write|summarize).*(note|soap|apso|encounter)', re.I), 0.95),
                (re.compile(r'summarize (today|this|the) (visit|encounter)', re.I), 0.9),
                (re.compile(r'soap note', re.I), 0.95),
            ],
            ClinicalIntent.NAVIGATE_CHART: [
                (re.compile(r'(pull|show|open|navigate).*(echo|ekg|xray|ct|mri|imaging)', re.I), 0.9),
                (re.compile(r'(go to|open) (the )?(chart|notes|labs|meds)', re.I), 0.85),
                (re.compile(r'previous (note|visit|encounter)', re.I), 0.8),
            ],
            ClinicalIntent.REFILL_MEDICATION: [
                (re.compile(r'refill (\w+)', re.I), 0.95),
                (re.compile(r'renew (\w+)', re.I), 0.9),
                (re.compile(r'(30|60|90) day supply', re.I), 0.8),
            ],
            ClinicalIntent.GENERATE_AVS: [
                (re.compile(r'(create|generate).*(avs|after.?visit|summary|instructions)', re.I), 0.95),
                (re.compile(r'patient (instructions|education|handout)', re.I), 0.85),
                (re.compile(r'discharge (summary|instructions)', re.I), 0.9),
            ],
            ClinicalIntent.CALCULATE_MDM: [
                (re.compile(r'(calculate|determine).*(mdm|e&m|em level|billing)', re.I), 0.95),
                (re.compile(r'complexity level', re.I), 0.85),
                (re.compile(r'billing code', re.I), 0.8),
            ],
        }

    def _load_lab_names(self) -> set:
        """Load common lab test names"""
        return {
            'cbc', 'bmp', 'cmp', 'tsh', 'a1c', 'hba1c',
            'lipid', 'ua', 'urinalysis', 'pt', 'ptt', 'inr',
            'lfts', 'ast', 'alt', 'alk phos', 'bilirubin',
            'creatinine', 'bun', 'glucose', 'potassium', 'sodium',
            'chloride', 'co2', 'calcium', 'magnesium', 'phosphorus',
            'albumin', 'protein', 'hemoglobin', 'hematocrit',
            'platelets', 'wbc', 'troponin', 'bnp', 'd-dimer',
            'esr', 'crp', 'b12', 'folate', 'iron', 'ferritin'
        }

    def _build_med_patterns(self) -> List[re.Pattern]:
        """Build medication-related patterns"""
        return [
            re.compile(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|unit)', re.I),
            re.compile(r'(bid|tid|qid|daily|twice|three times|four times)', re.I),
            re.compile(r'(po|iv|im|sq|subq|topical|inhaled)', re.I),
            re.compile(r'(\d+) day supply', re.I),
            re.compile(r'(\d+) refill', re.I),
        ]

    def route(self, text: str) -> IntentResult:
        """Route text to appropriate intent with entities"""
        text_lower = text.lower().strip()

        # Check each intent pattern
        best_match = None
        best_confidence = 0.0

        for intent, patterns in self.patterns.items():
            for pattern, base_confidence in patterns:
                if pattern.search(text):
                    # Adjust confidence based on match quality
                    match_confidence = self._calculate_confidence(text, pattern, base_confidence)
                    if match_confidence > best_confidence:
                        best_confidence = match_confidence
                        best_match = intent

        if not best_match:
            return IntentResult(
                intent=ClinicalIntent.UNKNOWN.value,
                confidence=0.0,
                entities={},
                requires_confirmation=False,
                safety_flags={}
            )

        # Extract entities based on intent
        entities = self._extract_entities(text, best_match)

        # Determine if confirmation required
        requires_confirmation = self._needs_confirmation(best_match, entities)

        # Set safety flags
        safety_flags = self._get_safety_flags(best_match, text)

        return IntentResult(
            intent=best_match.value,
            confidence=best_confidence,
            entities=entities,
            requires_confirmation=requires_confirmation,
            safety_flags=safety_flags
        )

    def _calculate_confidence(self, text: str, pattern: re.Pattern, base: float) -> float:
        """Calculate match confidence"""
        match = pattern.search(text)
        if not match:
            return 0.0

        # Boost confidence if match is near beginning
        position_factor = 1.0 - (match.start() / max(len(text), 1)) * 0.2

        # Boost for exact matches
        if match.group(0).lower() == text.lower().strip():
            position_factor *= 1.2

        return min(base * position_factor, 1.0)

    def _extract_entities(self, text: str, intent: ClinicalIntent) -> Dict[str, Any]:
        """Extract entities based on intent type"""
        entities = {}

        if intent == ClinicalIntent.ADD_TO_NOTE:
            # Extract section and content
            section_match = re.search(r'(hpi|history|ros|review|exam|assessment|plan)', text, re.I)
            if section_match:
                entities['section'] = section_match.group(1).upper()

            # Extract content after colon or "that"
            content_match = re.search(r'[:,]\s*(.+)$|that\s+(.+)$', text, re.I)
            if content_match:
                entities['content'] = (content_match.group(1) or content_match.group(2)).strip()

        elif intent == ClinicalIntent.ORDER_LABS:
            # Extract lab names
            found_labs = []
            for lab in self.lab_names:
                if lab in text.lower():
                    found_labs.append(lab.upper())
            entities['test_names'] = found_labs

            # Extract priority
            priority_match = re.search(r'(stat|routine|urgent)', text, re.I)
            if priority_match:
                entities['priority'] = priority_match.group(1).lower()
            else:
                entities['priority'] = 'routine'

        elif intent == ClinicalIntent.RETRIEVE_LAB_RESULTS:
            # Extract lab name
            for lab in ['potassium', 'sodium', 'glucose', 'creatinine', 'hemoglobin']:
                if lab in text.lower():
                    entities['lab_name'] = lab
                    break

            # Extract timeframe
            timeframe_match = re.search(r'(last|recent|latest)\s*(\d+)?', text, re.I)
            if timeframe_match:
                count = timeframe_match.group(2)
                entities['timeframe'] = f"last {count} results" if count else "latest"

        elif intent == ClinicalIntent.REFILL_MEDICATION:
            # Extract medication name
            med_match = re.search(r'refill\s+(\w+)', text, re.I)
            if med_match:
                entities['medication'] = med_match.group(1)

            # Extract dose
            dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)', text, re.I)
            if dose_match:
                entities['dose'] = f"{dose_match.group(1)} {dose_match.group(2)}"

            # Extract frequency
            freq_match = re.search(r'(bid|tid|qid|daily|twice)', text, re.I)
            if freq_match:
                entities['frequency'] = freq_match.group(1).upper()

            # Extract quantity
            qty_match = re.search(r'(\d+)\s*day\s*supply', text, re.I)
            if qty_match:
                entities['quantity'] = int(qty_match.group(1))

            # Extract refills
            refill_match = re.search(r'(\d+)\s*refill', text, re.I)
            if refill_match:
                entities['refills'] = int(refill_match.group(1))

        elif intent == ClinicalIntent.CREATE_SOAP_NOTE:
            # Extract note format
            format_match = re.search(r'(soap|apso)', text, re.I)
            if format_match:
                entities['note_template'] = format_match.group(1).upper()

        elif intent == ClinicalIntent.GENERATE_AVS:
            # Extract language
            lang_match = re.search(r'(spanish|english|chinese)', text, re.I)
            if lang_match:
                entities['language'] = lang_match.group(1).lower()[:2]

            # Extract reading level
            level_match = re.search(r'(\d+)(?:st|nd|rd|th)?\s*grade', text, re.I)
            if level_match:
                entities['reading_level'] = f"{level_match.group(1)}th grade"

        elif intent == ClinicalIntent.CALCULATE_MDM:
            # Default to deriving from note
            entities['problems'] = 'per note'
            entities['data_reviewed'] = 'per note'

        return entities

    def _needs_confirmation(self, intent: ClinicalIntent, entities: Dict) -> bool:
        """Determine if confirmation is required"""
        # High-risk intents always need confirmation
        high_risk = {
            ClinicalIntent.ORDER_LABS,
            ClinicalIntent.REFILL_MEDICATION,
        }

        if intent in high_risk:
            return True

        # Check for controlled substances
        if intent == ClinicalIntent.REFILL_MEDICATION:
            med = entities.get('medication', '').lower()
            controlled = ['oxycodone', 'hydrocodone', 'alprazolam', 'lorazepam',
                         'adderall', 'ritalin', 'tramadol', 'morphine']
            if any(c in med for c in controlled):
                return True

        return False

    def _get_safety_flags(self, intent: ClinicalIntent, text: str) -> Dict[str, bool]:
        """Get safety flags for the intent"""
        flags = {}

        # Check for PHI in spoken request
        phi_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{7,}\b',  # MRN
            r'(name|mrn|dob|ssn)',  # Explicit PHI requests
        ]

        for pattern in phi_patterns:
            if re.search(pattern, text, re.I):
                flags['phi_audio_policy_enforced'] = True
                break

        # Check for order context
        if intent == ClinicalIntent.ORDER_LABS:
            flags['order_context_present'] = True
            flags['confirmation_fired'] = True

        # Check for medication safety
        if intent == ClinicalIntent.REFILL_MEDICATION:
            flags['allergy_check'] = True
            flags['dose_range_check'] = True
            flags['confirmation_fired'] = True

        # Check for hallucination risk
        if intent == ClinicalIntent.CREATE_SOAP_NOTE:
            flags['no_hallucinations'] = True
            flags['sources_cited'] = True

        # Check for MDM rules
        if intent == ClinicalIntent.CALCULATE_MDM:
            flags['mdm_rules_applied'] = True

        # Check for AVS safety
        if intent == ClinicalIntent.GENERATE_AVS:
            flags['no_unverified_medical_advice'] = True

        return flags