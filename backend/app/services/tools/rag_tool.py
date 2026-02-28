import logging
import uuid

from backend.app.services.tools.base import register_tool
from backend.app.services.knowledge_service import search_knowledge_base
from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import Call, AgentConfig

log = logging.getLogger(__name__)

async def _query_knowledge_base(
    query: str,
    call_id: str,
    tenant_id: str,
    **kwargs,
) -> dict:
    """
    Query the knowledge base for relevant information.
    The kb_id is automatically inferred from the agent config via the call_id.
    """
    try:
        # Fetch the call's associated agent configuration to get the KB ID
        async with AsyncSessionLocal() as db:
            call = await db.get(Call, uuid.UUID(call_id))
            if not call:
                return {
                    "success": False,
                    "message": "Call not found, unable to query knowledge base."
                }
                
            agent_config = await db.get(AgentConfig, call.agent_config_id)
            if not agent_config or not agent_config.knowledge_base_id:
                return {
                    "success": False,
                    "message": "No knowledge base is configured for this agent."
                }
                
            kb_id = str(agent_config.knowledge_base_id)
            
            # Perform similarity search
            search_result = await search_knowledge_base(
                kb_id=kb_id, 
                query=query, 
                db=db, 
                limit=3
            )
            
            if search_result:
                return {
                    "success": True,
                    "context": search_result,
                    "message": "Successfully retrieved context. Use this context to answer the user's question."
                }
            else:
                return {
                    "success": True,
                    "context": "",
                    "message": "I searched the knowledge base but found no relevant information for this query."
                }

    except Exception as exc:
        log.exception("rag_tool_error", error=str(exc))
        return {
            "success": False,
            "error": str(exc),
            "message": "An error occurred while searching the knowledge base.",
        }

# ─── Register the tool ────────────────────────────────────────────────────────

register_tool(
    name="query_knowledge_base",
    description=(
        "Query the company's knowledge base to find answers to specific questions about products, services, policies, or general company information. "
        "Use this tool when the user asks a factual question you do not know the answer to."
    ),
    parameters={
        "type_": "OBJECT",
        "properties": {
            "query": {
                "type_": "STRING",
                "description": "The specific question or topic to search for in the knowledge base.",
            }
        },
        "required": ["query"],
    },
    func=_query_knowledge_base,
)
