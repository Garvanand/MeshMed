"""
MeshMed Care Journey LangGraph Pipeline.

Executes natural language queries over the patient's medical timeline.
"""

import operator
from typing import Annotated, Sequence, TypedDict, Any
from loguru import logger
from langchain_core.prompts import PromptTemplate
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from meshmed.core.config import get_settings

class CareJourneyState(TypedDict):
    user_id: str
    query: str
    query_type: str # 'medication_history', 'lab_trend', 'temporal_search', 'doctor_search'
    retrieved_documents: list[dict]
    structured_data: list[dict]
    safe_response: str
    whatsapp_formatted: str


SAFE_RESPONSE_PROMPT = """
You are a factual medical information coordinator.
Your ONLY job is to answer the patient's question based strictly on the provided medical records.

CRITICAL SAFETY CONSTRAINTS:
1. Answer the factual question precisely based ONLY on the context.
2. ALWAYS include source citations exactly like this: "According to your lab report from Dr. [Name] on [Date]..."
3. NEVER add clinical interpretation. Do NOT say a condition is worsening or improving.
4. MUST ALWAYS END YOUR RESPONSE WITH: "For any concerns about these results, please consult your doctor."

Context Records:
{records}

Patient Question:
{query}
"""

def parse_query(state: CareJourneyState) -> dict:
    """Parse and clean the raw natural language query."""
    return {"query": state["query"].strip()}

def determine_query_type(state: CareJourneyState) -> dict:
    """Determine the intent of the query for optimal routing."""
    # MVP Stub: Default to general temporal search
    return {"query_type": "temporal_search"}

def retrieve_relevant_documents(state: CareJourneyState) -> dict:
    """
    Search ChromaDB `meshmed_documents` collection.
    Note: ChromaDB only stores document UUIDs and embeddings.
    No PHI is present in the vector DB. We fetch UUIDs, then fetch encrypted PHI from Postgres.
    """
    logger.info("Searching ChromaDB using embeddings...")
    # Mock retrieval
    return {"retrieved_documents": [{"doc_id": "123", "type": "lab_report", "date": "2024-01-15"}]}

def execute_structured_query(state: CareJourneyState) -> dict:
    """
    If query_type is 'lab_trend' or similar, perform structured SQL queries
    in Postgres to fetch the specific data points.
    """
    # Fetch actual decrypted PHI using document UUIDs via @decrypt_phi decorators
    mock_data = [{"source": "Dr. Smith", "date": "2024-01-15", "details": "HbA1c: 6.2%"}]
    return {"structured_data": mock_data}

def generate_safe_response(state: CareJourneyState) -> dict:
    """Uses Claude to generate the final response with extreme safety constraints."""
    llm = ChatAnthropic(
        model="claude-3-opus-20240229",
        api_key=get_settings().anthropic_api_key,
        temperature=0.0
    )
    prompt = PromptTemplate.from_template(SAFE_RESPONSE_PROMPT)
    chain = prompt | llm
    
    # Format records context
    records_str = "\n".join([str(r) for r in state["structured_data"]])
    
    try:
        response = chain.invoke({"records": records_str, "query": state["query"]})
        return {"safe_response": response.content}
    except Exception as e:
        logger.error(f"Failed to generate safe response: {e}")
        return {"safe_response": "I am unable to retrieve this information right now. Please consult your doctor for medical advice."}

def format_for_channel(state: CareJourneyState) -> dict:
    """Format the safe response for WhatsApp (bolding, lists)."""
    wa_msg = f"*MeshMed Request*\n\n{state['safe_response']}"
    return {"whatsapp_formatted": wa_msg}


def build_care_journey_graph() -> StateGraph:
    """Compile the LangGraph workflow."""
    workflow = StateGraph(CareJourneyState)
    
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("determine_query_type", determine_query_type)
    workflow.add_node("retrieve_relevant_documents", retrieve_relevant_documents)
    workflow.add_node("execute_structured_query", execute_structured_query)
    workflow.add_node("generate_safe_response", generate_safe_response)
    workflow.add_node("format_for_channel", format_for_channel)
    
    workflow.set_entry_point("parse_query")
    workflow.add_edge("parse_query", "determine_query_type")
    workflow.add_edge("determine_query_type", "retrieve_relevant_documents")
    workflow.add_edge("retrieve_relevant_documents", "execute_structured_query")
    workflow.add_edge("execute_structured_query", "generate_safe_response")
    workflow.add_edge("generate_safe_response", "format_for_channel")
    workflow.add_edge("format_for_channel", END)
    
    return workflow.compile()
