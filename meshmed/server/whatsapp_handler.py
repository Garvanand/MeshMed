"""
MeshMed WhatsApp Interaction Layer.

The primary user interface for MeshMed, operating over 2G-friendly WhatsApp.
Supports multi-turn medical flows, document uploads, and AgentOS integrations.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger
from pydantic import BaseModel

# Mocked Redis integration for State Machine
# In a real app: import redis.asyncio as redis
mock_redis_store = {}

# ================================================================
# PRE-APPROVED WHATSAPP BUSINESS API TEMPLATES
# ================================================================
WHATSAPP_TEMPLATES = {
    "appointment_reminder": {
        "name": "appointment_reminder_template",
        "body": "Your appointment summary is ready! We've prepared a brief for your doctor and a checklist for you."
    },
    "drug_interaction_alert": {
        "name": "drug_interaction_alert_template",
        "body": "Important: We noticed a potential medication interaction in your recent records. Please review the attached alert."
    },
    "care_gap_reminder": {
        "name": "care_gap_reminder_template",
        "body": "Health check reminder: It has been a while since your last {test_name}. Would you like help preparing for your next appointment?"
    },
    "claim_ready": {
        "name": "claim_ready_template",
        "body": "Your insurance claim package is ready for submission."
    },
    "weekly_health_summary": {
        "name": "weekly_health_summary_template",
        "body": "Here is your weekly MeshMed health summary."
    }
}

# ================================================================
# CONVERSATION STATE MACHINE
# ================================================================
class ConversationState(BaseModel):
    user_id: str
    current_flow: Optional[str]  # "appointment_prep", "document_upload", etc.
    flow_step: int = 0
    context: Dict[str, Any] = {}
    last_message_at: datetime
    expires_at: datetime


class WhatsAppHandler:
    def __init__(self):
        pass

    async def get_state(self, user_id: str) -> ConversationState:
        """Fetch active multi-turn conversation state from Redis."""
        state = mock_redis_store.get(user_id)
        now = datetime.utcnow()
        if state and state.expires_at > now:
            return state
        # Create fresh state if expired or missing
        return ConversationState(
            user_id=user_id,
            current_flow=None,
            flow_step=0,
            last_message_at=now,
            expires_at=now + timedelta(minutes=30)
        )

    async def save_state(self, state: ConversationState):
        """Save conversation state back to Redis with TTL."""
        state.last_message_at = datetime.utcnow()
        state.expires_at = state.last_message_at + timedelta(minutes=30)
        mock_redis_store[state.user_id] = state

    async def clear_state(self, user_id: str):
        if user_id in mock_redis_store:
            del mock_redis_store[user_id]

    async def send_message(self, user_id: str, text: str, buttons: Optional[list] = None):
        """Mock WhatsApp API send text/buttons."""
        logger.info(f"WhatsApp -> [{user_id}]: {text}")
        if buttons:
            logger.info(f"Buttons: {buttons}")
        return True

    async def send_template(self, user_id: str, template_name: str, variables: list = None):
        """Mock WhatsApp API send pre-approved template."""
        template = WHATSAPP_TEMPLATES.get(template_name)
        if template:
            logger.info(f"WhatsApp (TEMPLATE) -> [{user_id}]: {template['name']}")
        return True

    # ================================================================
    # FLOW 1: DOCUMENT UPLOAD
    # ================================================================
    async def handle_document_upload(self, user_id: str, media_url: str):
        await self.send_message(user_id, "Got it! Processing your prescription... 🏥")
        
        # Mock Parser execution
        meds = ["Metformin 500mg BD", "Aspirin 75mg OD"]
        meds_str = "\n- ".join(meds)
        
        msg = (
            f"I've added your prescription from Dr. Smith on today's date.\n"
            f"Found {len(meds)} medications:\n- {meds_str}\n\n"
            "Please check if this looks correct."
        )
        await self.send_message(user_id, msg, buttons=["✅ Looks correct", "❌ Something's wrong"])
        
        # We don't advance the state heavily here for MVP, but normally:
        state = await self.get_state(user_id)
        state.current_flow = "document_upload_verification"
        await self.save_state(state)

    # ================================================================
    # FLOW 2: APPOINTMENT REMINDER TRIGGER (Multi-turn)
    # ================================================================
    async def handle_appointment_prep(self, user_id: str, message: str, state: ConversationState):
        if state.flow_step == 0:
            msg = (
                "I'll prepare your medical summary for Dr. Sharma.\n"
                "What specialty is this appointment? (General / Cardiology / Other)"
            )
            state.current_flow = "appointment_prep"
            state.flow_step = 1
            await self.save_state(state)
            await self.send_message(user_id, msg)
        
        elif state.flow_step == 1:
            specialty = message.strip()
            # Generate Handoff Packet
            logger.info(f"Generating packet for specialty: {specialty}")
            
            msg = (
                "Your medical summary is ready! I've sent you the PDF.\n\n"
                "Key points for tomorrow:\n"
                "- Mention your recent dizzy spells.\n"
                "- Ask if you should continue the Metformin.\n"
                "- Bring your recent CBC report."
            )
            await self.send_message(user_id, msg)
            await self.clear_state(user_id)

    # ================================================================
    # FLOW 3: MEDICATION QUERY
    # ================================================================
    async def handle_medication_query(self, user_id: str):
        # Fetch from DB logic
        msg = (
            "You are currently taking:\n"
            "1. Metformin 500mg (Twice daily)\n"
            "   Prescribed by: Dr. Sharma since Jan 2024\n"
            "2. Aspirin 75mg (Once daily)\n"
            "   Prescribed by: Dr. Gupta since Mar 2024\n\n"
            "⚠️ Notice: You may be running low on Aspirin (30-day supply ends soon)."
        )
        await self.send_message(user_id, msg)

    # ================================================================
    # FLOW 4: LAB RESULT QUERY
    # ================================================================
    async def handle_lab_query(self, user_id: str, test_name: str):
        # Fetch from DB logic
        msg = (
            f"Your most recent {test_name} test was on 10 May 2024.\n"
            "Result: 6.2 %\n"
            "Normal Reference Range: 4.0 - 5.7 %\n\n"
            "For any concerns about these results, please consult your doctor." # Strict Safety Enforced
        )
        await self.send_message(user_id, msg)

    # ================================================================
    # FLOW 5: DRUG INTERACTION ALERT
    # ================================================================
    async def send_drug_interaction_alert(self, user_id: str, drug_a: str, drug_b: str, plain_language: str):
        await self.send_template(user_id, "drug_interaction_alert")
        msg = (
            f"⚠️ Heads up: I noticed that {drug_a} and {drug_b} that you've been prescribed may interact.\n\n"
            f"This is something to mention to your doctor. {plain_language}\n\n"
            "Please don't stop any medication without speaking to your doctor first."
        )
        await self.send_message(user_id, msg)

    # ================================================================
    # FLOW 6: CARE GAP REMINDER
    # ================================================================
    async def send_care_gap_reminder(self, user_id: str, doctor_name: str, test_name: str):
        await self.send_template(user_id, "care_gap_reminder", variables=[test_name])
        msg = (
            f"A friendly reminder: Your last {test_name} test was 4 months ago. "
            f"Based on your records, Dr. {doctor_name} had mentioned checking it every 3 months.\n\n"
            "Would you like help finding a lab or preparing a reminder for your next appointment?"
        )
        await self.send_message(user_id, msg, buttons=["Yes, prepare reminder", "Not now"])

    # ================================================================
    # FLOW 7: VOICE INTERACTION (VaakShastra Routing)
    # ================================================================
    async def handle_voice_interaction(self, user_id: str, audio_file_url: str):
        """
        Receives voice note from WhatsApp. 
        Routes to VaakShastra (Day 01) for ASR -> processes intent -> routes to VaakShastra for TTS -> sends audio reply.
        """
        logger.info(f"Received Voice Note from {user_id}. Routing to VaakShastra API...")
        # Mocking VaakShastra processing
        transcript = "Mere sugar reports kaise hain?" # "How are my sugar reports?"
        await self.handle_lab_query(user_id, "HbA1c / Sugar")


    # ================================================================
    # MAIN ENTRY ROUTER
    # ================================================================
    async def process_incoming_message(self, user_id: str, message: str = None, media: str = None, is_audio: bool = False):
        """Master webhook router."""
        logger.info(f"Processing incoming WhatsApp from {user_id}")
        
        state = await self.get_state(user_id)
        
        # 1. Continue existing multi-turn flow
        if state.current_flow == "appointment_prep":
            return await self.handle_appointment_prep(user_id, message, state)
            
        # 2. Handle Audio
        if is_audio:
            return await self.handle_voice_interaction(user_id, media)
            
        # 3. Handle Images (Prescriptions/Labs)
        if media and not is_audio:
            return await self.handle_document_upload(user_id, media)
            
        # 4. Intent Routing (Mocked Regex for MVP)
        text = message.lower().strip() if message else ""
        
        if "appointment" in text or "doctor" in text:
            return await self.handle_appointment_prep(user_id, message, state)
            
        if "medication" in text or "what am i taking" in text:
            return await self.handle_medication_query(user_id)
            
        if "sugar" in text or "lab" in text or "hba1c" in text:
            return await self.handle_lab_query(user_id, "HbA1c")
            
        # Fallback
        await self.send_message(user_id, "I didn't quite catch that. Would you like me to prepare for an appointment or check your medications?")
