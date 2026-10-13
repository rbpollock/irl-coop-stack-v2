"""Query-aware retrieval 的統一路由框架與 profile resolver。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import json
import math
import re
import time
from typing import Literal

from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import EvaluationQueryType
from app.services.document_mentions import (
    DOCUMENT_MENTION_SOURCE_NONE,
    DocumentMentionCandidate,
    DocumentMentionResolution,
    resolve_document_mentions,
)
from app.services.embeddings import build_embedding_provider
from app.services.retrieval_query import detect_query_language, normalize_query_text


# `explicit` 表示 query type 由外部 contract 直接指定。
QUERY_ROUTING_SOURCE_EXPLICIT = "explicit"
# `rule` 表示 classifier 由高 precision 規則命中。
QUERY_ROUTING_SOURCE_RULE = "rule"
# `embedding` 表示 classifier 由 query-to-prototype embedding similarity 決定。
QUERY_ROUTING_SOURCE_EMBEDDING = "embedding"
# `llm_fallback` 表示 classifier 由低信心時的 LLM fallback 決定。
QUERY_ROUTING_SOURCE_LLM_FALLBACK = "llm_fallback"
# `fallback` 表示低信心且 LLM fallback 不可用時，退回保守預設。
QUERY_ROUTING_SOURCE_FALLBACK = "fallback"

# `fact_lookup_precision_v1` 表示事實查詢的 precision-first runtime profile。
RETRIEVAL_PROFILE_FACT_LOOKUP_PRECISION_V1 = "fact_lookup_precision_v1"
# `document_summary_single_document_diversified_v1` 表示單文件摘要的 diversified profile。
RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1 = "document_summary_single_document_diversified_v1"
# `document_summary_multi_document_diversified_v1` 表示多文件摘要的 diversified profile。
RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1 = "document_summary_multi_document_diversified_v1"
# `cross_document_compare_diversified_v1` 表示多文件比較的 diversified profile。
RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_DIVERSIFIED_V1 = "cross_document_compare_diversified_v1"

# `document_overview` 表示單文件整體摘要。
SUMMARY_STRATEGY_DOCUMENT_OVERVIEW = "document_overview"
# `section_focused` 表示單文件聚焦章節摘要。
SUMMARY_STRATEGY_SECTION_FOCUSED = "section_focused"
# `multi_document_theme` 表示多文件共同主題摘要。
SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME = "multi_document_theme"

# 第一層 `task_type` 的固定 label 集。
TASK_TYPE_LABELS = (
    EvaluationQueryType.fact_lookup.value,
    EvaluationQueryType.document_summary.value,
    EvaluationQueryType.cross_document_compare.value,
)
# 第二層 `summary_strategy` 的固定 label 集。
SUMMARY_STRATEGY_LABELS = (
    SUMMARY_STRATEGY_DOCUMENT_OVERVIEW,
    SUMMARY_STRATEGY_SECTION_FOCUSED,
    SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME,
)


class DocumentScope(StrEnum):
    """提供給 routing contract 的文件範圍提示列舉。"""

    AREA = "area"
    SINGLE_DOCUMENT = "single_document"
    MULTI_DOCUMENT = "multi_document"
    UNRESOLVED = "unresolved"


class SummaryStrategy(StrEnum):
    """提供給 routing contract 的摘要策略提示列舉。"""

    DOCUMENT_OVERVIEW = SUMMARY_STRATEGY_DOCUMENT_OVERVIEW
    SECTION_FOCUSED = SUMMARY_STRATEGY_SECTION_FOCUSED
    MULTI_DOCUMENT_THEME = SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME


# 提供給 agent/tool 的文件範圍提示入口；不得直接攜帶 document ids。
DOCUMENT_SCOPE_LABELS = tuple(item.value for item in DocumentScope)
# 提供給 agent/tool 的摘要策略提示入口；只在 document_summary 下有效。
SUMMARY_STRATEGY_HINT_LABELS = tuple(item.value for item in SummaryStrategy)

# `zh-TW` 摘要型 query 關鍵詞。
SUMMARY_TRIGGER_PHRASES_ZH_TW = ("摘要", "總結", "整理", "概述", "重點")
# `en` 摘要型 query 關鍵詞。
SUMMARY_TRIGGER_PHRASES_EN = ("summary", "summarize", "overview", "key points")
# `zh-TW` 比較型 query 關鍵詞。
COMPARE_TRIGGER_PHRASES_ZH_TW = ("比較", "差異", "相比", "不同", "優缺點")
# `en` 比較型 query 關鍵詞。
COMPARE_TRIGGER_PHRASES_EN = ("compare", "comparison", "difference", "vs", "versus")
# `zh-TW` 章節聚焦摘要 cue。
SECTION_FOCUS_TRIGGER_PHRASES_ZH_TW = ("章節", "段落", "部分", "聚焦", "著重")
# `en` 章節聚焦摘要 cue。
SECTION_FOCUS_TRIGGER_PHRASES_EN = ("section", "chapter", "part", "focus on")

# `task_type` prototype registry；內容僅允許 generic semantic templates。
TASK_TYPE_PROTOTYPES: dict[str, tuple[str, ...]] = {
    EvaluationQueryType.fact_lookup.value: (
        "what is the eligibility requirement",
        "who approves this request",
        "what is the deadline for this process",
        "what does this specific term mean",
        "申請資格是什麼",
        "誰可以核准這件事",
        "這個流程的期限是什麼",
        "這個名詞代表什麼",
    ),
    EvaluationQueryType.document_summary.value: (
        "summarize the whole document",
        "give me an overview of this policy",
        "what are the main points of this handbook",
        "summarize what this document says",
        "請摘要這份文件",
        "整理這份政策的重點",
        "概述這份手冊的主要內容",
        "總結這份文件在說什麼",
    ),
    EvaluationQueryType.cross_document_compare.value: (
        "compare these two documents",
        "what is the difference between the policies",
        "how do the documents differ on this topic",
        "compare what the documents say about this subject",
        "比較這兩份文件",
        "這兩份文件在這個主題上有什麼差異",
        "相比之下有哪些不同",
        "比較文件之間的說法",
    ),
}

# `summary_strategy` prototype registry；內容僅允許 generic semantic templates。
SUMMARY_STRATEGY_PROTOTYPES: dict[str, tuple[str, ...]] = {
    SUMMARY_STRATEGY_DOCUMENT_OVERVIEW: (
        "summarize the entire document",
        "give me a complete overview of this document",
        "what are the main points of this one document",
        "summarize the full policy",
        "請整理整份文件的重點",
        "概述這份單一文件的主要內容",
        "摘要這份文件的整體內容",
        "總結這份政策全文",
    ),
    SUMMARY_STRATEGY_SECTION_FOCUSED: (
        "summarize the section about this topic",
        "focus on the part that discusses this issue",
        "summarize the chapter related to this question",
        "give me the part about this requirement",
        "請整理關於這個主題的章節",
        "聚焦這份文件中和這個議題有關的部分",
        "摘要這份文件裡相關段落",
        "請只看這個章節的內容",
    ),
    SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME: (
        "summarize what multiple documents say about one topic",
        "what is the common theme across these documents",
        "summarize the shared topic across documents",
        "combine the documents into one thematic summary",
        "整理多份文件對同一主題的說法",
        "摘要多份文件的共同主題",
        "綜合多份文件對這個議題的內容",
        "總結不同文件對同一主題的資訊",
    ),
}

# `task_type` label 的簡短定義，供 LLM fallback 使用。
TASK_TYPE_LABEL_DESCRIPTIONS = {
    EvaluationQueryType.fact_lookup.value: "question asks for a specific fact, rule, definition, actor, number, or deadline",
    EvaluationQueryType.document_summary.value: "question asks for a summary, overview, or synthesis of document content",
    EvaluationQueryType.cross_document_compare.value: "question asks to compare or contrast multiple documents or viewpoints",
}

# `summary_strategy` label 的簡短定義，供 LLM fallback 使用。
SUMMARY_STRATEGY_LABEL_DESCRIPTIONS = {
    SUMMARY_STRATEGY_DOCUMENT_OVERVIEW: "single-document overall summary of the whole document",
    SUMMARY_STRATEGY_SECTION_FOCUSED: "single-document summary focused on one section, part, or topical subsection",
    SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME: "multi-document thematic synthesis across documents",
}

# `task_type` embedding classifier 的最低 confidence。
TASK_TYPE_EMBEDDING_CONFIDENCE_THRESHOLD = 0.78
# `task_type` embedding classifier 的最低 margin。
TASK_TYPE_EMBEDDING_MARGIN_THRESHOLD = 0.05
# `summary_strategy` embedding classifier 的最低 confidence。
SUMMARY_STRATEGY_EMBEDDING_CONFIDENCE_THRESHOLD = 0.8
# `summary_strategy` embedding classifier 的最低 margin。
SUMMARY_STRATEGY_EMBEDDING_MARGIN_THRESHOLD = 0.06
# 第一層 `task_type` fallback 只做極輕量標籤分類，固定採最小 reasoning effort。
OPENAI_REASONING_EFFORT_TASK_TYPE = "minimal"
# 第二層 `summary_strategy` fallback 需要較細的摘要意圖判斷，固定採低階 reasoning effort。
OPENAI_REASONING_EFFORT_SUMMARY_STRATEGY = "low"
# agent 明示 multi-document scope 時，候選文件可用較低門檻補入，但仍只限 SQL-gated ready 文件。
MULTI_DOCUMENT_SCOPE_HINT_CANDIDATE_THRESHOLD = 0.55
# compare / multi-doc summary 題保留第二候選所需的最低分數。
MULTI_DOCUMENT_QUERY_CANDIDATE_THRESHOLD = 0.55
# compare / multi-doc summary 常見 query cue。
MULTI_DOCUMENT_QUERY_PATTERN = re.compile(
    r"(?:\bbetween\b|\bacross\b|\bcompare\b|\bversus\b|\bvs\.?\b|\band\b|與|和|及|跟)",
    re.IGNORECASE,
)

# prototype embedding cache，避免每次 routing 都重算固定語義模板。
_ROUTING_PROTOTYPE_EMBEDDING_CACHE: dict[tuple[object, ...], tuple[tuple[str, tuple[float, ...]], ...]] = {}


@dataclass(frozen=True, slots=True)
class RoutingRuleHit:
    """單一高 precision routing 規則命中。"""

    label: str
    reason: str
    confidence: float


@dataclass(frozen=True, slots=True)
class RoutingEmbeddingScore:
    """單一 label 的 embedding classifier 分數。"""

    label: str
    score: float


@dataclass(frozen=True, slots=True)
class RoutingClassifierDecision:
    """共享 routing classifier 的單次決策結果。"""

    label: str
    confidence: float
    source: str
    rule_hits: tuple[RoutingRuleHit, ...]
    embedding_scores: tuple[RoutingEmbeddingScore, ...]
    top_label: str
    runner_up_label: str | None
    margin: float
    fallback_used: bool
    fallback_reason: str | None


@dataclass(frozen=True, slots=True)
class QueryTypeClassification:
    """單次 query type classifier 的輸出。"""

    query_type: EvaluationQueryType
    language: str
    confidence: float
    source: str
    matched_rules: tuple[str, ...]
    rule_hits: tuple[RoutingRuleHit, ...]
    embedding_scores: tuple[RoutingEmbeddingScore, ...]
    top_label: str
    runner_up_label: str | None
    margin: float
    fallback_used: bool
    fallback_reason: str | None


@dataclass(frozen=True, slots=True)
class QueryRoutingDecision:
    """單次 query-aware retrieval routing 的決策結果。"""

    query_type: EvaluationQueryType
    language: str
    confidence: float
    source: str
    matched_rules: tuple[str, ...]
    query_type_rule_hits: tuple[RoutingRuleHit, ...]
    query_type_embedding_scores: tuple[RoutingEmbeddingScore, ...]
    query_type_top_label: str
    query_type_runner_up_label: str | None
    query_type_embedding_margin: float
    query_type_fallback_used: bool
    query_type_fallback_reason: str | None
    summary_scope: str | None
    summary_strategy: str | None
    summary_strategy_source: str
    summary_strategy_confidence: float
    summary_strategy_rule_hits: tuple[RoutingRuleHit, ...]
    summary_strategy_embedding_scores: tuple[RoutingEmbeddingScore, ...]
    summary_strategy_top_label: str | None
    summary_strategy_runner_up_label: str | None
    summary_strategy_embedding_margin: float
    summary_strategy_fallback_used: bool
    summary_strategy_fallback_reason: str | None
    document_scope: str
    resolved_document_ids: tuple[str, ...]
    document_mention_source: str
    document_mention_confidence: float
    document_mention_candidates: tuple[dict[str, object], ...]
    selected_profile: str
    resolved_settings: dict[str, int | bool | str | float | list[str] | list[dict[str, object]]]
    effective_settings: AppSettings


def classify_query_type(*, query: str, settings: AppSettings | None = None) -> QueryTypeClassification:
    """以統一路由框架判定 query type。

    參數：
    - `query`：原始使用者問題。
    - `settings`：可選的應用程式設定；未提供時會使用 deterministic embedding 設定。

    回傳：
    - `QueryTypeClassification`：分類結果、信心與可觀測資訊。
    """

    normalized_query = normalize_query_text(query=query)
    language = detect_query_language(query=normalized_query)
    resolved_settings = settings or AppSettings(EMBEDDING_PROVIDER="deterministic")
    task_type_decision = resolve_task_type(
        settings=resolved_settings,
        query=normalized_query,
        language=language,
        raw_mention_resolution=_empty_document_mention_resolution(),
        explicit_query_type=None,
    )
    return QueryTypeClassification(
        query_type=EvaluationQueryType(task_type_decision.label),
        language=language,
        confidence=task_type_decision.confidence,
        source=task_type_decision.source,
        matched_rules=tuple(hit.reason for hit in task_type_decision.rule_hits),
        rule_hits=task_type_decision.rule_hits,
        embedding_scores=task_type_decision.embedding_scores,
        top_label=task_type_decision.top_label,
        runner_up_label=task_type_decision.runner_up_label,
        margin=task_type_decision.margin,
        fallback_used=task_type_decision.fallback_used,
        fallback_reason=task_type_decision.fallback_reason,
    )


def build_query_routing_decision(
    *,
    settings: AppSettings,
    query: str,
    explicit_document_scope: DocumentScope | str | None = None,
    explicit_summary_strategy: SummaryStrategy | str | None = None,
    explicit_query_type: EvaluationQueryType | None = None,
    session: Session | None = None,
    principal: CurrentPrincipal | None = None,
    area_id: str | None = None,
) -> QueryRoutingDecision:
    """建立單次 query-aware retrieval routing 決策。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `explicit_document_scope`：若由外部提供文件範圍提示，只影響 scope 判斷，不允許直接指定 document ids。
    - `explicit_summary_strategy`：若由外部提供摘要策略提示，只在 `document_summary` 下使用。
    - `explicit_query_type`：若由外部 contract 指定 query type，優先使用。
    - `session`：目前資料庫 session；供文件名稱解析使用。
    - `principal`：目前已驗證使用者；供文件名稱解析使用。
    - `area_id`：目標 area；供文件名稱解析使用。

    回傳：
    - `QueryRoutingDecision`：最終 query type、profile 與有效設定。
    """

    normalized_query = normalize_query_text(query=query)
    language = detect_query_language(query=normalized_query)
    raw_mention_resolution = resolve_document_mentions(
        session=session,
        principal=principal,
        area_id=area_id,
        query=normalized_query,
    )
    explicit_scope = _resolve_explicit_document_scope(explicit_document_scope=explicit_document_scope)
    explicit_summary_strategy_value = _resolve_explicit_summary_strategy(
        explicit_summary_strategy=explicit_summary_strategy,
    )
    effective_explicit_query_type = explicit_query_type or (
        EvaluationQueryType.document_summary if explicit_summary_strategy_value is not None else None
    )
    task_type_decision = resolve_task_type(
        settings=settings,
        query=normalized_query,
        language=language,
        raw_mention_resolution=raw_mention_resolution,
        explicit_query_type=effective_explicit_query_type,
    )
    mention_resolution = _resolve_document_mentions_for_query_type(
        raw_mention_resolution=raw_mention_resolution,
        query=normalized_query,
        query_type=EvaluationQueryType(task_type_decision.label),
        explicit_scope=explicit_scope,
    )
    document_scope = _resolve_document_scope(
        mention_resolution=mention_resolution,
        explicit_scope=explicit_scope,
    )
    summary_strategy_decision = resolve_summary_strategy(
        settings=settings,
        query=normalized_query,
        language=language,
        query_type=EvaluationQueryType(task_type_decision.label),
        mention_resolution=mention_resolution,
        document_scope=document_scope,
        explicit_summary_strategy=explicit_summary_strategy_value,
    )
    summary_scope = _resolve_final_summary_scope(
        query_type=EvaluationQueryType(task_type_decision.label),
        mention_resolution=mention_resolution,
        document_scope=document_scope,
        summary_strategy=summary_strategy_decision.label,
    )
    profile_name, overrides = _resolve_runtime_profile_overrides(
        settings=settings,
        query_type=EvaluationQueryType(task_type_decision.label),
        summary_scope=summary_scope,
        summary_strategy=summary_strategy_decision.label,
    )
    effective_settings = settings.model_copy(update=overrides)
    return QueryRoutingDecision(
        query_type=EvaluationQueryType(task_type_decision.label),
        language=language,
        confidence=task_type_decision.confidence,
        source=task_type_decision.source,
        matched_rules=tuple(hit.reason for hit in task_type_decision.rule_hits),
        query_type_rule_hits=task_type_decision.rule_hits,
        query_type_embedding_scores=task_type_decision.embedding_scores,
        query_type_top_label=task_type_decision.top_label,
        query_type_runner_up_label=task_type_decision.runner_up_label,
        query_type_embedding_margin=task_type_decision.margin,
        query_type_fallback_used=task_type_decision.fallback_used,
        query_type_fallback_reason=task_type_decision.fallback_reason,
        summary_scope=summary_scope,
        summary_strategy=summary_strategy_decision.label or None,
        summary_strategy_source=summary_strategy_decision.source,
        summary_strategy_confidence=summary_strategy_decision.confidence,
        summary_strategy_rule_hits=summary_strategy_decision.rule_hits,
        summary_strategy_embedding_scores=summary_strategy_decision.embedding_scores,
        summary_strategy_top_label=summary_strategy_decision.top_label or None,
        summary_strategy_runner_up_label=summary_strategy_decision.runner_up_label,
        summary_strategy_embedding_margin=summary_strategy_decision.margin,
        summary_strategy_fallback_used=summary_strategy_decision.fallback_used,
        summary_strategy_fallback_reason=summary_strategy_decision.fallback_reason,
        document_scope=document_scope.value,
        resolved_document_ids=mention_resolution.resolved_document_ids,
        document_mention_source=mention_resolution.source,
        document_mention_confidence=mention_resolution.confidence,
        document_mention_candidates=tuple(
            {
                "document_id": candidate.document_id,
                "file_name": candidate.file_name,
                "score": candidate.score,
                "match_signals": list(candidate.match_signals),
            }
            for candidate in mention_resolution.candidates
        ),
        selected_profile=profile_name,
        resolved_settings=build_resolved_settings_trace(
            settings=effective_settings,
            task_type_decision=task_type_decision,
            summary_strategy_decision=summary_strategy_decision,
        ),
        effective_settings=effective_settings,
    )


def _resolve_explicit_document_scope(
    *,
    explicit_document_scope: DocumentScope | str | None,
) -> DocumentScope | None:
    """解析外部提供的文件範圍提示。

    前置條件與風險：
    - 此函式只解析 scope hint；不得接受或信任外部傳入的 document ids。
    - 真正可用的文件集合仍必須由 SQL-gated ready 文件 mention resolver 產生。

    參數：
    - `explicit_document_scope`：外部提供的 scope 字串。

    回傳：
    - `DocumentScope | None`：成功解析的 scope；未提供時回傳空值。
    """

    if explicit_document_scope is None:
        return None
    if isinstance(explicit_document_scope, DocumentScope):
        return explicit_document_scope
    normalized = str(explicit_document_scope).strip()
    if not normalized:
        return None
    if normalized not in DOCUMENT_SCOPE_LABELS:
        allowed_text = "、".join(DOCUMENT_SCOPE_LABELS)
        raise ValueError(f"不支援的 explicit_document_scope：{normalized}；僅支援 {allowed_text}。")
    return DocumentScope(normalized)


def _resolve_explicit_summary_strategy(
    *,
    explicit_summary_strategy: SummaryStrategy | str | None,
) -> SummaryStrategy | None:
    """解析外部提供的摘要策略提示。

    參數：
    - `explicit_summary_strategy`：外部提供的 summary strategy 字串。

    回傳：
    - `SummaryStrategy | None`：成功解析的摘要策略；未提供時回傳空值。
    """

    if explicit_summary_strategy is None:
        return None
    if isinstance(explicit_summary_strategy, SummaryStrategy):
        return explicit_summary_strategy
    normalized = str(explicit_summary_strategy).strip()
    if not normalized:
        return None
    if normalized not in SUMMARY_STRATEGY_HINT_LABELS:
        allowed_text = "、".join(SUMMARY_STRATEGY_HINT_LABELS)
        raise ValueError(f"不支援的 explicit_summary_strategy：{normalized}；僅支援 {allowed_text}。")
    return SummaryStrategy(normalized)


def resolve_task_type(
    *,
    settings: AppSettings,
    query: str,
    language: str,
    raw_mention_resolution: DocumentMentionResolution,
    explicit_query_type: EvaluationQueryType | None,
) -> RoutingClassifierDecision:
    """使用共享 classifier framework 決定第一層 `task_type`。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `raw_mention_resolution`：未受 query type 限制的文件 mention 解析結果。
    - `explicit_query_type`：若由外部指定的 query type。

    回傳：
    - `RoutingClassifierDecision`：第一層決策結果。
    """

    if explicit_query_type is not None:
        return RoutingClassifierDecision(
            label=explicit_query_type.value,
            confidence=1.0,
            source=QUERY_ROUTING_SOURCE_EXPLICIT,
            rule_hits=(),
            embedding_scores=(),
            top_label=explicit_query_type.value,
            runner_up_label=None,
            margin=1.0,
            fallback_used=False,
            fallback_reason=None,
        )

    rule_hits = apply_task_type_rules(query=query, language=language)
    return _resolve_label_with_classifier_framework(
        settings=settings,
        query=query,
        language=language,
        label_options=TASK_TYPE_LABELS,
        prototypes=TASK_TYPE_PROTOTYPES,
        label_descriptions=TASK_TYPE_LABEL_DESCRIPTIONS,
        rule_hits=rule_hits,
        embedding_confidence_threshold=TASK_TYPE_EMBEDDING_CONFIDENCE_THRESHOLD,
        embedding_margin_threshold=TASK_TYPE_EMBEDDING_MARGIN_THRESHOLD,
        safe_fallback_label=EvaluationQueryType.fact_lookup.value,
        safe_fallback_confidence=0.0,
        safe_fallback_reason="llm_fallback_unavailable",
        llm_context={
            "document_mention_source": raw_mention_resolution.source,
            "document_mention_confidence": raw_mention_resolution.confidence,
            "document_mention_candidates": [
                {
                    "file_name": candidate.file_name,
                    "score": candidate.score,
                    "match_signals": list(candidate.match_signals),
                }
                for candidate in raw_mention_resolution.candidates[:3]
            ],
        },
        conflict_reason_resolver=(
            lambda top_label: _resolve_task_type_conflict_reason(
                top_label=top_label,
                mention_resolution=raw_mention_resolution,
            )
        ),
        classifier_name="task_type",
    )


def resolve_summary_strategy(
    *,
    settings: AppSettings,
    query: str,
    language: str,
    query_type: EvaluationQueryType,
    mention_resolution: DocumentMentionResolution,
    document_scope: DocumentScope,
    explicit_summary_strategy: SummaryStrategy | None,
) -> RoutingClassifierDecision:
    """使用共享 classifier framework 決定第二層 `summary_strategy`。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `query_type`：已完成解析的第一層 task type。
    - `mention_resolution`：文件 mention 解析結果。
    - `document_scope`：目前解析出的文件範圍。
    - `explicit_summary_strategy`：外部提供的摘要策略提示；可為空值。

    回傳：
    - `RoutingClassifierDecision`：第二層決策結果；若不適用則回傳空決策。
    """

    if query_type != EvaluationQueryType.document_summary:
        return RoutingClassifierDecision(
            label="",
            confidence=0.0,
            source="not_applicable",
            rule_hits=(),
            embedding_scores=(),
            top_label="",
            runner_up_label=None,
            margin=0.0,
            fallback_used=False,
            fallback_reason=None,
        )

    if explicit_summary_strategy is not None:
        return RoutingClassifierDecision(
            label=explicit_summary_strategy.value,
            confidence=1.0,
            source=QUERY_ROUTING_SOURCE_EXPLICIT,
            rule_hits=(),
            embedding_scores=(),
            top_label=explicit_summary_strategy.value,
            runner_up_label=None,
            margin=1.0,
            fallback_used=False,
            fallback_reason=None,
        )

    rule_hits = apply_summary_strategy_rules(
        query=query,
        language=language,
        mention_resolution=mention_resolution,
        document_scope=document_scope,
    )
    allowed_labels = _resolve_summary_strategy_label_options(
        mention_resolution=mention_resolution,
        document_scope=document_scope,
    )
    try:
        initial_embedding_decision = classify_summary_strategy_with_embeddings(
            settings=settings,
            query=query,
            label_options=allowed_labels,
        )
    except Exception:
        safe_fallback_label = (
            SUMMARY_STRATEGY_DOCUMENT_OVERVIEW
            if document_scope == DocumentScope.SINGLE_DOCUMENT and len(mention_resolution.resolved_document_ids) == 1
            else SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME
        )
        return RoutingClassifierDecision(
            label=safe_fallback_label,
            confidence=0.0,
            source=QUERY_ROUTING_SOURCE_FALLBACK,
            rule_hits=(),
            embedding_scores=(),
            top_label=safe_fallback_label,
            runner_up_label=None,
            margin=0.0,
            fallback_used=False,
            fallback_reason="embedding_classifier_error",
        )
    conflict_reason = _resolve_summary_strategy_conflict_reason(
        top_label=initial_embedding_decision.top_label,
        mention_resolution=mention_resolution,
    )
    if rule_hits:
        return RoutingClassifierDecision(
            label=rule_hits[0].label,
            confidence=rule_hits[0].confidence,
            source=QUERY_ROUTING_SOURCE_RULE,
            rule_hits=rule_hits,
            embedding_scores=initial_embedding_decision.embedding_scores,
            top_label=initial_embedding_decision.top_label,
            runner_up_label=initial_embedding_decision.runner_up_label,
            margin=initial_embedding_decision.margin,
            fallback_used=False,
            fallback_reason=None,
        )
    if (
        initial_embedding_decision.confidence >= SUMMARY_STRATEGY_EMBEDDING_CONFIDENCE_THRESHOLD
        and initial_embedding_decision.margin >= SUMMARY_STRATEGY_EMBEDDING_MARGIN_THRESHOLD
        and conflict_reason is None
    ):
        return initial_embedding_decision
    llm_context = {
        "document_mention_source": mention_resolution.source,
        "document_mention_confidence": mention_resolution.confidence,
        "document_mention_candidates": [
            {
                "file_name": candidate.file_name,
                "score": candidate.score,
                "match_signals": list(candidate.match_signals),
            }
            for candidate in mention_resolution.candidates[:3]
        ],
        "resolved_document_ids": list(mention_resolution.resolved_document_ids),
    }
    llm_decision = _run_llm_label_fallback(
        settings=settings,
        classifier_name="summary_strategy",
        query=query,
        language=language,
        label_options=allowed_labels,
        label_descriptions=SUMMARY_STRATEGY_LABEL_DESCRIPTIONS,
        llm_context=llm_context,
    )
    if llm_decision is not None:
        return RoutingClassifierDecision(
            label=llm_decision.label,
            confidence=llm_decision.confidence,
            source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
            rule_hits=(),
            embedding_scores=initial_embedding_decision.embedding_scores,
            top_label=initial_embedding_decision.top_label,
            runner_up_label=initial_embedding_decision.runner_up_label,
            margin=initial_embedding_decision.margin,
            fallback_used=True,
            fallback_reason=conflict_reason or "low_embedding_confidence",
        )
    safe_fallback_label = (
        SUMMARY_STRATEGY_DOCUMENT_OVERVIEW
        if document_scope == DocumentScope.SINGLE_DOCUMENT and len(mention_resolution.resolved_document_ids) == 1
        else SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME
    )
    return RoutingClassifierDecision(
        label=safe_fallback_label,
        confidence=0.0,
        source=QUERY_ROUTING_SOURCE_FALLBACK,
        rule_hits=(),
        embedding_scores=initial_embedding_decision.embedding_scores,
        top_label=initial_embedding_decision.top_label,
        runner_up_label=initial_embedding_decision.runner_up_label,
        margin=initial_embedding_decision.margin,
        fallback_used=False,
        fallback_reason="llm_fallback_unavailable",
    )


def apply_task_type_rules(*, query: str, language: str) -> tuple[RoutingRuleHit, ...]:
    """套用第一層 `task_type` 的高 precision 規則。

    參數：
    - `query`：原始使用者問題。
    - `language`：query 語言。

    回傳：
    - `tuple[RoutingRuleHit, ...]`：命中的高 precision 規則。
    """

    lowered_query = query.casefold()
    compare_matches = _match_trigger_phrases(
        lowered_query=lowered_query,
        language=language,
        zh_tw_phrases=COMPARE_TRIGGER_PHRASES_ZH_TW,
        en_phrases=COMPARE_TRIGGER_PHRASES_EN,
    )
    if compare_matches:
        return tuple(
            RoutingRuleHit(
                label=EvaluationQueryType.cross_document_compare.value,
                reason=match,
                confidence=_score_rule_confidence(match_count=len(compare_matches)),
            )
            for match in compare_matches
        )

    summary_matches = _match_trigger_phrases(
        lowered_query=lowered_query,
        language=language,
        zh_tw_phrases=SUMMARY_TRIGGER_PHRASES_ZH_TW,
        en_phrases=SUMMARY_TRIGGER_PHRASES_EN,
    )
    if summary_matches:
        return tuple(
            RoutingRuleHit(
                label=EvaluationQueryType.document_summary.value,
                reason=match,
                confidence=_score_rule_confidence(match_count=len(summary_matches)),
            )
            for match in summary_matches
        )
    return ()


def apply_summary_strategy_rules(
    *,
    query: str,
    language: str,
    mention_resolution: DocumentMentionResolution,
    document_scope: DocumentScope,
) -> tuple[RoutingRuleHit, ...]:
    """套用第二層 `summary_strategy` 的高 precision 規則。

    參數：
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `mention_resolution`：文件 mention 解析結果。
    - `document_scope`：目前解析出的文件範圍。

    回傳：
    - `tuple[RoutingRuleHit, ...]`：命中的高 precision 規則。
    """

    lowered_query = query.casefold()
    if len(mention_resolution.resolved_document_ids) >= 2 or document_scope == DocumentScope.MULTI_DOCUMENT:
        return (
            RoutingRuleHit(
                label=SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME,
                reason="multi_document_scope_rule",
                confidence=0.9,
            ),
        )

    if len(mention_resolution.resolved_document_ids) == 1:
        matches = _match_trigger_phrases(
            lowered_query=lowered_query,
            language=language,
            zh_tw_phrases=SECTION_FOCUS_TRIGGER_PHRASES_ZH_TW,
            en_phrases=SECTION_FOCUS_TRIGGER_PHRASES_EN,
        )
        if matches:
            return tuple(
                RoutingRuleHit(
                    label=SUMMARY_STRATEGY_SECTION_FOCUSED,
                    reason=match,
                    confidence=_score_rule_confidence(match_count=len(matches)),
                )
                for match in matches
            )
    return ()


def classify_task_type_with_embeddings(
    *,
    settings: AppSettings,
    query: str,
) -> RoutingClassifierDecision:
    """以 embedding classifier 決定第一層 `task_type`。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。

    回傳：
    - `RoutingClassifierDecision`：embedding classifier 決策。
    """

    return _classify_labels_with_embeddings(
        settings=settings,
        query=query,
        label_options=TASK_TYPE_LABELS,
        prototypes=TASK_TYPE_PROTOTYPES,
        classifier_name="task_type",
    )


def classify_summary_strategy_with_embeddings(
    *,
    settings: AppSettings,
    query: str,
    label_options: tuple[str, ...],
) -> RoutingClassifierDecision:
    """以 embedding classifier 決定第二層 `summary_strategy`。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `label_options`：本次允許的 summary strategy labels。

    回傳：
    - `RoutingClassifierDecision`：embedding classifier 決策。
    """

    filtered_prototypes = {
        label: SUMMARY_STRATEGY_PROTOTYPES[label]
        for label in label_options
    }
    return _classify_labels_with_embeddings(
        settings=settings,
        query=query,
        label_options=label_options,
        prototypes=filtered_prototypes,
        classifier_name="summary_strategy",
    )


def fallback_task_type_with_llm(
    *,
    settings: AppSettings,
    query: str,
    language: str,
    raw_mention_resolution: DocumentMentionResolution,
) -> RoutingClassifierDecision | None:
    """在第一層低信心時呼叫 LLM fallback。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `raw_mention_resolution`：未受 query type 限制的 mention 解析結果。

    回傳：
    - `RoutingClassifierDecision | None`：若 fallback 可用則回傳決策，否則回傳空值。
    """

    llm_decision = _run_llm_label_fallback(
        settings=settings,
        classifier_name="task_type",
        query=query,
        language=language,
        label_options=TASK_TYPE_LABELS,
        label_descriptions=TASK_TYPE_LABEL_DESCRIPTIONS,
        llm_context={
            "document_mention_source": raw_mention_resolution.source,
            "document_mention_confidence": raw_mention_resolution.confidence,
            "document_mention_candidates": [
                {
                    "file_name": candidate.file_name,
                    "score": candidate.score,
                    "match_signals": list(candidate.match_signals),
                }
                for candidate in raw_mention_resolution.candidates[:3]
            ],
        },
    )
    if llm_decision is None:
        return None
    return RoutingClassifierDecision(
        label=llm_decision.label,
        confidence=llm_decision.confidence,
        source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
        rule_hits=(),
        embedding_scores=(),
        top_label=llm_decision.label,
        runner_up_label=None,
        margin=0.0,
        fallback_used=True,
        fallback_reason="low_embedding_confidence",
    )


def fallback_summary_strategy_with_llm(
    *,
    settings: AppSettings,
    query: str,
    language: str,
    mention_resolution: DocumentMentionResolution,
    label_options: tuple[str, ...],
) -> RoutingClassifierDecision | None:
    """在第二層低信心時呼叫 LLM fallback。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `mention_resolution`：文件 mention 解析結果。
    - `label_options`：本次允許的 summary strategy labels。

    回傳：
    - `RoutingClassifierDecision | None`：若 fallback 可用則回傳決策，否則回傳空值。
    """

    llm_decision = _run_llm_label_fallback(
        settings=settings,
        classifier_name="summary_strategy",
        query=query,
        language=language,
        label_options=label_options,
        label_descriptions=SUMMARY_STRATEGY_LABEL_DESCRIPTIONS,
        llm_context={
            "document_mention_source": mention_resolution.source,
            "document_mention_confidence": mention_resolution.confidence,
            "document_mention_candidates": [
                {
                    "file_name": candidate.file_name,
                    "score": candidate.score,
                    "match_signals": list(candidate.match_signals),
                }
                for candidate in mention_resolution.candidates[:3]
            ],
            "resolved_document_ids": list(mention_resolution.resolved_document_ids),
        },
    )
    if llm_decision is None:
        return None
    return RoutingClassifierDecision(
        label=llm_decision.label,
        confidence=llm_decision.confidence,
        source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
        rule_hits=(),
        embedding_scores=(),
        top_label=llm_decision.label,
        runner_up_label=None,
        margin=0.0,
        fallback_used=True,
        fallback_reason="low_embedding_confidence",
    )


def _resolve_label_with_classifier_framework(
    *,
    settings: AppSettings,
    query: str,
    language: str,
    label_options: tuple[str, ...],
    prototypes: dict[str, tuple[str, ...]],
    label_descriptions: dict[str, str],
    rule_hits: tuple[RoutingRuleHit, ...],
    embedding_confidence_threshold: float,
    embedding_margin_threshold: float,
    safe_fallback_label: str,
    safe_fallback_confidence: float,
    safe_fallback_reason: str,
    llm_context: dict[str, object],
    conflict_reason_resolver: Callable[[str], str | None] | None,
    classifier_name: Literal["task_type", "summary_strategy"],
) -> RoutingClassifierDecision:
    """依 `rule -> embedding -> llm fallback` 決定 label。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `label_options`：本次允許的 labels。
    - `prototypes`：label 對應的 prototype registry。
    - `label_descriptions`：LLM fallback 使用的 label 定義。
    - `rule_hits`：高 precision rule hits。
    - `embedding_confidence_threshold`：embedding 最低 confidence 門檻。
    - `embedding_margin_threshold`：embedding 最低 margin 門檻。
    - `safe_fallback_label`：當 LLM fallback 不可用時的保守 label。
    - `safe_fallback_confidence`：保守 label 的 confidence。
    - `safe_fallback_reason`：保守 label 的 fallback reason。
    - `llm_context`：LLM fallback 可見的最小上下文。
    - `conflict_reason_resolver`：依 embedding top label 判斷是否存在 scope/mention conflict。
    - `classifier_name`：目前是第一層或第二層 classifier。

    回傳：
    - `RoutingClassifierDecision`：最終 classifier 決策。
    """

    try:
        embedding_decision = _classify_labels_with_embeddings(
            settings=settings,
            query=query,
            label_options=label_options,
            prototypes=prototypes,
            classifier_name=classifier_name,
        )
    except Exception:
        return RoutingClassifierDecision(
            label=safe_fallback_label,
            confidence=safe_fallback_confidence,
            source=QUERY_ROUTING_SOURCE_FALLBACK,
            rule_hits=(),
            embedding_scores=(),
            top_label=safe_fallback_label,
            runner_up_label=None,
            margin=0.0,
            fallback_used=False,
            fallback_reason="embedding_classifier_error",
        )
    if rule_hits:
        return RoutingClassifierDecision(
            label=rule_hits[0].label,
            confidence=rule_hits[0].confidence,
            source=QUERY_ROUTING_SOURCE_RULE,
            rule_hits=rule_hits,
            embedding_scores=embedding_decision.embedding_scores,
            top_label=embedding_decision.top_label,
            runner_up_label=embedding_decision.runner_up_label,
            margin=embedding_decision.margin,
            fallback_used=False,
            fallback_reason=None,
        )

    conflict_reason = (
        conflict_reason_resolver(embedding_decision.top_label)
        if conflict_reason_resolver is not None
        else None
    )
    if (
        embedding_decision.confidence >= embedding_confidence_threshold
        and embedding_decision.margin >= embedding_margin_threshold
        and conflict_reason is None
    ):
        return embedding_decision

    llm_decision = _run_llm_label_fallback(
        settings=settings,
        classifier_name=classifier_name,
        query=query,
        language=language,
        label_options=label_options,
        label_descriptions=label_descriptions,
        llm_context=llm_context,
    )
    if llm_decision is not None:
        return RoutingClassifierDecision(
            label=llm_decision.label,
            confidence=llm_decision.confidence,
            source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
            rule_hits=(),
            embedding_scores=embedding_decision.embedding_scores,
            top_label=embedding_decision.top_label,
            runner_up_label=embedding_decision.runner_up_label,
            margin=embedding_decision.margin,
            fallback_used=True,
            fallback_reason=conflict_reason or "low_embedding_confidence",
        )

    return RoutingClassifierDecision(
        label=safe_fallback_label,
        confidence=safe_fallback_confidence,
        source=QUERY_ROUTING_SOURCE_FALLBACK,
        rule_hits=(),
        embedding_scores=embedding_decision.embedding_scores,
        top_label=embedding_decision.top_label,
        runner_up_label=embedding_decision.runner_up_label,
        margin=embedding_decision.margin,
        fallback_used=False,
        fallback_reason=safe_fallback_reason,
    )


def _classify_labels_with_embeddings(
    *,
    settings: AppSettings,
    query: str,
    label_options: tuple[str, ...],
    prototypes: dict[str, tuple[str, ...]],
    classifier_name: str,
) -> RoutingClassifierDecision:
    """以 query-to-prototype similarity 決定 label。

    參數：
    - `settings`：目前應用程式設定。
    - `query`：原始使用者問題。
    - `label_options`：本次允許的 labels。
    - `prototypes`：label 對應的 prototype registry。
    - `classifier_name`：classifier 名稱，供除錯與錯誤訊息使用。

    回傳：
    - `RoutingClassifierDecision`：embedding classifier 的暫時決策。
    """

    provider = build_embedding_provider(settings)
    query_embedding = provider.embed_query(query)
    score_rows: list[RoutingEmbeddingScore] = []
    best_label = label_options[0]
    best_score = -1.0
    runner_up_label: str | None = None
    runner_up_score = -1.0

    for label in label_options:
        label_prototypes = prototypes[label]
        label_score = _score_label_against_prototypes(
            settings=settings,
            provider_query_embedding=query_embedding,
            label=label,
            prototypes=label_prototypes,
        )
        score_rows.append(RoutingEmbeddingScore(label=label, score=round(label_score, 4)))
        if label_score > best_score:
            runner_up_label = best_label
            runner_up_score = best_score
            best_label = label
            best_score = label_score
            continue
        if label_score > runner_up_score:
            runner_up_label = label
            runner_up_score = label_score

    margin = round(max(0.0, best_score - max(-1.0, runner_up_score)), 4)
    return RoutingClassifierDecision(
        label=best_label,
        confidence=round(_similarity_to_confidence(best_score), 4),
        source=QUERY_ROUTING_SOURCE_EMBEDDING,
        rule_hits=(),
        embedding_scores=tuple(sorted(score_rows, key=lambda item: (-item.score, item.label))),
        top_label=best_label,
        runner_up_label=runner_up_label,
        margin=margin,
        fallback_used=False,
        fallback_reason=None,
    )


def _score_label_against_prototypes(
    *,
    settings: AppSettings,
    provider_query_embedding: list[float],
    label: str,
    prototypes: tuple[str, ...],
) -> float:
    """計算 query 與單一 label prototype set 的相似度。

    參數：
    - `settings`：目前應用程式設定。
    - `provider_query_embedding`：query embedding。
    - `label`：要評分的 label。
    - `prototypes`：該 label 對應的 semantic prototypes。

    回傳：
    - `float`：0 到 1 左右的相似度。
    """

    prototype_embeddings = _get_cached_prototype_embeddings(
        settings=settings,
        label=label,
        prototypes=prototypes,
    )
    return max(
        _cosine_similarity(provider_query_embedding, list(prototype_embedding))
        for prototype_embedding in prototype_embeddings
    )


def _get_cached_prototype_embeddings(
    *,
    settings: AppSettings,
    label: str,
    prototypes: tuple[str, ...],
) -> tuple[tuple[float, ...], ...]:
    """取得固定 prototype set 的 embeddings。

    參數：
    - `settings`：目前應用程式設定。
    - `label`：目前 label 名稱。
    - `prototypes`：該 label 對應的 semantic prototypes。

    回傳：
    - `tuple[tuple[float, ...], ...]`：可重用的 prototype embeddings。
    """

    cache_key = (
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_dimensions,
        settings.self_hosted_embedding_base_url or "",
        settings.openrouter_http_referer or "",
        settings.openrouter_title or "",
        label,
        prototypes,
    )
    if cache_key in _ROUTING_PROTOTYPE_EMBEDDING_CACHE:
        return _ROUTING_PROTOTYPE_EMBEDDING_CACHE[cache_key]

    provider = build_embedding_provider(settings)
    embeddings = tuple(
        tuple(embedding)
        for embedding in provider.embed_texts(list(prototypes))
    )
    _ROUTING_PROTOTYPE_EMBEDDING_CACHE[cache_key] = embeddings
    return embeddings


def _run_llm_label_fallback(
    *,
    settings: AppSettings,
    classifier_name: str,
    query: str,
    language: str,
    label_options: tuple[str, ...],
    label_descriptions: dict[str, str],
    llm_context: dict[str, object],
) -> RoutingClassifierDecision | None:
    """在低信心時以 LLM 做受限 label fallback。

    參數：
    - `settings`：目前應用程式設定。
    - `classifier_name`：目前 classifier 名稱。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `label_options`：可選 labels。
    - `label_descriptions`：各 label 的簡短定義。
    - `llm_context`：除 query 外可見的最小上下文。

    回傳：
    - `RoutingClassifierDecision | None`：若 fallback 成功則回傳決策，否則回傳空值。
    """

    if not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
        return None

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.chat_timeout_seconds)
    system_prompt, user_prompt = _build_llm_label_fallback_prompt(
        classifier_name=classifier_name,
        query=query,
        language=language,
        label_options=label_options,
        label_descriptions=label_descriptions,
        llm_context=llm_context,
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=settings.chat_model,
                reasoning_effort=_resolve_llm_fallback_reasoning_effort(classifier_name=classifier_name),
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            label = str(payload.get("label", "")).strip()
            if label not in label_options:
                return None
            confidence = _normalize_llm_confidence(payload.get("confidence"))
            reason = str(payload.get("reason", "")).strip() or "llm_fallback"
            return RoutingClassifierDecision(
                label=label,
                confidence=confidence,
                source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
                rule_hits=(),
                embedding_scores=(),
                top_label=label,
                runner_up_label=None,
                margin=0.0,
                fallback_used=True,
                fallback_reason=reason,
            )
        except Exception as exc:  # pragma: no cover - 具體異常由整合測試覆蓋。
            last_error = exc
            if not _is_retryable_llm_routing_error(exc=exc) or attempt >= 3:
                return None
            time.sleep(min(2.0 * attempt, settings.chat_timeout_seconds))
    if last_error is not None:
        return None
    return None


def _resolve_llm_fallback_reasoning_effort(
    *,
    classifier_name: Literal["task_type", "summary_strategy"],
) -> str:
    """依 classifier 類型回傳對應的 fallback reasoning effort。

    參數：
    - `classifier_name`：目前是第一層或第二層 classifier。

    回傳：
    - `str`：應使用的 OpenAI reasoning effort。
    """

    if classifier_name == "summary_strategy":
        return OPENAI_REASONING_EFFORT_SUMMARY_STRATEGY
    return OPENAI_REASONING_EFFORT_TASK_TYPE


def _build_llm_label_fallback_prompt(
    *,
    classifier_name: str,
    query: str,
    language: str,
    label_options: tuple[str, ...],
    label_descriptions: dict[str, str],
    llm_context: dict[str, object],
) -> tuple[str, str]:
    """建立受限 label fallback prompt。

    參數：
    - `classifier_name`：目前 classifier 名稱。
    - `query`：原始使用者問題。
    - `language`：query 語言。
    - `label_options`：可選 labels。
    - `label_descriptions`：各 label 的簡短定義。
    - `llm_context`：除 query 外可見的最小上下文。

    回傳：
    - `tuple[str, str]`：system prompt 與 user prompt。
    """

    system_prompt = (
        "You are a strict routing classifier for a RAG system. "
        "Choose exactly one label from the provided label options. "
        "Do not rewrite the query. Do not infer from any hidden document content. "
        "Only use the query, language, and mention summary. "
        "Return JSON with keys `label`, `confidence`, and `reason`."
    )
    user_payload = {
        "classifier_name": classifier_name,
        "query": query,
        "language": language,
        "labels": [
            {
                "label": label,
                "description": label_descriptions[label],
            }
            for label in label_options
        ],
        "context": llm_context,
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=False, indent=2)


def _resolve_runtime_profile_overrides(
    *,
    settings: AppSettings,
    query_type: EvaluationQueryType,
    summary_scope: str | None,
    summary_strategy: str | None,
) -> tuple[str, dict[str, int | str | bool]]:
    """依 query type 解析 runtime profile 名稱與設定覆寫。

    參數：
    - `settings`：目前應用程式設定。
    - `query_type`：本次 query type。
    - `summary_scope`：若為摘要問題，表示 single/multi document scope。
    - `summary_strategy`：第二層 summary strategy。

    回傳：
    - `tuple[str, dict[str, int | str | bool]]`：profile 名稱與設定覆寫。
    """

    if query_type == EvaluationQueryType.document_summary:
        if summary_strategy == SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME:
            return (
                RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1,
                {
                    "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                    "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                    "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                    "retrieval_document_recall_enabled": True,
                    "retrieval_document_recall_top_k": max(settings.retrieval_document_recall_top_k, 6),
                    "rerank_top_n": max(settings.rerank_top_n, 36),
                    "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                    "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
                    "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 7),
                },
            )
        if summary_scope == "single_document":
            return (
                RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1,
                {
                    "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                    "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                    "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                    "retrieval_document_recall_enabled": True,
                    "retrieval_document_recall_top_k": 1,
                    "rerank_top_n": max(settings.rerank_top_n, 36),
                    "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                    "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
                    "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 7),
                },
            )
        return (
            RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1,
            {
                "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                "retrieval_document_recall_enabled": True,
                "retrieval_document_recall_top_k": max(settings.retrieval_document_recall_top_k, 6),
                "rerank_top_n": max(settings.rerank_top_n, 36),
                "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3600),
                "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 7),
            },
        )
    if query_type == EvaluationQueryType.cross_document_compare:
        return (
            RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_DIVERSIFIED_V1,
            {
                "retrieval_vector_top_k": max(settings.retrieval_vector_top_k, 45),
                "retrieval_fts_top_k": max(settings.retrieval_fts_top_k, 45),
                "retrieval_max_candidates": max(settings.retrieval_max_candidates, 45),
                "retrieval_document_recall_enabled": True,
                "retrieval_document_recall_top_k": max(settings.retrieval_document_recall_top_k, 8),
                "rerank_top_n": max(settings.rerank_top_n, 36),
                "assembler_max_contexts": max(settings.assembler_max_contexts, 12),
                "assembler_max_chars_per_context": max(settings.assembler_max_chars_per_context, 3200),
                "assembler_max_children_per_parent": max(settings.assembler_max_children_per_parent, 5),
            },
        )
    return (
        RETRIEVAL_PROFILE_FACT_LOOKUP_PRECISION_V1,
        {
            "retrieval_vector_top_k": settings.retrieval_vector_top_k,
            "retrieval_fts_top_k": settings.retrieval_fts_top_k,
            "retrieval_max_candidates": settings.retrieval_max_candidates,
            "retrieval_document_recall_enabled": False,
            "retrieval_document_recall_top_k": settings.retrieval_document_recall_top_k,
            "rerank_top_n": settings.rerank_top_n,
            "assembler_max_contexts": settings.assembler_max_contexts,
            "assembler_max_chars_per_context": settings.assembler_max_chars_per_context,
            "assembler_max_children_per_parent": settings.assembler_max_children_per_parent,
        },
    )


def build_resolved_settings_trace(
    *,
    settings: AppSettings,
    task_type_decision: RoutingClassifierDecision | None = None,
    summary_strategy_decision: RoutingClassifierDecision | None = None,
) -> dict[str, int | bool | str | float | list[str] | list[dict[str, object]]]:
    """建立 query routing 可觀測的有效設定摘要。

    參數：
    - `settings`：routing 後的有效設定。
    - `task_type_decision`：第一層決策；若未提供則略過其 trace。
    - `summary_strategy_decision`：第二層決策；若未提供則略過其 trace。

    回傳：
    - `dict[str, int | bool | str | float | list[str] | list[dict[str, object]]]`：debug-safe 設定與 classifier 摘要。
    """

    payload: dict[str, int | bool | str | float | list[str] | list[dict[str, object]]] = {
        "vector_top_k": settings.retrieval_vector_top_k,
        "fts_top_k": settings.retrieval_fts_top_k,
        "max_candidates": settings.retrieval_max_candidates,
        "document_recall_enabled": settings.retrieval_document_recall_enabled,
        "document_recall_top_k": settings.retrieval_document_recall_top_k,
        "rerank_top_n": settings.rerank_top_n,
        "selection_max_contexts": settings.assembler_max_contexts,
        "assembler_max_contexts": settings.assembler_max_contexts,
        "assembler_max_chars_per_context": settings.assembler_max_chars_per_context,
        "assembler_max_children_per_parent": settings.assembler_max_children_per_parent,
    }
    if task_type_decision is not None:
        payload["task_type_embedding_scores"] = [
            {"label": score.label, "score": score.score}
            for score in task_type_decision.embedding_scores
        ]
        payload["task_type_embedding_margin"] = task_type_decision.margin
        payload["task_type_fallback_used"] = task_type_decision.fallback_used
    if summary_strategy_decision is not None:
        payload["summary_strategy_embedding_scores"] = [
            {"label": score.label, "score": score.score}
            for score in summary_strategy_decision.embedding_scores
        ]
        payload["summary_strategy_embedding_margin"] = summary_strategy_decision.margin
        payload["summary_strategy_fallback_used"] = summary_strategy_decision.fallback_used
    return payload


def _resolve_document_mentions_for_query_type(
    *,
    raw_mention_resolution: DocumentMentionResolution,
    query: str,
    query_type: EvaluationQueryType,
    explicit_scope: DocumentScope | None,
) -> DocumentMentionResolution:
    """依 query type 決定是否輸出文件名稱提及解析結果。

    參數：
    - `raw_mention_resolution`：未受 query type 限制的 mention 解析結果。
    - `query_type`：目前 query type。
    - `explicit_scope`：外部提供的 scope hint；可為空值。

    回傳：
    - `DocumentMentionResolution`：可作為檢索 scope 的 mention 結果。
    """

    if explicit_scope == DocumentScope.MULTI_DOCUMENT and len(raw_mention_resolution.resolved_document_ids) < 2:
        promoted_candidates = _select_multi_document_candidates(
            candidates=raw_mention_resolution.candidates,
            threshold=MULTI_DOCUMENT_SCOPE_HINT_CANDIDATE_THRESHOLD,
        )
        if len(promoted_candidates) >= 2:
            return DocumentMentionResolution(
                resolved_document_ids=tuple(candidate.document_id for candidate in promoted_candidates),
                source="multi_document_scope_hint",
                confidence=promoted_candidates[0].score,
                candidates=raw_mention_resolution.candidates,
            )

    if (
        len(raw_mention_resolution.resolved_document_ids) == 1
        and _should_promote_to_multi_document_scope(
            query=query,
            query_type=query_type,
            mention_resolution=raw_mention_resolution,
        )
    ):
        promoted_candidates = _select_multi_document_candidates(
            candidates=raw_mention_resolution.candidates,
            threshold=MULTI_DOCUMENT_QUERY_CANDIDATE_THRESHOLD,
        )
        if len(promoted_candidates) >= 2:
            return DocumentMentionResolution(
                resolved_document_ids=tuple(candidate.document_id for candidate in promoted_candidates),
                source="multi_document_query_override",
                confidence=promoted_candidates[0].score,
                candidates=raw_mention_resolution.candidates,
            )
    return raw_mention_resolution


def _select_multi_document_candidates(
    *,
    candidates: tuple[DocumentMentionCandidate, ...],
    threshold: float,
) -> tuple[DocumentMentionCandidate, ...]:
    """挑出可保留為 multi-document scope 的候選文件。

    參數：
    - `candidates`：依分數排序後的 mention 候選。
    - `threshold`：最低保留分數。

    回傳：
    - `tuple[DocumentMentionCandidate, ...]`：符合門檻的候選集合。
    """

    return tuple(candidate for candidate in candidates if candidate.score >= threshold)


def _should_promote_to_multi_document_scope(
    *,
    query: str,
    query_type: EvaluationQueryType,
    mention_resolution: DocumentMentionResolution,
) -> bool:
    """判斷是否應覆寫單文件 mention，保留 multi-document scope。

    參數：
    - `query`：正規化後的原始 query。
    - `query_type`：目前第一層 task type。
    - `mention_resolution`：目前 mention 解析結果。

    回傳：
    - `bool`：若應優先保留 multi-document scope 則回傳真值。
    """

    if len(mention_resolution.candidates) < 2:
        return False
    if query_type == EvaluationQueryType.cross_document_compare:
        return True
    if query_type != EvaluationQueryType.document_summary:
        return False
    return bool(MULTI_DOCUMENT_QUERY_PATTERN.search(query))


def _resolve_document_scope(
    *,
    mention_resolution: DocumentMentionResolution,
    explicit_scope: DocumentScope | None,
) -> DocumentScope:
    """依後端 mention 解析與外部 hint 決定文件範圍。

    前置條件與風險：
    - high-confidence mention 結果優先於外部 scope hint，避免 agent 把明確文件指稱錯誤擴大成 area-wide。
    - `DocumentScope` 不攜帶 document ids；真正的檢索白名單仍只來自 `mention_resolution.resolved_document_ids`。

    參數：
    - `mention_resolution`：後端在已授權 ready 文件集合中解析出的文件 mention。
    - `explicit_scope`：外部提供的 scope hint；可為空值。

    回傳：
    - `DocumentScope`：本次檢索應採用的文件範圍描述。
    """

    if len(mention_resolution.resolved_document_ids) == 1:
        return DocumentScope.SINGLE_DOCUMENT
    if len(mention_resolution.resolved_document_ids) >= 2:
        return DocumentScope.MULTI_DOCUMENT
    if explicit_scope is not None:
        return explicit_scope
    if mention_resolution.candidates:
        return DocumentScope.UNRESOLVED
    return DocumentScope.AREA


def _resolve_final_summary_scope(
    *,
    query_type: EvaluationQueryType,
    mention_resolution: DocumentMentionResolution,
    document_scope: DocumentScope,
    summary_strategy: str,
) -> str | None:
    """依最終策略與 mention 結果決定 summary scope。

    參數：
    - `query_type`：目前 query type。
    - `mention_resolution`：文件 mention 解析結果。
    - `document_scope`：目前解析出的文件範圍。
    - `summary_strategy`：最終 summary strategy。

    回傳：
    - `str | None`：`single_document`、`multi_document` 或空值。
    """

    if query_type != EvaluationQueryType.document_summary:
        return None
    if summary_strategy == SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME:
        return "multi_document"
    if document_scope == DocumentScope.SINGLE_DOCUMENT and len(mention_resolution.resolved_document_ids) == 1:
        return "single_document"
    return "multi_document"


def _resolve_summary_strategy_label_options(
    *,
    mention_resolution: DocumentMentionResolution,
    document_scope: DocumentScope,
) -> tuple[str, ...]:
    """依 mention 結果限制可用的 summary strategy labels。

    參數：
    - `mention_resolution`：文件 mention 解析結果。
    - `document_scope`：目前解析出的文件範圍。

    回傳：
    - `tuple[str, ...]`：本次允許的 summary strategy labels。
    """

    if len(mention_resolution.resolved_document_ids) >= 2 or document_scope == DocumentScope.MULTI_DOCUMENT:
        return (SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME,)
    if len(mention_resolution.resolved_document_ids) == 1:
        return (
            SUMMARY_STRATEGY_DOCUMENT_OVERVIEW,
            SUMMARY_STRATEGY_SECTION_FOCUSED,
            SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME,
        )
    return (
        SUMMARY_STRATEGY_DOCUMENT_OVERVIEW,
        SUMMARY_STRATEGY_SECTION_FOCUSED,
        SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME,
    )


def _resolve_task_type_conflict_reason(
    *,
    top_label: str | None,
    mention_resolution: DocumentMentionResolution,
) -> str | None:
    """判斷第一層 embedding 結果是否與 mention 訊號衝突。

    參數：
    - `top_label`：embedding top-1 label；若尚未決定可為空值。
    - `mention_resolution`：未受 query type 限制的 mention 解析結果。

    回傳：
    - `str | None`：若存在衝突則回傳原因。
    """

    if top_label is None:
        return None
    resolved_count = len(mention_resolution.resolved_document_ids)
    if resolved_count == 1 and top_label == EvaluationQueryType.cross_document_compare.value:
        return "single_document_mention_conflict"
    return None


def _resolve_summary_strategy_conflict_reason(
    *,
    top_label: str,
    mention_resolution: DocumentMentionResolution,
) -> str | None:
    """判斷第二層 embedding 結果是否與 mention 訊號衝突。

    參數：
    - `top_label`：embedding top-1 label。
    - `mention_resolution`：文件 mention 解析結果。

    回傳：
    - `str | None`：若存在衝突則回傳原因。
    """

    resolved_count = len(mention_resolution.resolved_document_ids)
    if resolved_count >= 2 and top_label != SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME:
        return "multi_document_scope_conflict"
    if resolved_count == 1 and top_label == SUMMARY_STRATEGY_MULTI_DOCUMENT_THEME:
        return "single_document_scope_conflict"
    return None


def _match_trigger_phrases(
    *,
    lowered_query: str,
    language: str,
    zh_tw_phrases: tuple[str, ...],
    en_phrases: tuple[str, ...],
) -> tuple[str, ...]:
    """依 query language 回傳命中的 trigger phrases。

    參數：
    - `lowered_query`：已 casefold 的 query。
    - `language`：query 語言。
    - `zh_tw_phrases`：中文 trigger phrases。
    - `en_phrases`：英文 trigger phrases。

    回傳：
    - `tuple[str, ...]`：依命中順序去重後的 trigger phrases。
    """

    candidates: list[str] = []
    if language in {"zh-TW", "mixed"}:
        candidates.extend(zh_tw_phrases)
    if language in {"en", "mixed"}:
        candidates.extend(en_phrases)

    matches: list[str] = []
    seen: set[str] = set()
    for phrase in candidates:
        if phrase in seen:
            continue
        if _query_contains_phrase(lowered_query=lowered_query, phrase=phrase):
            seen.add(phrase)
            matches.append(phrase)
    return tuple(matches)


def _query_contains_phrase(*, lowered_query: str, phrase: str) -> bool:
    """判斷 query 是否包含指定 trigger phrase。

    參數：
    - `lowered_query`：已 casefold 的 query。
    - `phrase`：待檢查的 phrase。

    回傳：
    - `bool`：若 query 含有該 phrase 則回傳真值。
    """

    if re.search(r"[A-Za-z]", phrase):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(phrase.casefold())}(?![A-Za-z0-9])")
        return bool(pattern.search(lowered_query))
    return phrase.casefold() in lowered_query


def _score_rule_confidence(*, match_count: int) -> float:
    """依命中規則數量估計簡單 confidence。

    參數：
    - `match_count`：命中的規則數量。

    回傳：
    - `float`：簡單估計的 confidence。
    """

    if match_count >= 2:
        return 0.92
    if match_count == 1:
        return 0.84
    return 0.0


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """計算兩個向量的 cosine similarity。

    參數：
    - `left`：左側向量。
    - `right`：右側向量。

    回傳：
    - `float`：cosine similarity；若任一向量長度為零則回傳 `0.0`。
    """

    if len(left) != len(right):
        raise ValueError("embedding 長度不一致，無法計算 cosine similarity。")
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _similarity_to_confidence(score: float) -> float:
    """將 cosine similarity 轉成 0 到 1 的 confidence。

    參數：
    - `score`：cosine similarity。

    回傳：
    - `float`：0 到 1 的 confidence。
    """

    return max(0.0, min(1.0, (score + 1.0) / 2.0))


def _normalize_llm_confidence(value: object) -> float:
    """將 LLM fallback 的 confidence 欄位正規化到 0 到 1。

    參數：
    - `value`：LLM 回傳的 confidence 欄位。

    回傳：
    - `float`：正規化後的 confidence。
    """

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.7
    return max(0.0, min(1.0, confidence))


def _is_retryable_llm_routing_error(*, exc: Exception) -> bool:
    """判斷 LLM routing fallback 錯誤是否值得重試。

    參數：
    - `exc`：單次 fallback 錯誤。

    回傳：
    - `bool`：若屬於暫時性錯誤則回傳真值。
    """

    message = str(exc).casefold()
    if "timeout" in message or "timed out" in message:
        return True
    if "rate limit" in message or "429" in message:
        return True
    if "could not parse the json body" in message:
        return True
    return False


def _empty_document_mention_resolution() -> DocumentMentionResolution:
    """建立空的 document mention 解析結果。

    參數：
    - 無。

    回傳：
    - `DocumentMentionResolution`：空的 mention 解析結果。
    """

    return DocumentMentionResolution(
        resolved_document_ids=(),
        source=DOCUMENT_MENTION_SOURCE_NONE,
        confidence=0.0,
        candidates=(),
    )
