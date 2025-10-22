"""
Eligibility Verification Service
Integrates with Stedi API for real-time insurance checks
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional
import httpx
from loguru import logger

from .database import get_db_connection
from .cache import get_from_cache, set_cache


class EligibilityService:
    """Real-time insurance eligibility verification via Stedi"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = os.getenv(
            "STEDI_BASE_URL",
            "https://core.stedi.com/2023-01-01/healthcare"
        )
        self.cache_ttl_hours = int(os.getenv("CACHE_TTL_HOURS", "24"))

    async def check_eligibility(
        self,
        patient_id: str,
        provider_npi: str
    ) -> Dict:
        """
        Check insurance eligibility for a patient

        Args:
            patient_id: FHIR Patient resource ID
            provider_npi: Provider NPI number

        Returns:
            Dict with eligibility results
        """

        # 1. Check cache first
        cached = await self._get_cached_eligibility(patient_id)
        if cached:
            logger.info(f"Returning cached eligibility for patient {patient_id}")
            return {
                **cached,
                "cached": True,
                "check_date": cached["check_date"]
            }

        # 2. Fetch patient data from Medplum
        patient_data = await self._get_patient_data(patient_id)

        # 3. Call Stedi API
        result = await self._call_stedi_api(patient_data, provider_npi)

        # 4. Cache result
        await self._cache_eligibility(patient_id, result)

        return {
            **result,
            "cached": False,
            "check_date": datetime.now()
        }

    async def _get_cached_eligibility(self, patient_id: str) -> Optional[Dict]:
        """Get cached eligibility from database"""

        async with get_db_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    coverage_status as status,
                    plan_name,
                    copay,
                    deductible,
                    out_of_pocket_max as oop_max,
                    check_date,
                    response_data
                FROM eligibility_cache
                WHERE patient_id = $1
                AND expires_at > NOW()
                ORDER BY check_date DESC
                LIMIT 1
                """,
                patient_id
            )

            if row:
                return dict(row)

        return None

    async def _get_patient_data(self, patient_id: str) -> Dict:
        """Fetch patient data from Medplum FHIR server"""

        medplum_url = os.getenv("MEDPLUM_BASE_URL", "http://localhost:8103")

        async with httpx.AsyncClient() as client:
            # Get Patient resource
            patient_response = await client.get(
                f"{medplum_url}/fhir/R4/Patient/{patient_id}"
            )

            if patient_response.status_code != 200:
                raise ValueError(f"Patient {patient_id} not found in Medplum")

            patient = patient_response.json()

            # Extract required fields
            name = patient.get("name", [{}])[0]
            first_name = name.get("given", [""])[0]
            last_name = name.get("family", "")
            dob = patient.get("birthDate", "")

            # Get Coverage resource (insurance info)
            coverage_response = await client.get(
                f"{medplum_url}/fhir/R4/Coverage",
                params={"beneficiary": patient_id}
            )

            coverage_data = coverage_response.json()
            coverage_entries = coverage_data.get("entry", [])

            if not coverage_entries:
                raise ValueError(f"No insurance coverage found for patient {patient_id}")

            coverage = coverage_entries[0]["resource"]

            # Extract insurance details
            subscriber_id = coverage.get("subscriberId", "")
            payer = coverage.get("payor", [{}])[0]
            payer_id = payer.get("identifier", {}).get("value", "")

            return {
                "patient_id": patient_id,
                "first_name": first_name,
                "last_name": last_name,
                "dob": dob,
                "insurance_id": subscriber_id,
                "payer_id": payer_id
            }

    async def _call_stedi_api(self, patient_data: Dict, provider_npi: str) -> Dict:
        """Call Stedi eligibility API"""

        payload = {
            "controlNumber": self._generate_control_number(),
            "tradingPartnerServiceId": patient_data["payer_id"],
            "subscriber": {
                "memberId": patient_data["insurance_id"],
                "firstName": patient_data["first_name"],
                "lastName": patient_data["last_name"],
                "dateOfBirth": patient_data["dob"]
            },
            "provider": {
                "npi": provider_npi,
                "organizationName": os.getenv("PRACTICE_NAME", "Medical Practice")
            },
            "encounter": {
                "serviceTypeCodes": ["30"]  # Health Benefit Plan Coverage
            }
        }

        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/eligibility",
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"Stedi API error: {response.status_code} - {response.text}")
                    # Return unknown status instead of failing
                    return {
                        "status": "unknown",
                        "plan_name": None,
                        "copay": None,
                        "deductible": None,
                        "oop_max": None,
                        "raw_response": {"error": response.text}
                    }

                data = response.json()
                return self._parse_stedi_response(data)

        except httpx.TimeoutException:
            logger.error("Stedi API timeout")
            raise Exception("Eligibility check timed out - try again")
        except Exception as e:
            logger.error(f"Stedi API error: {e}")
            raise Exception(f"Eligibility check failed: {str(e)}")

    def _parse_stedi_response(self, data: Dict) -> Dict:
        """Parse Stedi API response"""

        benefits = data.get("benefits", [])

        return {
            "status": "active" if data.get("eligible") == "Y" else "inactive",
            "plan_name": data.get("planInformation", {}).get("planName"),
            "copay": self._find_benefit(benefits, "copay"),
            "deductible": self._find_benefit(benefits, "deductible"),
            "oop_max": self._find_benefit(benefits, "out_of_pocket_max"),
            "raw_response": data
        }

    def _find_benefit(self, benefits: list, benefit_type: str) -> Optional[str]:
        """Extract specific benefit from benefits array"""

        for benefit in benefits:
            if benefit.get("benefitType") == benefit_type:
                if benefit.get("inNetworkAmount"):
                    return f"${benefit['inNetworkAmount']}"
                elif benefit.get("inNetworkPercent"):
                    return f"{benefit['inNetworkPercent']}%"

        return None

    async def _cache_eligibility(self, patient_id: str, result: Dict):
        """Cache eligibility result in database"""

        expires_at = datetime.now() + timedelta(hours=self.cache_ttl_hours)

        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO eligibility_cache (
                    patient_id,
                    coverage_status,
                    plan_name,
                    copay,
                    deductible,
                    out_of_pocket_max,
                    response_data,
                    expires_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                patient_id,
                result["status"],
                result["plan_name"],
                result["copay"],
                result["deductible"],
                result["oop_max"],
                result["raw_response"],
                expires_at
            )

        logger.info(f"Cached eligibility for patient {patient_id} (expires {expires_at})")

    def _generate_control_number(self) -> str:
        """Generate unique 9-digit control number for Stedi"""
        import random
        return str(random.randint(100000000, 999999999))
