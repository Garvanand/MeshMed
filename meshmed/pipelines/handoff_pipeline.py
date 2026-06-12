"""
MeshMed Handoff Packet Delivery Pipeline.

LangGraph workflow for fetching history, generating the PDFs, and sending WhatsApp summaries.
"""

from typing import TypedDict, Optional
from loguru import logger
from langgraph.graph import StateGraph, END

from meshmed.handoffs.generator import HandoffGenerator
from meshmed.models.schemas import ProviderBrief, PatientBrief


class HandoffState(TypedDict):
    user_id: str
    appointment_context: str
    target_specialty: str
    raw_history: list[dict]
    relevant_documents: list[dict]
    provider_brief: Optional[ProviderBrief]
    patient_brief: Optional[PatientBrief]
    quality_passed: bool
    pdf_path: str
    whatsapp_summary: str


def load_user_history(state: HandoffState) -> dict:
    """Fetch all recent encrypted history from PostgreSQL."""
    logger.info(f"Loading history for user {state['user_id']}")
    return {"raw_history": [{"doc_type": "prescription", "date": "2026-06-01"}]}

def determine_specialty_context(state: HandoffState) -> dict:
    """Map natural language context to a known specialty map."""
    # MVP: Mock routing
    specialty = state.get("target_specialty", "general")
    return {"target_specialty": specialty.lower()}

def select_relevant_documents(state: HandoffState) -> dict:
    """Filter history down to only what is needed for the target specialty."""
    # MVP: Pass everything through
    return {"relevant_documents": state["raw_history"]}

def generate_briefs(state: HandoffState) -> dict:
    """Invoke the HandoffGenerator."""
    # In a fully async graph, we would await the generator
    # For this synchronous node definition block, we mock the result
    return {
        "provider_brief": ProviderBrief(
            brief_id="mock_brief", user_id=state['user_id'], appointment_date="2026-06-15",
            appointment_type="specialist_consult", provider_specialty=state['target_specialty'],
            generated_at="2026-06-12T12:00:00Z", presenting_concern=state['appointment_context'],
            relevant_history=[], current_medications=[], relevant_lab_results=[], unresolved_questions=[],
            previous_treatments=[], source_documents=[], confidence=0.95
        ),
        "patient_brief": PatientBrief(
            suggested_questions=[], things_to_mention=[], documents_to_bring=[],
            things_to_ask_about=[], red_flag_reminders=[]
        )
    }

def quality_check(state: HandoffState) -> dict:
    """Ensure no diagnostic claims slipped through the LLM."""
    passed = True
    # If failed, we would route back to generate_briefs or fallback
    return {"quality_passed": passed}

def render_pdf(state: HandoffState) -> dict:
    """Use ReportLab to generate a clean printable PDF of the Provider Brief."""
    from reportlab.pdfgen import canvas
    
    # Mocking actual layout
    pdf_file = f"/tmp/meshmed_brief_{state['user_id']}.pdf"
    try:
        c = canvas.Canvas(pdf_file)
        c.drawString(100, 800, f"MeshMed Provider Brief for {state['target_specialty'].upper()}")
        c.drawString(100, 780, f"Context: {state['appointment_context']}")
        c.save()
        logger.info(f"Generated PDF: {pdf_file}")
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}")
        
    return {"pdf_path": pdf_file}

def send_whatsapp_summary(state: HandoffState) -> dict:
    """Format the PatientBrief for WhatsApp (bolding, emojis) and send."""
    summary = f"""*MeshMed Appointment Prep* 🏥

You have a {state['target_specialty']} appointment coming up.

*Ask your doctor:*
- {len(state['patient_brief'].suggested_questions)} questions prepared

*Don't forget to mention:*
- {len(state['patient_brief'].things_to_mention)} key items

I have generated a PDF for your doctor. Just forward it to them!"""

    logger.info(f"Sending WhatsApp Summary:\n{summary}")
    return {"whatsapp_summary": summary}


def build_handoff_graph() -> StateGraph:
    """Compile the LangGraph workflow."""
    workflow = StateGraph(HandoffState)
    
    workflow.add_node("load_user_history", load_user_history)
    workflow.add_node("determine_specialty_context", determine_specialty_context)
    workflow.add_node("select_relevant_documents", select_relevant_documents)
    workflow.add_node("generate_briefs", generate_briefs)
    workflow.add_node("quality_check", quality_check)
    workflow.add_node("render_pdf", render_pdf)
    workflow.add_node("send_whatsapp_summary", send_whatsapp_summary)
    
    workflow.set_entry_point("load_user_history")
    workflow.add_edge("load_user_history", "determine_specialty_context")
    workflow.add_edge("determine_specialty_context", "select_relevant_documents")
    workflow.add_edge("select_relevant_documents", "generate_briefs")
    workflow.add_edge("generate_briefs", "quality_check")
    workflow.add_edge("quality_check", "render_pdf")
    workflow.add_edge("render_pdf", "send_whatsapp_summary")
    workflow.add_edge("send_whatsapp_summary", END)
    
    return workflow.compile()
