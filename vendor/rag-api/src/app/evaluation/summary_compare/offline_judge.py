"""summary/compare 離線 judge packet 讀寫、Codex CLI 執行與回填工具。"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from app.schemas.summary_compare_offline_judge import (
    SummaryCompareOfflineJudgeDecision,
    SummaryCompareOfflineJudgePacket,
)


DEFAULT_CODEX_CLI_BIN = "codex"
DEFAULT_CODEX_CLI_MODEL = "gpt-5.4"


def write_offline_judge_packets(
    *,
    packets: list[SummaryCompareOfflineJudgePacket],
    output_path: Path,
) -> Path:
    """將離線 judge packets 寫成 JSONL。

    參數：
    - `packets`：要寫出的 packet 清單。
    - `output_path`：JSONL 檔案路徑。

    回傳：
    - `Path`：實際寫出的檔案路徑。
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for packet in packets:
            file.write(json.dumps(packet.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return output_path


def load_offline_judge_packets(*, packet_path: Path) -> list[SummaryCompareOfflineJudgePacket]:
    """讀取離線 judge packets。

    參數：
    - `packet_path`：packet JSONL 路徑。

    回傳：
    - `list[SummaryCompareOfflineJudgePacket]`：依檔案順序排列的 packet 清單。
    """

    packets: list[SummaryCompareOfflineJudgePacket] = []
    with packet_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            packets.append(SummaryCompareOfflineJudgePacket.model_validate(json.loads(stripped)))
    return packets


def load_offline_judge_decisions(
    *,
    decision_path: Path,
) -> dict[str, SummaryCompareOfflineJudgeDecision]:
    """讀取離線 judge 回填結果並以 packet id 建索引。

    參數：
    - `decision_path`：decision JSONL 路徑。

    回傳：
    - `dict[str, SummaryCompareOfflineJudgeDecision]`：`packet_id -> decision` 對照表。
    """

    decisions: dict[str, SummaryCompareOfflineJudgeDecision] = {}
    with decision_path.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            decision = SummaryCompareOfflineJudgeDecision.model_validate(json.loads(stripped))
            decisions[decision.packet_id] = decision
    return decisions


def run_codex_cli_on_offline_judge_packets(
    *,
    packet_path: Path,
    output_path: Path,
    working_directory: Path,
    codex_cli_bin: str = DEFAULT_CODEX_CLI_BIN,
    codex_cli_model: str = DEFAULT_CODEX_CLI_MODEL,
    max_parallel_workers: int = 6,
    progress_reporter: Callable[[dict[str, object]], None] | None = None,
) -> Path:
    """使用 Codex CLI 對離線 judge packets 平行產生回填結果。

    參數：
    - `packet_path`：離線 judge packet JSONL 路徑。
    - `output_path`：decision JSONL 輸出路徑。
    - `working_directory`：執行 Codex CLI 時使用的工作目錄。
    - `codex_cli_bin`：Codex CLI 執行檔名稱或路徑。
    - `codex_cli_model`：Codex CLI judge 使用的模型名稱。
    - `max_parallel_workers`：同時執行的 Codex CLI judge 數量上限。
    - `progress_reporter`：可選的進度回報器；若提供，會在每筆 packet 前後回報事件。

    回傳：
    - `Path`：實際寫出的 decision JSONL 路徑。
    """

    packets = load_offline_judge_packets(packet_path=packet_path)
    if max_parallel_workers < 1:
        raise ValueError("Codex CLI judge 平行度至少要為 1。")
    model_label = _resolve_codex_cli_model_label(
        codex_cli_bin=codex_cli_bin,
        codex_cli_model=codex_cli_model,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        total_packets = len(packets)
        future_to_packet: dict[object, tuple[int, SummaryCompareOfflineJudgePacket]] = {}

        with ThreadPoolExecutor(max_workers=min(max_parallel_workers, total_packets or 1)) as executor:
            for index, packet in enumerate(packets, start=1):
                _emit_codex_cli_judge_progress(
                    reporter=progress_reporter,
                    event={
                        "type": "codex_cli_judge_started",
                        "packet_id": packet.packet_id,
                        "judge_kind": packet.judge_kind,
                        "item_id": packet.item_id,
                        "current": index,
                        "total": total_packets,
                        "decision_required": packet.decision_required,
                    },
                )
                if not packet.decision_required:
                    result = packet.seeded_result or {}
                    file.write(
                        json.dumps(
                            {
                                "packet_id": packet.packet_id,
                                "model": model_label,
                                "result": result,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    file.flush()
                    _emit_codex_cli_judge_progress(
                        reporter=progress_reporter,
                        event={
                            "type": "codex_cli_judge_completed",
                            "packet_id": packet.packet_id,
                            "judge_kind": packet.judge_kind,
                            "item_id": packet.item_id,
                            "current": index,
                            "total": total_packets,
                            "decision_required": packet.decision_required,
                        },
                    )
                    continue
                future = executor.submit(
                    _run_codex_cli_for_packet,
                    packet=packet,
                    working_directory=working_directory,
                    codex_cli_bin=codex_cli_bin,
                    codex_cli_model=codex_cli_model,
                )
                future_to_packet[future] = (index, packet)

            for future in as_completed(future_to_packet):
                index, packet = future_to_packet[future]
                try:
                    result = future.result()
                except Exception as exc:
                    _emit_codex_cli_judge_progress(
                        reporter=progress_reporter,
                        event={
                            "type": "codex_cli_judge_failed",
                            "packet_id": packet.packet_id,
                            "judge_kind": packet.judge_kind,
                            "item_id": packet.item_id,
                            "current": index,
                            "total": total_packets,
                            "error": str(exc),
                        },
                    )
                    raise
                file.write(
                    json.dumps(
                        {
                            "packet_id": packet.packet_id,
                            "model": model_label,
                            "result": result,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                file.flush()
                _emit_codex_cli_judge_progress(
                    reporter=progress_reporter,
                    event={
                        "type": "codex_cli_judge_completed",
                        "packet_id": packet.packet_id,
                        "judge_kind": packet.judge_kind,
                        "item_id": packet.item_id,
                        "current": index,
                        "total": total_packets,
                        "decision_required": packet.decision_required,
                    },
                )
    return output_path


def _run_codex_cli_for_packet(
    *,
    packet: SummaryCompareOfflineJudgePacket,
    working_directory: Path,
    codex_cli_bin: str,
    codex_cli_model: str,
) -> dict[str, object]:
    """對單一 packet 呼叫 Codex CLI 並解析回傳 JSON。

    參數：
    - `packet`：單一離線 judge packet。
    - `working_directory`：Codex CLI 執行時使用的工作目錄。
    - `codex_cli_bin`：Codex CLI 執行檔名稱或路徑。
    - `codex_cli_model`：Codex CLI judge 使用的模型名稱。

    回傳：
    - `dict[str, object]`：符合 packet 類型的 judge result JSON。
    """

    with TemporaryDirectory(prefix="codex-judge-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        schema_path = temp_dir_path / "schema.json"
        response_path = temp_dir_path / "response.json"
        schema_path.write_text(
            json.dumps(_build_codex_cli_output_schema(judge_kind=packet.judge_kind), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        command = [
            codex_cli_bin,
            "exec",
            "--model",
            codex_cli_model,
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(response_path),
            "-C",
            str(working_directory),
            "-",
        ]
        prompt = _build_codex_cli_prompt(packet=packet)
        try:
            subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - 實際 stderr 依環境而異。
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            message = stderr or stdout or str(exc)
            raise RuntimeError(f"Codex CLI judge 執行失敗：{message}") from exc
        return json.loads(response_path.read_text(encoding="utf-8"))


def _build_codex_cli_prompt(*, packet: SummaryCompareOfflineJudgePacket) -> str:
    """建立送給 Codex CLI 的單筆 judge prompt。

    參數：
    - `packet`：單一離線 judge packet。

    回傳：
    - `str`：可直接送進 Codex CLI 的完整 prompt。
    """

    return (
        "請嚴格依照以下 judge 指示作答，並只輸出符合 output schema 的 JSON。\n\n"
        "## System Prompt\n"
        f"{packet.system_prompt}\n\n"
        "## User Prompt\n"
        f"{packet.user_prompt}\n"
    )


def _build_codex_cli_output_schema(*, judge_kind: str) -> dict[str, object]:
    """依 packet 類型建立 Codex CLI output schema。

    參數：
    - `judge_kind`：離線 judge packet 類型。

    回傳：
    - `dict[str, object]`：可傳給 Codex CLI 的 JSON Schema。
    """

    if judge_kind == "benchmark_pairwise":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["candidate", "reference", "tie"],
                },
                "rationale": {"type": "string"},
            },
            "required": ["verdict", "rationale"],
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "scores": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "completeness": {"type": "number"},
                    "faithfulness_to_citations": {"type": "number"},
                    "structure_quality": {"type": "number"},
                    "compare_coverage": {"type": "number"},
                },
                "required": [
                    "completeness",
                    "faithfulness_to_citations",
                    "structure_quality",
                    "compare_coverage",
                ],
            },
            "coverage_dimension_name": {"type": "string"},
            "rationale": {"type": "string"},
            "missing_points": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["scores", "coverage_dimension_name", "rationale", "missing_points"],
    }


def _resolve_codex_cli_model_label(*, codex_cli_bin: str, codex_cli_model: str) -> str:
    """建立 decision JSONL 內使用的 Codex CLI 模型標籤。

    參數：
    - `codex_cli_bin`：Codex CLI 執行檔名稱或路徑。
    - `codex_cli_model`：Codex CLI judge 使用的模型名稱。

    回傳：
    - `str`：例如 `codex-cli 0.118.0 / gpt-5.4` 的顯示標籤。
    """

    try:
        version_result = subprocess.run(
            [codex_cli_bin, "--version"],
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - 版本查詢失敗時直接報錯。
        raise RuntimeError("無法取得 Codex CLI 版本。") from exc
    version_text = (version_result.stdout or version_result.stderr or codex_cli_bin).strip()
    return f"{version_text} / {codex_cli_model}"


def _emit_codex_cli_judge_progress(
    *,
    reporter: Callable[[dict[str, object]], None] | None,
    event: dict[str, object],
) -> None:
    """在有提供 reporter 時回報 Codex CLI judge 進度事件。

    參數：
    - `reporter`：可選的進度回報器。
    - `event`：可序列化的事件 payload。

    回傳：
    - `None`：僅在 reporter 存在時轉發事件。
    """

    if reporter is not None:
        reporter(event)
