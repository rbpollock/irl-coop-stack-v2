"""Query-aware retrieval routing 測試。"""

from uuid import uuid4

import sys
from types import SimpleNamespace

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Area, AreaUserRole, Document, DocumentStatus, EvaluationQueryType, Role
from app.services.document_mentions import DocumentMentionCandidate, DocumentMentionResolution
from app.services.retrieval_routing import (
    QUERY_ROUTING_SOURCE_EMBEDDING,
    QUERY_ROUTING_SOURCE_EXPLICIT,
    QUERY_ROUTING_SOURCE_LLM_FALLBACK,
    QUERY_ROUTING_SOURCE_RULE,
    RoutingClassifierDecision,
    RoutingEmbeddingScore,
    RoutingRuleHit,
    build_query_routing_decision,
    classify_query_type,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def _routing_settings(**overrides) -> AppSettings:
    """建立不依賴本機 `.env` 的 routing 測試設定。

    參數：
    - `**overrides`：要覆寫的設定欄位。

    回傳：
    - `AppSettings`：供 routing 測試使用的設定物件。
    """

    payload = {
        "_env_file": None,
        "EMBEDDING_PROVIDER": "deterministic",
        "OPENAI_API_KEY": "",
    }
    payload.update(overrides)
    return AppSettings(**payload)


def test_classifier_detects_document_summary_in_traditional_chinese() -> None:
    """中文摘要 cue 應由 rule 命中 `document_summary`。"""

    result = classify_query_type(
        query="請幫我摘要這份政策的重點",
        settings=_routing_settings(),
    )

    assert result.query_type == EvaluationQueryType.document_summary
    assert result.language == "zh-TW"
    assert result.source == QUERY_ROUTING_SOURCE_RULE
    assert "摘要" in result.matched_rules
    assert result.rule_hits


def test_classifier_detects_cross_document_compare_in_english() -> None:
    """英文 compare cue 應由 rule 命中 `cross_document_compare`。"""

    result = classify_query_type(
        query="Compare the onboarding policy versus the security policy",
        settings=_routing_settings(),
    )

    assert result.query_type == EvaluationQueryType.cross_document_compare
    assert result.language == "en"
    assert result.source == QUERY_ROUTING_SOURCE_RULE
    assert any(rule in result.matched_rules for rule in ("compare", "versus"))


def test_classifier_uses_embedding_when_high_confidence(monkeypatch) -> None:
    """高信心 embedding 應直接決定 `task_type`。"""

    def fake_classify_labels_with_embeddings(**kwargs) -> RoutingClassifierDecision:
        """回傳固定高信心 embedding 決策。

        參數：
        - `**kwargs`：classifier helper 輸入。

        回傳：
        - `RoutingClassifierDecision`：固定的 embedding 決策。
        """

        del kwargs
        return RoutingClassifierDecision(
            label=EvaluationQueryType.fact_lookup.value,
            confidence=0.91,
            source=QUERY_ROUTING_SOURCE_EMBEDDING,
            rule_hits=(),
            embedding_scores=(
                RoutingEmbeddingScore(label=EvaluationQueryType.fact_lookup.value, score=0.82),
                RoutingEmbeddingScore(label=EvaluationQueryType.document_summary.value, score=0.68),
                RoutingEmbeddingScore(label=EvaluationQueryType.cross_document_compare.value, score=0.6),
            ),
            top_label=EvaluationQueryType.fact_lookup.value,
            runner_up_label=EvaluationQueryType.document_summary.value,
            margin=0.14,
            fallback_used=False,
            fallback_reason=None,
        )

    monkeypatch.setattr(
        "app.services.retrieval_routing._classify_labels_with_embeddings",
        fake_classify_labels_with_embeddings,
    )

    result = classify_query_type(
        query="保單申請資格是什麼",
        settings=_routing_settings(),
    )

    assert result.query_type == EvaluationQueryType.fact_lookup
    assert result.source == QUERY_ROUTING_SOURCE_EMBEDDING
    assert result.fallback_used is False
    assert result.margin == 0.14


def test_classifier_uses_llm_fallback_when_embedding_low_confidence(monkeypatch) -> None:
    """embedding 低信心時應由 LLM fallback 決定第一層 `task_type`。"""

    def fake_classify_labels_with_embeddings(**kwargs) -> RoutingClassifierDecision:
        """回傳固定低信心 embedding 決策。

        參數：
        - `**kwargs`：classifier helper 輸入。

        回傳：
        - `RoutingClassifierDecision`：固定的低信心 embedding 決策。
        """

        del kwargs
        return RoutingClassifierDecision(
            label=EvaluationQueryType.document_summary.value,
            confidence=0.56,
            source=QUERY_ROUTING_SOURCE_EMBEDDING,
            rule_hits=(),
            embedding_scores=(
                RoutingEmbeddingScore(label=EvaluationQueryType.document_summary.value, score=0.12),
                RoutingEmbeddingScore(label=EvaluationQueryType.fact_lookup.value, score=0.1),
            ),
            top_label=EvaluationQueryType.document_summary.value,
            runner_up_label=EvaluationQueryType.fact_lookup.value,
            margin=0.02,
            fallback_used=False,
            fallback_reason=None,
        )

    def fake_run_llm_label_fallback(**kwargs) -> RoutingClassifierDecision:
        """回傳固定的 LLM fallback 決策。

        參數：
        - `**kwargs`：LLM fallback helper 輸入。

        回傳：
        - `RoutingClassifierDecision`：固定 fallback 決策。
        """

        del kwargs
        return RoutingClassifierDecision(
            label=EvaluationQueryType.fact_lookup.value,
            confidence=0.88,
            source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
            rule_hits=(),
            embedding_scores=(),
            top_label=EvaluationQueryType.fact_lookup.value,
            runner_up_label=None,
            margin=0.0,
            fallback_used=True,
            fallback_reason="llm_fallback",
        )

    monkeypatch.setattr(
        "app.services.retrieval_routing._classify_labels_with_embeddings",
        fake_classify_labels_with_embeddings,
    )
    monkeypatch.setattr(
        "app.services.retrieval_routing._run_llm_label_fallback",
        fake_run_llm_label_fallback,
    )

    result = classify_query_type(
        query="保單申請資格是什麼",
        settings=_routing_settings(OPENAI_API_KEY="test-key"),
    )

    assert result.query_type == EvaluationQueryType.fact_lookup
    assert result.source == QUERY_ROUTING_SOURCE_LLM_FALLBACK
    assert result.fallback_used is True
    assert result.fallback_reason == "low_embedding_confidence"


def test_build_query_routing_decision_respects_explicit_query_type() -> None:
    """明示題型時應直接採用該題型。"""

    settings = _routing_settings()

    decision = build_query_routing_decision(
        settings=settings,
        query="請整理這份文件",
        explicit_query_type=EvaluationQueryType.cross_document_compare,
    )

    assert decision.query_type == EvaluationQueryType.cross_document_compare
    assert decision.source == QUERY_ROUTING_SOURCE_EXPLICIT
    assert decision.selected_profile == "cross_document_compare_diversified_v1"


def test_build_query_routing_decision_keeps_document_scope_for_fact_lookup(db_session, monkeypatch) -> None:
    """多文件 scope 不應被第一層 fact lookup 題型丟棄。"""

    area = Area(id=_uuid(), name="Fact Lookup Scope Area")
    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="alpha-policy.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/alpha-policy.md",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="beta-manual.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/beta-manual.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            first_document,
            second_document,
        ]
    )
    db_session.commit()

    def fake_classify_labels_with_embeddings(**kwargs) -> RoutingClassifierDecision:
        """回傳固定高信心 fact lookup，驗證 scope 與 task type 正交保留。"""

        del kwargs
        return RoutingClassifierDecision(
            label=EvaluationQueryType.fact_lookup.value,
            confidence=0.91,
            source=QUERY_ROUTING_SOURCE_EMBEDDING,
            rule_hits=(),
            embedding_scores=(
                RoutingEmbeddingScore(label=EvaluationQueryType.fact_lookup.value, score=0.82),
                RoutingEmbeddingScore(label=EvaluationQueryType.document_summary.value, score=0.68),
                RoutingEmbeddingScore(label=EvaluationQueryType.cross_document_compare.value, score=0.6),
            ),
            top_label=EvaluationQueryType.fact_lookup.value,
            runner_up_label=EvaluationQueryType.document_summary.value,
            margin=0.14,
            fallback_used=False,
            fallback_reason=None,
        )

    monkeypatch.setattr(
        "app.services.retrieval_routing._classify_labels_with_embeddings",
        fake_classify_labels_with_embeddings,
    )

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="What are the deadlines in alpha policy and beta manual?",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.query_type == EvaluationQueryType.fact_lookup
    assert decision.source == QUERY_ROUTING_SOURCE_EMBEDDING
    assert decision.document_scope == "multi_document"
    assert set(decision.resolved_document_ids) == {first_document.id, second_document.id}
    assert decision.summary_scope is None
    assert decision.selected_profile == "fact_lookup_precision_v1"


