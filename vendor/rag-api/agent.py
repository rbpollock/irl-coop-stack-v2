"""LangGraph loader shim：僅供 CLI 載入正式 Deep Agents graph。"""

from app.chat.runtime.langgraph_boot_diagnostics import emit_langgraph_boot_diagnostics


emit_langgraph_boot_diagnostics("agent_shim")
from app.chat.runtime.langgraph_agent import graph
