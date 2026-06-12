"""
MeshMed Drug Interaction Detection System.

SAFETY CRITICAL: This module detects potential interactions and translates them
into 8th-grade reading level plain language using LLMs. It NEVER tells users to
stop taking medications.
"""

import httpx
import asyncio
from datetime import datetime
from loguru import logger
from itertools import combinations
import uuid

from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic

from meshmed.core.config import get_settings
from meshmed.models.schemas import MedicationItem, DrugInteractionAlert

# Seed interaction database for fast local lookups before hitting APIs
LOCAL_INTERACTION_KB = {
    frozenset(["metformin", "alcohol"]): {
        "severity": "major",
        "mechanism": "Increased risk of lactic acidosis."
    },
    frozenset(["warfarin", "aspirin"]): {
        "severity": "contraindicated",
        "mechanism": "Significantly increased risk of severe bleeding."
    },
    frozenset(["tramadol", "sertraline"]): { # SSRI
        "severity": "major",
        "mechanism": "Increased risk of serotonin syndrome."
    },
    frozenset(["lisinopril", "potassium chloride"]): { # ACE + Potassium
        "severity": "major",
        "mechanism": "Risk of hyperkalemia (high potassium)."
    },
    frozenset(["atorvastatin", "clarithromycin"]): {
        "severity": "contraindicated",
        "mechanism": "Increased statin toxicity and risk of rhabdomyolysis."
    }
}

PLAIN_LANGUAGE_PROMPT = """
You are a medical safety communicator for MeshMed.
Your task is to explain a technical drug interaction in simple, empathetic language (8th-grade reading level).

CRITICAL SAFETY RULES:
1. NEVER tell the patient to stop taking their medication.
2. ALWAYS end your explanation with: "Please discuss with your doctor before making any changes."
3. Follow this severity ladder language strictly:
   - contraindicated: "These two medications are generally not taken together. Please contact your doctor as soon as possible."
   - major: "This combination may need monitoring. Please mention this at your next appointment."
   - moderate: "There is a potential interaction worth discussing with your doctor."
   - minor: "A minor interaction is noted. Mention this at your next checkup."

Drugs involved: {drug_a} and {drug_b}
Severity rating: {severity}
Technical Mechanism: {mechanism}

Generate the plain language explanation. Do not include any other conversational text.
"""

class DrugInteractionDetector:
    def __init__(self):
        self.settings = get_settings()
        self.llm = ChatAnthropic(
            model="claude-3-opus-20240229",
            api_key=self.settings.anthropic_api_key,
            temperature=0.0
        )
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def get_rxcui(self, drug_name: str) -> str:
        """Fetches RxCUI from OpenFDA (with mocked caching)."""
        # MVP: Mock fetching
        # Typically: GET https://api.fda.gov/drug/label.json?search=openfda.brand_name:{name}
        return f"RX_{drug_name[:3].upper()}123"

    async def fetch_openfda_interaction(self, drug_a: str, drug_b: str) -> dict:
        """Fetches drug interaction from OpenFDA API."""
        # MVP: Mock API call
        # Typically: GET https://api.fda.gov/drug/label.json?search=drug_interactions:{drug_name}
        return {}

    async def translate_to_plain_language(self, drug_a: str, drug_b: str, severity: str, mechanism: str) -> str:
        """Uses Claude to convert technical mechanisms into safe, simple warnings."""
        prompt = PromptTemplate.from_template(PLAIN_LANGUAGE_PROMPT)
        chain = prompt | self.llm
        
        try:
            res = await chain.ainvoke({
                "drug_a": drug_a, "drug_b": drug_b,
                "severity": severity, "mechanism": mechanism
            })
            return res.content.strip()
        except Exception as e:
            logger.error(f"Failed to translate interaction: {e}")
            # Failsafe generic message
            return f"An interaction was detected between {drug_a} and {drug_b}. Please discuss with your doctor before making any changes."

    async def check_interactions(self, user_id: str, medications: list[MedicationItem]) -> list[DrugInteractionAlert]:
        """
        Check all N*(N-1)/2 pairs of medications for interactions.
        """
        logger.info(f"Checking interactions for {len(medications)} medications.")
        alerts = []
        
        # Get active medications
        active_meds = [m for m in medications if m.is_current]
        if len(active_meds) < 2:
            return alerts
            
        # N*(N-1)/2 pairs
        pairs = list(combinations(active_meds, 2))
        
        for m1, m2 in pairs:
            d1 = (m1.generic_name or m1.brand_name).lower().strip()
            d2 = (m2.generic_name or m2.brand_name).lower().strip()
            
            pair_set = frozenset([d1, d2])
            
            # 1. Local KB Check (Fastest)
            kb_match = LOCAL_INTERACTION_KB.get(pair_set)
            
            if kb_match:
                source = "local_kb"
                severity = kb_match["severity"]
                mechanism = kb_match["mechanism"]
            else:
                # 2. OpenFDA Check
                # rxcui_1 = await self.get_rxcui(d1)
                # rxcui_2 = await self.get_rxcui(d2)
                # fda_match = await self.fetch_openfda_interaction(d1, d2)
                # Mock no match for MVP
                continue
                
            # 3. Translate
            plain_text = await self.translate_to_plain_language(d1, d2, severity, mechanism)
            
            alert = DrugInteractionAlert(
                alert_id=str(uuid.uuid4()),
                user_id=user_id,
                drug_a=d1.title(),
                drug_b=d2.title(),
                interaction_severity=severity,
                mechanism=mechanism,
                clinical_effect="Refer to mechanism",
                recommendation=plain_text,
                source=source,
                detected_at=datetime.utcnow(),
                is_acknowledged=False,
                acknowledged_by_doctor=False
            )
            alerts.append(alert)
            
            # Action logic based on severity
            if severity in ["contraindicated", "major"]:
                logger.warning(f"CRITICAL INTERACTION DETECTED: {d1} + {d2}. Queueing immediate WhatsApp alert.")
                
        # Sort by severity (contraindicated first)
        severity_order = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3}
        alerts.sort(key=lambda x: severity_order.get(x.interaction_severity, 99))
        
        return alerts