def test_build_query_routing_decision_promotes_compare_query_to_multi_document_scope(monkeypatch) -> None:
    """compare 題若第二候選達中等信心，不應被單文件 mention 壓成 single-document。"""

    first_document_id = _uuid()
    second_document_id = _uuid()

    monkeypatch.setattr(
        "app.services.retrieval_routing.resolve_document_mentions",
        lambda **kwargs: DocumentMentionResolution(
            resolved_document_ids=(first_document_id,),
            source="query_contains_unique_suffix_phrase",
            confidence=0.94,
            candidates=(
                DocumentMentionCandidate(
                    document_id=first_document_id,
                    file_name="benefits-overview.mixed.md",
                    score=0.94,
                    match_signals=("query_contains_unique_suffix_phrase",),
                ),
                DocumentMentionCandidate(
                    document_id=second_document_id,
                    file_name="claims-guide.zh-TW.md",
                    score=0.60,
                    match_signals=("token_overlap", "ordered_token_coverage"),
                ),
            ),
        ),
    )

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="請比較 claims guide 與 Benefits Overview 對理賠時程的說明",
        explicit_query_type=EvaluationQueryType.cross_document_compare,
    )

    assert decision.document_scope == "multi_document"
    assert decision.resolved_document_ids == (first_document_id, second_document_id)


