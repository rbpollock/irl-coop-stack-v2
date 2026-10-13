"""雙語 summary/compare benchmark runner 測試。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.db.models import Area, Document, DocumentStatus
from app.schemas.summary_compare_benchmark import (
    SummaryCompareMetricResult,
    SummaryComparePairwiseJudgeResult,
)
from app.schemas.summary_compare_checkpoint import SummaryCompareJudgeResult, SummaryCompareJudgeScores
from app.evaluation.summary_compare.offline_judge import write_offline_judge_packets
from app.evaluation.summary_compare.benchmark import (
    build_summary_compare_benchmark_markdown,
    export_summary_compare_benchmark_offline_packets,
    load_summary_compare_benchmark_suite,
    run_summary_compare_benchmark,
    run_summary_compare_benchmark_from_offline_packets,
    write_summary_compare_benchmark_artifacts,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _write_package(
    *,
    package_dir: Path,
    manifest_payload: dict[str, object],
    question_payloads: list[dict[str, object]],
    reference_main_score: float | None,
) -> None:
    """建立測試用 benchmark package。

    參數：
    - `package_dir`：package 目錄。
    - `manifest_payload`：manifest payload。
    - `question_payloads`：questions payload。
    - `reference_main_score`：reference run 的主分數。

    回傳：
    - `None`：僅寫入檔案。
    """

    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "manifest.json").write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (package_dir / "questions.jsonl").write_text(
        "\n".join(json.dumps(payload, ensure_ascii=False) for payload in question_payloads) + "\n",
        encoding="utf-8",
    )
    source_documents_dir = package_dir / "source_documents"
    source_documents_dir.mkdir(parents=True, exist_ok=True)
    for payload in question_payloads:
        for file_name in payload.get("expected_document_names", []):
            (source_documents_dir / file_name).write_text(f"# {file_name}\nplaceholder\n", encoding="utf-8")
    (package_dir / "reference_run_summary.json").write_text(
        json.dumps({"main_score": reference_main_score}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class FakeSummaryScorer:
    """固定回傳 summary 分數的測試 scorer。"""

    def score(self, *, item, answer: str) -> SummaryCompareMetricResult:
        """回傳依題目 id 決定的分數。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。

        回傳：
        - `SummaryCompareMetricResult`：固定主分數。
        """

        del answer
        return SummaryCompareMetricResult(value=0.8 if item.id.endswith("1") else 0.6)


class FakeQAFactEvalScorer:
    """固定回傳 supporting summary 分數的測試 scorer。"""

    def score(self, *, item, answer: str, citations) -> SummaryCompareMetricResult:
        """回傳固定 supporting metric。

        參數：
        - `item`：summary benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryCompareMetricResult`：固定 supporting 分數。
        """

        del item, answer, citations
        return SummaryCompareMetricResult(value=0.5)


class FakeRubricJudge:
    """固定回傳 rubric 分數的測試 judge。"""

    def judge(self, *, item, answer: str, citations, trace) -> SummaryCompareJudgeResult:
        """回傳固定 rubric judge 結果。

        參數：
        - `item`：checkpoint 相容題目。
        - `answer`：模型回答。
        - `citations`：引用列表。
        - `trace`：trace。

        回傳：
        - `SummaryCompareJudgeResult`：固定分數。
        """

        del item, answer, citations, trace
        return SummaryCompareJudgeResult(
            model="fake-rubric",
            scores=SummaryCompareJudgeScores(
                completeness=4.0,
                faithfulness_to_citations=4.0,
                structure_quality=4.0,
                compare_coverage=4.0,
            ),
            coverage_dimension_name="coverage",
            rationale="synthetic",
            missing_points=[],
        )


class FakePairwiseJudge:
    """固定回傳 compare 主分數的測試 judge。"""

    def judge(self, *, item, answer: str, citations) -> SummaryComparePairwiseJudgeResult:
        """回傳固定 compare 主分數。

        參數：
        - `item`：compare benchmark 題目。
        - `answer`：模型回答。
        - `citations`：引用列表。

        回傳：
        - `SummaryComparePairwiseJudgeResult`：固定 pairwise 分數。
        """

        del item, answer, citations
        return SummaryComparePairwiseJudgeResult(
            model="fake-pairwise",
            verdict="candidate",
            rationale="synthetic",
            score=1.0,
        )


def test_load_summary_compare_benchmark_suite_supports_suite_manifest(tmp_path: Path) -> None:
    """suite manifest 應能載入多個 package。"""

    suite_dir = tmp_path / "suite"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_name": "summary-compare-suite",
                "version": "v1",
                "description": "test suite",
                "dataset_packages": ["summary-pkg", "compare-pkg"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_package(
        package_dir=suite_dir / "summary-pkg",
        manifest_payload={
            "benchmark_name": "summary-pkg",
            "version": "v1",
            "description": "summary test package",
            "language": "en",
            "task_family": "summary",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "task_type": "document_summary",
                "question": "Summarize the document.",
                "summary_strategy": "document_overview",
                "expected_document_names": ["summary-doc.md"],
                "expected_section_headings": ["Overview"],
                "required_claims_or_axes": ["overview"],
                "gold_span_refs": [{"file_name": "summary-doc.md", "quote": "Summary evidence."}],
                "reference_answer": "Reference answer.",
                "retrieval_scope": {"mode": "routing"},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.4,
    )
    _write_package(
        package_dir=suite_dir / "compare-pkg",
        manifest_payload={
            "benchmark_name": "compare-pkg",
            "version": "v1",
            "description": "compare test package",
            "language": "zh-TW",
            "task_family": "compare",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "compare-1",
                "language": "zh-TW",
                "task_type": "cross_document_compare",
                "question": "請比較兩份文件。",
                "comparison_axes": ["差異"],
                "expected_document_names": ["compare-doc-a.md", "compare-doc-b.md"],
                "required_claims_or_axes": ["差異"],
                "gold_span_refs": [{"file_name": "compare-doc-a.md", "quote": "Compare evidence."}],
                "reference_answer": "參考答案。",
                "retrieval_scope": {"mode": "routing"},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.7,
    )

    suite_manifest, packages = load_summary_compare_benchmark_suite(dataset_dir=suite_dir)

    assert suite_manifest.benchmark_name == "summary-compare-suite"
    assert [package.manifest.benchmark_name for package in packages] == ["summary-pkg", "compare-pkg"]


def test_run_summary_compare_benchmark_aggregates_summary_and_compare_scores(
    db_session,
    app_settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """runner 應輸出 summary/compare 主分數、baseline compare 與 artifacts。"""

    area = Area(id=_uuid(), name="Summary Compare Benchmark")
    summary_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="summary-doc.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/summary-doc.md",
        display_text="Overview\nSummary evidence.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    compare_document_a = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="compare-doc-a.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/compare-doc-a.md",
        display_text="Diff\nCompare evidence A.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    compare_document_b = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="compare-doc-b.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/compare-doc-b.md",
        display_text="Diff\nCompare evidence B.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, summary_document, compare_document_a, compare_document_b])
    db_session.commit()

    suite_dir = tmp_path / "suite"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_name": "bilingual-pilot",
                "version": "v1",
                "description": "Synthetic bilingual suite.",
                "dataset_packages": ["summary-pkg", "compare-pkg"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_package(
        package_dir=suite_dir / "summary-pkg",
        manifest_payload={
            "benchmark_name": "summary-pkg",
            "version": "v1",
            "description": "summary test package",
            "language": "en",
            "task_family": "summary",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "task_type": "document_summary",
                "question": "Summarize the document.",
                "summary_strategy": "document_overview",
                "expected_document_names": ["summary-doc.md"],
                "expected_section_headings": ["Overview"],
                "required_claims_or_axes": ["overview"],
                "gold_span_refs": [{"file_name": "summary-doc.md", "quote": "Summary evidence."}],
                "reference_answer": "Reference answer.",
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": ["summary-doc.md"]},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.4,
    )
    _write_package(
        package_dir=suite_dir / "compare-pkg",
        manifest_payload={
            "benchmark_name": "compare-pkg",
            "version": "v1",
            "description": "compare test package",
            "language": "zh-TW",
            "task_family": "compare",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "compare-1",
                "language": "zh-TW",
                "task_type": "cross_document_compare",
                "question": "請比較兩份文件。",
                "comparison_axes": ["差異"],
                "expected_document_names": ["compare-doc-a.md", "compare-doc-b.md"],
                "required_claims_or_axes": ["差異"],
                "gold_span_refs": [{"file_name": "compare-doc-a.md", "quote": "Compare evidence A."}],
                "reference_answer": "參考答案。",
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": ["compare-doc-a.md", "compare-doc-b.md"]},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.7,
    )

    from app.evaluation.summary_compare import benchmark as benchmark_module

    def fake_execute_summary_compare_item(*, item, benchmark_document_ids=None, **kwargs):
        """回傳固定 runtime 執行結果。"""

        del kwargs
        if item.id == "summary-1":
            assert benchmark_document_ids == (summary_document.id,)
            citations = [
                {
                    "context_label": "C1",
                    "document_id": summary_document.id,
                    "document_name": summary_document.file_name,
                    "heading": "Overview",
                    "start_offset": summary_document.display_text.find("Summary evidence."),
                    "end_offset": summary_document.display_text.find("Summary evidence.") + len("Summary evidence."),
                    "excerpt": "Summary evidence.",
                }
            ]
        else:
            assert benchmark_document_ids == (compare_document_a.id, compare_document_b.id)
            citations = [
                {
                    "context_label": "C1",
                    "document_id": compare_document_a.id,
                    "document_name": compare_document_a.file_name,
                    "heading": "Diff",
                    "start_offset": compare_document_a.display_text.find("Compare evidence A."),
                    "end_offset": compare_document_a.display_text.find("Compare evidence A.") + len("Compare evidence A."),
                    "excerpt": "Compare evidence A.",
                },
                {
                    "context_label": "C2",
                    "document_id": compare_document_b.id,
                    "document_name": compare_document_b.file_name,
                    "heading": "Diff",
                    "start_offset": compare_document_b.display_text.find("Compare evidence B."),
                    "end_offset": compare_document_b.display_text.find("Compare evidence B.") + len("Compare evidence B."),
                    "excerpt": "Compare evidence B.",
                },
            ]
        return benchmark_module.SummaryCompareExecution(
            answer="synthetic answer",
            answer_blocks=[],
            citations=citations,
            trace={"agent": {"map_reduce_trace": {"total_tokens": 120}}, "retrieval": {"query_type": item.expected_query_type.value}},
            latency_seconds=1.2,
            timed_out=False,
        )

    monkeypatch.setattr(benchmark_module, "execute_summary_compare_item", fake_execute_summary_compare_item)

    report = run_summary_compare_benchmark(
        session=db_session,
        settings=app_settings,
        area_id=area.id,
        actor_sub="benchmark-user",
        dataset_dir=suite_dir,
        summary_scorer=FakeSummaryScorer(),
        qafacteval_scorer=FakeQAFactEvalScorer(),
        rubric_judge=FakeRubricJudge(),
        pairwise_judge=FakePairwiseJudge(),
    )

    assert report.task_family_scores["summary_benchmark_score"].value == 0.8
    assert report.task_family_scores["compare_benchmark_score"].value == 1.0
    assert report.execution.parallel_workers == 6
    assert report.execution.judge_items_count == 2
    assert report.execution.judge_failed_count == 0
    assert report.per_dataset_scores[0].benchmark_name == "summary-pkg"
    assert report.per_dataset_scores[0].main_score.value == 0.8
    assert report.per_dataset_scores[1].main_score.value == 1.0
    assert report.per_item_results[0].missing_required_document_names == []
    assert report.baseline_compare["per_dataset"]["summary-pkg"]["delta"] == 0.4
    assert report.baseline_compare["per_dataset"]["compare-pkg"]["delta"] == 0.3

    json_path, markdown_path = write_summary_compare_benchmark_artifacts(
        report=report,
        output_path=tmp_path / "artifacts" / "summary-compare-benchmark.json",
    )
    assert json_path.exists()
    assert markdown_path.exists()
    assert "Summary / Compare Benchmark" in build_summary_compare_benchmark_markdown(report=report)


def test_run_summary_compare_benchmark_marks_partial_when_compare_judge_missing(
    db_session,
    app_settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """compare 主 judge 缺失時 dataset 應標記 partial。"""

    area = Area(id=_uuid(), name="Summary Compare Partial")
    compare_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="compare-doc-a.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/compare-doc-a.md",
        display_text="Diff\nCompare evidence A.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, compare_document])
    db_session.commit()

    package_dir = tmp_path / "compare-only"
    _write_package(
        package_dir=package_dir,
        manifest_payload={
            "benchmark_name": "compare-only",
            "version": "v1",
            "description": "compare test package",
            "language": "zh-TW",
            "task_family": "compare",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "compare-1",
                "language": "zh-TW",
                "task_type": "cross_document_compare",
                "question": "請比較兩份文件。",
                "comparison_axes": ["差異"],
                "expected_document_names": ["compare-doc-a.md"],
                "required_claims_or_axes": ["差異"],
                "gold_span_refs": [{"file_name": "compare-doc-a.md", "quote": "Compare evidence A."}],
                "reference_answer": "參考答案。",
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": ["compare-doc-a.md"]},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.2,
    )

    from app.evaluation.summary_compare import benchmark as benchmark_module

    def fake_execute_summary_compare_item(*, item, benchmark_document_ids=None, **kwargs):
        """回傳固定 runtime 執行結果。"""

        del kwargs
        assert item.id == "compare-1"
        assert benchmark_document_ids == (compare_document.id,)
        return benchmark_module.SummaryCompareExecution(
            answer="synthetic answer",
            answer_blocks=[],
            citations=[
                {
                    "context_label": "C1",
                    "document_id": compare_document.id,
                    "document_name": compare_document.file_name,
                    "heading": "Diff",
                    "start_offset": compare_document.display_text.find("Compare evidence A."),
                    "end_offset": compare_document.display_text.find("Compare evidence A.") + len("Compare evidence A."),
                    "excerpt": "Compare evidence A.",
                }
            ],
            trace={"agent": {"map_reduce_trace": {"total_tokens": 80}}, "retrieval": {"query_type": item.expected_query_type.value}},
            latency_seconds=0.7,
            timed_out=False,
        )

    monkeypatch.setattr(benchmark_module, "execute_summary_compare_item", fake_execute_summary_compare_item)

    report = run_summary_compare_benchmark(
        session=db_session,
        settings=app_settings.model_copy(update={"openai_api_key": None}),
        area_id=area.id,
        actor_sub="benchmark-user",
        dataset_dir=package_dir,
        summary_scorer=FakeSummaryScorer(),
        qafacteval_scorer=FakeQAFactEvalScorer(),
        rubric_judge=FakeRubricJudge(),
        pairwise_judge=None,
    )

    assert report.execution.judge_failed_count == 1
    assert report.execution.partial_items_count == 1
    assert report.per_dataset_scores[0].partial is True
    assert report.per_dataset_scores[0].main_score.status == "judge_failed"


def test_run_summary_compare_benchmark_rejects_parallel_workers_above_six(db_session, app_settings, tmp_path: Path) -> None:
    """runner 應拒絕超過 6 的並行設定。"""

    package_dir = tmp_path / "empty-package"
    _write_package(
        package_dir=package_dir,
        manifest_payload={
            "benchmark_name": "summary-only",
            "version": "v1",
            "description": "summary test package",
            "language": "en",
            "task_family": "summary",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "task_type": "document_summary",
                "question": "Summarize the document.",
                "summary_strategy": "document_overview",
                "expected_document_names": ["summary-doc.md"],
                "expected_section_headings": ["Overview"],
                "required_claims_or_axes": ["overview"],
                "gold_span_refs": [{"file_name": "summary-doc.md", "quote": "Summary evidence."}],
                "reference_answer": "Reference answer.",
                "retrieval_scope": {"mode": "routing"},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.4,
    )

    with pytest.raises(ValueError):
        run_summary_compare_benchmark(
            session=db_session,
            settings=app_settings,
            area_id=_uuid(),
            actor_sub="benchmark-user",
            dataset_dir=package_dir,
            max_parallel_workers=7,
            summary_scorer=FakeSummaryScorer(),
            qafacteval_scorer=FakeQAFactEvalScorer(),
            rubric_judge=FakeRubricJudge(),
            pairwise_judge=FakePairwiseJudge(),
        )


def test_summary_compare_benchmark_supports_offline_judge_packets(
    db_session,
    app_settings,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """benchmark suite 應支援離線 judge packet 匯出與回填。"""

    area = Area(id=_uuid(), name="Summary Compare Offline")
    summary_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="summary-doc.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/summary-doc.md",
        display_text="Overview\nSummary evidence.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    compare_document_a = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="compare-doc-a.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/compare-doc-a.md",
        display_text="Diff\nCompare evidence A.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    compare_document_b = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="compare-doc-b.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="benchmark/compare-doc-b.md",
        display_text="Diff\nCompare evidence B.",
        normalized_text="placeholder",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, summary_document, compare_document_a, compare_document_b])
    db_session.commit()

    suite_dir = tmp_path / "offline-suite"
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / "manifest.json").write_text(
        json.dumps(
            {
                "benchmark_name": "bilingual-offline",
                "version": "v1",
                "description": "Synthetic bilingual offline suite.",
                "dataset_packages": ["summary-pkg", "compare-pkg"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_package(
        package_dir=suite_dir / "summary-pkg",
        manifest_payload={
            "benchmark_name": "summary-pkg",
            "version": "v1",
            "description": "summary test package",
            "language": "en",
            "task_family": "summary",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "summary-1",
                "language": "en",
                "task_type": "document_summary",
                "question": "Summarize the document.",
                "summary_strategy": "document_overview",
                "expected_document_names": ["summary-doc.md"],
                "expected_section_headings": ["Overview"],
                "required_claims_or_axes": ["overview"],
                "gold_span_refs": [{"file_name": "summary-doc.md", "quote": "Summary evidence."}],
                "reference_answer": "Reference answer.",
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": ["summary-doc.md"]},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.4,
    )
    _write_package(
        package_dir=suite_dir / "compare-pkg",
        manifest_payload={
            "benchmark_name": "compare-pkg",
            "version": "v1",
            "description": "compare test package",
            "language": "zh-TW",
            "task_family": "compare",
            "item_count": 1,
        },
        question_payloads=[
            {
                "id": "compare-1",
                "language": "zh-TW",
                "task_type": "cross_document_compare",
                "question": "請比較兩份文件。",
                "comparison_axes": ["差異"],
                "expected_document_names": ["compare-doc-a.md", "compare-doc-b.md"],
                "required_claims_or_axes": ["差異"],
                "gold_span_refs": [{"file_name": "compare-doc-a.md", "quote": "Compare evidence A."}],
                "reference_answer": "參考答案。",
                "retrieval_scope": {"mode": "explicit_document_ids", "document_file_names": ["compare-doc-a.md", "compare-doc-b.md"]},
                "allows_insufficient_evidence": False,
            }
        ],
        reference_main_score=0.7,
    )

    from app.evaluation.summary_compare import benchmark as benchmark_module

    def fake_execute_summary_compare_item(*, item, benchmark_document_ids=None, **kwargs):
        """回傳固定 runtime 執行結果。"""

        del kwargs
        if item.id == "summary-1":
            assert benchmark_document_ids == (summary_document.id,)
            citations = [
                {
                    "context_label": "C1",
                    "document_id": summary_document.id,
                    "document_name": summary_document.file_name,
                    "heading": "Overview",
                    "start_offset": summary_document.display_text.find("Summary evidence."),
                    "end_offset": summary_document.display_text.find("Summary evidence.") + len("Summary evidence."),
                    "excerpt": "Summary evidence.",
                }
            ]
        else:
            assert benchmark_document_ids == (compare_document_a.id, compare_document_b.id)
            citations = [
                {
                    "context_label": "C1",
                    "document_id": compare_document_a.id,
                    "document_name": compare_document_a.file_name,
                    "heading": "Diff",
                    "start_offset": compare_document_a.display_text.find("Compare evidence A."),
                    "end_offset": compare_document_a.display_text.find("Compare evidence A.") + len("Compare evidence A."),
                    "excerpt": "Compare evidence A.",
                },
                {
                    "context_label": "C2",
                    "document_id": compare_document_b.id,
                    "document_name": compare_document_b.file_name,
                    "heading": "Diff",
                    "start_offset": compare_document_b.display_text.find("Compare evidence B."),
                    "end_offset": compare_document_b.display_text.find("Compare evidence B.") + len("Compare evidence B."),
                    "excerpt": "Compare evidence B.",
                },
            ]
        return benchmark_module.SummaryCompareExecution(
            answer="synthetic answer",
            answer_blocks=[],
            citations=citations,
            trace={"agent": {"map_reduce_trace": {"total_tokens": 120}}, "retrieval": {"query_type": item.expected_query_type.value}},
            latency_seconds=1.2,
            timed_out=False,
        )

    monkeypatch.setattr(benchmark_module, "execute_summary_compare_item", fake_execute_summary_compare_item)

    suite_manifest, _, packets = export_summary_compare_benchmark_offline_packets(
        session=db_session,
        settings=app_settings,
        area_id=area.id,
        actor_sub="benchmark-user",
        dataset_dir=suite_dir,
        judge_label="offline-codex",
        summary_scorer=FakeSummaryScorer(),
        qafacteval_scorer=FakeQAFactEvalScorer(),
    )

    assert suite_manifest.benchmark_name == "bilingual-offline"
    assert len(packets) == 3

    packet_path = write_offline_judge_packets(
        packets=packets,
        output_path=tmp_path / "benchmark-offline-packets.jsonl",
    )
    decision_path = tmp_path / "benchmark-offline-decisions.jsonl"
    decision_rows = [
        {
            "packet_id": "summary-pkg:summary-1:rubric",
            "model": "codex-pro",
            "result": {
                "scores": {
                    "completeness": 4.5,
                    "faithfulness_to_citations": 4.6,
                    "structure_quality": 4.4,
                    "compare_coverage": 4.3,
                },
                "rationale": "Summary looks grounded.",
                "missing_points": [],
            },
        },
        {
            "packet_id": "compare-pkg:compare-1:rubric",
            "model": "codex-pro",
            "result": {
                "scores": {
                    "completeness": 4.2,
                    "faithfulness_to_citations": 4.3,
                    "structure_quality": 4.1,
                    "compare_coverage": 4.0,
                },
                "rationale": "Compare answer is acceptable.",
                "missing_points": [],
            },
        },
        {
            "packet_id": "compare-pkg:compare-1:pairwise",
            "model": "codex-pro",
            "result": {
                "verdict": "candidate",
                "rationale": "Candidate is stronger.",
            },
        },
    ]
    decision_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in decision_rows) + "\n",
        encoding="utf-8",
    )

    report = run_summary_compare_benchmark_from_offline_packets(
        settings=app_settings,
        area_id=area.id,
        actor_sub="benchmark-user",
        dataset_dir=suite_dir,
        judge_packets_path=packet_path,
        judge_results_path=decision_path,
        judge_label="offline-codex",
    )

    assert report.run_metadata.judge_model == "offline-codex"
    assert report.execution.judge_items_count == 2
    assert report.task_family_scores["compare_benchmark_score"].value == 1.0
