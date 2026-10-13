"""Retrieval runtime 各階段共用的資料結構。"""

from dataclasses import dataclass

from app.db.models import ChunkStructureKind, Document, DocumentChunk, EvaluationQueryType


@dataclass(slots=True)
class RetrievalCandidate:
    """內部 retrieval candidate 結構。"""

    # 候選所屬文件識別碼。
    document_id: str
    # 候選 child chunk 識別碼。
    chunk_id: str
    # 候選所屬 parent chunk 識別碼。
    parent_chunk_id: str | None
    # 候選內容結構型別。
    structure_kind: ChunkStructureKind
    # 候選所屬 heading。
    heading: str | None
    # 候選內容。
    content: str
    # 候選在全文中的起始 offset。
    start_offset: int
    # 候選在全文中的結束 offset。
    end_offset: int
    # 候選來源，可能為 vector、fts 或 hybrid。
    source: str
    # vector recall 排名。
    vector_rank: int | None
    # FTS recall 排名。
    fts_rank: int | None
    # RRF 後排名。
    rrf_rank: int
    # RRF 分數。
    rrf_score: float
    # rerank 後排名。
    rerank_rank: int | None
    # rerank 分數。
    rerank_score: float | None
    # 是否已套用 rerank。
    rerank_applied: bool
    # rerank fallback 原因。
    rerank_fallback_reason: str | None


@dataclass(slots=True)
class RetrievalTraceEntry:
    """單一 retrieval candidate 的 trace metadata。"""

    # 候選 child chunk 識別碼。
    chunk_id: str
    # 候選來源。
    source: str
    # vector recall 排名。
    vector_rank: int | None
    # FTS recall 排名。
    fts_rank: int | None
    # RRF 後排名。
    rrf_rank: int
    # RRF 分數。
    rrf_score: float
    # rerank 後排名。
    rerank_rank: int | None
    # rerank 分數。
    rerank_score: float | None
    # 是否已套用 rerank。
    rerank_applied: bool
    # rerank fallback 原因。
    rerank_fallback_reason: str | None


@dataclass(slots=True)
class DocumentRecallTraceEntry:
    """單一 document recall candidate 的 trace metadata。"""

    # 文件識別碼。
    document_id: str
    # 文件名稱。
    file_name: str
    # vector recall 排名。
    vector_rank: int | None
    # FTS recall 排名。
    fts_rank: int | None
    # RRF 後排名。
    rrf_rank: int
    # RRF 分數。
    rrf_score: float


@dataclass(slots=True)
class DocumentRecallTrace:
    """第一階段 document recall 的 trace metadata。"""

    # 是否套用 document recall。
    applied: bool
    # 使用的 document recall 策略名稱。
    strategy: str
    # document recall top-k。
    top_k: int
    # 被選中的文件識別碼。
    selected_document_ids: list[str]
    # 被捨棄的文件識別碼。
    dropped_document_ids: list[str]
    # document recall 候選 trace。
    candidates: list[DocumentRecallTraceEntry]


@dataclass(slots=True)
class SectionRecallTraceEntry:
    """單一 section recall candidate 的 trace metadata。"""

    # parent chunk 識別碼。
    parent_chunk_id: str
    # 文件識別碼。
    document_id: str
    # heading。
    heading: str | None
    # heading path。
    heading_path: str | None
    # section path-aware 文字。
    section_path_text: str | None
    # vector recall 排名。
    vector_rank: int | None
    # FTS recall 排名。
    fts_rank: int | None
    # RRF 後排名。
    rrf_rank: int
    # RRF 分數。
    rrf_score: float


@dataclass(slots=True)
class SectionRecallTrace:
    """section recall trace metadata。"""

    # 是否套用 section recall。
    applied: bool
    # 使用的 section recall 策略名稱。
    strategy: str
    # section recall top-k。
    top_k: int
    # 被選中的 parent chunk 識別碼。
    selected_parent_ids: list[str]
    # 被捨棄的 parent chunk 識別碼。
    dropped_parent_ids: list[str]
    # section recall 候選 trace。
    candidates: list[SectionRecallTraceEntry]