def test_build_query_routing_decision_promotes_multi_document_summary_query_from_candidates(monkeypatch) -> None:
    """明顯 multi-doc summary 語句不應被高分單文件 mention 蓋掉第二候選。"""

    first_document_id = _uuid()
    second_document_id = _uuid()

    monkeypatch.setattr(
        "app.services.retrieval_routing.resolve_document_mentions",
        lambda **kwargs: DocumentMentionResolution(
            resolved_document_ids=(first_document_id,),
            source="query_contains_canonical_title",
            confidence=0.96,
            candidates=(
                DocumentMentionCandidate(
                    document_id=first_document_id,
                    file_name="travel-policy.md",
                    score=0.96,
                    match_signals=("query_contains_canonical_title",),
                ),
                DocumentMentionCandidate(
                    document_id=second_document_id,
                    file_name="claims-guide.zh-TW.md",
                    score=0.60,
                    match_signals=("token_overlap", "ordered_token_coverage"),
                ),
            ),
        ),
    )

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="Summarize approval and deadline rules across the travel policy and the claims guide.",
        explicit_query_type=EvaluationQueryType.document_summary,
    )

    assert decision.document_scope == "multi_document"
    assert decision.resolved_document_ids == (first_document_id, second_document_id)


def test_build_query_routing_decision_keeps_single_document_scope_without_multi_document_cue(monkeypatch) -> None:
    """一般單文件摘要題不應因第二候選中等分數而自動升成 multi-document。"""

    first_document_id = _uuid()
    second_document_id = _uuid()

    monkeypatch.setattr(
        "app.services.retrieval_routing.resolve_document_mentions",
        lambda **kwargs: DocumentMentionResolution(
            resolved_document_ids=(first_document_id,),
            source="query_contains_canonical_title",
            confidence=0.96,
            candidates=(
                DocumentMentionCandidate(
                    document_id=first_document_id,
                    file_name="travel-policy.md",
                    score=0.96,
                    match_signals=("query_contains_canonical_title",),
                ),
                DocumentMentionCandidate(
                    document_id=second_document_id,
                    file_name="claims-guide.zh-TW.md",
                    score=0.60,
                    match_signals=("token_overlap", "ordered_token_coverage"),
                ),
            ),
        ),
    )

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="Summarize the travel policy.",
        explicit_query_type=EvaluationQueryType.document_summary,
    )

    assert decision.document_scope == "single_document"
    assert decision.resolved_document_ids == (first_document_id,)


