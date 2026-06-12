"""
MeshMed Pydantic Schemas.

Defines the structure for API requests, LangGraph states, and safety-critical data validation.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ================================================================
# CLINICAL DATA STRUCTURES
# ================================================================

class MedicalDocument(BaseModel):
    document_id: str
    user_id: str
    document_type: Literal[
        "prescription", "lab_report", "discharge_summary",
        "imaging_report", "insurance_document", "vaccination_record"
    ]
    upload_timestamp: datetime
    document_date: date                  # date on the document itself
    source_provider: Optional[str]       # PHI: doctor/hospital name
    source_provider_type: Optional[str]  # "gp", "specialist", "lab", "hospital"
    raw_text_encrypted: str              # PHI: full extracted text, encrypted
    file_hash: str                       # SHA256 of original file (integrity check)
    parse_confidence: float
    is_verified: bool = False            # has a doctor verified this parsing?
    abha_linked: bool = False            # synced to ABHA account?
    language: str = "en"                 # document language
    tags: list[str]                      # user-defined tags


class MedicationItem(BaseModel):
    medication_id: str
    prescription_id: str
    brand_name: str                     # as written on prescription
    generic_name: Optional[str]         # normalized using OpenFDA
    dosage_strength: str                # "500mg", "10mg/5ml"
    dosage_form: str                    # "tablet", "syrup", "injection"
    frequency: str                      # "twice daily", "BD", "OD"
    frequency_normalized: Optional[str] # standardized: "BD" -> "twice_daily"
    duration_days: Optional[int]
    route: str = "oral"                 # "oral", "topical", "IV"
    instructions: Optional[str]         # "take with food"
    rxcui: Optional[str]                # RxNorm concept ID (from OpenFDA)
    is_current: bool = True
    started_date: Optional[date]
    stopped_date: Optional[date]
    stopped_reason: Optional[str]


class Prescription(MedicalDocument):
    prescription_id: str
    prescribed_date: date
    prescribing_doctor: str             # PHI
    prescribing_doctor_reg_no: Optional[str]  # MCI registration number
    hospital_clinic: Optional[str]      # PHI
    diagnosis_mentioned: Optional[str]  # PHI: as written on prescription
    medications: list[MedicationItem]
    instructions: Optional[str]         # PHI: general instructions
    follow_up_date: Optional[date]
    follow_up_instructions: Optional[str]
    is_active: bool = True              # is this prescription still current?


class LabTestResult(BaseModel):
    result_id: str
    lab_report_id: str
    test_name: str
    test_name_normalized: Optional[str]  # standardized name
    loinc_code: Optional[str]           # LOINC code for interoperability
    value: str                          # PHI: actual result value
    unit: str
    reference_range_low: Optional[float]
    reference_range_high: Optional[float]
    reference_range_text: Optional[str]
    is_abnormal: bool
    abnormality_direction: Optional[Literal["high", "low", "critical_high", "critical_low"]]
    methodology: Optional[str]


class LabReport(MedicalDocument):
    lab_report_id: str
    lab_name: str                       # PHI
    collection_date: date
    report_date: date
    ordering_doctor: Optional[str]      # PHI
    test_results: list[LabTestResult]
    overall_interpretation: Optional[str]  # as written by lab
    critical_flags: list[str]           # tests flagged as critical/panic values


class CareEpisode(BaseModel):
    episode_id: str
    user_id: str
    condition: Optional[str]            # PHI: primary condition being managed
    icd10_code: Optional[str]           # ICD-10 classification
    start_date: date
    end_date: Optional[date]
    is_chronic: bool = False
    managing_doctors: list[str]         # PHI: list of involved doctors
    linked_prescriptions: list[str]     # prescription_ids
    linked_lab_reports: list[str]       # lab_report_ids
    summary: Optional[str]              # PHI: AI-generated episode summary
    status: Literal["active", "resolved", "chronic", "monitoring"]

    @field_validator("summary")
    @classmethod
    def validate_no_diagnosis(cls, v: str) -> str:
        """SAFETY GUARDRAIL: Reject summaries that sound like diagnostic claims."""
        if not v:
            return v
        forbidden_phrases = [
            r"\b(i diagnose|diagnosis is|patient is suffering from)\b"
        ]
        text_lower = v.lower()
        for pattern in forbidden_phrases:
            if re.search(pattern, text_lower):
                raise ValueError(f"Safety Violation: Summary contains potential diagnostic claim matching '{pattern}'")
        return v


class DrugInteractionAlert(BaseModel):
    alert_id: str
    user_id: str
    drug_a: str
    drug_b: str
    interaction_severity: Literal["contraindicated", "major", "moderate", "minor"]
    mechanism: str
    clinical_effect: str
    recommendation: str                 # ALWAYS ends with "Discuss with your doctor"
    source: str                         # "OpenFDA", "local_kb", "claude_analysis"
    detected_at: datetime
    is_acknowledged: bool = False
    acknowledged_by_doctor: bool = False

    @field_validator("recommendation")
    @classmethod
    def enforce_physician_consult(cls, v: str) -> str:
        """SAFETY GUARDRAIL: Ensure interactions always defer to a doctor."""
        if "doctor" not in v.lower() and "physician" not in v.lower():
            return v + " Discuss this interaction with your doctor."
        return v

class ParseConfidence(BaseModel):
    overall: float               # weighted average
    ocr_quality: float           # how clean was the source text?
    entity_extraction: float     # how confident in extracted entities?
    normalization: float         # how well were names/codes normalized?
    completeness: float          # what % of expected fields were found?
    low_confidence_fields: list[str]  # specific fields to flag for review

# ================================================================
# HANDOFF GENERATOR STRUCTURES
# ================================================================

class HistoryItem(BaseModel):
    category: str
    summary: str
    date: date
    source_document_id: str

class MedicationSummary(BaseModel):
    name: str
    dose: str
    frequency: str
    prescribed_by: str
    started_date: date
    interaction_flags: list[str] = Field(default_factory=list)

class LabResultSummary(BaseModel):
    test_name: str
    date: date
    value: str
    unit: str
    is_abnormal: bool
    reference_range: str

class ProviderBrief(BaseModel):
    brief_id: str
    user_id: str
    appointment_date: date
    appointment_type: str       # "specialist_consult", "gp_followup", "lab_review"
    provider_name: Optional[str]
    provider_specialty: Optional[str]
    generated_at: datetime

    presenting_concern: str     # 1-2 sentences, factual
    relevant_history: list[HistoryItem]
    current_medications: list[MedicationSummary]
    relevant_lab_results: list[LabResultSummary]
    unresolved_questions: list[str]
    previous_treatments: list[str]

    source_documents: list[str]  # document_ids used
    confidence: float
    generated_by: str = "MeshMed AgentOS"
    disclaimer: str = "This brief was compiled from patient-uploaded documents and may not reflect complete medical history. Verify with patient."

class PatientBrief(BaseModel):
    suggested_questions: list[str]      # based on care gaps + unresolved items
    things_to_mention: list[str]        # important history the patient may forget
    documents_to_bring: list[str]       # which physical documents are relevant
    things_to_ask_about: list[str]      # new medications, test results to review
    red_flag_reminders: list[str]       # symptoms to mention immediately if present

# ================================================================
# INSURANCE CLAIM COMPILATION STRUCTURES
# ================================================================

class ClaimForm(BaseModel):
    patient_name: str
    abha_id: Optional[str]
    diagnosis: str
    hospital_name: Optional[str]
    treating_doctor: Optional[str]
    treatment_start_date: Optional[date]
    treatment_end_date: Optional[date]
    # Note: These fields simulate IRDAI standard form fields

class CompletenessReport(BaseModel):
    missing_documents: list[str]
    incomplete_documents: list[str]
    ready_to_submit: bool

class ClaimPackage(BaseModel):
    episode_id: str
    insurer: str
    filled_form: ClaimForm
    documents: list[str]                # Document IDs compiled
    completeness: CompletenessReport
