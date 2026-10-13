"""Worker 使用的表格感知 parent-child chunk tree 建立邏輯。"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import count
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from worker.parsers import ParsedDocument, ParsedRegion


@dataclass(slots=True)
class ChunkingConfig:
    """chunking 策略使用的參數。"""

    # parent section 最小長度；不足時優先與後續 section 合併。
    min_parent_section_length: int
    # child chunk 目標大小，單位為字元。
    target_child_chunk_size: int
    # child chunk overlap 大小，單位為字元。
    child_chunk_overlap: int
    # UI 與 observability 使用的內容摘要長度。
    content_preview_length: int
    # TXT 每個 parent section 預設合併的段落數。
    txt_parent_group_size: int
    # 整張表格可原封保留的最大字元數。
    table_preserve_max_chars: int
    # 超大表格分段時每個 child 最多資料列數。
    table_max_rows_per_child: int
    # 是否啟用 fact-heavy section 的 evidence-centric child refinement。
    fact_heavy_refinement_enabled: bool


@dataclass(slots=True)
class SectionDraft:
    """尚未展開 child chunks 前的 parent section 草稿。"""

    # parent section 順序。
    section_index: int
    # 內容結構型別。
    structure_kind: str
    # markdown heading；若無則為空值。
    heading: str | None
    # parent section 文字內容。
    content: str
    # section 在 normalize 後文字中的起始 offset。
    start_offset: int
    # section 在 normalize 後文字中的結束 offset。
    end_offset: int
    # section 層級路徑文字。
    heading_path: str | None = None
    # 供 section recall 使用的 path-aware section 文字。
    section_path_text: str | None = None
    # heading level；未知時為空值。
    heading_level: int | None = None
    # 此 parent 內部保留的 component blocks；若為空值代表整段視為單一 component。
    components: list["SectionComponent"] | None = None
    # 此 section 涵蓋的起始頁碼。
    page_start: int | None = None
    # 此 section 涵蓋的結束頁碼。
    page_end: int | None = None
    # 此 section 關聯的 PDF regions。
    regions: list[ParsedRegion] | None = None


@dataclass(slots=True)
class SectionComponent:
    """parent section 內部的可切分 component block。"""

    # component 內容結構型別。
    structure_kind: str
    # component 所屬 heading。
    heading: str | None
    # component 內容。
    content: str
    # component 相對於 parent content 的起始 offset。
    start_offset: int
    # component 相對於 parent content 的結束 offset。
    end_offset: int
    # component 涵蓋的起始頁碼。
    page_start: int | None = None
    # component 涵蓋的結束頁碼。
    page_end: int | None = None
    # component 關聯的 PDF regions。
    regions: list[ParsedRegion] | None = None


@dataclass(slots=True)
class ChunkDraft:
    """待寫入資料庫的 chunk 草稿。"""

    # chunk 型別。
    chunk_type: str
    # chunk 內容結構型別。
    structure_kind: str
    # chunk 在整份文件中的穩定排序。
    position: int
    # parent section 順序。
    section_index: int
    # parent 下 child 順序；parent 本身為空值。
    child_index: int | None
    # markdown heading；若無則為空值。
    heading: str | None
    # chunk 內容。
    content: str
    # UI 與 observability 使用的摘要。
    content_preview: str
    # chunk 內容長度。
    char_count: int
    # chunk 在 display_text 中的起始 offset。
    start_offset: int
    # chunk 在 display_text 中的結束 offset。
    end_offset: int
    # section 層級路徑文字；child 預設為空值。
    heading_path: str | None = None
    # 供 section recall 使用的 path-aware section 文字；child 預設為空值。
    section_path_text: str | None = None
    # heading level；未知時為空值。
    heading_level: int | None = None
    # chunk 涵蓋的起始頁碼。
    page_start: int | None = None
    # chunk 涵蓋的結束頁碼。
    page_end: int | None = None
    # chunk 關聯的 PDF regions。
    regions: list[ParsedRegion] | None = None


@dataclass(slots=True)
class ChunkingResult:
    """完整 chunking 結果。"""

    # parent chunks 草稿。
    parent_chunks: list[ChunkDraft]
    # child chunks 草稿。
    child_chunks: list[ChunkDraft]
    # 供 preview 與定位使用的顯示用全文。
    display_text: str


def build_chunk_tree(*, parsed_document: ParsedDocument, config: ChunkingConfig) -> ChunkingResult:
    """將 ParsedDocument 切成 parent-child chunk tree。

    參數：
    - `parsed_document`：parser 回傳的結構化文件內容。
    - `config`：chunking 參數設定。

    回傳：
    - `ChunkingResult`：包含 parent 與 child chunk 草稿的結果。
    """

    if not parsed_document.normalized_text.strip():
        raise ValueError("文件內容不可為空白。")

    sections = _build_sections(parsed_document=parsed_document, config=config)
    if not sections:
        raise ValueError("無法從文件內容建立有效 chunks。")

    parent_chunks: list[ChunkDraft] = []
    child_chunks: list[ChunkDraft] = []
    display_parts: list[str] = []
    position_counter = count()
    display_cursor = 0

    for index, section in enumerate(sections):
        if index > 0:
            display_parts.append("\n\n")
            display_cursor += 2

        display_prefix = _render_display_heading_prefix(section.heading)
        if display_prefix:
            display_parts.append(display_prefix)
            display_cursor += len(display_prefix)

        display_content_start = display_cursor
        parent_chunks.append(
            ChunkDraft(
                chunk_type="parent",
                structure_kind=section.structure_kind,
                position=next(position_counter),
                section_index=section.section_index,
                child_index=None,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=display_content_start,
                end_offset=display_content_start + len(section.content),
                heading_path=section.heading_path,
                section_path_text=section.section_path_text,
                heading_level=section.heading_level,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        )
        child_chunks.extend(
            _build_child_chunks(
                section=section,
                position_counter=position_counter,
                config=config,
                display_content_start=display_content_start,
            )
        )
        display_parts.append(section.content)
        display_cursor += len(section.content)

    if not child_chunks:
        raise ValueError("無法從文件內容建立有效 chunks。")

    display_text = "".join(display_parts)
    _include_verified_heading_prefix_in_parent_offsets(parent_chunks=parent_chunks, display_text=display_text)
    return ChunkingResult(
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
        display_text=display_text,
    )


def _build_sections(*, parsed_document: ParsedDocument, config: ChunkingConfig) -> list[SectionDraft]:
    """將 ParsedDocument 轉為 parent section 草稿。

    參數：
    - `parsed_document`：parser 回傳的結構化文件內容。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：正規化後的 parent sections。
    """

    if parsed_document.source_format == "txt":
        return _build_text_sections(text=parsed_document.normalized_text, config=config)

    sections = []
    for index, (block, heading_path) in enumerate(_resolve_block_heading_paths(parsed_document.blocks)):
        if not block.content.strip():
            continue
        sections.append(
            SectionDraft(
                section_index=index,
                structure_kind=block.block_kind,
                heading=block.heading,
                content=block.content,
                start_offset=block.start_offset,
                end_offset=block.end_offset,
                heading_path=heading_path,
                section_path_text=_build_section_path_text(heading_path=heading_path, section_index=index),
                heading_level=block.heading_level if block.heading_level is not None else _infer_heading_level(block.heading),
                components=[
                    SectionComponent(
                        structure_kind=block.block_kind,
                        heading=block.heading,
                        content=block.content,
                        start_offset=0,
                        end_offset=len(block.content),
                        page_start=block.page_start,
                        page_end=block.page_end,
                        regions=block.regions,
                    )
                ],
                page_start=block.page_start,
                page_end=block.page_end,
                regions=block.regions,
            )
        )
    if parsed_document.source_format == "pdf":
        sections = _consolidate_pdf_sections(sections, config=config)
    return _normalize_sections(sections, config=config)


def _build_text_sections(text: str, *, config: ChunkingConfig) -> list[SectionDraft]:
    """依 TXT 段落群組建立 parent sections。

    參數：
    - `text`：normalize 後的純文字內容。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：依段落群組切好的 parent section 草稿。
    """

    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs:
        return []

    grouped_sections: list[SectionDraft] = []
    for index in range(0, len(paragraphs), config.txt_parent_group_size):
        content = "\n\n".join(paragraphs[index : index + config.txt_parent_group_size]).strip()
        grouped_sections.append(
            SectionDraft(
                section_index=len(grouped_sections),
                structure_kind="text",
                heading=None,
                content=content,
                start_offset=0,
                end_offset=0,
                heading_path=None,
                section_path_text=_build_section_path_text(
                    heading_path=None,
                    section_index=len(grouped_sections),
                ),
                heading_level=None,
            )
        )
    return _normalize_sections(grouped_sections, config=config)


def _resolve_block_heading_paths(blocks) -> list[tuple[object, str | None]]:
    """為 parser blocks 建立最小 path-aware heading 路徑。

    參數：
    - `blocks`：parser 產出的 block 清單。

    回傳：
    - `list[tuple[object, str | None]]`：每個 block 與其 heading path。
    """

    resolved: list[tuple[object, str | None]] = []
    heading_stack: list[str] = []

    for block in blocks:
        heading = _normalize_heading_text(getattr(block, "heading", None))
        heading_level = getattr(block, "heading_level", None)
        if heading:
            if isinstance(heading_level, int) and heading_level > 0:
                heading_stack = heading_stack[: max(heading_level - 1, 0)]
                heading_stack.append(heading)
            elif not heading_stack or heading_stack[-1] != heading:
                heading_stack = [heading]
        resolved.append((block, " / ".join(heading_stack) if heading_stack else None))

    return resolved


def _normalize_heading_text(heading: str | None) -> str | None:
    """將 heading 正規化為單行文字。"""

    normalized = re.sub(r"\s+", " ", heading or "").strip()
    return normalized or None


def _infer_heading_level(heading: str | None) -> int | None:
    """在 parser 未提供 heading level 時，用最小規則推估層級。"""

    normalized_heading = _normalize_heading_text(heading)
    if normalized_heading is None:
        return None
    if "/" in normalized_heading:
        return max(1, len(_split_heading_segments(normalized_heading)))
    return 1


def _build_section_path_text(*, heading_path: str | None, section_index: int) -> str:
    """建立 section recall 使用的 path-aware section 文字。"""

    if heading_path:
        return heading_path
    return f"Section {section_index + 1}"


def _normalize_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """合併過短 parent sections，並重算 section index 與 offsets。

    參數：
    - `sections`：初步切好的 parent section 草稿。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：合併短 section 後的正規化結果。
    """

    if not sections:
        return []

    merged_sections = _merge_adjacent_text_sections(sections=sections, config=config)
    merged_sections = _merge_undersized_sections(sections=merged_sections, config=config)
    return _reindex_sections(sections=merged_sections)


def _merge_adjacent_text_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """先套用既有的短文字 parent 合併規則。

    參數：
    - `sections`：初步切好的 parent section 草稿。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：完成文字優先合併的 section 清單。
    """

    merged_sections: list[SectionDraft] = []
    index = 0
    while index < len(sections):
        current = sections[index]
        index += 1

        if current.structure_kind == "table":
            merged_sections.append(current)
            continue

        while (
            current.structure_kind == "text"
            and len(current.content) < config.min_parent_section_length
            and index < len(sections)
            and sections[index].structure_kind == "text"
        ):
            current = _merge_sections(current, sections[index])
            index += 1

        if (
            current.structure_kind == "text"
            and len(current.content) < config.min_parent_section_length
            and merged_sections
            and merged_sections[-1].structure_kind == "text"
        ):
            previous = merged_sections.pop()
            current = _merge_sections(previous, current)

        merged_sections.append(current)

    return merged_sections


def _merge_undersized_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """將仍過短的 parent 與相鄰同 heading section 合併。

    參數：
    - `sections`：已完成初步文字合併的 section 清單。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：完成過短 parent 補併的 section 清單。
    """

    if len(sections) <= 1:
        return sections

    merged_sections = list(sections)
    changed = True
    while changed and len(merged_sections) > 1:
        changed = False
        index = 0
        while index < len(merged_sections):
            current = merged_sections[index]
            if not _is_undersized_section(section=current, config=config):
                index += 1
                continue

            merged = _merge_undersized_section_at_index(
                sections=merged_sections,
                index=index,
                config=config,
            )
            if merged is None:
                index += 1
                continue

            merged_sections = merged
            changed = True
            break

    return merged_sections


def _merge_undersized_section_at_index(
    *,
    sections: list[SectionDraft],
    index: int,
    config: ChunkingConfig,
) -> list[SectionDraft] | None:
    """嘗試合併指定索引的過短 parent section。

    參數：
    - `sections`：目前的 section 清單。
    - `index`：欲處理的過短 section 索引。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft] | None`：若成功合併則回傳新清單，否則回傳空值。
    """

    current = sections[index]
    previous = sections[index - 1] if index > 0 else None
    next_section = sections[index + 1] if index + 1 < len(sections) else None

    if (
        previous is not None
        and next_section is not None
        and _can_merge_by_heading(current, previous)
        and _can_merge_by_heading(current, next_section)
        and _is_text_like(previous)
        and current.structure_kind == "table"
        and _is_text_like(next_section)
    ):
        merged = _merge_mixed_sections(previous, current, next_section)
        return [*sections[: index - 1], merged, *sections[index + 2 :]]

    candidates: list[tuple[str, SectionDraft]] = []
    if previous is not None and _can_merge_by_heading(current, previous):
        candidates.append(("left", _merge_pair_for_undersized(previous, current)))
    if next_section is not None and _can_merge_by_heading(current, next_section):
        candidates.append(("right", _merge_pair_for_undersized(current, next_section)))

    if not candidates:
        return None

    direction, merged = min(
        candidates,
        key=lambda item: (
            abs(len(item[1].content) - config.min_parent_section_length),
            0 if item[0] == "right" else 1,
        ),
    )
    if direction == "left":
        return [*sections[: index - 1], merged, *sections[index + 1 :]]
    return [*sections[:index], merged, *sections[index + 2 :]]


def _is_undersized_section(*, section: SectionDraft, config: ChunkingConfig) -> bool:
    """判斷 parent section 是否低於最小長度門檻。

    參數：
    - `section`：欲判斷的 parent section。
    - `config`：chunking 參數設定。

    回傳：
    - `bool`：若字元數低於門檻則回傳真值。
    """

    return len(section.content) < config.min_parent_section_length


def _can_merge_by_heading(current: SectionDraft, neighbor: SectionDraft) -> bool:
    """判斷過短 parent 是否可與相鄰 section 合併。

    參數：
    - `current`：目前過短的 section。
    - `neighbor`：相鄰候選 section。

    回傳：
    - `bool`：若兩者屬於同一 heading family 則允許合併。
    """

    return _headings_belong_to_same_family(current.heading, neighbor.heading)


def _headings_belong_to_same_family(current_heading: str | None, neighbor_heading: str | None) -> bool:
    """判斷兩個 headings 是否屬於同一條階層路徑。

    參數：
    - `current_heading`：目前 section 的 heading。
    - `neighbor_heading`：相鄰 section 的 heading。

    回傳：
    - `bool`：若兩者完全相同，或其中一方為另一方的 path prefix，則回傳真值。
    """

    current_segments = _split_heading_segments(current_heading)
    neighbor_segments = _split_heading_segments(neighbor_heading)
    if not current_segments or not neighbor_segments:
        return current_segments == neighbor_segments
    return _is_heading_prefix(current_segments, neighbor_segments) or _is_heading_prefix(
        neighbor_segments,
        current_segments,
    )


def _split_heading_segments(heading: str | None) -> tuple[str, ...]:
    """將 heading 依階層分隔符拆成 path segments。

    參數：
    - `heading`：原始 heading；允許空值。

    回傳：
    - `tuple[str, ...]`：清理空白後的 heading segments。
    """

    if heading is None:
        return ()
    normalized_heading = re.sub(r"\s+", " ", heading).strip()
    if not normalized_heading:
        return ()
    return tuple(segment.strip() for segment in re.split(r"\s+/\s+", normalized_heading) if segment.strip())


def _is_heading_prefix(prefix_segments: tuple[str, ...], target_segments: tuple[str, ...]) -> bool:
    """判斷一組 heading segments 是否為另一組的 prefix。

    參數：
    - `prefix_segments`：候選 prefix segments。
    - `target_segments`：完整 heading segments。

    回傳：
    - `bool`：若 `prefix_segments` 為 `target_segments` 的 prefix，則回傳真值。
    """

    return len(prefix_segments) <= len(target_segments) and target_segments[: len(prefix_segments)] == prefix_segments


def _is_text_like(section: SectionDraft) -> bool:
    """判斷 section 是否屬於文字型 parent。

    參數：
    - `section`：欲判斷的 section。

    回傳：
    - `bool`：若 `structure_kind` 為 `text` 則回傳真值。
    """

    return section.structure_kind == "text"


def _has_component_boundaries(section: SectionDraft) -> bool:
    """判斷 section 是否保留多個 component 邊界。

    參數：
    - `section`：欲判斷的 section。

    回傳：
    - `bool`：若 section 內含多個 component 則回傳真值。
    """

    return bool(section.components and len(section.components) > 1)


def _merge_pair_for_undersized(left_section: SectionDraft, right_section: SectionDraft) -> SectionDraft:
    """依相鄰 section 型別選擇適合的合併方式。

    參數：
    - `left_section`：前段 section。
    - `right_section`：後段 section。

    回傳：
    - `SectionDraft`：合併後但尚未重新編號的 section。
    """

    if (
        left_section.structure_kind == right_section.structure_kind == "text"
        and (_has_component_boundaries(left_section) or _has_component_boundaries(right_section))
    ):
        return _merge_mixed_sections(left_section, right_section)

    if left_section.structure_kind == right_section.structure_kind:
        if left_section.structure_kind == "text":
            return _merge_sections(left_section, right_section)
        return _merge_same_kind_sections(left_section, right_section)
    return _merge_mixed_sections(left_section, right_section)


def _merge_mixed_sections(*sections: SectionDraft) -> SectionDraft:
    """將含 text/table 的相鄰 sections 合併為 mixed text parent。

    參數：
    - `sections`：欲合併的相鄰 sections。

    回傳：
    - `SectionDraft`：保留 component 邊界的 mixed parent。
    """

    return _merge_section_sequence(*sections, structure_kind="text", preserve_components=True)


def _reindex_sections(*, sections: list[SectionDraft]) -> list[SectionDraft]:
    """重算 section index 與 normalize 後 offsets。

    參數：
    - `sections`：待重算索引的 section 清單。

    回傳：
    - `list[SectionDraft]`：完成重新編號的 section 清單。
    """

    normalized_sections: list[SectionDraft] = []
    cursor = 0
    for section_index, section in enumerate(sections):
        start_offset = cursor
        end_offset = start_offset + len(section.content)
        normalized_sections.append(
            SectionDraft(
                section_index=section_index,
                structure_kind=section.structure_kind,
                heading=section.heading,
                content=section.content,
                start_offset=start_offset,
                end_offset=end_offset,
                heading_path=section.heading_path,
                section_path_text=section.section_path_text,
                heading_level=section.heading_level,
                components=section.components,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        )
        cursor = end_offset + 2
    return normalized_sections


def _consolidate_pdf_sections(sections: list[SectionDraft], *, config: ChunkingConfig) -> list[SectionDraft]:
    """在 PDF 路徑先合併過碎的 parser blocks，降低 parent section 碎片化。

    參數：
    - `sections`：由 parser 直接輸出的 section 草稿。
    - `config`：chunking 參數設定。

    回傳：
    - `list[SectionDraft]`：做過 PDF consolidation 的 section 清單。
    """

    if not sections:
        return []

    consolidated: list[SectionDraft] = []
    index = 0
    while index < len(sections):
        clustered = _build_pdf_table_cluster(sections=sections, start_index=index, config=config)
        if clustered is not None:
            consolidated.append(clustered)
            index += 3
            continue

        current = sections[index]

        if current.structure_kind == "table":
            if (
                consolidated
                and consolidated[-1].structure_kind == "table"
                and consolidated[-1].heading == current.heading
                and consolidated[-1].end_offset == current.start_offset - 2
            ):
                consolidated[-1] = _merge_same_kind_sections(consolidated[-1], current)
            else:
                consolidated.append(current)
            index += 1
            continue

        merged = current
        lookahead = index + 1
        while lookahead < len(sections):
            candidate = sections[lookahead]
            if candidate.structure_kind != "text":
                break
            if candidate.heading != merged.heading:
                break
            if len(merged.content) >= config.min_parent_section_length:
                break
            merged = _merge_same_kind_sections(merged, candidate)
            lookahead += 1

        if (
            consolidated
            and consolidated[-1].structure_kind == "text"
            and consolidated[-1].heading == merged.heading
            and len(merged.content) < config.min_parent_section_length
        ):
            consolidated[-1] = _merge_same_kind_sections(consolidated[-1], merged)
        else:
            consolidated.append(merged)

        index = lookahead

    return consolidated


def _build_pdf_table_cluster(
    *,
    sections: list[SectionDraft],
    start_index: int,
    config: ChunkingConfig,
) -> SectionDraft | None:
    """將 `text -> table -> text` 的短 PDF blocks 合併為單一 parent cluster。

    參數：
    - `sections`：PDF parser 直接輸出的 section 草稿。
    - `start_index`：欲檢查的起始索引。
    - `config`：chunking 參數設定。

    回傳：
    - `SectionDraft | None`：若符合 cluster 規則則回傳合併後 parent，否則回傳空值。
    """

    if start_index + 2 >= len(sections):
        return None

    first = sections[start_index]
    middle = sections[start_index + 1]
    last = sections[start_index + 2]
    if first.structure_kind != "text" or middle.structure_kind != "table" or last.structure_kind != "text":
        return None
    if first.heading != middle.heading or first.heading != last.heading:
        return None
    if len(first.content) >= config.min_parent_section_length or len(last.content) >= config.min_parent_section_length:
        return None
    return _merge_section_sequence(first, middle, last, structure_kind="text", preserve_components=True)


def _merge_same_kind_sections(left_section: SectionDraft, right_section: SectionDraft) -> SectionDraft:
    """合併兩個同類型 section，保留 heading 與原始 offset 範圍。

    參數：
    - `left_section`：前段 section。
    - `right_section`：後段 section。

    回傳：
    - `SectionDraft`：合併後但尚未重新正規化 index/offset 的 section。
    """

    return _merge_section_sequence(left_section, right_section, structure_kind=left_section.structure_kind)


def _merge_sections(left_section: SectionDraft, right_section: SectionDraft) -> SectionDraft:
    """合併兩個相鄰文字 parent section 草稿。

    參數：
    - `left_section`：前段 section。
    - `right_section`：後段 section。

    回傳：
    - `SectionDraft`：尚未重新計算 index 與 offset 的合併結果。
    """

    return _merge_section_sequence(left_section, right_section, structure_kind="text")


def _merge_section_sequence(
    *sections: SectionDraft,
    structure_kind: str,
    preserve_components: bool = False,
) -> SectionDraft:
    """依序合併多個 sections，並保留 component offsets。

    參數：
    - `sections`：要合併的 sections。
    - `structure_kind`：合併後 parent 的結構型別。

    回傳：
    - `SectionDraft`：合併後但尚未重新正規化的 section。
    """

    merged_content_parts: list[str] = []
    merged_components: list[SectionComponent] = []
    cursor = 0
    heading: str | None = None
    heading_path: str | None = None
    heading_level: int | None = None

    for index, section in enumerate(sections):
        if index > 0 and merged_content_parts and section.content:
            merged_content_parts.append("\n\n")
            cursor += 2
        merged_content_parts.append(section.content)
        heading = _merge_headings(heading, section.heading)
        heading_path = _merge_section_heading_paths(heading_path, section.heading_path)
        heading_level = _pick_heading_level(heading_level, section.heading_level)
        if preserve_components:
            for component in _section_components(section):
                merged_components.append(
                    SectionComponent(
                        structure_kind=component.structure_kind,
                        heading=component.heading,
                        content=component.content,
                        start_offset=cursor + component.start_offset,
                        end_offset=cursor + component.end_offset,
                        page_start=component.page_start,
                        page_end=component.page_end,
                        regions=component.regions,
                    )
                )
        cursor += len(section.content)

    return SectionDraft(
        section_index=sections[0].section_index if sections else 0,
        structure_kind=structure_kind,
        heading=heading,
        content="".join(merged_content_parts),
        start_offset=sections[0].start_offset if sections else 0,
        end_offset=sections[-1].end_offset if sections else 0,
        heading_path=heading_path,
        section_path_text=_build_section_path_text(
            heading_path=heading_path,
            section_index=sections[0].section_index if sections else 0,
        ),
        heading_level=heading_level,
        components=merged_components if preserve_components else None,
        page_start=min((section.page_start for section in sections if section.page_start is not None), default=None),
        page_end=max((section.page_end for section in sections if section.page_end is not None), default=None),
        regions=[
            ParsedRegion(
                page_number=region.page_number,
                region_order=index,
                bbox_left=region.bbox_left,
                bbox_bottom=region.bbox_bottom,
                bbox_right=region.bbox_right,
                bbox_top=region.bbox_top,
            )
            for index, region in enumerate(region for section in sections for region in (section.regions or []))
        ]
        or None,
    )


def _section_components(section: SectionDraft) -> list[SectionComponent]:
    """回傳 section 內可供 child chunking 使用的 component blocks。

    參數：
    - `section`：目標 parent section。

    回傳：
    - `list[SectionComponent]`：component 清單。
    """

    if section.components:
        return section.components
    return [
        SectionComponent(
            structure_kind=section.structure_kind,
            heading=section.heading,
            content=section.content,
            start_offset=0,
            end_offset=len(section.content),
            page_start=section.page_start,
            page_end=section.page_end,
            regions=section.regions,
        )
    ]


def _merge_headings(left_heading: str | None, right_heading: str | None) -> str | None:
    """合併兩個 parent section 的 heading。

    參數：
    - `left_heading`：前段 heading。
    - `right_heading`：後段 heading。

    回傳：
    - `str | None`：合併後的 heading；若兩側都沒有則回傳空值。
    """

    if left_heading and right_heading and left_heading != right_heading:
        left_segments = _split_heading_segments(left_heading)
        right_segments = _split_heading_segments(right_heading)
        if _is_heading_prefix(left_segments, right_segments):
            return left_heading
        if _is_heading_prefix(right_segments, left_segments):
            return right_heading
        return f"{left_heading} / {right_heading}"
    return left_heading or right_heading


def _merge_section_heading_paths(left_path: str | None, right_path: str | None) -> str | None:
    """合併多個 section 的 heading path。"""

    if left_path and right_path:
        left_segments = _split_heading_segments(left_path)
        right_segments = _split_heading_segments(right_path)
        if _is_heading_prefix(left_segments, right_segments):
            return right_path
        if _is_heading_prefix(right_segments, left_segments):
            return left_path
        return f"{left_path} / {right_path}"
    return left_path or right_path


def _pick_heading_level(left_level: int | None, right_level: int | None) -> int | None:
    """在合併 section 時保留較深的 heading level。"""

    if left_level is None:
        return right_level
    if right_level is None:
        return left_level
    return max(left_level, right_level)


def _build_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
    display_content_start: int,
) -> list[ChunkDraft]:
    """將 parent section 切成 child chunks。

    參數：
    - `section`：待切分的 parent section。
    - `position_counter`：整份文件的全域 position 計數器。
    - `config`：chunking 參數設定。
    - `display_content_start`：此 section 內容在 display_text 中的起始 offset。

    回傳：
    - `list[ChunkDraft]`：此 section 下的 child chunk 草稿。
    """

    components = _section_components(section)
    if len(components) == 1 and components[0].structure_kind == section.structure_kind:
        if section.structure_kind == "table":
            return _build_table_child_chunks(
                section=section,
                position_counter=position_counter,
                config=config,
                display_content_start=display_content_start,
                starting_child_index=0,
            )
        return _build_text_child_chunks(
            section=section,
            position_counter=position_counter,
            config=config,
            display_content_start=display_content_start,
            starting_child_index=0,
        )

    children: list[ChunkDraft] = []
    next_child_index = 0
    for component in components:
        component_display_content_start = display_content_start + component.start_offset
        component_section = SectionDraft(
            section_index=section.section_index,
            structure_kind=component.structure_kind,
            heading=component.heading or section.heading,
            content=component.content,
            start_offset=section.start_offset + component.start_offset,
            end_offset=section.start_offset + component.end_offset,
            heading_path=section.heading_path,
            section_path_text=section.section_path_text,
            heading_level=section.heading_level,
            components=[component],
            page_start=component.page_start,
            page_end=component.page_end,
            regions=component.regions,
        )
        if component.structure_kind == "table":
            component_children = _build_table_child_chunks(
                section=component_section,
                position_counter=position_counter,
                config=config,
                display_content_start=component_display_content_start,
                starting_child_index=next_child_index,
            )
        else:
            component_children = _build_text_child_chunks(
                section=component_section,
                position_counter=position_counter,
                config=config,
                display_content_start=component_display_content_start,
                starting_child_index=next_child_index,
            )
        children.extend(component_children)
        next_child_index += len(component_children)
    return children


def _build_text_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
    display_content_start: int,
    starting_child_index: int,
) -> list[ChunkDraft]:
    """將文字 parent section 切成 child chunks。

    參數：
    - `section`：待切分的文字 parent section。
    - `position_counter`：整份文件的全域 position 計數器。
    - `config`：chunking 參數設定。
    - `display_content_start`：此 section 內容在 display_text 中的起始 offset。

    回傳：
    - `list[ChunkDraft]`：文字 child chunk 草稿。
    """

    children: list[ChunkDraft] = []
    child_index = starting_child_index
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.target_child_chunk_size,
        chunk_overlap=config.child_chunk_overlap,
        add_start_index=True,
        strip_whitespace=False,
    )

    split_contents = _split_fact_heavy_text_content(section=section, config=config)
    if not split_contents:
        split_contents = _split_text_content(section.content, splitter=splitter)

    for relative_start, chunk_content in split_contents:
        display_start = display_content_start + relative_start
        display_end = display_start + len(chunk_content)
        children.append(
            ChunkDraft(
                chunk_type="child",
                structure_kind="text",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=child_index,
                heading=section.heading,
                content=chunk_content,
                content_preview=_build_content_preview(chunk_content, config=config),
                char_count=len(chunk_content),
                start_offset=display_start,
                end_offset=display_end,
                heading_path=None,
                section_path_text=None,
                heading_level=None,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        )
        child_index += 1

    return children


def _split_text_content(content: str, *, splitter: RecursiveCharacterTextSplitter) -> list[tuple[int, str]]:
    """將文字內容切成帶相對 offset 的 child 內容。

    參數：
    - `content`：文字 parent 內容。
    - `splitter`：LangChain splitter 實例。

    回傳：
    - `list[tuple[int, str]]`：每個 child 的相對起始 offset 與內容。
    """

    split_documents = splitter.create_documents([content])
    children: list[tuple[int, str]] = []
    for document in split_documents:
        raw_content = document.page_content
        start_index = int(document.metadata.get("start_index", 0))
        leading_trim = len(raw_content) - len(raw_content.lstrip())
        trailing_trim = len(raw_content) - len(raw_content.rstrip())
        normalized_end = len(raw_content) - trailing_trim
        if normalized_end <= leading_trim:
            continue
        chunk_content = raw_content[leading_trim:normalized_end]
        if not chunk_content.strip():
            continue
        children.append((start_index + leading_trim, chunk_content))
    return children


FACT_HEAVY_HEADING_PATTERN = re.compile(
    r"(dataset|experimental setup|evaluation metrics|metrics|setup)",
    re.IGNORECASE,
)


def _split_fact_heavy_text_content(*, section: SectionDraft, config: ChunkingConfig) -> list[tuple[int, str]]:
    """在 fact-heavy section 上做較細的 evidence-centric child refinement。

    參數：
    - `section`：待切分的文字 section。
    - `config`：chunking 參數設定。

    回傳：
    - `list[tuple[int, str]]`：若命中 refinement 條件則回傳較細 child；否則回傳空列表。
    """

    if not config.fact_heavy_refinement_enabled:
        return []

    heading = (section.heading or "").strip()
    if not heading or not FACT_HEAVY_HEADING_PATTERN.search(heading):
        return []

    if len(section.content) < 240:
        return []

    sentence_chunks = _split_into_sentence_windows(section.content)
    refined_chunks = [(start, chunk) for start, chunk in sentence_chunks if chunk.strip()]
    return refined_chunks if len(refined_chunks) > 1 else []


def _split_into_sentence_windows(content: str) -> list[tuple[int, str]]:
    """依句界與空行將文字切成較小的 evidence windows。

    參數：
    - `content`：原始 section 內容。

    回傳：
    - `list[tuple[int, str]]`：每段 window 的相對起始 offset 與內容。
    """

    windows: list[tuple[int, str]] = []
    pattern = re.compile(r".*?(?:[。！？.!?](?:\s+|$)|\n\n|$)", re.DOTALL)
    for match in pattern.finditer(content):
        chunk = match.group(0)
        if not chunk or not chunk.strip():
            continue
        normalized = chunk.strip()
        start_offset = match.start() + (len(chunk) - len(chunk.lstrip()))
        windows.append((start_offset, normalized))
    return windows


def _build_table_child_chunks(
    *,
    section: SectionDraft,
    position_counter: count[int],
    config: ChunkingConfig,
    display_content_start: int,
    starting_child_index: int,
) -> list[ChunkDraft]:
    """將表格 parent section 切成 table-aware child chunks。

    參數：
    - `section`：待切分的表格 parent section。
    - `position_counter`：整份文件的全域 position 計數器。
    - `config`：chunking 參數設定。
    - `display_content_start`：此 section 內容在 display_text 中的起始 offset。

    回傳：
    - `list[ChunkDraft]`：表格 child chunk 草稿。
    """

    if len(section.content) <= config.table_preserve_max_chars:
        return [
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=starting_child_index,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=display_content_start,
                end_offset=display_content_start + len(section.content),
                heading_path=None,
                section_path_text=None,
                heading_level=None,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        ]

    table_parts = _parse_markdown_table_content(section.content)
    if not table_parts.data_rows:
        return [
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=starting_child_index,
                heading=section.heading,
                content=section.content,
                content_preview=_build_content_preview(section.content, config=config),
                char_count=len(section.content),
                start_offset=display_content_start,
                end_offset=display_content_start + len(section.content),
                heading_path=None,
                section_path_text=None,
                heading_level=None,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        ]

    children: list[ChunkDraft] = []
    for group_index, row_group in enumerate(
        _group_table_rows(data_rows=table_parts.data_rows, max_rows_per_child=config.table_max_rows_per_child)
    ):
        row_start = row_group[0].start_offset
        row_end = row_group[-1].end_offset
        child_content = "\n".join(
            [table_parts.header_row, table_parts.delimiter_row, *(row.content for row in row_group)]
        ).strip()
        children.append(
            ChunkDraft(
                chunk_type="child",
                structure_kind="table",
                position=next(position_counter),
                section_index=section.section_index,
                child_index=starting_child_index + group_index,
                heading=section.heading,
                content=child_content,
                content_preview=_build_content_preview(child_content, config=config),
                char_count=len(child_content),
                start_offset=display_content_start + row_start,
                end_offset=display_content_start + row_end,
                heading_path=None,
                section_path_text=None,
                heading_level=None,
                page_start=section.page_start,
                page_end=section.page_end,
                regions=section.regions,
            )
        )
    return children


def _render_display_heading_prefix(heading: str | None) -> str:
    """將 section heading 渲染為 display_text 用的 markdown 標題前綴。

    參數：
    - `heading`：section heading；允許為空值。

    回傳：
    - `str`：供顯示使用的標題前綴；若沒有 heading 則回傳空字串。
    """

    normalized_heading = re.sub(r"\s+", " ", heading or "").strip()
    if not normalized_heading:
        return ""
    return f"## {normalized_heading}\n\n"


def _include_verified_heading_prefix_in_parent_offsets(
    *,
    parent_chunks: list[ChunkDraft],
    display_text: str,
) -> None:
    """只在 display_text 前綴實際匹配時，將 parent offset 擴到包含 heading。

    參數：
    - `parent_chunks`：待調整的 parent chunk 草稿清單。
    - `display_text`：本次 materialize 後的完整顯示文字。

    回傳：
    - `None`：僅原地更新符合條件的 parent chunk offset。
    """

    for chunk in parent_chunks:
        heading_prefix = _render_display_heading_prefix(chunk.heading)
        if not heading_prefix:
            continue

        prefix_start = chunk.start_offset - len(heading_prefix)
        if prefix_start < 0:
            continue

        # 只有當 materialized display_text 中，chunk 前面的字串真的就是該 heading
        # 的顯示前綴時，才把 parent locator 擴張到包含 heading。
        if display_text[prefix_start:chunk.start_offset] != heading_prefix:
            continue

        chunk.start_offset = prefix_start


@dataclass(slots=True)
class _TableRow:
    """表格資料列與其在 parent content 中的 offset。"""

    # 資料列文字內容。
    content: str
    # 資料列相對於表格內容的起始 offset。
    start_offset: int
    # 資料列相對於表格內容的結束 offset。
    end_offset: int


@dataclass(slots=True)
class _ParsedTableContent:
    """表格內容拆解結果。"""

    # 表頭列文字。
    header_row: str
    # delimiter 列文字。
    delimiter_row: str
    # 資料列清單。
    data_rows: list[_TableRow]


def _parse_markdown_table_content(content: str) -> _ParsedTableContent:
    """將 Markdown table 文本拆成 header、delimiter 與資料列。

    參數：
    - `content`：Markdown table 文字。

    回傳：
    - `_ParsedTableContent`：拆解後的表格內容。
    """

    lines = content.splitlines()
    if len(lines) < 2:
        return _ParsedTableContent(header_row=content, delimiter_row="| --- |", data_rows=[])

    line_offsets = _compute_line_offsets(content)
    data_rows = [
        _TableRow(
            content=line,
            start_offset=line_offsets[index],
            end_offset=line_offsets[index] + len(line),
        )
        for index, line in enumerate(lines[2:], start=2)
        if line.strip()
    ]
    return _ParsedTableContent(header_row=lines[0], delimiter_row=lines[1], data_rows=data_rows)


def _compute_line_offsets(content: str) -> list[int]:
    """計算每一行在原始字串中的相對起始 offset。

    參數：
    - `content`：原始字串。

    回傳：
    - `list[int]`：每一行的起始 offset。
    """

    offsets: list[int] = []
    cursor = 0
    for line in content.splitlines():
        offsets.append(cursor)
        cursor += len(line) + 1
    return offsets


def _group_table_rows(*, data_rows: list[_TableRow], max_rows_per_child: int) -> list[list[_TableRow]]:
    """將表格資料列依固定列數分組。

    參數：
    - `data_rows`：表格資料列。
    - `max_rows_per_child`：每個 child 最多資料列數。

    回傳：
    - `list[list[_TableRow]]`：分組後的資料列。
    """

    if not data_rows:
        return []
    return [data_rows[index : index + max_rows_per_child] for index in range(0, len(data_rows), max_rows_per_child)]


def _build_content_preview(content: str, *, config: ChunkingConfig) -> str:
    """建立固定長度的 chunk 摘要。

    參數：
    - `content`：原始 chunk 內容。
    - `config`：chunking 參數設定。

    回傳：
    - `str`：固定長度、去除多餘空白的摘要字串。
    """

    normalized = " ".join(content.split())
    return normalized[: config.content_preview_length]
