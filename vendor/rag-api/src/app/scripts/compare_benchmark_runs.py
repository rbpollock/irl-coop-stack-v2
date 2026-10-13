"""比較 benchmark run 與 reference report 差異的 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.auth.verifier import CurrentPrincipal
from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.evaluation.retrieval.datasets import get_evaluation_run_report


# 固定比較的 stage 名稱，避免散落 magic string。
STAGES = ("recall", "rerank", "assembled")

# 固定比較的 summary metric 名稱，兼容 schema key 與 README 顯示名稱。
SUMMARY_METRICS = (
    ("nDCG@k", "nDCG_at_k"),
    ("Recall@k", "recall_at_k"),
    ("MRR@k", "mrr_at_k"),
    ("Precision@k", "precision_at_k"),
    ("Doc Coverage@k", "document_coverage_at_k"),
)


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI argument parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：可解析 compare CLI 參數的 parser。
    """

    parser = argparse.ArgumentParser(description="比較 benchmark run 與 reference report 的差異。")
    parser.add_argument("--reference-report", required=True, help="reference_run_report.json 路徑。")
    candidate_group = parser.add_mutually_exclusive_group(required=True)
    candidate_group.add_argument("--candidate-report", help="候選 run report JSON 路徑。")
    candidate_group.add_argument("--candidate-run-id", help="直接從資料庫讀取的候選 run id。")
    parser.add_argument("--actor-sub", default="benchmark-compare", help="讀取資料庫 run report 時使用的 principal sub。")
    return parser


def read_report_json(path: Path) -> dict[str, Any]:
    """讀取單一 run report JSON。

    參數：
    - `path`：report JSON 檔案路徑。

    回傳：
    - `dict[str, Any]`：解析後的 report payload。
    """

    return json.loads(path.read_text(encoding="utf-8"))


def load_report_from_run_id(*, run_id: str, actor_sub: str) -> dict[str, Any]:
    """由資料庫讀取指定 run 的完整 report。

    參數：
    - `run_id`：目標 run 識別碼。
    - `actor_sub`：讀取報表時使用的 principal sub。

    回傳：
    - `dict[str, Any]`：可序列化的 report payload。
    """

    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    principal = CurrentPrincipal(sub=actor_sub, groups=())
    with session_factory() as session:
        report = get_evaluation_run_report(session=session, principal=principal, run_id=run_id)
    return report.model_dump(mode="json")


