"""Phase 8A summary/compare checkpoint 測試。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.models import Area, Document, DocumentStatus
from app.schemas.summary_compare_checkpoint import SummaryCompareCheckpointItem, SummaryCompareJudgeResult, SummaryCompareJudgeScores
from app.evaluation.summary_compare.offline_judge import write_offline_judge_packets
from app.evaluation.summary_compare.checkpoint import (
    SummaryCompareExecution,
    build_summary_compare_checkpoint_markdown,
    build_summary_compare_judge_prompt,
    export_summary_compare_checkpoint_offline_packets,
    execute_summary_compare_item,
    load_summary_compare_checkpoint_dataset,
    run_summary_compare_checkpoint,
    run_summary_compare_checkpoint_from_offline_packets,
    write_summary_compare_checkpoint_artifacts,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _write_checkpoint_dataset(*, dataset_dir: Path, item_payloads: list[dict[str, object]], item_count: int | None = None) -> None:
    """建立測試用 checkpoint dataset。

    參數：
    - `dataset_dir`：要寫入的目錄。
    - `item_payloads`：題目 payload 清單。
    - `item_count`：可選的 manifest item_count 覆寫。

    回傳：
    - `None`：僅寫入檔案。
    """

    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_name": "phase8a-test",
                "version": "v1",
                "description": "Phase 8A summary/compare checkpoint test dataset.",
                "item_count": item_count if item_count is not None else len(item_payloads),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (dataset_dir / "questions.jsonl").open("w", encoding="utf-8") as file:
        for payload in item_payloads:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


class FakeJudge:
    """供 checkpoint 測試使用的固定 judge。"""

    def __init__(self, *, scores_by_item_id: dict[str, SummaryCompareJudgeScores]) -> None:
        """初始化 fake judge。

        參數：
        - `scores_by_item_id`：題目 id 對應的固定分數。

        回傳：
        - `None`：僅保存設定。
        """

        self._scores_by_item_id = scores_by_item_id

    def judge(self, *, item, answer: str, citations, trace) -> SummaryCompareJudgeResult:
        """回傳固定 judge 結果。

        參數：
        - `item`：checkpoint fixture 題目。
        - `answer`：runtime 回答。
        - `citations`：runtime citations。
        - `trace`：runtime trace。

        回傳：
        - `SummaryCompareJudgeResult`：固定 judge 結果。
        """

        del answer, citations, trace
        scores = self._scores_by_item_id[item.id]
        return SummaryCompareJudgeResult(
            model="fake-judge",
            scores=scores,
            coverage_dimension_name=(
                "compare_coverage" if item.expected_query_type.value == "cross_document_compare" else "section_focus_accuracy"
            ),
            rationale="synthetic test result",
            missing_points=[],
        )


def test_load_summary_compare_checkpoint_dataset_validates_manifest_count(tmp_path: Path) -> None:
    """manifest 題數與 questions.jsonl 不一致時應失敗。"""

    dataset_dir = tmp_path / "checkpoint-dataset"
    _write_checkpoint_dataset(
        dataset_dir=dataset_dir,
        item_payloads=[
            {
                "id": "item-1",
                "language": "en",
                "question": "Summarize handbook",
                "expected_query_type": "document_summary",
                "expected_summary_strategy": "document_overview",
                "expected_document_names": ["employee-handbook.md"],
                "expected_section_headings": ["Leave Policy"],
                "required_claims_or_compare_axes": ["leave", "remote work"],
                "gold_span_refs": [{"file_name": "employee-handbook.md", "quote": "Employees receive 15 days of annual leave after probation."}],
                "allows_insufficient_evidence": False,
            }
        ],
        item_count=2,
    )

    with pytest.raises(ValueError):
        load_summary_compare_checkpoint_dataset(dataset_dir=dataset_dir)


def test_build_summary_compare_judge_prompt_uses_cited_evidence_only() -> None:
    """judge prompt 應只包含題目、回答、citations 與 trace 摘要。"""

    item = SummaryCompareCheckpointItem.model_validate(
        {
            "id": "item-judge",
            "language": "mixed",
            "question": "比較 handbook 與 benefits",
            "expected_query_type": "cross_document_compare",
            "expected_summary_strategy": None,
            "expected_document_names": ["employee-handbook.md", "benefits-overview.mixed.md"],
            "expected_section_headings": ["Remote Work", "Leave and Flexibility"],
            "required_claims_or_compare_axes": ["annual leave", "remote work"],
            "gold_span_refs": [{"file_name": "employee-handbook.md", "quote": "Regular employees may work remotely up to three days per week."}],
            "allows_insufficient_evidence": False,
        }
    )

    system_prompt, user_prompt = build_summary_compare_judge_prompt(
        item=item,
        answer="The two documents disagree on remote work.",
        citations=[
            {
                "context_label": "C1",
                "document_name": "employee-handbook.md",
                "heading": "Remote Work",
                "excerpt": "Regular employees may work remotely up to three days per week.",
            }
        ],
        trace={"retrieval": {"query_type": "cross_document_compare"}},
    )

    assert "不可腦補未被引用的內容" in system_prompt
    assert "employee-handbook.md" in user_prompt
    assert "Regular employees may work remotely up to three days per week." in user_prompt
    assert "coverage_dimension_name" in user_prompt


def test_run_summary_compare_checkpoint_passes_with_fake_executor_and_judge(db_session, app_settings, tmp_path, monkeypatch) -> None:
    """滿足所有 gate 時 checkpoint 應回傳 passed。"""

    area = Area(id=_uuid(), name="Checkpoint Pass Area")
    employee_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="employee-handbook.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="checkpoint/employee-handbook.md",
        display_text=(
            "Leave Policy\nEmployees receive 15 days of annual leave after probation.\n\n"
            "Remote Work\nRegular employees may work remotely up to three days per week."
        ),
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    benefits_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-overview.mixed.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="checkpoint/benefits-overview.mixed.md",
        display_text=(
            "Leave and Flexibility\nFull-time employees receive 12 days of annual leave in the first year.\n"
            "The hybrid work arrangement allows up to two remote days per week."
        ),
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, employee_document, benefits_document])
    db_session.commit()

    dataset_dir = tmp_path / "checkpoint-dataset-pass"
    _write_checkpoint_dataset(
        dataset_dir=dataset_dir,
        item_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "question": "Summarize the employee handbook.",
                "expected_query_type": "document_summary",
                "expected_summary_strategy": "document_overview",
                "expected_document_names": ["employee-handbook.md"],
                "expected_section_headings": ["Leave Policy"],
                "required_claims_or_compare_axes": ["annual leave", "remote work"],
                "gold_span_refs": [
                    {"file_name": "employee-handbook.md", "quote": "Employees receive 15 days of annual leave after probation."}
                ],
                "allows_insufficient_evidence": False,
            },
            {
                "id": "compare-1",
                "language": "mixed",
                "question": "Compare leave and remote work across the two documents.",
                "expected_query_type": "cross_document_compare",
                "expected_summary_strategy": None,
                "expected_document_names": ["employee-handbook.md", "benefits-overview.mixed.md"],
                "expected_section_headings": ["Remote Work", "Leave and Flexibility"],
                "required_claims_or_compare_axes": ["annual leave", "remote work"],
                "gold_span_refs": [
                    {"file_name": "employee-handbook.md", "quote": "Regular employees may work remotely up to three days per week."},
                    {"file_name": "benefits-overview.mixed.md", "quote": "The hybrid work arrangement allows up to two remote days per week."},
                ],
                "allows_insufficient_evidence": False,
            },
        ],
    )

    def fake_execute_summary_compare_item(*, item, **kwargs) -> SummaryCompareExecution:
        """回傳固定的 runtime 執行結果。"""

        del kwargs
        if item.id == "summary-1":
            return SummaryCompareExecution(
                answer="The handbook covers leave and remote work.",
                answer_blocks=[{"text": "The handbook covers leave and remote work.", "citation_context_indices": [0], "display_citations": []}],
                citations=[
                    {
                        "context_label": "C1",
                        "document_id": employee_document.id,
                        "document_name": employee_document.file_name,
                        "heading": "Leave Policy",
                        "start_offset": employee_document.display_text.find("Employees receive"),
                        "end_offset": employee_document.display_text.find("Employees receive") + len("Employees receive 15 days of annual leave after probation."),
                        "excerpt": "Employees receive 15 days of annual leave after probation.",
                    }
                ],
                trace={
                    "retrieval": {
                        "query_type": "document_summary",
                        "summary_strategy": "document_overview",
                        "fallback_reason": None,
                    },
                    "agent": {"map_reduce_trace": {"total_tokens": 1200}},
                },
                latency_seconds=1.2,
                timed_out=False,
            )
        return SummaryCompareExecution(
            answer="The documents disagree on both annual leave and remote work.",
            answer_blocks=[{"text": "The documents disagree on both annual leave and remote work.", "citation_context_indices": [0, 1], "display_citations": []}],
            citations=[
                {
                    "context_label": "C1",
                    "document_id": employee_document.id,
                    "document_name": employee_document.file_name,
                    "heading": "Remote Work",
                    "start_offset": employee_document.display_text.find("Regular employees"),
                    "end_offset": employee_document.display_text.find("Regular employees") + len("Regular employees may work remotely up to three days per week."),
                    "excerpt": "Regular employees may work remotely up to three days per week.",
                },
                {
                    "context_label": "C2",
                    "document_id": benefits_document.id,
                    "document_name": benefits_document.file_name,
                    "heading": "Leave and Flexibility",
                    "start_offset": benefits_document.display_text.find("The hybrid work arrangement"),
                    "end_offset": benefits_document.display_text.find("The hybrid work arrangement") + len("The hybrid work arrangement allows up to two remote days per week."),
                    "excerpt": "The hybrid work arrangement allows up to two remote days per week.",
                },
            ],
            trace={
                "retrieval": {
                    "query_type": "cross_document_compare",
                    "summary_strategy": None,
                    "fallback_reason": None,
                },
                "agent": {"map_reduce_trace": {"total_tokens": 1800}},
            },
            latency_seconds=1.4,
            timed_out=False,
        )

    monkeypatch.setattr("app.evaluation.summary_compare.checkpoint.execute_summary_compare_item", fake_execute_summary_compare_item)

    judge = FakeJudge(
        scores_by_item_id={
            "summary-1": SummaryCompareJudgeScores(
                completeness=4.7,
                faithfulness_to_citations=4.8,
                structure_quality=4.6,
                compare_coverage=4.5,
            ),
            "compare-1": SummaryCompareJudgeScores(
                completeness=4.8,
                faithfulness_to_citations=4.8,
                structure_quality=4.6,
                compare_coverage=4.7,
            ),
        }
    )
    progress_events: list[dict[str, object]] = []

    report = run_summary_compare_checkpoint(
        session=db_session,
        settings=app_settings,
        area_id=area.id,
        actor_sub="checkpoint-runner",
        dataset_dir=dataset_dir,
        thinking_mode=False,
        judge=judge,
        progress_reporter=progress_events.append,
    )

    assert report.passed is True
    assert report.run_metadata.thinking_mode is False
    assert report.aggregate_metrics.task_type_accuracy == 1.0
    assert report.aggregate_metrics.summary_strategy_accuracy == 1.0
    assert report.aggregate_metrics.required_document_coverage == 1.0
    assert report.aggregate_metrics.citation_coverage == 1.0
    assert report.aggregate_metrics.section_coverage == 1.0
    assert report.aggregate_metrics.fallback_rate == 0.0
    assert report.aggregate_metrics.avg_faithfulness_to_citations >= 4.5
    assert report.aggregate_metrics.avg_overall_score >= 4.2
    assert report.hard_blocker_failures == []
    assert [event["type"] for event in progress_events].count("item_started") == 2
    assert [event["type"] for event in progress_events].count("item_completed") == 2
    assert {event["item_id"] for event in progress_events if event["type"] == "item_started"} == {"summary-1", "compare-1"}
    assert {event["item_id"] for event in progress_events if event["type"] == "item_completed"} == {"summary-1", "compare-1"}
    assert all(event["thinking_mode"] is False for event in progress_events)

    json_path, markdown_path = write_summary_compare_checkpoint_artifacts(
        report=report,
        output_path=tmp_path / "checkpoint-report.json",
    )
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Phase 8A Summary / Compare Checkpoint" in build_summary_compare_checkpoint_markdown(report=report)


def test_run_summary_compare_checkpoint_reports_hard_and_soft_failures(db_session, app_settings, tmp_path, monkeypatch) -> None:
    """hard blocker 與低分題目應讓 checkpoint fail。"""

    area = Area(id=_uuid(), name="Checkpoint Fail Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="claims-guide.zh-TW.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="checkpoint/claims-guide.zh-TW.md",
        display_text="給付時程\n文件齊備後，標準案件於七個工作天內完成審核。",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.commit()

    dataset_dir = tmp_path / "checkpoint-dataset-fail"
    _write_checkpoint_dataset(
        dataset_dir=dataset_dir,
        item_payloads=[
            {
                "id": "compare-fail",
                "language": "zh-TW",
                "question": "比較 claims-guide 與 benefits-overview 的理賠時程。",
                "expected_query_type": "cross_document_compare",
                "expected_summary_strategy": None,
                "expected_document_names": ["claims-guide.zh-TW.md", "benefits-overview.mixed.md"],
                "expected_section_headings": ["給付時程", "Claims Support"],
                "required_claims_or_compare_axes": ["formal review timeline", "missing evidence"],
                "gold_span_refs": [{"file_name": "claims-guide.zh-TW.md", "quote": "文件齊備後，標準案件於七個工作天內完成審核。"}],
                "allows_insufficient_evidence": True,
            }
        ],
    )

    def fake_execute_summary_compare_item(**kwargs) -> SummaryCompareExecution:
        """回傳帶有 mismatch 與不足證據缺口的結果。"""

        del kwargs
        return SummaryCompareExecution(
            answer="claims-guide 說理賠審核需要七個工作天。",
            answer_blocks=[],
            citations=[
                {
                    "context_label": "C1",
                    "document_id": document.id,
                    "document_name": document.file_name,
                    "heading": "給付時程",
                    "start_offset": document.display_text.find("文件齊備後"),
                    "end_offset": document.display_text.find("文件齊備後") + len("文件齊備後，標準案件於七個工作天內完成審核。"),
                    "excerpt": "文件齊備後，標準案件於七個工作天內完成審核。",
                }
            ],
            trace={
                "retrieval": {
                    "query_type": "document_summary",
                    "summary_strategy": "document_overview",
                    "fallback_reason": "retrieval_scope_relaxed",
                },
                "agent": {"map_reduce_trace": {"total_tokens": 15000}},
            },
            latency_seconds=35.0,
            timed_out=True,
        )

    monkeypatch.setattr("app.evaluation.summary_compare.checkpoint.execute_summary_compare_item", fake_execute_summary_compare_item)

    judge = FakeJudge(
        scores_by_item_id={
            "compare-fail": SummaryCompareJudgeScores(
                completeness=2.5,
                faithfulness_to_citations=4.0,
                structure_quality=2.5,
                compare_coverage=2.0,
            )
        }
    )

    report = run_summary_compare_checkpoint(
        session=db_session,
        settings=app_settings,
        area_id=area.id,
        actor_sub="checkpoint-runner",
        dataset_dir=dataset_dir,
        judge=judge,
    )

    assert report.passed is False
    assert report.hard_blocker_failures[0]["item_id"] == "compare-fail"
    assert "task_type_mismatch" in report.hard_blocker_failures[0]["reasons"]
    assert "required_document_not_cited" in report.hard_blocker_failures[0]["reasons"]
    assert "insufficient_evidence_not_acknowledged" in report.hard_blocker_failures[0]["reasons"]
    assert report.per_item_results[0].missing_required_document_names == ["benefits-overview.mixed.md"]
    assert any(metric.name == "hard_blocker_failures" and metric.passed is False for metric in report.gate_results)
    assert report.failure_category_counts["judge_low_completeness"] == 1
    assert report.failure_category_counts["timeout"] == 1


def test_execute_summary_compare_item_requires_deepagents(app_settings, db_session) -> None:
    """checkpoint executor 應拒絕非 deepagents provider。"""

    item = SummaryCompareCheckpointItem.model_validate(
        {
            "id": "item-exec",
            "language": "en",
            "question": "Summarize handbook",
            "expected_query_type": "document_summary",
            "expected_summary_strategy": "document_overview",
            "expected_document_names": ["employee-handbook.md"],
            "expected_section_headings": ["Leave Policy"],
            "required_claims_or_compare_axes": ["leave"],
            "gold_span_refs": [{"file_name": "employee-handbook.md", "quote": "leave"}],
            "allows_insufficient_evidence": False,
        }
    )

    with pytest.raises(ValueError):
        execute_summary_compare_item(
            session=db_session,
            settings=app_settings,
            principal=object(),
            area_id="area-1",
            item=item,
        )


def test_summary_compare_checkpoint_supports_offline_judge_packets(
    db_session,
    app_settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """checkpoint 應支援離線 judge packet 匯出與回填。"""

    area = Area(id=_uuid(), name="Checkpoint Offline Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="employee-handbook.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="checkpoint/employee-handbook.md",
        display_text="Overview\nEmployees receive 15 days of annual leave after probation.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, document])
    db_session.commit()

    dataset_dir = tmp_path / "checkpoint-offline-dataset"
    _write_checkpoint_dataset(
        dataset_dir=dataset_dir,
        item_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "question": "Summarize the employee handbook.",
                "expected_query_type": "document_summary",
                "expected_summary_strategy": "document_overview",
                "expected_document_names": ["employee-handbook.md"],
                "expected_section_headings": ["Overview"],
                "required_claims_or_compare_axes": ["annual leave"],
                "gold_span_refs": [{"file_name": "employee-handbook.md", "quote": "Employees receive 15 days of annual leave after probation."}],
                "allows_insufficient_evidence": False,
            }
        ],
    )

    def fake_execute_summary_compare_item(*, item, **kwargs) -> SummaryCompareExecution:
        """回傳固定 runtime 執行結果。"""

        del kwargs
        assert item.id == "summary-1"
        return SummaryCompareExecution(
            answer="The handbook grants 15 days of annual leave after probation.",
            answer_blocks=[],
            citations=[
                {
                    "context_label": "C1",
                    "document_id": document.id,
                    "document_name": document.file_name,
                    "heading": "Overview",
                    "start_offset": document.display_text.find("Employees receive"),
                    "end_offset": document.display_text.find("Employees receive") + len("Employees receive 15 days of annual leave after probation."),
                    "excerpt": "Employees receive 15 days of annual leave after probation.",
                }
            ],
            trace={
                "retrieval": {"query_type": "document_summary", "summary_strategy": "document_overview"},
                "agent": {"map_reduce_trace": {"total_tokens": 120}},
            },
            latency_seconds=0.8,
            timed_out=False,
        )

    monkeypatch.setattr("app.evaluation.summary_compare.checkpoint.execute_summary_compare_item", fake_execute_summary_compare_item)

    manifest, packets = export_summary_compare_checkpoint_offline_packets(
        session=db_session,
        settings=app_settings,
        area_id=area.id,
        actor_sub="checkpoint-user",
        dataset_dir=dataset_dir,
        judge_label="offline-codex",
    )

    assert manifest.item_count == 1
    assert len(packets) == 1
    assert packets[0].judge_kind == "checkpoint_rubric"
    assert "不可腦補未被引用的內容" in packets[0].system_prompt

    packet_path = write_offline_judge_packets(
        packets=packets,
        output_path=tmp_path / "checkpoint-offline-packets.jsonl",
    )
    decision_path = tmp_path / "checkpoint-offline-decisions.jsonl"
    decision_path.write_text(
        json.dumps(
            {
                "packet_id": packets[0].packet_id,
                "model": "codex-pro",
                "result": {
                    "scores": {
                        "completeness": 4.8,
                        "faithfulness_to_citations": 4.9,
                        "structure_quality": 4.6,
                        "compare_coverage": 4.5,
                    },
                    "coverage_dimension_name": "section_focus_accuracy",
                    "rationale": "Looks grounded.",
                    "missing_points": [],
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_summary_compare_checkpoint_from_offline_packets(
        settings=app_settings,
        area_id=area.id,
        actor_sub="checkpoint-user",
        dataset_dir=dataset_dir,
        thinking_mode=True,
        judge_packets_path=packet_path,
        judge_results_path=decision_path,
        judge_label="offline-codex",
    )

    assert report.run_metadata.judge_model == "offline-codex"
    assert report.per_item_results[0].judge_result.model == "codex-pro"
    assert report.aggregate_metrics.avg_overall_score > 4.0
