"""
MeshMed Handoff Packet Generator.

Generates structured Provider and Patient briefs ensuring that the right information
arrives before the patient does. Synthesizes ONLY from provided source documents.
"""

from loguru import logger
from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic

from meshmed.core.config import get_settings
from meshmed.models.schemas import ProviderBrief, PatientBrief

SPECIALTY_RELEVANCE_MAP = {
    "cardiology": {
        "lab_tests": ["BP", "ECG", "Echocardiogram", "Lipid Profile", "HbA1c",
                      "CBC", "Kidney Function", "BNP"],
        "medication_classes": ["antihypertensive", "anticoagulant", "statin",
                                "beta_blocker", "diuretic"],
        "history_keywords": ["chest pain", "palpitation", "breathlessness",
                              "edema", "syncope"]
    },
    "endocrinology": {
        "lab_tests": ["HbA1c", "Fasting Glucose", "TSH", "T3", "T4", "Insulin",
                      "Cortisol", "Vitamin D"],
        "medication_classes": ["insulin", "oral_hypoglycemic", "thyroid_hormone"],
        "history_keywords": ["diabetes", "thyroid", "weight", "fatigue"]
    },
    "nephrology": {
        "lab_tests": ["Serum Creatinine", "BUN", "eGFR", "Electrolytes", "Urine Routine"],
        "medication_classes": ["diuretic", "phosphate_binder", "erythropoietin"],
        "history_keywords": ["kidney", "renal", "dialysis", "swelling", "urine"]
    },
    "gastroenterology": {
        "lab_tests": ["Liver Function", "Amylase", "Lipase", "Stool Routine", "CBC"],
        "medication_classes": ["ppi", "antacid", "laxative", "antiemetic"],
        "history_keywords": ["abdominal pain", "nausea", "vomiting", "diarrhea", "jaundice"]
    },
    "general": {
        "lab_tests": ["*"],
        "medication_classes": ["*"],
        "history_keywords": ["*"]
    }
}

HANDOFF_GENERATION_PROMPT = """
You are a Medical Document Synthesis Specialist for MeshMed.
Your task is to generate a comprehensive handoff brief for a doctor (Provider Brief) and a guide for the patient (Patient Brief) based strictly on the patient's uploaded medical records.

CRITICAL CONSTRAINTS:
1. Synthesize ONLY from the provided source documents. Do NOT use external medical knowledge to invent history or guess conditions.
2. The target provider is a {specialty}. Filter and prioritize the history, labs, and medications relevant to this specialty based on the provided relevance maps.
3. Prioritize Recency: Highlight documents from the last 30 days most prominently. Summarize older items (last 6 months) briefly unless they represent chronic conditions.
4. Flag Conflicts: If two documents contradict each other (e.g., GP prescription says 500mg, recent hospital discharge says 1000mg), explicitly flag this discrepancy in the brief.
5. Tone: Clinical but highly readable. Avoid over-abbreviating.
6. Length: Provider brief should be concise (max 1 page, ~400 words). Patient brief should be actionable (max 10 bullet points).
7. SAFETY: MeshMed is a coordination tool. You must NOT diagnose or suggest changes to treatment.

Patient Intent / Appointment Reason:
{appointment_context}

Available Medical Context (Extracted from Documents):
{medical_records}

Please generate the ProviderBrief and PatientBrief matching the requested JSON schemas.
"""

class HandoffGenerator:
    def __init__(self):
        self.settings = get_settings()
        self.llm = ChatAnthropic(
            model="claude-3-opus-20240229",
            api_key=self.settings.anthropic_api_key,
            temperature=0.0
        )

    async def generate_briefs(self, specialty: str, appointment_context: str, documents: list[dict]) -> tuple[ProviderBrief, PatientBrief]:
        """Synthesizes the context into targeted briefs using Claude Opus."""
        
        relevance_rules = SPECIALTY_RELEVANCE_MAP.get(specialty.lower(), SPECIALTY_RELEVANCE_MAP["general"])
        
        prompt = PromptTemplate.from_template(HANDOFF_GENERATION_PROMPT)
        
        # In a full implementation, we'd use .with_structured_output to force both schemas.
        # For MVP, we mock the output generation.
        logger.info(f"Generating briefs for specialty: {specialty}")
        
        return ProviderBrief(
            brief_id="mock_brief",
            user_id="mock_user",
            appointment_date="2026-06-15",
            appointment_type="specialist_consult",
            provider_specialty=specialty,
            generated_at="2026-06-12T12:00:00Z",
            presenting_concern=appointment_context,
            relevant_history=[],
            current_medications=[],
            relevant_lab_results=[],
            unresolved_questions=[],
            previous_treatments=[],
            source_documents=[],
            confidence=0.95
        ), PatientBrief(
            suggested_questions=["Should I continue taking X?"],
            things_to_mention=["Mention the dizziness from last Tuesday."],
            documents_to_bring=["Bring your latest CBC report."],
            things_to_ask_about=["Ask about the new dosage."],
            red_flag_reminders=[]
        )