def _stage_summary_metric_delta(
    *,
    reference_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> dict[str, Any]:
    """建立單一 stage 的 summary metric 差異摘要。

    參數：
    - `reference_metrics`：reference run 的 stage summary metrics。
    - `candidate_metrics`：候選 run 的 stage summary metrics。

    回傳：
    - `dict[str, Any]`：每個 metric 的 reference/candidate/delta。
    """

    payload: dict[str, Any] = {}
    for display_name, schema_name in SUMMARY_METRICS:
        reference_value = _get_metric_value(reference_metrics, display_name, schema_name)
        candidate_value = _get_metric_value(candidate_metrics, display_name, schema_name)
        delta = None
        reference_numeric = _coerce_numeric(reference_value)
        candidate_numeric = _coerce_numeric(candidate_value)
        if reference_numeric is not None and candidate_numeric is not None:
            delta = round(candidate_numeric - reference_numeric, 6)
        payload[display_name] = {
            "reference": reference_value,
            "candidate": candidate_value,
            "delta": delta,
        }
    return payload


def _get_metric_value(payload: dict[str, Any], display_name: str, schema_name: str) -> Any:
    """以兼容格式讀取單一 summary metric。

    參數：
    - `payload`：stage summary metrics payload。
    - `display_name`：README 顯示名稱。
    - `schema_name`：report schema key。

    回傳：
    - `Any`：找到的 metric 值；若缺少則回傳 `None`。
    """

    if schema_name in payload:
        return payload.get(schema_name)
    return payload.get(display_name)


def _coerce_numeric(value: Any) -> float | None:
    """將可解析的數值轉成 float。

    參數：
    - `value`：待轉換值。

    回傳：
    - `float | None`：成功時回傳 float，否則回傳 `None`。
    """

    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def build_summary_metric_deltas(*, reference_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, Any]:
    """建立三個 stage 的 summary metric 差異摘要。

    參數：
    - `reference_report`：reference report payload。
    - `candidate_report`：候選 report payload。

    回傳：
    - `dict[str, Any]`：依 stage 分組的 summary metric 差異。
    """

    payload: dict[str, Any] = {}
    reference_summary = reference_report.get("summary_metrics", {})
    candidate_summary = candidate_report.get("summary_metrics", {})
    for stage in STAGES:
        payload[stage] = _stage_summary_metric_delta(
            reference_metrics=reference_summary.get(stage, {}),
            candidate_metrics=candidate_summary.get(stage, {}),
        )
    return payload


def build_per_query_diff(*, reference_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, Any]:
    """建立 per-query 差異摘要。

    參數：
    - `reference_report`：reference report payload。
    - `candidate_report`：候選 report payload。

    回傳：
    - `dict[str, Any]`：逐題比對後的差異統計與 mismatch 清單。
    """

    reference_per_query = {
        row["item_id"]: row for row in reference_report.get("per_query", [])
    }
    candidate_per_query = {
        row["item_id"]: row for row in candidate_report.get("per_query", [])
    }
    reference_item_ids = set(reference_per_query)
    candidate_item_ids = set(candidate_per_query)
    shared_item_ids = sorted(reference_item_ids & candidate_item_ids)

    mismatch_rows: list[dict[str, Any]] = []
    matched_core_evidence_mismatch_count = {stage: 0 for stage in STAGES}
    first_hit_rank_changed_count = {stage: 0 for stage in STAGES}
    fallback_reason_changed_count = {stage: 0 for stage in STAGES}

    for item_id in shared_item_ids:
        reference_row = reference_per_query[item_id]
        candidate_row = candidate_per_query[item_id]
        stage_mismatches: dict[str, Any] = {}
        for stage in STAGES:
            reference_stage = reference_row.get(stage, {})
            candidate_stage = candidate_row.get(stage, {})
            stage_diff = {
                "matched_core_evidence_changed": reference_stage.get("matched_core_evidence") != candidate_stage.get("matched_core_evidence"),
                "first_hit_rank_changed": reference_stage.get("first_hit_rank") != candidate_stage.get("first_hit_rank"),
                "fallback_reason_changed": reference_stage.get("fallback_reason") != candidate_stage.get("fallback_reason"),
                "reference": {
                    "matched_core_evidence": reference_stage.get("matched_core_evidence"),
                    "first_hit_rank": reference_stage.get("first_hit_rank"),
                    "fallback_reason": reference_stage.get("fallback_reason"),
                },
                "candidate": {
                    "matched_core_evidence": candidate_stage.get("matched_core_evidence"),
                    "first_hit_rank": candidate_stage.get("first_hit_rank"),
                    "fallback_reason": candidate_stage.get("fallback_reason"),
                },
            }
            if stage_diff["matched_core_evidence_changed"]:
                matched_core_evidence_mismatch_count[stage] += 1
            if stage_diff["first_hit_rank_changed"]:
                first_hit_rank_changed_count[stage] += 1
            if stage_diff["fallback_reason_changed"]:
                fallback_reason_changed_count[stage] += 1
            if (
                stage_diff["matched_core_evidence_changed"]
                or stage_diff["first_hit_rank_changed"]
                or stage_diff["fallback_reason_changed"]
            ):
                stage_mismatches[stage] = stage_diff
        if stage_mismatches:
            mismatch_rows.append(
                {
                    "item_id": item_id,
                    "query_text": reference_row.get("query_text"),
                    "stage_mismatches": stage_mismatches,
                }
            )

    return {
        "reference_item_count": len(reference_per_query),
        "candidate_item_count": len(candidate_per_query),
        "shared_item_count": len(shared_item_ids),
        "missing_in_candidate": sorted(reference_item_ids - candidate_item_ids),
        "extra_in_candidate": sorted(candidate_item_ids - reference_item_ids),
        "matched_core_evidence_mismatch_count": matched_core_evidence_mismatch_count,
        "first_hit_rank_changed_count": first_hit_rank_changed_count,
        "fallback_reason_changed_count": fallback_reason_changed_count,
        "mismatch_items": mismatch_rows,
    }


def compare_reports(*, reference_report: dict[str, Any], candidate_report: dict[str, Any]) -> dict[str, Any]:
    """比較兩份 benchmark run report。

    參數：
    - `reference_report`：reference report payload。
    - `candidate_report`：候選 report payload。

    回傳：
    - `dict[str, Any]`：summary metrics 與 per-query 差異摘要。
    """

    return {
        "reference": {
            "run_id": reference_report.get("run", {}).get("id"),
            "evaluation_profile": reference_report.get("run", {}).get("evaluation_profile"),
        },
        "candidate": {
            "run_id": candidate_report.get("run", {}).get("id"),
            "evaluation_profile": candidate_report.get("run", {}).get("evaluation_profile"),
        },
        "summary_metric_deltas": build_summary_metric_deltas(
            reference_report=reference_report,
            candidate_report=candidate_report,
        ),
        "per_query_diff": build_per_query_diff(
            reference_report=reference_report,
            candidate_report=candidate_report,
        ),
    }


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：將比較結果以 JSON 輸出到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    reference_report = read_report_json(Path(args.reference_report).resolve())
    if args.candidate_report:
        candidate_report = read_report_json(Path(args.candidate_report).resolve())
    else:
        candidate_report = load_report_from_run_id(run_id=args.candidate_run_id, actor_sub=args.actor_sub)
    print(json.dumps(compare_reports(reference_report=reference_report, candidate_report=candidate_report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
