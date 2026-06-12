"""
MeshMed ABHA (Ayushman Bharat Health Account) Integration.

Integrates with NHA Sandbox APIs for fetching and linking personal health records (PHR).
Provides the FHIR R4 parser to convert ABHA standard payloads into MeshMed models.
"""

from typing import Optional, List
from datetime import datetime
from loguru import logger
import httpx

from meshmed.models.schemas import MedicalDocument, MedicationItem, LabReport

ABDM_GATEWAY_URL = "https://dev.abdm.gov.in/gateway/"

class FHIRParser:
    """Parses FHIR R4 bundles returned by the ABHA API into MeshMed internal models."""
    
    def parse_bundle(self, fhir_bundle: dict) -> List[MedicalDocument]:
        """Parse FHIR R4 bundle into MeshMed models."""
        documents = []
        entries = fhir_bundle.get("entry", [])
        for entry in entries:
            resource = entry.get("resource", {})
            r_type = resource.get("resourceType")
            
            if r_type == "MedicationRequest":
                # We extract the item, but usually wrap it in a MedicalDocument or Prescription
                med_item = self.parse_medication_request(resource)
                # For MVP: logging instead of returning raw items, returning empty docs
                logger.info(f"Parsed Medication: {med_item.brand_name}")
            elif r_type == "DiagnosticReport":
                lab_report = self.parse_diagnostic_report(resource)
                documents.append(lab_report)
                
        return documents

    def parse_medication_request(self, fhir_resource: dict) -> MedicationItem:
        """Parse FHIR MedicationRequest -> MedicationItem."""
        # MVP FHIR parsing stub
        med_concept = fhir_resource.get("medicationCodeableConcept", {}).get("text", "Unknown Med")
        dosage_instr = fhir_resource.get("dosageInstruction", [{}])
        frequency = dosage_instr[0].get("text", "Unknown frequency") if dosage_instr else "Unknown frequency"
        
        return MedicationItem(
            medication_id="fhir_mock",
            prescription_id="fhir_presc_mock",
            brand_name=med_concept,
            generic_name=med_concept,
            dosage_strength="Unknown",
            dosage_form="tablet",
            frequency=frequency,
            is_current=True
        )

    def parse_diagnostic_report(self, fhir_resource: dict) -> LabReport:
        """Parse FHIR DiagnosticReport -> LabReport."""
        # MVP FHIR parsing stub
        title = fhir_resource.get("code", {}).get("text", "Lab Report")
        effective_datetime = fhir_resource.get("effectiveDateTime", "2026-06-12")
        
        return LabReport(
            document_id="fhir_doc_mock",
            user_id="mock_user",
            document_type="lab_report",
            upload_timestamp=datetime.utcnow(),
            document_date=datetime.strptime(effective_datetime[:10], "%Y-%m-%d").date(),
            raw_text_encrypted=f"ABHA FHIR Payload: {title}",
            file_hash="fhir_hash",
            parse_confidence=1.0,
            lab_name="ABHA Connected Lab",
            collection_date=datetime.strptime(effective_datetime[:10], "%Y-%m-%d").date(),
            report_date=datetime.strptime(effective_datetime[:10], "%Y-%m-%d").date(),
            test_results=[],
            critical_flags=[]
        )

class ABHAIntegration:
    """Manages ABHA Linking and Consent-based Record Fetching."""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(base_url=ABDM_GATEWAY_URL, timeout=10.0)
        self.fhir_parser = FHIRParser()

    async def link_abha_id(self, user_id: str, abha_number: str) -> dict:
        """
        Initiate ABHA linking via OTP.
        """
        logger.info(f"Initiating ABHA link for {user_id} with ABHA {abha_number}")
        # MVP Stub: Normally POST /v0.5/users/auth/init
        return {"status": "otp_sent", "transaction_id": "mock_txn_123"}

    async def verify_abha_otp(self, user_id: str, transaction_id: str, otp: str) -> bool:
        """
        Verify OTP to finalize linking.
        """
        logger.info(f"Verifying ABHA OTP for {user_id}")
        # MVP Stub: Normally POST /v0.5/users/auth/confirm
        # Store encrypted ABHA ID in Postgres users table
        return True

    async def fetch_health_records(self, user_id: str, consent_artefact_id: str) -> List[MedicalDocument]:
        """
        Fetch PHR based on a granted consent artefact.
        """
        logger.info(f"Fetching health records for {user_id} using consent {consent_artefact_id}")
        # MVP Stub: Normally POST /v0.5/health-information/cm/request
        # And process incoming data transfer callbacks containing FHIR R4 bundles
        
        mock_fhir_bundle = {
            "resourceType": "Bundle",
            "entry": [
                {
                    "resource": {
                        "resourceType": "DiagnosticReport",
                        "code": {"text": "Complete Blood Count"},
                        "effectiveDateTime": "2026-05-10T10:00:00Z"
                    }
                }
            ]
        }
        
        return self.fhir_parser.parse_bundle(mock_fhir_bundle)

    async def push_health_record(self, user_id: str, document: MedicalDocument) -> bool:
        """
        Push user-uploaded documents back to ABHA.
        """
        logger.info(f"Pushing document {document.document_id} to ABHA for {user_id}")
        # MVP Stub: Requires document signing and provider registry auth.
        return True