def test_build_query_routing_decision_accepts_orthogonal_task_type_and_scope_hints(db_session) -> None:
    """task type 與 document scope hint 應可正交提供，且不直接指定 document ids。"""

    area = Area(id=_uuid(), name="Orthogonal Routing Area")
    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="claims-guide.zh-TW.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/claims-guide.zh-TW.md",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-overview.mixed.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/benefits-overview.mixed.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            first_document,
            second_document,
        ]
    )
    db_session.commit()

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="Summarize what the claims guide and Benefits Overview say about claims-related timelines.",
        explicit_query_type=EvaluationQueryType.document_summary,
        explicit_document_scope="multi_document",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.query_type == EvaluationQueryType.document_summary
    assert decision.document_scope == "multi_document"
    assert decision.summary_strategy == "multi_document_theme"
    assert decision.summary_scope == "multi_document"
    assert decision.selected_profile == "document_summary_multi_document_diversified_v1"
    assert decision.resolved_document_ids == (second_document.id, first_document.id)


def test_build_query_routing_decision_uses_section_focused_for_single_document_section_query(db_session) -> None:
    """單文件摘要且帶 section cue 時應選 `section_focused`。"""

    area = Area(id=_uuid(), name="Routing Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="employee-handbook.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/employee-handbook.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader), document])
    db_session.commit()

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="請摘要 employee handbook 關於 leave policy 的章節",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.summary_scope == "single_document"
    assert decision.summary_strategy == "section_focused"
    assert decision.summary_strategy_source == QUERY_ROUTING_SOURCE_RULE
    assert decision.summary_strategy_rule_hits


def test_build_query_routing_decision_uses_document_overview_for_single_document_summary(db_session) -> None:
    """單文件摘要且未命中 section cue 時應選 `document_overview`。"""

    area = Area(id=_uuid(), name="Routing Overview Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-policy.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/benefits-policy.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader), document])
    db_session.commit()

    decision = build_query_routing_decision(
        settings=_routing_settings(),
        query="請摘要 benefits policy",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.summary_scope == "single_document"
    assert decision.summary_strategy == "document_overview"
    assert decision.summary_strategy_source == "fallback"


def test_build_query_routing_decision_llm_fallback_can_override_single_document_scope(db_session, monkeypatch) -> None:
    """低信心時 LLM fallback 應可把單文件誤判拉回 multi-document theme。"""

    area = Area(id=_uuid(), name="Routing LLM Override Area")
    alpha = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="claims-guide.zh-TW.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/claims-guide.zh-TW.md",
        status=DocumentStatus.ready,
    )
    beta = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="benefits-overview.mixed.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="routing/benefits-overview.mixed.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            alpha,
            beta,
        ]
    )
    db_session.commit()

    def fake_classify_summary_strategy_with_embeddings(**kwargs) -> RoutingClassifierDecision:
        """回傳會與 scope 衝突的低信心 embedding 決策。"""

        del kwargs
        return RoutingClassifierDecision(
            label="section_focused",
            confidence=0.58,
            source=QUERY_ROUTING_SOURCE_EMBEDDING,
            rule_hits=(),
            embedding_scores=(
                RoutingEmbeddingScore(label="section_focused", score=0.13),
                RoutingEmbeddingScore(label="multi_document_theme", score=0.12),
            ),
            top_label="section_focused",
            runner_up_label="multi_document_theme",
            margin=0.01,
            fallback_used=False,
            fallback_reason=None,
        )

    def fake_run_llm_label_fallback(**kwargs) -> RoutingClassifierDecision:
        """回傳固定的 multi-document theme fallback 決策。"""

        del kwargs
        return RoutingClassifierDecision(
            label="multi_document_theme",
            confidence=0.86,
            source=QUERY_ROUTING_SOURCE_LLM_FALLBACK,
            rule_hits=(),
            embedding_scores=(),
            top_label="multi_document_theme",
            runner_up_label=None,
            margin=0.0,
            fallback_used=True,
            fallback_reason="scope_conflict",
        )

    monkeypatch.setattr(
        "app.services.retrieval_routing.classify_summary_strategy_with_embeddings",
        fake_classify_summary_strategy_with_embeddings,
    )
    monkeypatch.setattr(
        "app.services.retrieval_routing._run_llm_label_fallback",
        fake_run_llm_label_fallback,
    )

    decision = build_query_routing_decision(
        settings=_routing_settings(OPENAI_API_KEY="test-key"),
        query="Summarize what the claims guide and Benefits Overview say regarding claims-related timelines.",
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=()),
        area_id=area.id,
    )

    assert decision.summary_strategy == "multi_document_theme"
    assert decision.summary_strategy_source == QUERY_ROUTING_SOURCE_RULE
    assert decision.summary_scope == "multi_document"
    assert decision.selected_profile == "document_summary_multi_document_diversified_v1"


