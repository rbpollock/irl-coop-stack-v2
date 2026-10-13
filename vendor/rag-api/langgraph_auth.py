"""LangGraph loader shim：僅供 CLI 載入 custom auth handler。"""

from app.chat.runtime.langgraph_boot_diagnostics import emit_langgraph_boot_diagnostics


emit_langgraph_boot_diagnostics("auth_shim")
from app.chat.runtime.langgraph_auth import auth
