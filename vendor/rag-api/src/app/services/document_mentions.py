"""文件名稱提及解析與 document summary scope 判定 service。"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.verifier import CurrentPrincipal
from app.db.models import Document, DocumentStatus, EvaluationQueryType
from app.services.access import require_area_access
from app.services.retrieval_query import extract_query_tokens, normalize_query_text


# basename 完整命中的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_EXACT_BASENAME = "exact_basename_match"
# canonical title 完整命中的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_EXACT_CANONICAL = "exact_canonical_match"
# basename 包含 query 的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_BASENAME_CONTAINS_QUERY = "basename_contains_query"
# query 包含 basename 的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_BASENAME = "query_contains_basename"
# query 含有文件 canonical title 的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_CANONICAL = "query_contains_canonical_title"
# query 含有唯一 suffix 片語的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_UNIQUE_SUFFIX = "query_contains_unique_suffix_phrase"
# token overlap 的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_TOKEN_OVERLAP = "token_overlap"
# token 依序覆蓋的 signal 名稱。
DOCUMENT_MENTION_SIGNAL_ORDERED_TOKEN_COVERAGE = "ordered_token_coverage"
# 無有效命中的 source 名稱。
DOCUMENT_MENTION_SOURCE_NONE = "none"

# 將常見分隔符統一轉成空白。
_SEPARATOR_PATTERN = re.compile(r"[_\-.\/()\[\]{}]+")
# 壓縮多餘空白。
_WHITESPACE_PATTERN = re.compile(r"\s+")
# CJK 字元偵測。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# 常見版次 / 日期尾碼。
_TRAILING_VERSION_PATTERN = re.compile(
    r"\s*(?:\(\s*(?:\d{2,4}年\d{1,2}月版|\d{2,4}年版|v\d+|V\d+|\d{4}版)\s*\)|(?:v|V)\d+|\d{4}版)\s*$"
)
# 文件摘要 / 比較指令前綴。
_INSTRUCTION_PREFIX_PATTERN = re.compile(
    r"^\s*(?:請|幫我|麻煩|請幫我)?\s*(?:摘要(?:一下)?|總結(?:一下)?|整理(?:一下)?|概述(?:一下)?|比較(?:一下)?|compare|summarize|summary of|overview of)\s*",
    re.IGNORECASE,
)

# 過於通用、不可單獨作為文件判定依據的詞。
GENERIC_DOCUMENT_TERMS = frozenset(
    {
        "policy",
        "policies",
        "doc",
        "docs",
        "document",
        "documents",
        "file",
        "files",
        "guide",
        "guides",
        "manual",
        "report",
        "reports",
        "summary",
        "version",
        "v1",
        "v2",
        "v3",
        "文件",
        "檔案",
        "文檔",
        "政策",
        "規範",
        "規格",
        "手冊",
        "流程",
        "報告",
        "摘要",
        "版本",
    }
)

# 唯一命中單一文件所需的最低分數。
SINGLE_DOCUMENT_CONFIDENCE_THRESHOLD = 0.8
# 進入高信心多文件集合的最低分數。
MULTI_DOCUMENT_CONFIDENCE_THRESHOLD = 0.8
# 單一文件與第二名至少要拉開的安全分差。
SINGLE_DOCUMENT_MARGIN_THRESHOLD = 0.12


@dataclass(frozen=True, slots=True)
class DocumentMentionCandidate:
    """單一文件名稱解析候選。"""

    document_id: str
    file_name: str
    score: float
    match_signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentMentionResolution:
    """文件名稱提及解析結果。"""

    resolved_document_ids: tuple[str, ...]
    source: str
    confidence: float
    candidates: tuple[DocumentMentionCandidate, ...]


@dataclass(frozen=True, slots=True)
class _CanonicalDocumentName:
    """單一文件名稱的 canonicalization 結果。"""

    document_id: str
    file_name: str
    basename: str
    canonical_title: str
    title_segments: tuple[str, ...]
    tokens: tuple[str, ...]


def normalize_document_name(*, file_name: str) -> str:
    """將文件名稱正規化為可供 mention matching 使用的文字。

    參數：
    - `file_name`：原始文件名稱。

    回傳：
    - `str`：去副檔名、分隔符正規化後的 basename。
    """

    basename = _strip_trailing_version_suffix(text=Path(file_name).stem)
    separator_normalized = _SEPARATOR_PATTERN.sub(" ", basename.casefold())
    return _WHITESPACE_PATTERN.sub(" ", separator_normalized).strip()


def resolve_document_mentions(
    *,
    session: Session | None,
    principal: CurrentPrincipal | None,
    area_id: str | None,
    query: str,
) -> DocumentMentionResolution:
    """解析 query 是否高信心提及某一份或多份已授權文件。

    參數：
    - `session`：目前資料庫 session；缺少時直接回空解析結果。
    - `principal`：目前已驗證使用者；缺少時直接回空解析結果。
    - `area_id`：目標 area；缺少時直接回空解析結果。
    - `query`：使用者原始問題。

    回傳：
    - `DocumentMentionResolution`：解析出的高信心文件集合與 debug 候選摘要。
    """

    if session is None or principal is None or area_id is None:
        return DocumentMentionResolution(
            resolved_document_ids=(),
            source=DOCUMENT_MENTION_SOURCE_NONE,
            confidence=0.0,
            candidates=(),
        )

    require_area_access(session=session, principal=principal, area_id=area_id)

    normalized_query = normalize_reference_query(query=query)
    if not normalized_query:
        return DocumentMentionResolution(
            resolved_document_ids=(),
            source=DOCUMENT_MENTION_SOURCE_NONE,
            confidence=0.0,
            candidates=(),
        )

    rows = session.execute(
        select(Document.id, Document.file_name)
        .where(
            Document.area_id == area_id,
            Document.status == DocumentStatus.ready,
        )
        .order_by(Document.file_name.asc())
    ).all()

    canonical_documents = [
        _build_canonical_document_name(document_id=str(row.id), file_name=str(row.file_name))
        for row in rows
    ]
    token_document_frequency = _build_token_document_frequency(canonical_documents=canonical_documents)
    unique_suffix_owner = _build_unique_suffix_owner_map(canonical_documents=canonical_documents)

    candidates: list[DocumentMentionCandidate] = []
    for document in canonical_documents:
        score, signals = score_document_mention(
            query=normalized_query,
            canonical_document=document,
            token_document_frequency=token_document_frequency,
            unique_suffix_owner=unique_suffix_owner,
        )
        if score <= 0.0:
            continue
        candidates.append(
            DocumentMentionCandidate(
                document_id=document.document_id,
                file_name=document.file_name,
                score=score,
                match_signals=signals,
            )
        )

    ranked_candidates = tuple(
        sorted(
            candidates,
            key=lambda item: (-item.score, item.file_name.casefold(), item.document_id),
        )[:5]
    )
    if not ranked_candidates:
        return DocumentMentionResolution(
            resolved_document_ids=(),
            source=DOCUMENT_MENTION_SOURCE_NONE,
            confidence=0.0,
            candidates=(),
        )

    best_candidate = ranked_candidates[0]
    second_candidate = ranked_candidates[1] if len(ranked_candidates) > 1 else None
    if _should_prefer_single_document(best_candidate=best_candidate, second_candidate=second_candidate):
        first_source = best_candidate.match_signals[0] if best_candidate.match_signals else DOCUMENT_MENTION_SOURCE_NONE
        return DocumentMentionResolution(
            resolved_document_ids=(best_candidate.document_id,),
            source=first_source,
            confidence=best_candidate.score,
            candidates=ranked_candidates,
        )

    high_confidence_candidates = tuple(
        candidate for candidate in ranked_candidates if candidate.score >= MULTI_DOCUMENT_CONFIDENCE_THRESHOLD
    )
    if len(high_confidence_candidates) >= 2:
        first_source = high_confidence_candidates[0].match_signals[0] if high_confidence_candidates[0].match_signals else DOCUMENT_MENTION_SOURCE_NONE
        return DocumentMentionResolution(
            resolved_document_ids=tuple(candidate.document_id for candidate in high_confidence_candidates),
            source=first_source,
            confidence=high_confidence_candidates[0].score,
            candidates=ranked_candidates,
        )

    second_score = ranked_candidates[1].score if len(ranked_candidates) > 1 else 0.0
    if (
        best_candidate.score >= SINGLE_DOCUMENT_CONFIDENCE_THRESHOLD
        and (best_candidate.score - second_score) >= SINGLE_DOCUMENT_MARGIN_THRESHOLD
    ):
        first_source = best_candidate.match_signals[0] if best_candidate.match_signals else DOCUMENT_MENTION_SOURCE_NONE
        return DocumentMentionResolution(
            resolved_document_ids=(best_candidate.document_id,),
            source=first_source,
            confidence=best_candidate.score,
            candidates=ranked_candidates,
        )

    return DocumentMentionResolution(
        resolved_document_ids=(),
        source=DOCUMENT_MENTION_SOURCE_NONE,
        confidence=best_candidate.score,
        candidates=ranked_candidates,
    )


def resolve_summary_scope(
    *,
    query_type: EvaluationQueryType,
    mention_resolution: DocumentMentionResolution,
) -> str | None:
    """依 query type 與 mention 解析結果決定 summary scope。

    參數：
    - `query_type`：目前 query type。
    - `mention_resolution`：文件 mention 解析結果。

    回傳：
    - `str | None`：`single_document`、`multi_document` 或空值。
    """

    if query_type != EvaluationQueryType.document_summary:
        return None
    if len(mention_resolution.resolved_document_ids) == 1:
        return "single_document"
    return "multi_document"


def _score_document_mention_with_metadata(
    *,
    query: str,
    canonical_document: _CanonicalDocumentName,
    token_document_frequency: dict[str, int],
    unique_suffix_owner: dict[str, str],
) -> tuple[float, tuple[str, ...]]:
    """計算 query 與單一文件名稱的 mention 相似度。

    參數：
    - `query`：原始或已正規化的 query。
    - `canonical_document`：已 canonicalize 的文件名稱資料。
    - `token_document_frequency`：同一 area 內 token 出現於幾份文件的統計。
    - `unique_suffix_owner`：唯一 suffix 片語與文件對照表。

    回傳：
    - `tuple[float, tuple[str, ...]]`：分數與命中的 signals。
    """

    normalized_query = normalize_reference_query(query=query).casefold()
    normalized_basename = normalize_document_name(file_name=canonical_document.file_name)
    normalized_canonical_title = canonical_document.canonical_title
    if not normalized_query or not normalized_basename:
        return 0.0, ()

    query_tokens = tuple(_filter_generic_tokens(tokens=extract_query_tokens(query=normalized_query)))
    basename_tokens = canonical_document.tokens

    score = 0.0
    signals: list[str] = []

    if normalized_query == normalized_canonical_title:
        return 1.0, (DOCUMENT_MENTION_SIGNAL_EXACT_CANONICAL,)

    if normalized_query == normalized_basename:
        return 1.0, (DOCUMENT_MENTION_SIGNAL_EXACT_BASENAME,)

    if normalized_canonical_title and normalized_canonical_title in normalized_query and _is_specific_phrase(text=normalized_canonical_title):
        score = max(score, 0.96)
        signals.append(DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_CANONICAL)

    if normalized_basename in normalized_query and _is_specific_phrase(text=normalized_basename):
        score = max(score, 0.92)
        signals.append(DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_BASENAME)

    if normalized_query in normalized_basename and _is_specific_phrase(text=normalized_query):
        score = max(score, 0.86)
        signals.append(DOCUMENT_MENTION_SIGNAL_BASENAME_CONTAINS_QUERY)

    for segment in canonical_document.title_segments:
        if segment in unique_suffix_owner and unique_suffix_owner[segment] == canonical_document.document_id and segment in normalized_query:
            score = max(score, 0.94)
            signals.append(DOCUMENT_MENTION_SIGNAL_UNIQUE_SUFFIX)

    token_overlap = _compute_token_overlap_ratio(left_tokens=query_tokens, right_tokens=basename_tokens)
    if token_overlap > 0.0:
        score = max(
            score,
            0.42 + (token_overlap * 0.18) + _compute_rare_token_bonus(
                query_tokens=query_tokens,
                basename_tokens=basename_tokens,
                token_document_frequency=token_document_frequency,
            ),
        )
        signals.append(DOCUMENT_MENTION_SIGNAL_TOKEN_OVERLAP)

    ordered_coverage = _compute_ordered_token_coverage(query_tokens=query_tokens, basename_tokens=basename_tokens)
    if ordered_coverage > 0.0:
        score = max(score, 0.4 + (ordered_coverage * 0.22))
        signals.append(DOCUMENT_MENTION_SIGNAL_ORDERED_TOKEN_COVERAGE)

    if not query_tokens or _is_generic_only_match(tokens=query_tokens):
        score = min(score, 0.55)

    return min(score, 1.0), tuple(dict.fromkeys(signals))


def score_document_mention(
    *,
    query: str,
    canonical_document: _CanonicalDocumentName,
    token_document_frequency: dict[str, int],
    unique_suffix_owner: dict[str, str],
) -> tuple[float, tuple[str, ...]]:
    """計算 query 與單一文件名稱的 mention 相似度。

    參數：
    - `query`：原始或已正規化的 query。
    - `canonical_document`：已 canonicalize 的文件名稱資料。
    - `token_document_frequency`：同一 area 內 token 出現於幾份文件的統計。
    - `unique_suffix_owner`：唯一 suffix 片語與文件對照表。

    回傳：
    - `tuple[float, tuple[str, ...]]`：分數與命中的 signals。
    """

    return _score_document_mention_with_metadata(
        query=query,
        canonical_document=canonical_document,
        token_document_frequency=token_document_frequency,
        unique_suffix_owner=unique_suffix_owner,
    )


def normalize_reference_query(*, query: str) -> str:
    """將 query 正規化為更接近文件名稱解析用途的 reference phrase。

    參數：
    - `query`：使用者原始 query。

    回傳：
    - `str`：移除常見任務前綴後的 reference phrase。
    """

    normalized_query = normalize_query_text(query=query)
    stripped_query = _INSTRUCTION_PREFIX_PATTERN.sub("", normalized_query)
    return normalize_query_text(query=stripped_query)


def _build_canonical_document_name(*, document_id: str, file_name: str) -> _CanonicalDocumentName:
    """建立單一文件名稱的 canonicalization 結果。

    參數：
    - `document_id`：文件識別碼。
    - `file_name`：原始文件名稱。

    回傳：
    - `_CanonicalDocumentName`：canonical title、segments 與 tokens。
    """

    basename = _strip_trailing_version_suffix(text=Path(file_name).stem)
    title_segments = tuple(
        segment for segment in (_normalize_segment_text(segment) for segment in re.split(r"[-_/]+", basename)) if segment
    )
    canonical_title = _normalize_segment_text(basename)
    tokens = tuple(_filter_generic_tokens(tokens=extract_query_tokens(query=canonical_title)))
    return _CanonicalDocumentName(
        document_id=document_id,
        file_name=file_name,
        basename=basename,
        canonical_title=canonical_title,
        title_segments=title_segments,
        tokens=tokens,
    )


def _strip_trailing_version_suffix(*, text: str) -> str:
    """移除文件名稱常見的尾端版本 / 日期標記。

    參數：
    - `text`：原始 basename。

    回傳：
    - `str`：移除尾端版次後的文字。
    """

    stripped_text = text.strip()
    while True:
        next_text = _TRAILING_VERSION_PATTERN.sub("", stripped_text).strip()
        if next_text == stripped_text:
            return stripped_text
        stripped_text = next_text


def _normalize_segment_text(text: str) -> str:
    """將片段文字正規化為可供比對的 canonical string。

    參數：
    - `text`：原始片段文字。

    回傳：
    - `str`：分隔符正規化後的 canonical string。
    """

    separator_normalized = _SEPARATOR_PATTERN.sub(" ", text.casefold())
    return _WHITESPACE_PATTERN.sub(" ", separator_normalized).strip()


def _build_token_document_frequency(*, canonical_documents: list[_CanonicalDocumentName]) -> dict[str, int]:
    """統計 token 在多少份文件標題中出現。

    參數：
    - `canonical_documents`：同一 area 內的文件 canonical title 集合。

    回傳：
    - `dict[str, int]`：token -> document frequency。
    """

    counter: Counter[str] = Counter()
    for document in canonical_documents:
        counter.update(set(document.tokens))
    return dict(counter)


def _build_unique_suffix_owner_map(*, canonical_documents: list[_CanonicalDocumentName]) -> dict[str, str]:
    """建立唯一 suffix 片語與文件的對照表。

    參數：
    - `canonical_documents`：同一 area 內的文件 canonical title 集合。

    回傳：
    - `dict[str, str]`：僅保留唯一屬於單一文件的 suffix 片語。
    """

    owners: dict[str, set[str]] = {}
    for document in canonical_documents:
        for segment in document.title_segments:
            if not _is_specific_phrase(text=segment):
                continue
            owners.setdefault(segment, set()).add(document.document_id)
    return {
        segment: next(iter(document_ids))
        for segment, document_ids in owners.items()
        if len(document_ids) == 1
    }


def _compute_rare_token_bonus(
    *,
    query_tokens: tuple[str, ...],
    basename_tokens: tuple[str, ...],
    token_document_frequency: dict[str, int],
) -> float:
    """計算 query 與文件共用的稀有 token 加權分數。

    參數：
    - `query_tokens`：query tokens。
    - `basename_tokens`：文件 title tokens。
    - `token_document_frequency`：token 的文件頻率。

    回傳：
    - `float`：0 到 0.3 左右的稀有 token bonus。
    """

    overlap = set(query_tokens) & set(basename_tokens)
    if not overlap:
        return 0.0
    bonus = 0.0
    for token in overlap:
        frequency = token_document_frequency.get(token, 1)
        if frequency <= 1:
            bonus += 0.12
        elif frequency == 2:
            bonus += 0.06
        else:
            bonus += 0.01
    return min(bonus, 0.3)


def _is_specific_phrase(*, text: str) -> bool:
    """判斷一段文字是否足夠具體，可作為高信心文件指涉。

    參數：
    - `text`：待判斷文字。

    回傳：
    - `bool`：是否屬於具體短語。
    """

    stripped_text = text.strip()
    if not stripped_text:
        return False
    if " " in stripped_text:
        return True
    if _CJK_PATTERN.search(stripped_text):
        return len(stripped_text) >= 4
    return len(stripped_text) >= 8


def _compute_token_overlap_ratio(*, left_tokens: tuple[str, ...], right_tokens: tuple[str, ...]) -> float:
    """計算 query 與 basename 的 token overlap ratio。

    參數：
    - `left_tokens`：query tokens。
    - `right_tokens`：basename tokens。

    回傳：
    - `float`：0 到 1 之間的 overlap ratio。
    """

    if not left_tokens or not right_tokens:
        return 0.0
    overlap = set(left_tokens) & set(right_tokens)
    if not overlap:
        return 0.0
    return len(overlap) / max(1, min(len(left_tokens), len(right_tokens)))


def _compute_ordered_token_coverage(*, query_tokens: tuple[str, ...], basename_tokens: tuple[str, ...]) -> float:
    """計算 query tokens 在 basename 中的依序覆蓋率。

    參數：
    - `query_tokens`：query tokens。
    - `basename_tokens`：basename tokens。

    回傳：
    - `float`：0 到 1 之間的有序覆蓋比例。
    """

    if not query_tokens or not basename_tokens:
        return 0.0

    current_index = 0
    matched = 0
    for token in basename_tokens:
        while current_index < len(query_tokens) and query_tokens[current_index] != token:
            current_index += 1
        if current_index >= len(query_tokens):
            break
        matched += 1
        current_index += 1
    return matched / max(1, min(len(query_tokens), len(basename_tokens)))


def _filter_generic_tokens(*, tokens: list[str]) -> tuple[str, ...]:
    """移除過於通用、不可單獨作為文件名稱辨識依據的 tokens。

    參數：
    - `tokens`：原始 tokens。

    回傳：
    - `tuple[str, ...]`：過濾後 tokens。
    """

    return tuple(token for token in tokens if token not in GENERIC_DOCUMENT_TERMS)


def _is_generic_only_match(*, tokens: tuple[str, ...]) -> bool:
    """判斷 token 集合是否只包含過短或過於通用的資訊。

    參數：
    - `tokens`：待判斷 tokens。

    回傳：
    - `bool`：是否屬於 generic-only match。
    """

    if not tokens:
        return True
    for token in tokens:
        if _CJK_PATTERN.search(token):
            if len(token) >= 4 and token not in GENERIC_DOCUMENT_TERMS:
                return False
            continue
        if len(token) >= 4 and token not in GENERIC_DOCUMENT_TERMS:
            return False
    return True


def _should_prefer_single_document(
    *,
    best_candidate: DocumentMentionCandidate,
    second_candidate: DocumentMentionCandidate | None,
) -> bool:
    """判斷是否應優先把第一名視為單文件命中。

    參數：
    - `best_candidate`：目前最高分候選。
    - `second_candidate`：第二名候選；若不存在則為空值。

    回傳：
    - `bool`：若第一名具強識別 signal 且第二名不具同級 signal，則回傳真值。
    """

    if best_candidate.score < 0.9:
        return False
    strong_signals = {
        DOCUMENT_MENTION_SIGNAL_EXACT_CANONICAL,
        DOCUMENT_MENTION_SIGNAL_EXACT_BASENAME,
        DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_CANONICAL,
        DOCUMENT_MENTION_SIGNAL_QUERY_CONTAINS_BASENAME,
        DOCUMENT_MENTION_SIGNAL_UNIQUE_SUFFIX,
    }
    best_has_strong_signal = any(signal in strong_signals for signal in best_candidate.match_signals)
    if not best_has_strong_signal:
        return False
    if second_candidate is None:
        return True
    second_has_strong_signal = any(signal in strong_signals for signal in second_candidate.match_signals)
    if second_has_strong_signal:
        return False
    return (best_candidate.score - second_candidate.score) >= 0.05
