"""匯出 FastAPI OpenAPI schema，供前端產生 REST contract types 使用。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.main import create_app


# 標準輸出模式使用的保留字串。
STDOUT_TARGET = "-"


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI 參數解析器。

    參數：
    - 無

    回傳：
    - `argparse.ArgumentParser`：已包含輸出路徑選項的 parser。
    """

    parser = argparse.ArgumentParser(description="匯出目前 API 的 OpenAPI JSON schema。")
    parser.add_argument(
        "--output",
        default=STDOUT_TARGET,
        help="輸出檔案路徑；預設為標準輸出。",
    )
    return parser


def dump_openapi(*, output_path: str) -> int:
    """匯出目前 API OpenAPI schema。

    參數：
    - `output_path`：輸出路徑；若為 `-` 則寫到標準輸出。

    回傳：
    - `int`：成功時回傳 `0`。
    """

    openapi_payload = create_app().openapi()
    serialized_payload = json.dumps(openapi_payload, ensure_ascii=False, indent=2)

    if output_path == STDOUT_TARGET:
        sys.stdout.write(serialized_payload)
        sys.stdout.write("\n")
        return 0

    target_path = Path(output_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(f"{serialized_payload}\n", encoding="utf-8")
    return 0


def main() -> int:
    """執行 OpenAPI 匯出 CLI。

    參數：
    - 無

    回傳：
    - `int`：CLI 結束碼。
    """

    parser = build_parser()
    args = parser.parse_args()
    return dump_openapi(output_path=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
