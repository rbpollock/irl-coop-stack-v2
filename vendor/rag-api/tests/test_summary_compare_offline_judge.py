"""summary/compare 離線 judge 與 Codex CLI 自動化測試。"""

from __future__ import annotations

import json
from pathlib import Path
import time

from app.schemas.summary_compare_offline_judge import SummaryCompareOfflineJudgePacket
from app.evaluation.summary_compare import offline_judge as offline_judge_module
from app.evaluation.summary_compare.offline_judge import (
    load_offline_judge_decisions,
    run_codex_cli_on_offline_judge_packets,
    write_offline_judge_packets,
)
from app.scripts.run_summary_compare_benchmark import build_parser as build_benchmark_parser
from app.scripts.run_summary_compare_checkpoint import build_parser as build_checkpoint_parser


def test_run_codex_cli_on_offline_judge_packets_writes_decisions(tmp_path, monkeypatch) -> None:
    """Codex CLI 自動 judge 應可將 packet 轉成 decision JSONL。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以檔案內容斷言 helper 行為。
    """

    packets = [
        SummaryCompareOfflineJudgePacket(
            packet_id="benchmark:compare-1:pairwise",
            judge_kind="benchmark_pairwise",
            benchmark_name="benchmark",
            item_id="compare-1",
            model_label="offline-codex",
            system_prompt="pairwise system",
            user_prompt="pairwise user",
            context_payload={},
        ),
        SummaryCompareOfflineJudgePacket(
            packet_id="benchmark:compare-1:rubric",
            judge_kind="benchmark_rubric",
            benchmark_name="benchmark",
            item_id="compare-1",
            model_label="offline-codex",
            system_prompt="rubric system",
            user_prompt="rubric user",
            context_payload={},
        ),
    ]
    packet_path = write_offline_judge_packets(
        packets=packets,
        output_path=tmp_path / "packets.jsonl",
    )
    decision_path = tmp_path / "decisions.jsonl"
    progress_events: list[dict[str, object]] = []

    def fake_run(command, *, input=None, text=None, capture_output=None, check=None):
        """模擬 Codex CLI 寫出符合 schema 的 JSON 結果。

        參數：
        - `command`：subprocess command 參數。
        - `input`：送進 stdin 的 prompt。
        - `text`：是否以文字模式執行。
        - `capture_output`：是否擷取 stdout/stderr。
        - `check`：是否在非零退出碼時丟錯。

        回傳：
        - 具備 `stdout` / `stderr` 欄位的簡單物件。
        """

        del text, capture_output, check
        if command[1:] == ["--version"]:
            return type("Completed", (), {"stdout": "codex-cli 0.118.0\n", "stderr": ""})()

        response_path = Path(command[command.index("--output-last-message") + 1])
        if "pairwise system" in (input or ""):
            time.sleep(0.05)
            payload = {"verdict": "candidate", "rationale": "Candidate is stronger."}
        else:
            payload = {
                "scores": {
                    "completeness": 4,
                    "faithfulness_to_citations": 5,
                    "structure_quality": 4,
                    "compare_coverage": 4,
                },
                "coverage_dimension_name": "compare_coverage",
                "rationale": "Looks grounded.",
                "missing_points": [],
            }
        response_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return type("Completed", (), {"stdout": "", "stderr": ""})()

    monkeypatch.setattr(offline_judge_module.subprocess, "run", fake_run)

    written_path = run_codex_cli_on_offline_judge_packets(
        packet_path=packet_path,
        output_path=decision_path,
        working_directory=tmp_path,
        max_parallel_workers=2,
        progress_reporter=progress_events.append,
    )

    assert written_path == decision_path
    decisions = load_offline_judge_decisions(decision_path=decision_path)
    assert decisions["benchmark:compare-1:pairwise"].model == "codex-cli 0.118.0 / gpt-5.4"
    assert decisions["benchmark:compare-1:pairwise"].result["verdict"] == "candidate"
    assert decisions["benchmark:compare-1:rubric"].result["scores"]["faithfulness_to_citations"] == 5
    assert [event["type"] for event in progress_events] == [
        "codex_cli_judge_started",
        "codex_cli_judge_started",
        "codex_cli_judge_completed",
        "codex_cli_judge_completed",
    ]
    assert progress_events[0]["packet_id"] == "benchmark:compare-1:pairwise"
    assert progress_events[1]["packet_id"] == "benchmark:compare-1:rubric"
    assert progress_events[2]["packet_id"] == "benchmark:compare-1:rubric"
    assert progress_events[3]["packet_id"] == "benchmark:compare-1:pairwise"


def test_summary_compare_cli_defaults_to_codex_cli_judge() -> None:
    """summary/compare CLI 應預設走 Codex CLI judge。

    參數：
    - 無。

    回傳：
    - `None`：以 parser 預設值斷言 CLI 合約。
    """

    benchmark_args = build_benchmark_parser().parse_args(
        [
            "--area-id",
            "area-1",
            "--dataset-dir",
            "benchmarks/example",
            "--actor-sub",
            "user-1",
            "--output-path",
            "artifacts/example.json",
        ]
    )
    checkpoint_args = build_checkpoint_parser().parse_args(
        [
            "--area-id",
            "area-1",
            "--dataset-dir",
            "benchmarks/example",
            "--actor-sub",
            "user-1",
            "--output-path",
            "artifacts/example.json",
        ]
    )

    assert benchmark_args.judge_mode == "codex-cli"
    assert benchmark_args.codex_cli_bin == "codex"
    assert benchmark_args.codex_cli_model == "gpt-5.4"
    assert checkpoint_args.judge_mode == "codex-cli"
    assert checkpoint_args.codex_cli_bin == "codex"
    assert checkpoint_args.codex_cli_model == "gpt-5.4"
    assert checkpoint_args.judge_parallelism == 6
