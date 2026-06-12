"""
MeshMed Insurance Claim Compiler.

Compiles medical evidence and pre-fills IRDAI standardized claim forms.
Integrates tightly with RiteOfWay (Day 06) for grievance processing.
"""

from typing import List, Optional
from datetime import datetime
from loguru import logger

from meshmed.models.schemas import CareEpisode, MedicalDocument, ClaimForm, CompletenessReport, ClaimPackage

# IRDAI standard documentary requirements
REQUIRED_DOCUMENT_TYPES = [
    "discharge_summary",
    "prescription",
    "lab_report"
    # "final_bill", "photo_id", "abha_card"
]

class InsuranceClaimCompiler:
    """Automates the painful process of compiling medical insurance claims."""
    
    def __init__(self):
        pass

    def check_completeness(self, episode: CareEpisode, uploaded_documents: List[MedicalDocument]) -> CompletenessReport:
        """
        Compare uploaded documents against IRDAI requirements for the episode.
        """
        logger.info(f"Checking claim completeness for episode {episode.episode_id}")
        
        found_types = {doc.document_type for doc in uploaded_documents}
        missing_documents = [req for req in REQUIRED_DOCUMENT_TYPES if req not in found_types]
        
        # Determine if ready (MVP logic)
        ready_to_submit = len(missing_documents) == 0
        
        return CompletenessReport(
            missing_documents=missing_documents,
            incomplete_documents=[],
            ready_to_submit=ready_to_submit
        )

    def generate_claim_form(self, episode: CareEpisode, documents: List[MedicalDocument]) -> ClaimForm:
        """
        Pre-populate standard IRDAI claim form fields from medical records.
        """
        logger.info(f"Pre-populating IRDAI claim form for episode {episode.episode_id}")
        
        # We assume the caller decrypts PHI before passing CareEpisode/MedicalDocument
        patient_name = "Patient Name (Requires Decrypted Scope)"
        hospital_name = "Hospital Name (From Docs)"
        treating_doctor = "Doctor Name (From Docs)"
        
        if episode.managing_doctors and len(episode.managing_doctors) > 0:
            treating_doctor = episode.managing_doctors[0]
            
        return ClaimForm(
            patient_name=patient_name,
            abha_id="ABHA-1234-5678-9012",
            diagnosis=episode.condition or "Unknown Condition",
            hospital_name=hospital_name,
            treating_doctor=treating_doctor,
            treatment_start_date=episode.start_date,
            treatment_end_date=episode.end_date
        )

    async def compile_claim(self, user_id: str, episode_id: str, insurer: str) -> ClaimPackage:
        """
        Compile the full claim package.
        1. Load documents
        2. Check completeness
        3. Generate form
        4. Compile zip (mocked)
        """
        logger.info(f"Compiling claim package for user {user_id}, insurer {insurer}")
        
        # 1. MVP Mock: Load docs
        mock_episode = CareEpisode(
            episode_id=episode_id, user_id=user_id, condition="Appendicitis",
            start_date=datetime.utcnow().date(), status="resolved", managing_doctors=[],
            linked_prescriptions=[], linked_lab_reports=[]
        )
        mock_docs = [] # Assume empty for mock, which means missing docs will be flagged
        
        # 2. Completeness
        completeness = self.check_completeness(mock_episode, mock_docs)
        
        # 3. Form Generation
        filled_form = self.generate_claim_form(mock_episode, mock_docs)
        
        # 4. Packaging
        logger.info(f"Claim package generation complete. Missing items: {completeness.missing_documents}")
        
        return ClaimPackage(
            episode_id=episode_id,
            insurer=insurer,
            filled_form=filled_form,
            documents=[d.document_id for d in mock_docs],
            completeness=completeness
        )
