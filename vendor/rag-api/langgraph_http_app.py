"""LangGraph loader shim：僅供 CLI 載入 FastAPI HTTP app。"""

from app.chat.runtime.langgraph_boot_diagnostics import emit_langgraph_boot_diagnostics


emit_langgraph_boot_diagnostics("http_shim")
from app.chat.runtime.langgraph_http_app import app