def test_task_type_llm_label_fallback_uses_minimal_reasoning_effort(monkeypatch) -> None:
    """第一層 task_type LLM fallback 應固定使用最小 reasoning effort。"""

    captured_create_kwargs: list[dict[str, object]] = []

    class FakeCompletions:
        """模擬 OpenAI chat completions client。"""

        def create(self, **kwargs):
            """記錄 create 參數並回傳固定 JSON。

            參數：
            - `**kwargs`：chat completion 參數。

            回傳：
            - `SimpleNamespace`：固定 completion 回應。
            """

            captured_create_kwargs.append(dict(kwargs))
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"label":"fact_lookup","confidence":0.83,"reason":"minimal-test"}'))]
            )

    class FakeOpenAI:
        """模擬 OpenAI client。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 client。

            參數：
            - `**kwargs`：OpenAI client 參數。

            回傳：
            - `None`：僅建立 chat namespace。
            """

            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    from app.services.retrieval_routing import _run_llm_label_fallback

    decision = _run_llm_label_fallback(
        settings=_routing_settings(OPENAI_API_KEY="test-key"),
        classifier_name="task_type",
        query="保單申請資格是什麼",
        language="zh-TW",
        label_options=("fact_lookup", "document_summary", "cross_document_compare"),
        label_descriptions={
            "fact_lookup": "fact",
            "document_summary": "summary",
            "cross_document_compare": "compare",
        },
        llm_context={"document_mention_candidates": []},
    )

    assert decision is not None
    assert decision.label == "fact_lookup"
    assert captured_create_kwargs[0]["reasoning_effort"] == "minimal"


def test_summary_strategy_llm_label_fallback_uses_low_reasoning_effort(monkeypatch) -> None:
    """第二層 summary_strategy LLM fallback 應固定使用低階 reasoning effort。"""

    captured_create_kwargs: list[dict[str, object]] = []

    class FakeCompletions:
        """模擬 OpenAI chat completions client。"""

        def create(self, **kwargs):
            """記錄 create 參數並回傳固定 JSON。

            參數：
            - `**kwargs`：chat completion 參數。

            回傳：
            - `SimpleNamespace`：固定 completion 回應。
            """

            captured_create_kwargs.append(dict(kwargs))
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"label":"document_overview","confidence":0.83,"reason":"low-test"}'))]
            )

    class FakeOpenAI:
        """模擬 OpenAI client。"""

        def __init__(self, **kwargs) -> None:
            """初始化假 client。

            參數：
            - `**kwargs`：OpenAI client 參數。

            回傳：
            - `None`：僅建立 chat namespace。
            """

            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    from app.services.retrieval_routing import _run_llm_label_fallback

    decision = _run_llm_label_fallback(
        settings=_routing_settings(OPENAI_API_KEY="test-key"),
        classifier_name="summary_strategy",
        query="Summarize the key points of Benefits Overview, including the Chinese onboarding note.",
        language="en",
        label_options=("document_overview", "section_focused", "multi_document_theme"),
        label_descriptions={
            "document_overview": "overview",
            "section_focused": "section",
            "multi_document_theme": "theme",
        },
        llm_context={"document_mention_candidates": []},
    )

    assert decision is not None
    assert decision.label == "document_overview"
    assert captured_create_kwargs[0]["reasoning_effort"] == "low"
