"""Rerank 後、assembler 前的 scope-aware diversified selection。"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from app.services.retrieval_routing import (
    RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_DIVERSIFIED_V1,
    RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1,
    RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1,
)
from app.services.retrieval_types import RetrievalCandidate


# single-document summary 過濾掉非目標文件的原因。
DROP_REASON_NOT_IN_SINGLE_DOCUMENT_SCOPE = "not_in_single_document_scope"
# 明確指定 comparison set / preferred documents 外的候選被捨棄原因。
DROP_REASON_NOT_IN_RESOLVED_DOCUMENT_SET = "not_in_resolved_document_set"
# 因 context budget 不足被捨棄。
DROP_REASON_CONTEXT_BUDGET_EXHAUSTED = "context_budget_exhausted"

# single-document summary 的 selection 策略名稱。
SELECTION_STRATEGY_SINGLE_DOCUMENT = "single_document_parent_diversity_v1"
# multi-document summary 的 selection 策略名稱。
SELECTION_STRATEGY_MULTI_DOCUMENT_SUMMARY = "multi_document_round_robin_fill_v1"
# compare 的 selection 策略名稱。
SELECTION_STRATEGY_CROSS_DOCUMENT_COMPARE = "compare_coverage_then_fill_v1"
# 未啟用 selection 的策略名稱。
SELECTION_STRATEGY_DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SelectionDropEntry:
    """單一被 diversity guardrail 捨棄的候選摘要。"""

    document_id: str
    parent_chunk_id: str | None
    chunk_id: str
    drop_reason: str


@dataclass(frozen=True, slots=True)
class RetrievalSelectionResult:
    """selection layer 的輸出。"""

    candidates: list[RetrievalCandidate]
    applied: bool
    strategy: str
    selected_document_ids: tuple[str, ...]
    selected_parent_ids: tuple[str, ...]
    dropped_by_diversity: tuple[SelectionDropEntry, ...]


@dataclass(slots=True)
class _ParentGroup:
    """selection 使用的 parent-level 候選群組。"""

    group_id: str
    document_id: str
    parent_chunk_id: str | None
    candidates: list[RetrievalCandidate]
    order: int


def apply_scope_aware_selection(
    *,
    candidates: list[RetrievalCandidate],
    selected_profile: str,
    resolved_document_ids: tuple[str, ...],
    max_contexts: int,
) -> RetrievalSelectionResult:
    """依 routing profile 對 reranked parent groups 做 diversified selection。

    參數：
    - `candidates`：rerank 後的 child-level candidates。
    - `selected_profile`：本次 routing 選中的 runtime profile。
    - `resolved_document_ids`：document mention resolver 高信心命中的文件集合。
    - `max_contexts`：selection 可用的最大 context budget。

    回傳：
    - `RetrievalSelectionResult`：selection 後保留的 candidates 與 trace metadata。
    """

    if selected_profile not in {
        RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1,
        RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1,
        RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_DIVERSIFIED_V1,
    }:
        return RetrievalSelectionResult(
            candidates=candidates,
            applied=False,
            strategy=SELECTION_STRATEGY_DISABLED,
            selected_document_ids=tuple(dict.fromkeys(candidate.document_id for candidate in candidates)),
            selected_parent_ids=tuple(
                dict.fromkeys((candidate.parent_chunk_id or candidate.chunk_id) for candidate in candidates)
            ),
            dropped_by_diversity=(),
        )

    if not candidates or max_contexts <= 0:
        strategy = _resolve_selection_strategy(selected_profile=selected_profile)
        return RetrievalSelectionResult(
            candidates=[],
            applied=True,
            strategy=strategy,
            selected_document_ids=(),
            selected_parent_ids=(),
            dropped_by_diversity=tuple(
                SelectionDropEntry(
                    document_id=candidate.document_id,
                    parent_chunk_id=candidate.parent_chunk_id,
                    chunk_id=candidate.chunk_id,
                    drop_reason=DROP_REASON_CONTEXT_BUDGET_EXHAUSTED,
                )
                for candidate in candidates
            ),
        )

    grouped_candidates = _group_candidates_by_parent(candidates=candidates)
    if selected_profile == RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1:
        return _select_single_document_summary(
            grouped_candidates=grouped_candidates,
            resolved_document_ids=resolved_document_ids,
            max_contexts=max_contexts,
        )
    if selected_profile == RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1:
        return _select_multi_document_summary(
            grouped_candidates=grouped_candidates,
            resolved_document_ids=resolved_document_ids,
            max_contexts=max_contexts,
        )
    return _select_cross_document_compare(
        grouped_candidates=grouped_candidates,
        resolved_document_ids=resolved_document_ids,
        max_contexts=max_contexts,
    )


def _group_candidates_by_parent(*, candidates: list[RetrievalCandidate]) -> list[_ParentGroup]:
    """依 parent 邊界將 child candidates 聚合為 selection 使用的群組。

    參數：
    - `candidates`：rerank 後的 child-level candidates。

    回傳：
    - `list[_ParentGroup]`：依原始排序穩定聚合後的 parent groups。
    """

    grouped: OrderedDict[str, _ParentGroup] = OrderedDict()
    for order, candidate in enumerate(candidates):
        stable_parent_id = candidate.parent_chunk_id or candidate.chunk_id
        group_id = f"{candidate.document_id}:{stable_parent_id}"
        if group_id not in grouped:
            grouped[group_id] = _ParentGroup(
                group_id=group_id,
                document_id=candidate.document_id,
                parent_chunk_id=candidate.parent_chunk_id,
                candidates=[candidate],
                order=order,
            )
            continue
        grouped[group_id].candidates.append(candidate)
    return list(grouped.values())


def _select_single_document_summary(
    *,
    grouped_candidates: list[_ParentGroup],
    resolved_document_ids: tuple[str, ...],
    max_contexts: int,
) -> RetrievalSelectionResult:
    """對 single-document summary 套用 parent-level 過濾。

    參數：
    - `grouped_candidates`：已聚合的 parent groups。
    - `resolved_document_ids`：高信心命中的文件集合。
    - `max_contexts`：可用 context budget。

    回傳：
    - `RetrievalSelectionResult`：selection 結果。
    """

    target_document_id = resolved_document_ids[0] if len(resolved_document_ids) == 1 else None
    selected_groups: list[_ParentGroup] = []
    dropped_entries: list[SelectionDropEntry] = []

    for group in grouped_candidates:
        if target_document_id is not None and group.document_id != target_document_id:
            dropped_entries.extend(_build_drop_entries(group=group, reason=DROP_REASON_NOT_IN_SINGLE_DOCUMENT_SCOPE))
            continue
        if len(selected_groups) >= max_contexts:
            dropped_entries.extend(_build_drop_entries(group=group, reason=DROP_REASON_CONTEXT_BUDGET_EXHAUSTED))
            continue
        selected_groups.append(group)

    return _build_selection_result(
        groups=selected_groups,
        applied=True,
        strategy=SELECTION_STRATEGY_SINGLE_DOCUMENT,
        dropped_entries=dropped_entries,
    )


def _select_multi_document_summary(
    *,
    grouped_candidates: list[_ParentGroup],
    resolved_document_ids: tuple[str, ...],
    max_contexts: int,
) -> RetrievalSelectionResult:
    """對 multi-document summary 套用 round-robin + fill diversified selection。

    參數：
    - `grouped_candidates`：已聚合的 parent groups。
    - `resolved_document_ids`：高信心命中的文件集合。
    - `max_contexts`：可用 context budget。

    回傳：
    - `RetrievalSelectionResult`：selection 結果。
    """

    preferred_document_ids = resolved_document_ids if len(resolved_document_ids) >= 2 else ()
    return _select_multi_document_groups(
        grouped_candidates=grouped_candidates,
        preferred_document_ids=preferred_document_ids,
        max_contexts=max_contexts,
        strategy=SELECTION_STRATEGY_MULTI_DOCUMENT_SUMMARY,
        run_second_coverage_pass=False,
    )


def _select_cross_document_compare(
    *,
    grouped_candidates: list[_ParentGroup],
    resolved_document_ids: tuple[str, ...],
    max_contexts: int,
) -> RetrievalSelectionResult:
    """對 compare query 套用 coverage-first diversified selection。

    參數：
    - `grouped_candidates`：已聚合的 parent groups。
    - `resolved_document_ids`：高信心命中的文件集合。
    - `max_contexts`：可用 context budget。

    回傳：
    - `RetrievalSelectionResult`：selection 結果。
    """

    preferred_document_ids = resolved_document_ids if len(resolved_document_ids) >= 2 else ()
    return _select_multi_document_groups(
        grouped_candidates=grouped_candidates,
        preferred_document_ids=preferred_document_ids,
        max_contexts=max_contexts,
        strategy=SELECTION_STRATEGY_CROSS_DOCUMENT_COMPARE,
        run_second_coverage_pass=True,
    )


def _select_multi_document_groups(
    *,
    grouped_candidates: list[_ParentGroup],
    preferred_document_ids: tuple[str, ...],
    max_contexts: int,
    strategy: str,
    run_second_coverage_pass: bool,
) -> RetrievalSelectionResult:
    """執行 multi-document summary / compare 共用的 selection 流程。

    參數：
    - `grouped_candidates`：已聚合的 parent groups。
    - `preferred_document_ids`：高信心指涉的文件集合；若為空則以整體候選為準。
    - `max_contexts`：可用 context budget。
    - `strategy`：本次 selection 的策略名稱。
    - `run_second_coverage_pass`：是否執行第二輪 coverage pass。

    回傳：
    - `RetrievalSelectionResult`：selection 結果。
    """

    candidate_pool = grouped_candidates
    dropped_entries: list[SelectionDropEntry] = []
    if preferred_document_ids:
        preferred_document_set = set(preferred_document_ids)
        in_scope_groups = [group for group in grouped_candidates if group.document_id in preferred_document_set]
        out_of_scope_groups = [group for group in grouped_candidates if group.document_id not in preferred_document_set]
        dropped_entries.extend(
            entry
            for group in out_of_scope_groups
            for entry in _build_drop_entries(group=group, reason=DROP_REASON_NOT_IN_RESOLVED_DOCUMENT_SET)
        )
        if in_scope_groups:
            candidate_pool = in_scope_groups

    remaining_by_document = _group_groups_by_document(groups=candidate_pool)
    selected_groups: list[_ParentGroup] = []

    _run_round_robin_coverage_pass(
        remaining_by_document=remaining_by_document,
        selected_groups=selected_groups,
        max_contexts=max_contexts,
    )
    if run_second_coverage_pass and len(selected_groups) < max_contexts:
        _run_round_robin_coverage_pass(
            remaining_by_document=remaining_by_document,
            selected_groups=selected_groups,
            max_contexts=max_contexts,
        )

    remaining_groups = _flatten_remaining_groups(remaining_by_document=remaining_by_document)
    if not run_second_coverage_pass:
        remaining_groups = _run_soft_guardrail_fill_pass(
            remaining_groups=remaining_groups,
            remaining_by_document=remaining_by_document,
            selected_groups=selected_groups,
            max_contexts=max_contexts,
        )
    if len(selected_groups) < max_contexts and remaining_groups:
        selected_groups.extend(remaining_groups[: max_contexts - len(selected_groups)])
        remaining_groups = remaining_groups[max(0, max_contexts - len(selected_groups)) :]

    if remaining_groups:
        dropped_entries.extend(
            entry
            for group in remaining_groups
            for entry in _build_drop_entries(group=group, reason=DROP_REASON_CONTEXT_BUDGET_EXHAUSTED)
        )

    return _build_selection_result(
        groups=selected_groups,
        applied=True,
        strategy=strategy,
        dropped_entries=dropped_entries,
    )


def _run_round_robin_coverage_pass(
    *,
    remaining_by_document: OrderedDict[str, list[_ParentGroup]],
    selected_groups: list[_ParentGroup],
    max_contexts: int,
) -> None:
    """對每文件依序選取一個最佳 parent group。

    參數：
    - `remaining_by_document`：依文件分組的剩餘 groups。
    - `selected_groups`：目前已選 groups。
    - `max_contexts`：可用 context budget。

    回傳：
    - `None`：僅更新 selected 與 remaining groups。
    """

    for document_id in list(remaining_by_document.keys()):
        if len(selected_groups) >= max_contexts:
            return
        groups = remaining_by_document.get(document_id, [])
        if not groups:
            continue
        selected_groups.append(groups.pop(0))


def _run_soft_guardrail_fill_pass(
    *,
    remaining_groups: list[_ParentGroup],
    remaining_by_document: OrderedDict[str, list[_ParentGroup]],
    selected_groups: list[_ParentGroup],
    max_contexts: int,
) -> list[_ParentGroup]:
    """在 multi-document summary fill pass 套用 soft guardrail。

    參數：
    - `remaining_groups`：尚未被選取的剩餘 groups。
    - `remaining_by_document`：依文件分組的剩餘 groups。
    - `selected_groups`：目前已選 groups。
    - `max_contexts`：可用 context budget。

    回傳：
    - `list[_ParentGroup]`：仍未被選取的剩餘 groups。
    """

    selected_count_by_document: dict[str, int] = {}
    for group in selected_groups:
        selected_count_by_document[group.document_id] = selected_count_by_document.get(group.document_id, 0) + 1

    working_remaining = list(remaining_groups)
    while len(selected_groups) < max_contexts and working_remaining:
        eligible_groups = [
            group
            for group in working_remaining
            if not _violates_second_parent_guardrail(
                group=group,
                selected_count_by_document=selected_count_by_document,
                remaining_by_document=remaining_by_document,
            )
        ]
        if not eligible_groups:
            break
        next_group = eligible_groups[0]
        selected_groups.append(next_group)
        selected_count_by_document[next_group.document_id] = selected_count_by_document.get(next_group.document_id, 0) + 1
        working_remaining.remove(next_group)
        if next_group in remaining_by_document.get(next_group.document_id, []):
            remaining_by_document[next_group.document_id].remove(next_group)
    return working_remaining


def _violates_second_parent_guardrail(
    *,
    group: _ParentGroup,
    selected_count_by_document: dict[str, int],
    remaining_by_document: OrderedDict[str, list[_ParentGroup]],
) -> bool:
    """判斷某文件是否在其他文件尚未拿到第二個 parent 前先取得第三個。

    參數：
    - `group`：待判斷 group。
    - `selected_count_by_document`：目前每文件已選數量。
    - `remaining_by_document`：每文件尚餘 groups。

    回傳：
    - `bool`：是否違反 soft guardrail。
    """

    current_count = selected_count_by_document.get(group.document_id, 0)
    if current_count < 2:
        return False
    for document_id, remaining_groups in remaining_by_document.items():
        if document_id == group.document_id or not remaining_groups:
            continue
        if selected_count_by_document.get(document_id, 0) < 2:
            return True
    return False


def _group_groups_by_document(*, groups: list[_ParentGroup]) -> OrderedDict[str, list[_ParentGroup]]:
    """將 parent groups 依文件排序分組。

    參數：
    - `groups`：待分組的 parent groups。

    回傳：
    - `OrderedDict[str, list[_ParentGroup]]`：依原始文件出現順序分組後的剩餘 groups。
    """

    grouped: OrderedDict[str, list[_ParentGroup]] = OrderedDict()
    for group in groups:
        grouped.setdefault(group.document_id, []).append(group)
    return grouped


def _flatten_remaining_groups(*, remaining_by_document: OrderedDict[str, list[_ParentGroup]]) -> list[_ParentGroup]:
    """將依文件分組的剩餘候選重新攤平成原排序列表。

    參數：
    - `remaining_by_document`：依文件分組的剩餘 groups。

    回傳：
    - `list[_ParentGroup]`：按原始 order 排序的剩餘 groups。
    """

    return sorted(
        [group for groups in remaining_by_document.values() for group in groups],
        key=lambda group: group.order,
    )


def _build_selection_result(
    *,
    groups: list[_ParentGroup],
    applied: bool,
    strategy: str,
    dropped_entries: list[SelectionDropEntry],
) -> RetrievalSelectionResult:
    """將已選 groups 轉成最終 selection 結果。

    參數：
    - `groups`：最終保留的 groups。
    - `applied`：本次是否有套用 selection。
    - `strategy`：本次使用的策略名稱。
    - `dropped_entries`：被捨棄的候選摘要。

    回傳：
    - `RetrievalSelectionResult`：對外 selection 結果。
    """

    flattened_candidates = [candidate for group in groups for candidate in group.candidates]
    selected_document_ids = tuple(dict.fromkeys(group.document_id for group in groups))
    selected_parent_ids = tuple(
        dict.fromkeys((group.parent_chunk_id or group.candidates[0].chunk_id) for group in groups)
    )
    return RetrievalSelectionResult(
        candidates=flattened_candidates,
        applied=applied,
        strategy=strategy,
        selected_document_ids=selected_document_ids,
        selected_parent_ids=selected_parent_ids,
        dropped_by_diversity=tuple(dropped_entries),
    )


def _build_drop_entries(*, group: _ParentGroup, reason: str) -> tuple[SelectionDropEntry, ...]:
    """為單一 parent group 內的所有 child candidates 建立 drop entries。

    參數：
    - `group`：被捨棄的 parent group。
    - `reason`：捨棄原因。

    回傳：
    - `tuple[SelectionDropEntry, ...]`：對應 group 內所有 child 的捨棄摘要。
    """

    return tuple(
        SelectionDropEntry(
            document_id=candidate.document_id,
            parent_chunk_id=candidate.parent_chunk_id,
            chunk_id=candidate.chunk_id,
            drop_reason=reason,
        )
        for candidate in group.candidates
    )


def _resolve_selection_strategy(*, selected_profile: str) -> str:
    """依 selected profile 回傳對應的 selection 策略名稱。

    參數：
    - `selected_profile`：本次 routing 選中的 profile。

    回傳：
    - `str`：selection 策略名稱。
    """

    if selected_profile == RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_SINGLE_DOCUMENT_DIVERSIFIED_V1:
        return SELECTION_STRATEGY_SINGLE_DOCUMENT
    if selected_profile == RETRIEVAL_PROFILE_DOCUMENT_SUMMARY_MULTI_DOCUMENT_DIVERSIFIED_V1:
        return SELECTION_STRATEGY_MULTI_DOCUMENT_SUMMARY
    if selected_profile == RETRIEVAL_PROFILE_CROSS_DOCUMENT_COMPARE_DIVERSIFIED_V1:
        return SELECTION_STRATEGY_CROSS_DOCUMENT_COMPARE
    return SELECTION_STRATEGY_DISABLED
