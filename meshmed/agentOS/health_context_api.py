"""
MeshMed AgentOS Integration Layer.

Exposes safe, non-PHI, structured context to the rest of the AgentOS ecosystem
(VaakShastra, GhostCFO, RiteOfWay, SoulMap) while maintaining strict audit logging.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import httpx
from loguru import logger

from meshmed.models.schemas import HealthDataAccessLog

router = APIRouter(prefix="/v1/agentOS/health", tags=["AgentOS Health Context"])

# ================================================================
# AUDIT LOGGING MIDDLEWARE / DEPENDENCY
# ================================================================

async def log_access(
    user_id: str, 
    accessed_by: str, 
    access_type: str, 
    data_category: str, 
    purpose: str, 
    ip_address: Optional[str] = None
):
    """Logs all health data access for HIPAA/DISHA compliance."""
    log_entry = HealthDataAccessLog(
        log_id=str(uuid.uuid4()),
        user_id=user_id,
        accessed_by=accessed_by,
        access_type=access_type,
        data_category=data_category,
        purpose=purpose,
        timestamp=datetime.utcnow(),
        ip_address=ip_address
    )
    # MVP: Async DB insert mock
    logger.info(f"AUDIT LOG: {accessed_by} accessed {data_category} for {user_id} ({purpose})")

# ================================================================
# ENDPOINTS
# ================================================================

@router.get("/context/{user_id}")
async def get_health_context(user_id: str, request: Request):
    """
    Returns shared memory object (no PHI)
    Used by: SoulMap (emotional context), NexusOps (scheduling around health)
    """
    await log_access(user_id, "agentOS:soulmap/nexusops", "read", "shared_context", "contextual_awareness", request.client.host)
    
    return {
        "updated_at": "2026-06-12T08:00:00+05:30",
        "has_chronic_conditions": True,
        "chronic_condition_categories": ["metabolic", "cardiovascular"],
        "medication_count": 4,
        "has_active_drug_interactions": False,
        "pending_care_gaps": 2,
        "last_lab_upload_days_ago": 45,
        "upcoming_appointment": True,
        "upcoming_appointment_days": 2,
        "insurance_claim_pending": False,
        "health_engagement_score": 72,
        "preferred_language": "hi",
        "preferred_interaction": "voice",
        "abha_linked": True
    }


@router.get("/appointment_ready/{user_id}")
async def get_appointment_readiness(user_id: str, request: Request):
    """
    Returns appointment readiness state.
    Used by: VaakShastra (proactive voice reminder), scheduling agent.
    """
    await log_access(user_id, "agentOS:vaakshastra", "read", "appointment_status", "proactive_reminder", request.client.host)
    
    return {
        "has_pending_appointment": True,
        "days_until": 2,
        "specialty": "Cardiology",
        "handoff_ready": True
    }


class ClaimEvidenceRequest(BaseModel):
    user_id: str
    episode_id: str
    claim_type: str

@router.post("/claim_evidence_package")
async def generate_claim_evidence_package(req: ClaimEvidenceRequest, request: Request):
    """
    Used by: RiteOfWay (Day 06) for insurance grievance filing.
    """
    await log_access(req.user_id, "agentOS:riteofway", "export", "claim_evidence", "grievance_filing", request.client.host)
    
    return {
        "status": "compiled",
        "download_url": f"https://internal.agentos.local/storage/claims/evidence_{req.user_id}_{req.episode_id}.zip",
        "document_count": 5
    }


@router.get("/medication_list/{user_id}")
async def get_medication_list(user_id: str, request: Request):
    """
    Returns list of medication names ONLY (no diagnosis, no PHI beyond drug names).
    Used by: scheduling agent.
    """
    await log_access(user_id, "agentOS:scheduler", "read", "medications", "scheduling_conflict_check", request.client.host)
    
    return {
        "medications": ["Metformin", "Aspirin", "Lisinopril", "Atorvastatin"]
    }


class ExpenseLogRequest(BaseModel):
    user_id: str
    amount: float
    category: str = "health"
    description_category: str

@router.post("/expense_logged")
async def log_expense(req: ExpenseLogRequest, request: Request):
    """
    Notifies GhostCFO of health-related expense.
    """
    await log_access(req.user_id, "agentOS:meshmed", "write", "expense_sync", "ghostcfo_integration", request.client.host)
    
    # Mock GhostCFO HTTP Call
    # async with httpx.AsyncClient() as client:
    #     await client.post("http://ghostcfo:8000/v1/agentOS/financial/expense_recorded", json=req.dict())
        
    return {"status": "synced_to_ghostcfo"}

# ================================================================
# VAAKSHASTRA (Day 01) INTEGRATION PATTERNS
# ================================================================
"""
MeshMed uses VaakShastra for elderly patients. The exact integration call patterns:

1. Voice-based Medication Reminder
----------------------------------
MeshMed Cron Job -> detects medication due -> calls VaakShastra TTS:
POST http://vaakshastra:8000/v1/tts/generate
{
    "text": "Namaste, aapki Metformin ki goli lene ka samay ho gaya hai.",
    "language": "hi-IN",
    "voice_id": "empathetic_female_1"
}
-> Returns audio URL -> MeshMed sends via WhatsApp Audio message.


2. Voice-based Health Queries
----------------------------------
User sends WhatsApp voice note -> MeshMed webhook receives it.
MeshMed -> calls VaakShastra ASR:
POST http://vaakshastra:8000/v1/asr/transcribe
{
    "audio_url": "whatsapp_media_url",
    "language_hint": "hi-IN"
}
-> Returns text ("Mere sugar reports kaise hain?").
-> MeshMed processes text in LangGraph pipeline.
-> MeshMed gets text reply ("Aapka aakhiri sugar report normal tha...")
-> MeshMed -> calls VaakShastra TTS (as above).
-> MeshMed sends audio reply.


3. Audio Delivery of Appointment Reminders
----------------------------------
MeshMed determines handoff is ready.
MeshMed -> calls VaakShastra TTS:
POST http://vaakshastra:8000/v1/tts/generate
{
    "text": "Kal aapka appointment Dr. Sharma ke paas hai. Maine aapki reports unhe bhej di hain.",
    "language": "hi-IN"
}
-> MeshMed sends audio to user.
"""
