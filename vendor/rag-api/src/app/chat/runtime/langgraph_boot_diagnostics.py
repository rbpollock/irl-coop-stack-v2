"""LangGraph 啟動診斷輔助工具。"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any


# 啟動診斷需要觀測的 LangGraph 環境變數鍵集合。
BOOT_DIAGNOSTIC_ENV_KEYS: tuple[str, ...] = (
    "LANGGRAPH_AUTH",
    "LANGGRAPH_HTTP",
    "LANGGRAPH_AUTH_TYPE",
    "LANGGRAPH_RUNTIME_EDITION",
)

# 避免啟動 log 被超長 JSON 淹沒的單一欄位長度上限。
MAX_LOG_VALUE_LENGTH = 600

# LangGraph 啟動診斷專用 logger。
logger = logging.getLogger(__name__)


def _truncate(value: str | None) -> str | None:
    """限制 log 欄位長度，避免單行過長。

    參數：
    - `value`：原始字串值。

    回傳：
    - `str | None`：截斷後的字串；若原值為 `None` 則回傳 `None`。
    """

    if value is None or len(value) <= MAX_LOG_VALUE_LENGTH:
        return value
    return f"{value[:MAX_LOG_VALUE_LENGTH]}...(truncated)"


def _read_json_env(key: str) -> dict[str, Any] | list[Any] | None:
    """讀取並解析指定的 JSON 環境變數。

    參數：
    - `key`：要讀取的環境變數名稱。

    回傳：
    - `dict[str, Any] | list[Any] | None`：成功解析時回傳 JSON 結構；未設定或解析失敗時回傳 `None`。
    """

    raw_value = os.getenv(key)
    if not raw_value:
        return None
    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        logger.warning("LangGraph boot diagnostics JSON parse failed: key=%s raw=%s", key, _truncate(raw_value))
        return None
    if isinstance(parsed_value, dict | list):
        return parsed_value
    return None


def emit_langgraph_boot_diagnostics(entrypoint: str) -> None:
    """輸出 LangGraph 啟動時的重要診斷資訊。

    參數：
    - `entrypoint`：目前發出診斷 log 的載入入口標記，例如 `agent_shim` 或 `http_shim`。

    回傳：
    - `None`：僅輸出診斷 log，不回傳值。
    """

    raw_snapshot = {key: _truncate(os.getenv(key)) for key in BOOT_DIAGNOSTIC_ENV_KEYS}
    parsed_snapshot = {
        "LANGGRAPH_AUTH": _read_json_env("LANGGRAPH_AUTH"),
        "LANGGRAPH_HTTP": _read_json_env("LANGGRAPH_HTTP"),
    }
    logger.warning(
        "LangGraph boot diagnostics: entrypoint=%s pid=%s cwd=%s argv=%s env=%s parsed=%s",
        entrypoint,
        os.getpid(),
        os.getcwd(),
        list(sys.argv),
        raw_snapshot,
        parsed_snapshot,
    )
