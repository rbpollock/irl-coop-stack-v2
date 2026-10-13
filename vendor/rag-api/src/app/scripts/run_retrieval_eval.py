"""Retrieval evaluation dataset 的 CLI 入口。"""

from __future__ import annotations

import argparse
import json

from app.auth.verifier import CurrentPrincipal
from app.core.settings import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.evaluation.retrieval.datasets import (
    create_area_evaluation_dataset,
    create_evaluation_item,
    create_evaluation_run,
    get_evaluation_run_report,
)
from app.evaluation.retrieval.profiles import SUPPORTED_EVALUATION_PROFILES
from app.schemas.evaluation import CreateEvaluationItemRequest
from app.db.models import EvaluationLanguage, EvaluationQueryType


def build_parser() -> argparse.ArgumentParser:
    """建立 CLI argument parser。

    參數：
    - 無。

    回傳：
    - `argparse.ArgumentParser`：CLI parser。
    """

    parser = argparse.ArgumentParser(description="執行 retrieval evaluation benchmark。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare-candidates")
    prepare_parser.add_argument("--area-id", required=True)
    prepare_parser.add_argument("--name", required=True)
    prepare_parser.add_argument("--query-text", required=True)
    prepare_parser.add_argument("--language", choices=["zh-TW", "en", "mixed"], required=True)
    prepare_parser.add_argument(
        "--query-type",
        choices=[query_type.value for query_type in EvaluationQueryType],
        default=EvaluationQueryType.fact_lookup.value,
    )
    prepare_parser.add_argument("--actor-sub", default="cli-evaluator")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--dataset-id", required=True)
    run_parser.add_argument("--top-k", type=int, default=10)
    run_parser.add_argument("--evaluation-profile", choices=SUPPORTED_EVALUATION_PROFILES, default="production_like_v1")
    run_parser.add_argument("--actor-sub", default="cli-evaluator")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--run-id", required=True)
    report_parser.add_argument("--actor-sub", default="cli-evaluator")
    return parser


def main() -> None:
    """CLI 主入口。

    參數：
    - 無。

    回傳：
    - `None`：直接輸出 JSON 到 stdout。
    """

    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    principal = CurrentPrincipal(sub=args.actor_sub, groups=())

    with session_factory() as session:
        if args.command == "prepare-candidates":
            dataset = create_area_evaluation_dataset(
                session=session,
                principal=principal,
                area_id=args.area_id,
                name=args.name,
                query_type=EvaluationQueryType(args.query_type),
            )
            item = create_evaluation_item(
                session=session,
                principal=principal,
                dataset_id=str(dataset.id),
                payload=CreateEvaluationItemRequest(
                    query_text=args.query_text,
                    language=EvaluationLanguage(args.language),
                    query_type=EvaluationQueryType(args.query_type),
                ),
            )
            print(json.dumps({"dataset": dataset.model_dump(mode="json"), "item": item.model_dump(mode="json")}, ensure_ascii=False))
        elif args.command == "run":
            report = create_evaluation_run(
                session=session,
                principal=principal,
                settings=settings,
                dataset_id=args.dataset_id,
                top_k=args.top_k,
                evaluation_profile=args.evaluation_profile,
            )
            print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))
        elif args.command == "report":
            report = get_evaluation_run_report(session=session, principal=principal, run_id=args.run_id)
            print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
