"""匯出 chat/runtime contract schema，供前端產生 TypeScript types。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter
from pydantic.json_schema import models_json_schema

from app.chat.contracts.types import (
    AgentToolPayload,
    ChatAnswerBlock,
    ChatAssembledContext,
    ChatCitation,
    ChatDisplayCitation,
    ChatMessageArtifact,
    ChatMessageArtifactPayload,
    ChatPhaseEventPayload,
    ChatReferencesEventPayload,
    ChatRuntimeResult,
    ChatTokenEventPayload,
    ChatToolCallEventPayload,
    ChatTrace,
)


# 標準輸出模式使用的保留字串。
STDOUT_TARGET = "-"

# 匯入 generated schema 的 Pydantic model 清單。
CHAT_CONTRACT_MODELS = (
    ChatDisplayCitation,
    ChatAnswerBlock,
    ChatCitation,
    ChatAssembledContext,
    ChatTrace,
    ChatMessageArtifact,
    ChatRuntimeResult,
)

# 匯入 generated schema 的 JSON-friendly TypedDict payload 清單。
CHAT_TYPED_PAYLOADS = (
    ChatMessageArtifactPayload,
    ChatPhaseEventPayload,
    ChatToolCallEventPayload,
    ChatTokenEventPayload,
    ChatReferencesEventPayload,
    AgentToolPayload,
)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。

    參數：
    - 無

    回傳：
    - `argparse.ArgumentParser`：已包含輸出路徑選項的 parser。
    """

    parser = argparse.ArgumentParser(description="匯出 chat/runtime contract JSON schema。")
    parser.add_argument(
        "--output",
        default=STDOUT_TARGET,
        help="輸出檔案路徑；預設為標準輸出。",
    )
    return parser


def _collect_model_schemas() -> dict[str, Any]:
    """收集 Pydantic model 的 JSON schemas。

    參數：
    - 無

    回傳：
    - `dict[str, Any]`：以 schema 名稱為 key 的 components schema。
    """

    _, top_level_schema = models_json_schema(
        [(model, "validation") for model in CHAT_CONTRACT_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    return dict(top_level_schema.get("$defs", {}))


def _collect_typed_payload_schemas() -> dict[str, Any]:
    """收集 TypedDict payload 的 JSON schemas。

    參數：
    - 無

    回傳：
    - `dict[str, Any]`：以 schema 名稱為 key 的 components schema。
    """

    schemas: dict[str, Any] = {}
    for payload_type in CHAT_TYPED_PAYLOADS:
        schema = TypeAdapter(payload_type).json_schema(ref_template="#/components/schemas/{model}")
        nested_defs = schema.pop("$defs", {})
        schemas.update(nested_defs)
        schemas[payload_type.__name__] = schema
    return schemas


def build_chat_contract_openapi() -> dict[str, Any]:
    """建立可供 `openapi-typescript` 消費的 chat contract OpenAPI 文件。

    參數：
    - 無

    回傳：
    - `dict[str, Any]`：只包含 components schemas 的 OpenAPI 文件。
    """

    schemas = _collect_model_schemas()
    schemas.update(_collect_typed_payload_schemas())
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Deep Agent Chat Runtime Contracts",
            "version": "1.0.0",
        },
        "paths": {},
        "components": {
            "schemas": dict(sorted(schemas.items())),
        },
    }


def dump_chat_contracts(*, output_path: str) -> int:
    """匯出 chat/runtime contract schema。

    參數：
    - `output_path`：輸出路徑；若為 `-` 則寫到標準輸出。

    回傳：
    - `int`：成功時回傳 `0`。
    """

    serialized_payload = json.dumps(build_chat_contract_openapi(), ensure_ascii=False, indent=2)

    if output_path == STDOUT_TARGET:
        sys.stdout.write(serialized_payload)
        sys.stdout.write("\n")
        return 0

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(f"{serialized_payload}\n", encoding="utf-8")
    return 0


def main() -> int:
    """執行 chat contract 匯出 CLI。

    參數：
    - 無

    回傳：
    - `int`：CLI 結束碼。
    """

    parser = build_parser()
    args = parser.parse_args()
    return dump_chat_contracts(output_path=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
