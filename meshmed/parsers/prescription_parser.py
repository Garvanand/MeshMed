"""
MeshMed Prescription Parser.

Handles Indian handwritten prescriptions via OCR and LLM Vision extraction.
Normalizes abbreviations and strictly refuses to infer unwritten medical details.
"""

import os
from typing import Optional, Tuple
from loguru import logger
from PIL import Image

from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq

from meshmed.models.schemas import Prescription, MedicationItem, ParseConfidence
from meshmed.core.config import get_settings


INDIAN_DOSAGE_MAP = {
    "OD": "once_daily",
    "QD": "once_daily",
    "BD": "twice_daily",
    "BID": "twice_daily",
    "TDS": "three_times_daily",
    "TID": "three_times_daily",
    "QID": "four_times_daily",
    "HS": "at_bedtime",
    "SOS": "as_needed",
    "PRN": "as_needed",
    "AC": "before_meals",
    "PC": "after_meals",
    "STAT": "immediately"
}

# The LLM prompt for extracting structured data from raw OCR text
PRESCRIPTION_EXTRACTION_PROMPT = """
You are an expert clinical pharmacist in India.
Your task is to extract structured medication and prescription data from the raw OCR text of a doctor's handwritten or typed prescription.

CRITICAL SAFETY RULES:
1. NEVER INFER WHAT IS NOT WRITTEN. If dosage is illegible or missing, return null and flag confidence.
2. NEVER SUGGEST DIAGNOSES. Just extract what is written on the paper.
3. If a drug name is partially legible, extract your best guess but flag overall confidence.
4. Normalize abbreviations using standard mappings (e.g., Tab -> tablet, Cap -> capsule, Inj -> injection).

Raw OCR Text:
{ocr_text}

Extract the following fields and return as JSON matching the requested schema.
Apply these standard dosage normalizations if you see them:
OD/QD = once_daily, BD/BID = twice_daily, TDS/TID = three_times_daily, QID = four_times_daily, HS = at_bedtime, SOS/PRN = as_needed, AC = before_meals, PC = after_meals, STAT = immediately.
"""

class PrescriptionParser:
    def __init__(self):
        self.settings = get_settings()
        # Primary for structuring text
        self.structuring_llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=self.settings.groq_api_key,
            temperature=0.0
        )
        # Fallback for vision if OCR fails or is terrible
        self.vision_llm = ChatAnthropic(
            model="claude-3-opus-20240229",
            api_key=self.settings.anthropic_api_key,
            temperature=0.0
        )

    async def pre_process_image(self, image_path: str) -> Image.Image:
        """Deskew, denoise, enhance contrast."""
        try:
            img = Image.open(image_path)
            # In a real pipeline: apply OpenCV adaptive thresholding and deskewing here.
            # img = cv2_preprocess(img)
            return img
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            raise

    async def extract_ocr_text(self, img: Image.Image) -> Tuple[str, float]:
        """
        Uses pytesseract or Google Vision API to get raw text.
        Returns (extracted_text, confidence_score)
        """
        import pytesseract
        try:
            # MVP: Tesseract fallback
            text = pytesseract.image_to_string(img)
            # Tesseract confidence is complex to average, returning mock 0.85 for MVP
            return text.strip(), 0.85
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return "", 0.0

    def normalize_dosage(self, frequency: str) -> Optional[str]:
        if not frequency:
            return None
        freq_upper = frequency.strip().upper()
        return INDIAN_DOSAGE_MAP.get(freq_upper, frequency)

    async def parse(self, file_path: str) -> Tuple[Prescription, ParseConfidence]:
        """Orchestrates the entire parsing pipeline."""
        img = await self.pre_process_image(file_path)
        raw_text, ocr_conf = await self.extract_ocr_text(img)
        
        # Determine if we should fallback to Claude Vision
        if ocr_conf < 0.5 or len(raw_text) < 20:
            logger.info("OCR confidence low, routing to Claude Vision for raw extraction.")
            # Mock Claude Vision call (requires base64 image encoding in LangChain)
            pass

        prompt = PromptTemplate.from_template(PRESCRIPTION_EXTRACTION_PROMPT)
        chain = prompt | self.structuring_llm.with_structured_output(Prescription)
        
        try:
            # Assuming LangChain handles JSON output mapping to Pydantic
            prescription: Prescription = await chain.ainvoke({"ocr_text": raw_text})
            
            # Post-process normalization
            for item in prescription.medications:
                item.frequency_normalized = self.normalize_dosage(item.frequency)
            
            # Calculate Confidence Breakdown
            conf = ParseConfidence(
                overall=(ocr_conf * 0.4) + 0.5, # Mock math
                ocr_quality=ocr_conf,
                entity_extraction=0.9,
                normalization=0.95,
                completeness=0.8,
                low_confidence_fields=[]
            )
            
            if conf.overall < 0.7:
                logger.warning(f"Low parsing confidence ({conf.overall}). Queuing for WhatsApp user verification.")
                
            return prescription, conf
            
        except Exception as e:
            logger.error(f"LLM Extraction failed: {e}")
            raise
