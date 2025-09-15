"""
External system integrations
"""

# Available integrations
INTEGRATIONS = {
    'fhir': 'FHIR R4 EHR integration',
    'hl7': 'HL7 message processing (future)',
    'x12': 'X12 EDI transactions (future)',
}

__all__ = ['INTEGRATIONS']
