"""
MeshMed Lab Report Parser.

Handles tabular data extraction from Indian Lab Reports (SRL, Thyrocare, etc).
Maps local test names to LOINC codes and flags critical anomalies.
"""

from typing import Tuple
from loguru import logger
import pdfplumber

from meshmed.models.schemas import LabReport, LabTestResult, ParseConfidence

# Local to LOINC mapping for 10 common Indian lab tests (MVP subset of 100+)
LOINC_MAP = {
    "hba1c": "4548-4",
    "glycosylated hemoglobin": "4548-4",
    "serum creatinine": "2160-0",
    "creatinine": "2160-0",
    "hemoglobin": "718-7",
    "hb": "718-7",
    "tsh": "3016-3",
    "thyroid stimulating hormone": "3016-3",
    "total cholesterol": "2093-3",
    "triglycerides": "2571-8"
}

# Critical boundaries (panic_low, panic_high) to flag anomalies
CRITICAL_THRESHOLDS = {
    "potassium": (2.5, 6.5),
    "glucose": (40.0, 500.0),
    "sodium": (120.0, 160.0),
    "hemoglobin": (6.0, 20.0)
}

class LabReportParser:
    def __init__(self):
        pass

    def extract_text_and_tables(self, pdf_path: str) -> str:
        """Extracts text and tabular structures using pdfplumber."""
        full_text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text() + "\n"
                    tables = page.extract_tables()
                    for table in tables:
                        # Convert table grid into structured text block for LLM
                        for row in table:
                            clean_row = [str(c).replace("\n", " ") if c else "" for c in row]
                            full_text += " | ".join(clean_row) + "\n"
            return full_text
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            raise

    def detect_critical_flags(self, test_name: str, value: str) -> bool:
        """Checks if a numeric lab value crosses strict panic thresholds."""
        try:
            val_float = float(value)
            t_name = test_name.lower().strip()
            if t_name in CRITICAL_THRESHOLDS:
                low, high = CRITICAL_THRESHOLDS[t_name]
                if val_float <= low or val_float >= high:
                    return True
        except ValueError:
            pass # Non-numeric result
        return False

    async def parse(self, file_path: str) -> Tuple[LabReport, ParseConfidence]:
        """Orchestrates lab parsing."""
        raw_text = self.extract_text_and_tables(file_path)
        
        # In a full implementation, we pass raw_text to claude-opus-4-6
        # to cleanly map the table rows into the LabReport schema.
        # For MVP, we mock the LLM call that returns the Pydantic object.
        
        # Mock structured data
        report = LabReport(
            document_id="mock_doc",
            user_id="mock_user",
            document_type="lab_report",
            upload_timestamp="2026-06-12T00:00:00Z",
            document_date="2026-06-12",
            raw_text_encrypted=raw_text, # Will be encrypted by decorator later
            file_hash="hash",
            parse_confidence=0.9,
            lab_name="SRL Diagnostics",
            collection_date="2026-06-11",
            report_date="2026-06-12",
            test_results=[],
            critical_flags=[]
        )
        
        # Post-process: Map LOINC and Critical Thresholds
        for test in report.test_results:
            normalized_name = test.test_name.lower().strip()
            test.loinc_code = LOINC_MAP.get(normalized_name)
            
            if self.detect_critical_flags(normalized_name, test.value):
                test.abnormality_direction = "critical_high" # Simplified
                report.critical_flags.append(test.test_name)
        
        conf = ParseConfidence(
            overall=0.92,
            ocr_quality=0.95,  # native PDFs are clean
            entity_extraction=0.9,
            normalization=0.85,
            completeness=0.9,
            low_confidence_fields=[]
        )
        
        return report, conf
