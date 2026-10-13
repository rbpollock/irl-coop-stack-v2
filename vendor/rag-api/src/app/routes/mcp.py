"""MCP endpoint — exposes list_areas + retrieve_area_contexts as JSON-RPC tools.

A thin Model Context Protocol surface (streamable-HTTP shape, JSON-RPC 2.0 over
POST) so the coop-api MCP aggregator can proxy the RAG stack's retrieval
capability as `rag.*` tools. No LLM runs here — the client-side model calls these
tools and reasons on-device.

Auth is the same Bearer-token principal as every other protected route
(get_current_principal -> sub/groups), so the SQL gate, deny-by-default, and
ready-only boundaries hold unchanged.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_optional_principal
from app.auth.verifier import CurrentPrincipal
from app.chat.tools.retrieval import retrieve_area_contexts_tool
from app.core.settings import get_app_settings
from app.db.session import get_database_session
from app.services.areas import list_accessible_areas

router = APIRouter()


def _to_dict(obj: Any) -> Any:
    """Best-effort JSON conversion: Pydantic model_dump, dataclass asdict, else vars."""
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    return obj


def _text(data: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(data, default=str, ensure_ascii=False)}]}


def _serialize_retrieval(result: Any) -> dict[str, Any]:
    """Extract the LLM-relevant fields: assembled contexts + citation metadata."""
    # Map document_id → document_name (file name) from the citations, so callers
    # can resolve a result back to its source document.
    doc_names: dict[str, str] = {}
    for citation in result.citations:
        doc_id = getattr(citation, "document_id", None)
        name = getattr(citation, "document_name", None)
        if doc_id and name:
            doc_names.setdefault(doc_id, name)
    contexts = [
        {
            "document_id": c.document_id,
            "document_name": doc_names.get(c.document_id),
            "parent_chunk_id": c.parent_chunk_id,
            "chunk_ids": c.chunk_ids,
            "heading": c.heading,
            "text": c.assembled_text,
            "source": c.source,
            "start_offset": c.start_offset,
            "end_offset": c.end_offset,
        }
        for c in result.assembled_contexts
    ]
    citations = [
        c.model_dump(mode="json") if hasattr(c, "model_dump") else _to_dict(c)
        for c in result.citations
    ]
    return {"contexts": contexts, "citations": citations}


TOOLS = [
    {
        "name": "list_areas",
        "description": "List the knowledge areas the caller can access (id, name, role).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "retrieve_area_contexts",
        "description": (
            "Retrieve the relevant document contexts and citations for a question "
            "within one of the caller's areas. Enforces the same SQL gate, "
            "deny-by-default, and ready-only boundaries as the chat runtime."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "area_id": {"type": "string", "description": "The knowledge area id."},
                "question": {"type": "string", "description": "The question to retrieve evidence for."},
                "rerank": {"type": "boolean", "description": "Apply the cross-encoder rerank (default true); false = hybrid recall + RRF only."},
            },
            "required": ["area_id", "question"],
        },
    },
]


@router.post("/mcp")
def mcp_endpoint(
    body: dict[str, Any] = Body(...),
    principal: CurrentPrincipal = Depends(get_optional_principal),
    session: Session = Depends(get_database_session),
    settings=Depends(get_app_settings),
) -> dict[str, Any]:
    """Dispatch a single JSON-RPC message (initialize / tools/list / tools/call / ping)."""
    method = str(body.get("method", ""))
    params = body.get("params") or {}
    req_id = body.get("id")

    # JSON-RPC notification (no id) — acknowledge, no response.
    if req_id is None:
        return {}

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    try:
        if method == "initialize":
            return ok({
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "rag-mcp", "version": "1.0.0"},
            })
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "tools/call":
            name = str(params.get("name", ""))
            args = params.get("arguments") or {}
            if name == "list_areas":
                areas = list_accessible_areas(session=session, principal=principal)
                return ok(_text([_to_dict(a) for a in areas]))
            if name == "retrieve_area_contexts":
                result = retrieve_area_contexts_tool(
                    session=session,
                    principal=principal,
                    settings=settings,
                    area_id=str(args.get("area_id", "")),
                    question=str(args.get("question", "")),
                    rerank=bool(args.get("rerank", True)),
                )
                return ok(_text(_serialize_retrieval(result)))
            return err(-32602, f"unknown tool: {name}")
        return err(-32601, f"method not found: {method}")
    except Exception as exc:  # noqa: BLE001 — JSON-RPC needs a structured error, not a 500
        return err(-32603, f"internal error: {exc}")
