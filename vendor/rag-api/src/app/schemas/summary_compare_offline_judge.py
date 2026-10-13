"""summary/compare 離線 judge packet 與回填結果資料契約。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# 離線 judge packet 的合法種類。
SUMMARY_COMPARE_OFFLINE_JUDGE_KINDS = (
    "checkpoint_rubric",
    "benchmark_rubric",
    "benchmark_pairwise",
)


class SummaryCompareOfflineJudgePacket(BaseModel):
    """單一離線 judge packet。"""

    # packet 唯一識別碼。
    packet_id: str = Field(min_length=1)
    # packet 類型。
    judge_kind: Literal["checkpoint_rubric", "benchmark_rubric", "benchmark_pairwise"]
    # 所屬 benchmark 名稱。
    benchmark_name: str = Field(min_length=1)
    # 所屬題目識別碼。
    item_id: str = Field(min_length=1)
    # 顯示用的 judge label。
    model_label: str = Field(min_length=1)
    # judge system prompt。
    system_prompt: str = Field(min_length=1)
    # judge user prompt。
    user_prompt: str = Field(min_length=1)
    # 產生正式報表時要回填的上下文 payload。
    context_payload: dict[str, object]
    # 此 packet 是否需要外部 judge 決策。
    decision_required: bool = True
    # 若不需外部 judge，可直接帶入預設結果。
    seeded_result: dict[str, object] | None = None

    @field_validator("packet_id", "benchmark_name", "item_id", "model_label", "system_prompt", "user_prompt")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        """清理必要文字欄位。

        參數：
        - `value`：原始文字欄位。

        回傳：
        - `str`：去除首尾空白後的文字。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("離線 judge packet 必填文字欄位不可為空白。")
        return stripped


class SummaryCompareOfflineJudgeDecision(BaseModel):
    """離線 judge 回填結果。"""

    # 對應的 packet 識別碼。
    packet_id: str = Field(min_length=1)
    # 本次人工 / Codex judge 的模型標籤。
    model: str | None = None
    # 回填的 judge 結果 payload。
    result: dict[str, object]

    @field_validator("packet_id")
    @classmethod
    def validate_packet_id(cls, value: str) -> str:
        """清理 packet id。

        參數：
        - `value`：原始 packet id。

        回傳：
        - `str`：清理後的 packet id。
        """

        stripped = value.strip()
        if not stripped:
            raise ValueError("離線 judge decision.packet_id 不可為空白。")
        return stripped