@dataclass(slots=True)
class RetrievalTrace:
    """單次 retrieval 的 trace metadata。"""

    # 使用者查詢。
    query: str
    # vector recall top-k。
    vector_top_k: int
    # FTS recall top-k。
    fts_top_k: int
    # 最大候選數。
    max_candidates: int
    # rerank top-n。
    rerank_top_n: int
    # 最終候選 trace。
    candidates: list[RetrievalTraceEntry]
    # query type。
    query_type: str = EvaluationQueryType.fact_lookup.value
    # query type 語言。
    query_type_language: str = "en"
    # query type 來源。
    query_type_source: str = "fallback"
    # query type 信心分數。
    query_type_confidence: float = 0.0
    # query type 命中的規則名稱。
    query_type_matched_rules: list[str] | None = None
    # query type 規則命中細節。
    query_type_rule_hits: list[dict[str, object]] | None = None
    # query type embedding 分數。
    query_type_embedding_scores: list[dict[str, object]] | None = None
    # query type 第一候選 label。
    query_type_top_label: str | None = None
    # query type 第二候選 label。
    query_type_runner_up_label: str | None = None
    # query type embedding margin。
    query_type_embedding_margin: float = 0.0
    # query type 是否使用 fallback。
    query_type_fallback_used: bool = False
    # query type fallback 原因。
    query_type_fallback_reason: str | None = None
    # summary scope。
    summary_scope: str | None = None
    # summary strategy。
    summary_strategy: str | None = None
    # summary strategy 來源。
    summary_strategy_source: str = "not_applicable"
    # summary strategy 信心分數。
    summary_strategy_confidence: float = 0.0
    # summary strategy 規則命中細節。
    summary_strategy_rule_hits: list[dict[str, object]] | None = None
    # summary strategy embedding 分數。
    summary_strategy_embedding_scores: list[dict[str, object]] | None = None
    # summary strategy 第一候選 label。
    summary_strategy_top_label: str | None = None
    # summary strategy 第二候選 label。
    summary_strategy_runner_up_label: str | None = None
    # summary strategy embedding margin。
    summary_strategy_embedding_margin: float = 0.0
    # summary strategy 是否使用 fallback。
    summary_strategy_fallback_used: bool = False
    # summary strategy fallback 原因。
    summary_strategy_fallback_reason: str | None = None
    # 文件範圍。
    document_scope: str = "area"
    # 已解析文件識別碼。
    resolved_document_ids: list[str] | None = None
    # 文件 mention 來源。
    document_mention_source: str = "none"
    # 文件 mention 信心分數。
    document_mention_confidence: float = 0.0
    # 文件 mention 候選。
    document_mention_candidates: list[dict[str, object]] | None = None
    # 選中的 runtime profile。
    selected_profile: str = ""
    # profile 設定快照。
    profile_settings: dict[str, object] | None = None
    # 是否套用 selection。
    selection_applied: bool = False
    # selection 策略。
    selection_strategy: str = "disabled"
    # selection 後文件數。
    selected_document_count: int = 0
    # selection 後 parent 數。
    selected_parent_count: int = 0
    # selection 後文件識別碼。
    selected_document_ids: list[str] | None = None
    # selection 後 parent 識別碼。
    selected_parent_ids: list[str] | None = None
    # diversity 捨棄細節。
    dropped_by_diversity: list[dict[str, object]] | None = None
    # retrieval fallback 原因。
    fallback_reason: str | None = None


@dataclass(slots=True)
class RetrievalResult:
    """Internal retrieval service 的回傳結構。"""

    # 最終候選。
    candidates: list[RetrievalCandidate]
    # retrieval trace。
    trace: RetrievalTrace


@dataclass(slots=True)
class RankedChunkMatch:
    """合併與 rerank 前使用的中間結構。"""

    # 候選 child chunk。
    chunk: DocumentChunk
    # vector recall 排名。
    vector_rank: int | None = None
    # FTS recall 排名。
    fts_rank: int | None = None
    # RRF 後排名。
    rrf_rank: int | None = None
    # RRF 分數。
    rrf_score: float = 0.0
    # rerank 後排名。
    rerank_rank: int | None = None
    # rerank 分數。
    rerank_score: float | None = None
    # 是否已套用 rerank。
    rerank_applied: bool = False
    # rerank fallback 原因。
    rerank_fallback_reason: str | None = None


@dataclass(slots=True)
class DocumentRecallMatch:
    """document-level recall 使用的中間結構。"""

    # 候選文件。
    document: Document
    # vector recall 排名。
    vector_rank: int | None = None
    # FTS recall 排名。
    fts_rank: int | None = None
    # RRF 後排名。
    rrf_rank: int | None = None
    # RRF 分數。
    rrf_score: float = 0.0


@dataclass(slots=True)
class DocumentRecallResult:
    """第一階段 document recall 的選文件結果。"""

    # 被選中的文件識別碼。
    selected_document_ids: tuple[str, ...]
    # document recall trace。
    trace: DocumentRecallTrace


@dataclass(slots=True)
class SectionRecallMatch:
    """section-level recall 使用的中間結構。"""

    # 候選 parent chunk。
    parent_chunk: DocumentChunk
    # vector recall 排名。
    vector_rank: int | None = None
    # FTS recall 排名。
    fts_rank: int | None = None
    # RRF 後排名。
    rrf_rank: int | None = None
    # RRF 分數。
    rrf_score: float = 0.0


@dataclass(slots=True)
class SectionRecallResult:
    """section-level recall 結果。"""

    # 被選中的 parent chunk 識別碼。
    selected_parent_ids: tuple[str, ...]
    # section recall trace。
    trace: SectionRecallTrace
