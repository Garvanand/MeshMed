"""
MeshMed FastAPI Server.

Exposes the WhatsApp Webhook and internal AgentOS integration endpoints
so that VaakShastra, GhostCFO, and RiteOfWay can coordinate with MeshMed.
"""

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from meshmed.core.config import get_settings
from meshmed.server.whatsapp_handler import WhatsAppHandler
from meshmed.agentOS.health_context_api import router as agentos_router

app = FastAPI(title="MeshMed - AgentOS Coordination Layer")
whatsapp_handler = WhatsAppHandler()

app.include_router(agentos_router)

# ================================================================
# WHATSAPP WEBHOOKS (Primary External Interface)
# ================================================================

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receives incoming WhatsApp messages (Text, Audio, Images).
    """
    payload = await request.json()
    # Assuming standard WhatsApp Business API payload structure
    try:
        messages = payload['entry'][0]['changes'][0]['value']['messages']
        user_id = messages[0]['from']
        msg_type = messages[0]['type']
        
        message_text = None
        media_url = None
        is_audio = False
        
        if msg_type == 'text':
            message_text = messages[0]['text']['body']
        elif msg_type == 'image':
            media_url = messages[0]['image']['id'] # Normally fetch URL using media ID
        elif msg_type == 'audio':
            media_url = messages[0]['audio']['id']
            is_audio = True
            
        await whatsapp_handler.process_incoming_message(
            user_id=user_id,
            message=message_text,
            media=media_url,
            is_audio=is_audio
        )
        return {"status": "ok"}
    except KeyError:
        return {"status": "ignored"}

# ================================================================
# AGENT OS INTERNAL ENDPOINTS
# ================================================================

class GhostCFOExpenseReport(BaseModel):
    user_id: str
    expense_type: str
    amount: float
    date: str
    description: str

@app.get("/v1/agentOS/health/context/{user_id}")
async def get_shared_health_context(user_id: str):
    """
    Endpoint for other agents (like SoulMap or VaakShastra) to fetch
    the high-level shared health memory context.
    """
    return {
        "user_id": user_id,
        "active_conditions": ["Diabetes Type II"],
        "medication_count": 2,
        "last_upload": "2026-06-12"
    }

@app.post("/v1/agentOS/finance/expense_sync")
async def sync_expense_to_ghostcfo(expense: GhostCFOExpenseReport):
    """
    MeshMed calls this to notify GhostCFO (Day 02) when a user uploads
    a hospital bill or pharmacy receipt.
    """
    # In reality, this would make an outgoing HTTP call to the GhostCFO container.
    return {"status": "synced_to_finance_layer"}

@app.post("/v1/agentOS/legal/submit_grievance")
async def trigger_riteofway_grievance(user_id: str, episode_id: str):
    """
    MeshMed triggers RiteOfWay (Day 06) to automatically file an insurance
    grievance using the compiled ClaimPackage.
    """
    # Outgoing call to RiteOfWay container
    return {"status": "grievance_initiated", "evidence_attached": True}
