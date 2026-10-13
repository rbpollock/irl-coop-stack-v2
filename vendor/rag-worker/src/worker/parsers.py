"""Worker ingest 流程使用的 block-aware parser。"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile


# 本 phase 真正支援解析的副檔名。
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".html", ".pdf", ".xlsx", ".docx", ".pptx"}

# 支援的 PDF parser provider 名稱。
SUPPORTED_PDF_PARSER_PROVIDERS = {"local", "llamaparse", "opendataloader"}

# 可在 reindex 時重用的 parse artifact 檔名。
REUSABLE_PARSE_ARTIFACT_FILE_NAMES = {
    "pdf:local": "pdf.unstructured.extracted.html",
    "pdf:opendataloader": "opendataloader.json",
    "pdf:llamaparse": "llamaparse.cleaned.md",
    "xlsx": "xlsx.extracted.html",
    "docx": "docx.extracted.html",
    "pptx": "pptx.extracted.html",
}

# Markdown heading 判定規則。
MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(?P<heading>.+?)\s*$")

# Markdown table delimiter 判定規則。
MARKDOWN_TABLE_DELIMITER_PATTERN = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$")

# Markdown table cell 分隔規則；忽略 escaped pipe。
MARKDOWN_TABLE_CELL_SPLIT_PATTERN = re.compile(r"(?<!\\)\|")

# PDF Markdown 常見頁碼噪音。
PDF_PAGE_LABEL_PATTERN = re.compile(r"^\s*(?:page|p\.)\s+\d+(?:\s*(?:/|of)\s*\d+)?\s*$", re.IGNORECASE)

# PDF Markdown 常見頁面分隔符噪音。
PDF_PAGE_SEPARATOR_PATTERN = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

# local PDF parser 使用的 Unstructured strategy。
LOCAL_PDF_UNSTRUCTURED_STRATEGY = "fast"


@dataclass(slots=True)
class PdfParserConfig:
    """PDF parser provider 使用的設定。"""

    # 要使用的 PDF parser provider 名稱。
    provider: str = "opendataloader"
    # 是否要求 OpenDataLoader 儘量使用 tagged PDF struct tree。
    opendataloader_use_struct_tree: bool = True
    # 是否要求 OpenDataLoader 以 quiet mode 執行。
    opendataloader_quiet: bool = True
    # LlamaParse API 金鑰。
    llamaparse_api_key: str | None = None
    # 是否要求 LlamaParse 不快取文件內容。
    llamaparse_do_not_cache: bool = True
    # 是否啟用跨頁延續表格合併。
    llamaparse_merge_continued_tables: bool = False


@dataclass(slots=True)
class ParsedRegion:
    """單一文字或表格片段對應的 PDF 區域定位資訊。"""

    # 所屬頁碼，從 1 開始。
    page_number: int
    # 區域在同一 block / chunk 內的順序。
    region_order: int
    # 左邊界座標。
    bbox_left: float
    # 下邊界座標。
    bbox_bottom: float
    # 右邊界座標。
    bbox_right: float
    # 上邊界座標。
    bbox_top: float


@dataclass(slots=True)
class ParsedBlock:
    """Parser 輸出的結構化內容區塊。"""

    # block 內容型別。
    block_kind: str
    # 區塊所屬 heading。
    heading: str | None
    # 區塊文字內容。
    content: str
    # 區塊在 normalized text 的起始 offset。
    start_offset: int
    # 區塊在 normalized text 的結束 offset。
    end_offset: int
    # PDF semantic element 類型；非 PDF 可為空值。
    element_kind: str | None = None
    # heading 等級；若無則為空值。
    heading_level: int | None = None
    # 此 block 橫跨的起始頁碼。
    page_start: int | None = None
    # 此 block 橫跨的結束頁碼。
    page_end: int | None = None
    # 此 block 關聯的 PDF regions。
    regions: list[ParsedRegion] | None = None


@dataclass(slots=True)
class ParseArtifact:
    """Parser 產生並需持久化的中介產物。"""

    # artifact 檔名。
    file_name: str
    # artifact MIME 類型。
    content_type: str
    # artifact 原始內容。
    payload: bytes


@dataclass(slots=True)
class ParsedDocument:
    """Parser 輸出的標準化文件內容。"""

    # normalize 後的整份文字內容。
    normalized_text: str
    # 原始來源格式。
    source_format: str
    # parser 辨識出的結構化 blocks。
    blocks: list[ParsedBlock]
    # parser 產生並需持久化的中介 artifact。
    artifacts: list[ParseArtifact]


@dataclass(slots=True)
class _OpenDataLoaderElement:
    """OpenDataLoader JSON element 的內部正規化表示。"""

    # element 類型名稱。
    element_kind: str
    # element 文字內容。
    content: str
    # element heading。
    heading: str | None
    # heading 等級。
    heading_level: int | None
    # element 起始頁碼。
    page_start: int | None
    # element 結束頁碼。
    page_end: int | None
    # element 關聯的 regions。
    regions: list[ParsedRegion]


@dataclass(slots=True)
class OpenDataLoaderRawRegion:
    """OpenDataLoader artifact 中的原始 region payload。"""

    # 所屬頁碼。
    page_number: int | None
    # 左邊界座標。
    left: float | None
    # 下邊界座標。
    bottom: float | None
    # 右邊界座標。
    right: float | None
    # 上邊界座標。
    top: float | None


@dataclass(slots=True)
class OpenDataLoaderRawElement:
    """OpenDataLoader artifact 中的原始 element payload。"""

    # element 類型名稱。
    element_kind: str
    # 優先使用的 Markdown 文字。
    markdown: str | None
    # fallback 純文字內容。
    text: str | None
    # 另一種常見內容欄位。
    content: str | None
    # element heading。
    heading: str | None
    # heading 等級。
    heading_level: int | None
    # 單頁時的頁碼。
    page_number: int | None
    # element 起始頁碼。
    page_start: int | None
    # element 結束頁碼。
    page_end: int | None
    # 關聯的原始 regions。
    regions: list[OpenDataLoaderRawRegion]


@dataclass(slots=True)
class OpenDataLoaderArtifactPayload:
    """可持久化與可重建的 OpenDataLoader artifact。"""

    # artifact schema 版本。
    schema_version: str
    # 供重建 ParsedDocument 使用的乾淨 Markdown。
    cleaned_markdown: str
    # 原始 Markdown；若來源提供則保留。
    markdown: str | None
    # 已標準化的 OpenDataLoader elements。
    elements: list[OpenDataLoaderRawElement]


def parse_document(
    *,
    file_name: str,
    payload: bytes,
    pdf_config: PdfParserConfig | None = None,
) -> ParsedDocument:
    """依副檔名選擇 parser，並回傳 block-aware 結果。

    參數：
    - `file_name`：使用者上傳時的原始檔名。
    - `payload`：從物件儲存讀出的原始位元組內容。
    - `pdf_config`：PDF parser provider 設定；非 PDF 檔案時可省略。

    回傳：
    - `ParsedDocument`：解析後的標準化文件內容。
    """

    lower_name = file_name.lower()
    if lower_name.endswith(".txt"):
        return _parse_txt_document(payload=payload)
    if lower_name.endswith(".md"):
        return _parse_markdown_document(payload=payload)
    if lower_name.endswith(".html"):
        return _parse_html_document(payload=payload)
    if lower_name.endswith(".pdf"):
        return _parse_pdf_document(payload=payload, pdf_config=pdf_config or PdfParserConfig())
    if lower_name.endswith(".xlsx"):
        return _parse_xlsx_document(payload=payload)
    if lower_name.endswith(".docx"):
        return _parse_docx_document(payload=payload)
    if lower_name.endswith(".pptx"):
        return _parse_pptx_document(payload=payload)
    raise ValueError("目前尚未支援此檔案類型的解析。")


def get_reusable_parse_artifact_names(
    *,
    file_name: str,
    pdf_config: PdfParserConfig | None = None,
) -> list[str]:
    """回傳指定文件可重用的 parse artifact 檔名候選。

    參數：
    - `file_name`：原始文件檔名。
    - `pdf_config`：PDF parser provider 設定；非 PDF 時可省略。

    回傳：
    - `list[str]`：可直接拿來重建 ParsedDocument 的 artifact 檔名清單。
    """

    lower_name = file_name.lower()
    if lower_name.endswith(".pdf"):
        provider = (pdf_config.provider if pdf_config is not None else PdfParserConfig().provider).strip().lower()
        artifact_name = REUSABLE_PARSE_ARTIFACT_FILE_NAMES.get(f"pdf:{provider}")
        return [artifact_name] if artifact_name is not None else []
    if lower_name.endswith(".xlsx"):
        return [REUSABLE_PARSE_ARTIFACT_FILE_NAMES["xlsx"]]
    if lower_name.endswith(".docx"):
        return [REUSABLE_PARSE_ARTIFACT_FILE_NAMES["docx"]]
    if lower_name.endswith(".pptx"):
        return [REUSABLE_PARSE_ARTIFACT_FILE_NAMES["pptx"]]
    return []


def parse_document_from_artifact(
    *,
    file_name: str,
    artifact_file_name: str,
    payload: bytes,
    pdf_config: PdfParserConfig | None = None,
) -> ParsedDocument:
    """以既有 parse artifact 重建 ParsedDocument，避免重跑 parser。

    參數：
    - `file_name`：原始文件檔名，用於判定來源格式。
    - `artifact_file_name`：artifact 檔名。
    - `payload`：artifact 原始位元組內容。
    - `pdf_config`：PDF parser provider 設定；非 PDF 時可省略。

    回傳：
    - `ParsedDocument`：依 artifact 內容重建的標準化文件內容。
    """

    if artifact_file_name.endswith(".md"):
        text = _decode_payload(payload=payload).strip()
        return _parse_markdown_text(text=text, source_format=_resolve_artifact_source_format(file_name=file_name))

    if artifact_file_name.endswith(".json"):
        artifact_payload = _decode_json_payload(payload=payload)
        return _parse_opendataloader_json_artifact_payload(
            artifact_payload=artifact_payload,
            source_format=_resolve_artifact_source_format(file_name=file_name),
        )

    if artifact_file_name.endswith(".html"):
        text = _decode_payload(payload=payload)
        return _materialize_blocks(
            source_format=_resolve_artifact_source_format(file_name=file_name, pdf_config=pdf_config),
            block_inputs=_extract_html_block_inputs(text=text),
        )

    raise ValueError(f"不支援的 parse artifact 類型：{artifact_file_name}")


def _resolve_artifact_source_format(
    *,
    file_name: str,
    pdf_config: PdfParserConfig | None = None,
) -> str:
    """依原始文件副檔名決定 artifact 重建後的 source_format。"""

    lower_name = file_name.lower()
    if lower_name.endswith(".pdf"):
        return "pdf"
    if lower_name.endswith(".xlsx"):
        return "xlsx"
    if lower_name.endswith(".docx"):
        return "docx"
    if lower_name.endswith(".pptx"):
        return "pptx"
    if lower_name.endswith(".html"):
        return "html"
    if lower_name.endswith(".md"):
        return "markdown"
    if lower_name.endswith(".txt"):
        return "txt"

    provider = (pdf_config.provider if pdf_config is not None else "").strip().lower()
    if provider in SUPPORTED_PDF_PARSER_PROVIDERS:
        return "pdf"
    raise ValueError("無法判定 parse artifact 的來源格式。")


def _decode_payload(*, payload: bytes) -> str:
    """將檔案位元組解碼為 UTF-8 文字。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `str`：解碼後文字。
    """

    text = payload.decode("utf-8")
    if not text.strip():
        raise ValueError("文件內容不可為空白。")
    return text


def _decode_json_payload(*, payload: bytes) -> OpenDataLoaderArtifactPayload:
    """將 JSON artifact 解碼為物件。"""

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON parse artifact 內容無法解碼。") from exc
    if not isinstance(decoded, dict):
        raise ValueError("JSON parse artifact 格式不正確。")
    return _normalize_opendataloader_artifact_payload(raw_payload=decoded)


def _parse_txt_document(*, payload: bytes) -> ParsedDocument:
    """解析 TXT 文件。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：包含單一 text block 的結果。
    """

    normalized_text = _decode_payload(payload=payload).strip()
    return _materialize_blocks(source_format="txt", block_inputs=[("text", None, normalized_text)])


def _parse_markdown_document(*, payload: bytes) -> ParsedDocument:
    """解析 Markdown 文件，辨識 heading、文字與表格 blocks。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：Markdown block-aware 結果。
    """

    text = _decode_payload(payload=payload).strip()
    return _parse_markdown_text(text=text, source_format="markdown")


def _parse_markdown_text(*, text: str, source_format: str) -> ParsedDocument:
    """解析 Markdown 字串，辨識 heading、文字與表格 blocks。

    參數：
    - `text`：已解碼的 Markdown 文字。
    - `source_format`：來源格式名稱。

    回傳：
    - `ParsedDocument`：Markdown block-aware 結果。
    """

    if not text.strip():
        raise ValueError("文件內容不可為空白。")

    lines = text.splitlines()
    block_inputs: list[tuple[str, str | None, str]] = []
    current_heading: str | None = None
    current_text_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        heading_match = MARKDOWN_HEADING_PATTERN.match(line)
        if heading_match:
            _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
            current_heading = heading_match.group("heading").strip()
            current_text_lines = []
            index += 1
            continue

        if _is_markdown_table_start(lines=lines, start_index=index, source_format=source_format):
            _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
            current_text_lines = []
            table_lines, next_index = _consume_markdown_table(lines=lines, start_index=index)
            block_inputs.append(("table", current_heading, "\n".join(table_lines).strip()))
            index = next_index
            continue

        current_text_lines.append(line)
        index += 1

    _append_markdown_text_block(block_inputs=block_inputs, heading=current_heading, lines=current_text_lines)
    if not block_inputs:
        block_inputs.append(("text", None, text))
    return _materialize_blocks(source_format=source_format, block_inputs=block_inputs)


def _parse_pdf_document(*, payload: bytes, pdf_config: PdfParserConfig) -> ParsedDocument:
    """依 provider 解析 PDF，再交由現有 Markdown parser 處理。

    參數：
    - `payload`：PDF 原始位元組內容。
    - `pdf_config`：PDF parser provider 設定。

    回傳：
    - `ParsedDocument`：解析後的標準化文件內容。
    """

    provider = pdf_config.provider.strip().lower()
    if provider not in SUPPORTED_PDF_PARSER_PROVIDERS:
        raise ValueError(f"不支援的 PDF parser provider：{pdf_config.provider}")

    if provider == "local":
        elements = _extract_pdf_elements_with_unstructured(payload=payload)
        block_inputs, artifacts = _build_pdf_block_inputs_from_unstructured_elements(elements=elements)
        return _materialize_blocks(
            source_format="pdf",
            block_inputs=block_inputs,
            artifacts=artifacts,
        )

    if provider == "opendataloader":
        markdown, json_payload = _extract_pdf_content_with_opendataloader(payload=payload, pdf_config=pdf_config)
        cleaned_markdown = _clean_pdf_markdown(markdown=markdown, provider_name="OpenDataLoader")
        artifact_payload = _build_opendataloader_artifact_payload(
            raw_payload=json_payload,
            cleaned_markdown=cleaned_markdown,
        )
        parsed_document = _parse_opendataloader_payload(markdown=cleaned_markdown, artifact_payload=artifact_payload)
        return ParsedDocument(
            normalized_text=parsed_document.normalized_text,
            source_format=parsed_document.source_format,
            blocks=parsed_document.blocks,
            artifacts=[
                _build_json_artifact(
                    file_name="opendataloader.json",
                    payload_obj=artifact_payload,
                ),
                _build_text_artifact(
                    file_name="opendataloader.cleaned.md",
                    content_type="text/markdown; charset=utf-8",
                    text=cleaned_markdown,
                ),
            ],
        )

    markdown = _extract_pdf_markdown_with_llamaparse(payload=payload, pdf_config=pdf_config)
    cleaned_markdown = _clean_llamaparse_markdown(markdown)
    parsed_document = _parse_markdown_text(text=cleaned_markdown, source_format="pdf")
    return ParsedDocument(
        normalized_text=parsed_document.normalized_text,
        source_format=parsed_document.source_format,
        blocks=parsed_document.blocks,
        artifacts=[
            _build_text_artifact(
                file_name="llamaparse.raw.md",
                content_type="text/markdown; charset=utf-8",
                text=markdown,
            ),
            _build_text_artifact(
                file_name="llamaparse.cleaned.md",
                content_type="text/markdown; charset=utf-8",
                text=cleaned_markdown,
            ),
        ],
    )


def _append_markdown_text_block(
    *,
    block_inputs: list[tuple[str, str | None, str]],
    heading: str | None,
    lines: list[str],
) -> None:
    """將 Markdown 累積中的文字內容附加為 text block。

    參數：
    - `block_inputs`：目前累積的 block 輸入。
    - `heading`：當前 heading。
    - `lines`：當前文字行列表。

    回傳：
    - `None`：此函式只在有有效內容時附加 block。
    """

    content = "\n".join(lines).strip()
    if content:
        block_inputs.append(("text", heading, content))


def _is_markdown_table_start(*, lines: list[str], start_index: int, source_format: str) -> bool:
    """判定指定位置是否為 Markdown table 起點。

    參數：
    - `lines`：整份 Markdown 行列表。
    - `start_index`：欲檢查的起始行位置。
    - `source_format`：目前解析的來源格式，用於套用格式特定的容錯規則。

    回傳：
    - `bool`：若為 GFM table 起點則回傳真。
    """

    if start_index + 1 >= len(lines):
        return False
    header_line = lines[start_index].rstrip()
    delimiter_line = lines[start_index + 1].rstrip()
    return "|" in header_line and _is_markdown_table_delimiter_row(
        delimiter_line=delimiter_line,
        allow_short_hyphen_cells=source_format == "pdf",
    )


def _is_markdown_table_delimiter_row(*, delimiter_line: str, allow_short_hyphen_cells: bool) -> bool:
    """判定指定行是否可視為 Markdown table delimiter row。

    參數：
    - `delimiter_line`：欲檢查的 delimiter 行。
    - `allow_short_hyphen_cells`：是否容忍 PDF provider 常見的單一 `-` delimiter cell。

    回傳：
    - `bool`：若符合 delimiter row 規則則回傳真。
    """

    if MARKDOWN_TABLE_DELIMITER_PATTERN.match(delimiter_line):
        return True
    if not allow_short_hyphen_cells:
        return False

    delimiter_cells = _split_markdown_table_row(delimiter_line)
    if not delimiter_cells:
        return False

    for cell in delimiter_cells:
        compact = cell.replace(" ", "")
        if not compact or "-" not in compact:
            return False
        stripped = compact.strip(":")
        if not stripped or any(character != "-" for character in stripped):
            return False
    return True


def _consume_markdown_table(*, lines: list[str], start_index: int) -> tuple[list[str], int]:
    """讀取從指定位置開始的整張 Markdown table。

    參數：
    - `lines`：整份 Markdown 行列表。
    - `start_index`：table 起始行位置。

    回傳：
    - `tuple[list[str], int]`：table 行列表與下一個尚未消耗的行索引。
    """

    table_lines = [lines[start_index].rstrip(), lines[start_index + 1].rstrip()]
    index = start_index + 2
    while index < len(lines):
        candidate = lines[index].rstrip()
        if not candidate.strip() or "|" not in candidate:
            break
        table_lines.append(candidate)
        index += 1
    return _normalize_markdown_table_lines(table_lines), index


def _normalize_markdown_table_lines(lines: list[str]) -> list[str]:
    """將 Markdown table 正規化為穩定且精簡的 canonical 文字。

    參數：
    - `lines`：原始 Markdown table 行列表，至少包含 header 與 delimiter。

    回傳：
    - `list[str]`：移除 padding 空白並壓縮 delimiter 的 table 行列表。
    """

    if len(lines) < 2:
        return [line.rstrip() for line in lines]

    header_cells = _split_markdown_table_row(lines[0])
    delimiter_cells = _split_markdown_table_row(lines[1])
    data_rows = [_split_markdown_table_row(line) for line in lines[2:]]
    column_count = max(
        len(header_cells),
        len(delimiter_cells),
        *(len(row) for row in data_rows),
    )
    padded_header = _pad_markdown_table_row(header_cells, column_count=column_count)
    padded_data_rows = [_pad_markdown_table_row(row, column_count=column_count) for row in data_rows]
    normalized_delimiter = _normalize_markdown_table_delimiter(
        cells=delimiter_cells,
        column_count=column_count,
    )
    return [
        _render_markdown_row(padded_header),
        _render_markdown_delimiter_row(normalized_delimiter),
        *(_render_markdown_row(row) for row in padded_data_rows),
    ]


def _split_markdown_table_row(line: str) -> list[str]:
    """將 Markdown table row 拆為 cell 清單。

    參數：
    - `line`：單行 Markdown table 文字。

    回傳：
    - `list[str]`：去除欄位 padding 後的 cell 內容。
    """

    normalized_line = line.strip()
    if normalized_line.startswith("|"):
        normalized_line = normalized_line[1:]
    if normalized_line.endswith("|"):
        normalized_line = normalized_line[:-1]
    if not normalized_line:
        return []
    return [cell.strip() for cell in MARKDOWN_TABLE_CELL_SPLIT_PATTERN.split(normalized_line)]


def _pad_markdown_table_row(cells: list[str], *, column_count: int) -> list[str]:
    """補齊 Markdown row 的欄位數，維持穩定欄數。

    參數：
    - `cells`：原始 cell 清單。
    - `column_count`：目標欄位數。

    回傳：
    - `list[str]`：補齊空字串後的 cell 清單。
    """

    return cells + [""] * max(column_count - len(cells), 0)


def _normalize_markdown_table_delimiter(*, cells: list[str], column_count: int) -> list[str]:
    """將 delimiter row 壓成最短合法格式並保留對齊資訊。

    參數：
    - `cells`：原始 delimiter cell 清單。
    - `column_count`：目標欄位數。

    回傳：
    - `list[str]`：最小化後的 delimiter cell 清單。
    """

    normalized_cells: list[str] = []
    padded_cells = _pad_markdown_table_row(cells, column_count=column_count)
    for cell in padded_cells:
        compact = cell.replace(" ", "")
        align_left = compact.startswith(":")
        align_right = compact.endswith(":")
        core = "---"
        if align_left:
            core = ":" + core
        if align_right:
            core = core + ":"
        normalized_cells.append(core)
    return normalized_cells


def _parse_html_document(*, payload: bytes) -> ParsedDocument:
    """解析 HTML 文件，抽出文字與表格 blocks。

    參數：
    - `payload`：原始位元組內容。

    回傳：
    - `ParsedDocument`：HTML block-aware 結果。
    """

    text = _decode_payload(payload=payload)
    return _materialize_blocks(source_format="html", block_inputs=_extract_html_block_inputs(text=text))


def _parse_xlsx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 XLSX，並將 worksheet 轉為 table-aware blocks。

    參數：
    - `payload`：XLSX 原始位元組內容。

    回傳：
    - `ParsedDocument`：包含各 worksheet table blocks 的結果。
    """

    elements = _extract_xlsx_elements_with_unstructured(payload=payload)
    block_inputs: list[tuple[str, str | None, str]] = []
    html_fragments: list[tuple[str | None, str]] = []

    for element in elements:
        metadata = getattr(element, "metadata", None)
        heading = _normalize_worksheet_heading(metadata=metadata)
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        if text_as_html:
            html_fragments.append((heading, text_as_html))
            block_inputs.extend(
                _extract_html_block_inputs(text=f"<h1>{escape(heading)}</h1>\n{text_as_html}" if heading else text_as_html)
            )
            continue

        fallback_text = (getattr(element, "text", "") or "").strip()
        if fallback_text:
            block_inputs.append(("table", heading, fallback_text))

    if not block_inputs:
        raise ValueError("Unstructured XLSX parser 未回傳可用的 worksheet 內容。")

    artifacts = _build_html_artifacts(
        file_name="xlsx.extracted.html",
        html_fragments=html_fragments,
    )
    return _materialize_blocks(source_format="xlsx", block_inputs=block_inputs, artifacts=artifacts)


def _parse_docx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 DOCX，並映射為 block-aware 結果。

    參數：
    - `payload`：DOCX 原始位元組內容。

    回傳：
    - `ParsedDocument`：DOCX block-aware 結果。
    """

    elements = _extract_docx_elements_with_unstructured(payload=payload)
    block_inputs, artifacts = _build_office_block_inputs_from_unstructured_elements(
        elements=elements,
        artifact_file_name="docx.extracted.html",
    )
    return _materialize_blocks(
        source_format="docx",
        block_inputs=block_inputs,
        artifacts=artifacts,
    )


def _parse_pptx_document(*, payload: bytes) -> ParsedDocument:
    """使用 Unstructured 解析 PPTX，並映射為 block-aware 結果。

    參數：
    - `payload`：PPTX 原始位元組內容。

    回傳：
    - `ParsedDocument`：PPTX block-aware 結果。
    """

    elements = _extract_pptx_elements_with_unstructured(payload=payload)
    block_inputs, artifacts = _build_office_block_inputs_from_unstructured_elements(
        elements=elements,
        artifact_file_name="pptx.extracted.html",
    )
    return _materialize_blocks(
        source_format="pptx",
        block_inputs=block_inputs,
        artifacts=artifacts,
    )


def _extract_html_block_inputs(*, text: str) -> list[tuple[str, str | None, str]]:
    """將 HTML 字串轉為 block 輸入清單。

    參數：
    - `text`：HTML 原始文字。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    parser = _HTMLBlockParser()
    parser.feed(text)
    parser.close()
    if not parser.block_inputs:
        raise ValueError("無法從文件內容建立有效 chunks。")
    return parser.block_inputs


def _materialize_blocks(
    *,
    source_format: str,
    block_inputs: list[tuple[str, str | None, str]],
    artifacts: list[ParseArtifact] | None = None,
) -> ParsedDocument:
    """將 block 輸入轉為帶 offset 的 ParsedDocument。

    參數：
    - `source_format`：來源格式。
    - `block_inputs`：block 型別、heading 與內容清單。

    回傳：
    - `ParsedDocument`：帶有 normalized text 與 blocks 的結果。
    """

    blocks: list[ParsedBlock] = []
    normalized_parts: list[str] = []
    cursor = 0

    for block_kind, heading, raw_content in block_inputs:
        content = raw_content.strip()
        if not content:
            continue
        start_offset = cursor
        end_offset = start_offset + len(content)
        blocks.append(
            ParsedBlock(
                block_kind=block_kind,
                heading=heading,
                content=content,
                start_offset=start_offset,
                end_offset=end_offset,
            )
        )
        normalized_parts.append(content)
        cursor = end_offset + 2

    if not blocks:
        raise ValueError("無法從文件內容建立有效 chunks。")

    return ParsedDocument(
        normalized_text="\n\n".join(normalized_parts),
        source_format=source_format,
        blocks=blocks,
        artifacts=list(artifacts or []),
    )


def _normalize_opendataloader_artifact_payload(
    *,
    raw_payload: dict[str, object],
) -> OpenDataLoaderArtifactPayload:
    """將外部或既有 JSON artifact 正規化為內部 dataclass。"""

    cleaned_markdown = str(raw_payload.get("cleaned_markdown", "") or "").strip()
    markdown = raw_payload.get("markdown")
    if not cleaned_markdown and isinstance(markdown, str):
        cleaned_markdown = markdown.strip()
    return OpenDataLoaderArtifactPayload(
        schema_version=str(raw_payload.get("schema_version", "deep-agent-opendataloader-v1") or "deep-agent-opendataloader-v1"),
        cleaned_markdown=cleaned_markdown,
        markdown=str(markdown).strip() if isinstance(markdown, str) and markdown.strip() else None,
        elements=_extract_raw_opendataloader_elements_from_mapping(raw_payload=raw_payload),
    )


def _extract_raw_opendataloader_elements_from_mapping(
    *,
    raw_payload: dict[str, object],
) -> list[OpenDataLoaderRawElement]:
    """從任意 OpenDataLoader JSON mapping 萃取標準化 elements。"""

    raw_elements = raw_payload.get("elements")
    if not isinstance(raw_elements, list):
        raw_content = raw_payload.get("content")
        if isinstance(raw_content, dict):
            raw_elements = raw_content.get("elements")
        elif isinstance(raw_payload.get("document"), dict):
            raw_elements = raw_payload["document"].get("elements")
    if not isinstance(raw_elements, list):
        return []

    elements: list[OpenDataLoaderRawElement] = []
    for item in raw_elements:
        if not isinstance(item, dict):
            continue
        raw_regions = item.get("regions") or item.get("bboxes") or item.get("boxes")
        if isinstance(raw_regions, dict):
            raw_regions = [raw_regions]
        if raw_regions is None:
            raw_bbox = item.get("bbox")
            raw_regions = [raw_bbox] if isinstance(raw_bbox, dict) else []
        normalized_regions: list[OpenDataLoaderRawRegion] = []
        if isinstance(raw_regions, list):
            for region in raw_regions:
                if not isinstance(region, dict):
                    continue
                page_number = region.get("page_number") or region.get("page")
                left = region.get("left", region.get("x0"))
                bottom = region.get("bottom", region.get("y0"))
                right = region.get("right", region.get("x1"))
                top = region.get("top", region.get("y1"))
                normalized_regions.append(
                    OpenDataLoaderRawRegion(
                        page_number=page_number if isinstance(page_number, int) else None,
                        left=float(left) if isinstance(left, (int, float)) else None,
                        bottom=float(bottom) if isinstance(bottom, (int, float)) else None,
                        right=float(right) if isinstance(right, (int, float)) else None,
                        top=float(top) if isinstance(top, (int, float)) else None,
                    )
                )
        heading = item.get("heading")
        heading_level = item.get("heading_level") or item.get("level")
        elements.append(
            OpenDataLoaderRawElement(
                element_kind=str(item.get("type") or item.get("kind") or item.get("label") or "text"),
                markdown=str(item.get("markdown")).strip() if isinstance(item.get("markdown"), str) and str(item.get("markdown")).strip() else None,
                text=str(item.get("text")).strip() if isinstance(item.get("text"), str) and str(item.get("text")).strip() else None,
                content=(
                    str(item.get("content")).strip()
                    if isinstance(item.get("content"), str) and str(item.get("content")).strip()
                    else None
                ),
                heading=str(heading).strip() if isinstance(heading, str) and heading.strip() else None,
                heading_level=int(heading_level) if isinstance(heading_level, int) else None,
                page_number=item.get("page_number") if isinstance(item.get("page_number"), int) else item.get("page") if isinstance(item.get("page"), int) else None,
                page_start=item.get("page_start") if isinstance(item.get("page_start"), int) else None,
                page_end=item.get("page_end") if isinstance(item.get("page_end"), int) else None,
                regions=normalized_regions,
            )
        )
    return elements


def _serialize_opendataloader_artifact_payload(
    *,
    payload_obj: OpenDataLoaderArtifactPayload,
) -> dict[str, object]:
    """將內部 OpenDataLoader artifact dataclass 轉回可持久化 JSON。"""

    return {
        "schema_version": payload_obj.schema_version,
        "cleaned_markdown": payload_obj.cleaned_markdown,
        **({"markdown": payload_obj.markdown} if payload_obj.markdown else {}),
        "elements": [
            _serialize_opendataloader_raw_element(element=element)
            for element in payload_obj.elements
        ],
    }


def _serialize_opendataloader_raw_element(
    *,
    element: OpenDataLoaderRawElement,
) -> dict[str, object]:
    """將內部 raw element dataclass 轉回 JSON mapping。"""

    payload: dict[str, object] = {"type": element.element_kind}
    if element.markdown:
        payload["markdown"] = element.markdown
    if element.text:
        payload["text"] = element.text
    if element.content:
        payload["content"] = element.content
    if element.heading:
        payload["heading"] = element.heading
    if element.heading_level is not None:
        payload["heading_level"] = element.heading_level
    if element.page_number is not None:
        payload["page_number"] = element.page_number
    if element.page_start is not None:
        payload["page_start"] = element.page_start
    if element.page_end is not None:
        payload["page_end"] = element.page_end
    if element.regions:
        payload["regions"] = [
            _serialize_opendataloader_raw_region(region=region)
            for region in element.regions
        ]
    return payload


def _serialize_opendataloader_raw_region(
    *,
    region: OpenDataLoaderRawRegion,
) -> dict[str, object]:
    """將內部 raw region dataclass 轉回 JSON mapping。"""

    payload: dict[str, object] = {}
    if region.page_number is not None:
        payload["page_number"] = region.page_number
    if region.left is not None:
        payload["left"] = region.left
    if region.bottom is not None:
        payload["bottom"] = region.bottom
    if region.right is not None:
        payload["right"] = region.right
    if region.top is not None:
        payload["top"] = region.top
    return payload


def _build_opendataloader_artifact_payload(
    *,
    raw_payload: dict[str, object],
    cleaned_markdown: str,
) -> OpenDataLoaderArtifactPayload:
    """建立可供 reindex 重用的 OpenDataLoader JSON artifact。"""

    normalized = _normalize_opendataloader_artifact_payload(raw_payload=raw_payload)
    normalized.schema_version = "deep-agent-opendataloader-v1"
    normalized.cleaned_markdown = cleaned_markdown
    return normalized


def _parse_opendataloader_json_artifact_payload(
    *,
    artifact_payload: OpenDataLoaderArtifactPayload,
    source_format: str,
) -> ParsedDocument:
    """從 OpenDataLoader JSON artifact 重建 ParsedDocument。"""

    cleaned_markdown = artifact_payload.cleaned_markdown.strip()
    if not cleaned_markdown:
        raise ValueError("OpenDataLoader JSON artifact 缺少 cleaned_markdown。")
    parsed_document = _parse_opendataloader_payload(markdown=cleaned_markdown, artifact_payload=artifact_payload)
    return ParsedDocument(
        normalized_text=parsed_document.normalized_text,
        source_format=source_format,
        blocks=parsed_document.blocks,
        artifacts=[],
    )


def _parse_opendataloader_payload(
    *,
    markdown: str,
    artifact_payload: OpenDataLoaderArtifactPayload,
) -> ParsedDocument:
    """依 OpenDataLoader JSON+Markdown 建立帶 locator metadata 的 ParsedDocument。"""

    parsed_markdown = _parse_markdown_text(text=markdown, source_format="pdf")
    elements = _extract_opendataloader_elements(artifact_payload=artifact_payload)
    enriched_blocks = _enrich_blocks_with_opendataloader_elements(
        blocks=parsed_markdown.blocks,
        elements=elements,
    )
    return ParsedDocument(
        normalized_text=parsed_markdown.normalized_text,
        source_format=parsed_markdown.source_format,
        blocks=enriched_blocks,
        artifacts=[],
    )


def _extract_opendataloader_elements(
    *,
    artifact_payload: OpenDataLoaderArtifactPayload,
) -> list[_OpenDataLoaderElement]:
    """從 OpenDataLoader artifact 中擷取可對齊 Markdown blocks 的 elements。"""

    extracted_elements: list[_OpenDataLoaderElement] = []
    for item in artifact_payload.elements:
        content = str(item.markdown or item.text or item.content or "").strip()
        if not content:
            continue
        element_kind = item.element_kind.strip().lower() or "text"
        page_start, page_end = _extract_page_span(item)
        extracted_elements.append(
            _OpenDataLoaderElement(
                element_kind=element_kind,
                content=content,
                heading=item.heading.strip() if isinstance(item.heading, str) and item.heading.strip() else None,
                heading_level=item.heading_level,
                page_start=page_start,
                page_end=page_end,
                regions=_extract_parsed_regions(item),
            )
        )
    return extracted_elements


def _enrich_blocks_with_opendataloader_elements(
    *,
    blocks: list[ParsedBlock],
    elements: list[_OpenDataLoaderElement],
) -> list[ParsedBlock]:
    """將 OpenDataLoader semantic metadata 依序對齊到 Markdown blocks。"""

    if not elements:
        return blocks

    enriched_blocks: list[ParsedBlock] = []
    element_index = 0
    for block in blocks:
        matched_elements, next_index = _match_elements_for_block(
            block=block,
            elements=elements,
            starting_index=element_index,
        )
        element_index = next_index
        if not matched_elements:
            enriched_blocks.append(block)
            continue

        page_numbers = [region.page_number for element in matched_elements for region in element.regions]
        all_regions = [
            ParsedRegion(
                page_number=region.page_number,
                region_order=index,
                bbox_left=region.bbox_left,
                bbox_bottom=region.bbox_bottom,
                bbox_right=region.bbox_right,
                bbox_top=region.bbox_top,
            )
            for index, region in enumerate(region for element in matched_elements for region in element.regions)
        ]
        first_element = matched_elements[0]
        enriched_blocks.append(
            ParsedBlock(
                block_kind=block.block_kind,
                heading=block.heading,
                content=block.content,
                start_offset=block.start_offset,
                end_offset=block.end_offset,
                element_kind=first_element.element_kind,
                heading_level=first_element.heading_level,
                page_start=min(page_numbers) if page_numbers else first_element.page_start,
                page_end=max(page_numbers) if page_numbers else first_element.page_end,
                regions=all_regions or None,
            )
        )
    return enriched_blocks


def _match_elements_for_block(
    *,
    block: ParsedBlock,
    elements: list[_OpenDataLoaderElement],
    starting_index: int,
) -> tuple[list[_OpenDataLoaderElement], int]:
    """依序為單一 Markdown block 找出最合理的 OpenDataLoader elements。"""

    normalized_block = _normalize_whitespace(block.content)
    expected_kind = "table" if block.block_kind == "table" else "text"
    matched: list[_OpenDataLoaderElement] = []
    concatenated = ""
    index = starting_index

    while index < len(elements):
        element = elements[index]
        element_kind = _normalize_element_kind(element.element_kind)
        if matched:
            if element_kind != expected_kind:
                break
        elif element_kind != expected_kind:
            index += 1
            continue

        matched.append(element)
        concatenated = _normalize_whitespace(f"{concatenated} {element.content}")
        if not normalized_block:
            break
        if normalized_block in concatenated or concatenated in normalized_block:
            index += 1
            break
        if len(matched) >= 4:
            index += 1
            break
        index += 1

    return matched, index


def _normalize_element_kind(value: str) -> str:
    """將 OpenDataLoader element 類型映射為既有 text/table 類別。"""

    normalized = value.strip().lower()
    if "table" in normalized:
        return "table"
    return "text"


def _extract_page_span(item: OpenDataLoaderRawElement) -> tuple[int | None, int | None]:
    """從 OpenDataLoader element 擷取頁碼範圍。"""

    if isinstance(item.page_number, int):
        return item.page_number, item.page_number
    return (
        item.page_start if isinstance(item.page_start, int) else None,
        item.page_end if isinstance(item.page_end, int) else (item.page_start if isinstance(item.page_start, int) else None),
    )


def _extract_parsed_regions(item: OpenDataLoaderRawElement) -> list[ParsedRegion]:
    """從 OpenDataLoader element 擷取 bounding box regions。"""

    parsed_regions: list[ParsedRegion] = []
    fallback_page, _ = _extract_page_span(item)
    for region_order, region in enumerate(item.regions):
        page_number = region.page_number or fallback_page
        if page_number is None:
            continue
        left = region.left
        bottom = region.bottom
        right = region.right
        top = region.top
        if not all(isinstance(value, (int, float)) for value in (left, bottom, right, top)):
            continue
        parsed_regions.append(
            ParsedRegion(
                page_number=page_number,
                region_order=region_order,
                bbox_left=float(left),
                bbox_bottom=float(bottom),
                bbox_right=float(right),
                bbox_top=float(top),
            )
        )
    return parsed_regions


def _build_pdf_block_inputs_from_unstructured_elements(
    *,
    elements: list[object],
) -> tuple[list[tuple[str, str | None, str]], list[ParseArtifact]]:
    """將 Unstructured PDF elements 映射為 block-aware parser 輸入。

    參數：
    - `elements`：Unstructured PDF partition 回傳的 element 清單。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    block_inputs: list[tuple[str, str | None, str]] = []
    html_fragments: list[tuple[str | None, str]] = []
    current_heading: str | None = None

    for element in elements:
        metadata = getattr(element, "metadata", None)
        category = str(getattr(element, "category", "") or element.__class__.__name__).strip().lower()
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        raw_text = (getattr(element, "text", "") or "").strip()

        if category == "title" and raw_text:
            current_heading = raw_text
            block_inputs.append(("text", None, raw_text))
            continue

        if category == "table":
            if text_as_html:
                html_fragments.append((current_heading, text_as_html))
                block_inputs.extend(
                    _extract_html_block_inputs(
                        text=f"<h1>{escape(current_heading)}</h1>\n{text_as_html}" if current_heading else text_as_html
                    )
                )
                continue
            if raw_text:
                block_inputs.append(("table", current_heading, raw_text))
            continue

        if raw_text:
            block_inputs.append(("text", current_heading, raw_text))

    if not block_inputs:
        raise ValueError("local PDF parser 無法從文件中擷取文字內容。")
    return block_inputs, _build_html_artifacts(
        file_name="pdf.unstructured.extracted.html",
        html_fragments=html_fragments,
    )


def _build_office_block_inputs_from_unstructured_elements(
    *,
    elements: list[object],
    artifact_file_name: str,
) -> tuple[list[tuple[str, str | None, str]], list[ParseArtifact]]:
    """將 Unstructured DOCX/PPTX elements 映射為 block-aware parser 輸入。

    參數：
    - `elements`：Unstructured office partition 回傳的 element 清單。

    回傳：
    - `list[tuple[str, str | None, str]]`：可供 materialize 的 block 輸入。
    """

    block_inputs: list[tuple[str, str | None, str]] = []
    html_fragments: list[tuple[str | None, str]] = []
    current_heading: str | None = None

    for element in elements:
        metadata = getattr(element, "metadata", None)
        category = str(getattr(element, "category", "") or element.__class__.__name__).strip().lower()
        text_as_html = (getattr(metadata, "text_as_html", None) or "").strip() if metadata is not None else ""
        raw_text = (getattr(element, "text", "") or "").strip()

        if category == "title" and raw_text:
            current_heading = raw_text
            block_inputs.append(("text", None, raw_text))
            continue

        if category == "table":
            if text_as_html:
                html_fragments.append((current_heading, text_as_html))
                block_inputs.extend(
                    _extract_html_block_inputs(
                        text=f"<h1>{escape(current_heading)}</h1>\n{text_as_html}" if current_heading else text_as_html
                    )
                )
                continue
            if raw_text:
                block_inputs.append(("table", current_heading, raw_text))
            continue

        if raw_text:
            block_inputs.append(("text", current_heading, raw_text))

    if not block_inputs:
        raise ValueError("Unstructured office parser 未回傳可用內容。")
    return block_inputs, _build_html_artifacts(
        file_name=artifact_file_name,
        html_fragments=html_fragments,
    )


def _build_html_artifacts(*, file_name: str, html_fragments: list[tuple[str | None, str]]) -> list[ParseArtifact]:
    """將多段 HTML 片段組成單一可持久化 artifact。"""

    if not html_fragments:
        return []
    return [
        _build_text_artifact(
            file_name=file_name,
            content_type="text/html; charset=utf-8",
            text=_render_html_artifact_document(html_fragments=html_fragments),
        )
    ]


def _build_text_artifact(*, file_name: str, content_type: str, text: str) -> ParseArtifact:
    """建立 UTF-8 文字 artifact。"""

    return ParseArtifact(file_name=file_name, content_type=content_type, payload=text.encode("utf-8"))


def _build_json_artifact(*, file_name: str, payload_obj: OpenDataLoaderArtifactPayload) -> ParseArtifact:
    """建立 JSON artifact。"""

    return ParseArtifact(
        file_name=file_name,
        content_type="application/json; charset=utf-8",
        payload=json.dumps(
            _serialize_opendataloader_artifact_payload(payload_obj=payload_obj),
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"),
    )


def _render_html_artifact_document(*, html_fragments: list[tuple[str | None, str]]) -> str:
    """將多段 HTML fragment 包成單一可閱讀的 HTML 文件。"""

    rendered_sections: list[str] = ["<html>", "<body>"]
    for heading, html in html_fragments:
        normalized_html = html.strip()
        if not normalized_html:
            continue
        rendered_sections.append("<section>")
        if heading:
            rendered_sections.append(f"<h1>{escape(heading)}</h1>")
        rendered_sections.append(normalized_html)
        rendered_sections.append("</section>")
    rendered_sections.extend(["</body>", "</html>"])
    return "\n".join(rendered_sections)


def _extract_pdf_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_pdf 萃取 PDF elements。

    參數：
    - `payload`：PDF 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.pdf import partition_pdf
    except ImportError as exc:
        raise ValueError("local PDF parser 需要安裝 unstructured[pdf] 與相關系統依賴。") from exc

    temp_path = _write_temporary_pdf(payload=payload)
    try:
        elements = partition_pdf(filename=str(temp_path), strategy=LOCAL_PDF_UNSTRUCTURED_STRATEGY)
    except Exception as exc:  # noqa: BLE001 - 對第三方 parser 失敗統一包成受控錯誤。
        raise ValueError(f"Unstructured PDF 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("local PDF parser 無法從文件中擷取文字內容。")
    return list(elements)


def _extract_pdf_markdown_with_llamaparse(*, payload: bytes, pdf_config: PdfParserConfig) -> str:
    """使用 LlamaParse 將 PDF 轉為 Markdown。

    參數：
    - `payload`：PDF 原始位元組內容。
    - `pdf_config`：LlamaParse 設定。

    回傳：
    - `str`：LlamaParse 回傳的 Markdown 內容。
    """

    if not pdf_config.llamaparse_api_key:
        raise ValueError("PDF_PARSER_PROVIDER=llamaparse 需要設定 LLAMAPARSE_API_KEY。")

    try:
        from llama_parse import LlamaParse
    except ImportError as exc:
        raise ValueError("llamaparse provider 需要安裝 llama-parse。") from exc

    temp_path = _write_temporary_pdf(payload=payload)
    try:
        parser = LlamaParse(
            api_key=pdf_config.llamaparse_api_key,
            result_type="markdown",
            do_not_cache=pdf_config.llamaparse_do_not_cache,
            merge_tables_across_pages_in_markdown=pdf_config.llamaparse_merge_continued_tables,
        )
        documents = parser.load_data(str(temp_path))
    except Exception as exc:  # noqa: BLE001 - 對外部 SaaS 失敗統一包成受控錯誤。
        raise ValueError(f"LlamaParse PDF 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    markdown = "\n\n".join(
        document.text.strip()
        for document in documents
        if getattr(document, "text", "").strip()
    ).strip()
    if not markdown:
        raise ValueError("LlamaParse 未回傳可用的 Markdown 內容。")
    return markdown


def _extract_pdf_content_with_opendataloader(
    *,
    payload: bytes,
    pdf_config: PdfParserConfig,
) -> tuple[str, dict[str, object]]:
    """使用 OpenDataLoader 將 PDF 轉為 Markdown 與 JSON。"""

    try:
        from opendataloader_pdf import convert
    except ImportError as exc:
        raise ValueError("opendataloader provider 需要安裝 opendataloader-pdf 與 Java 11+。") from exc

    temp_path = _write_temporary_pdf(payload=payload)
    output_dir = Path(tempfile.mkdtemp(prefix="opendataloader-output-"))
    try:
        result = convert(
            input_path=[str(temp_path)],
            output_dir=str(output_dir),
            format="json,markdown",
            quiet=pdf_config.opendataloader_quiet,
            use_struct_tree=pdf_config.opendataloader_use_struct_tree,
            image_output="off",
            hybrid="off",
            include_header_footer=False,
        )
    except Exception as exc:  # noqa: BLE001 - 對第三方 parser 失敗統一包成受控錯誤。
        raise ValueError(f"OpenDataLoader PDF 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    json_path = next(output_dir.rglob("*.json"), None)
    if json_path is None:
        raise ValueError("OpenDataLoader 未回傳可用的 JSON 內容。")

    try:
        payload_obj = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("OpenDataLoader JSON artifact 不是有效的 JSON。") from exc

    markdown = str(payload_obj.get("markdown") or payload_obj.get("text") or "").strip()
    if not markdown:
        markdown_path = next(output_dir.rglob("*.md"), None)
        if markdown_path is not None:
            markdown = markdown_path.read_text(encoding="utf-8").strip()
    if not markdown:
        raise ValueError("OpenDataLoader 未回傳可用的 Markdown 內容。")

    return markdown, payload_obj


def _extract_xlsx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_xlsx 擷取 worksheet elements。

    參數：
    - `payload`：XLSX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 worksheet elements。
    """

    try:
        from unstructured.partition.xlsx import partition_xlsx
    except ImportError as exc:
        raise ValueError("XLSX parser 需要安裝 unstructured[all-docs] 或至少可用的 xlsx 相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".xlsx")
    try:
        elements = partition_xlsx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001 - 對第三方 parser 失敗統一包成受控錯誤。
        raise ValueError(f"Unstructured XLSX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured XLSX parser 未回傳任何 worksheet。")
    return list(elements)


def _extract_docx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_docx 擷取 DOCX elements。

    參數：
    - `payload`：DOCX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.docx import partition_docx
    except ImportError as exc:
        raise ValueError("DOCX parser 需要安裝 unstructured[docx] 與相關相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".docx")
    try:
        elements = partition_docx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unstructured DOCX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured DOCX parser 未回傳任何內容。")
    return list(elements)


def _extract_pptx_elements_with_unstructured(*, payload: bytes) -> list[object]:
    """使用 Unstructured partition_pptx 擷取 PPTX elements。

    參數：
    - `payload`：PPTX 原始位元組內容。

    回傳：
    - `list[object]`：Unstructured 回傳的 element 清單。
    """

    try:
        from unstructured.partition.pptx import partition_pptx
    except ImportError as exc:
        raise ValueError("PPTX parser 需要安裝 unstructured[pptx] 與相關相依套件。") from exc

    temp_path = _write_temporary_file(payload=payload, suffix=".pptx")
    try:
        elements = partition_pptx(filename=str(temp_path))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unstructured PPTX 解析失敗：{exc}") from exc
    finally:
        temp_path.unlink(missing_ok=True)

    if not elements:
        raise ValueError("Unstructured PPTX parser 未回傳任何內容。")
    return list(elements)


def _write_temporary_pdf(*, payload: bytes) -> Path:
    """將 PDF bytes 寫入暫存檔，供 PDF loader 使用。

    參數：
    - `payload`：PDF 原始位元組內容。

    回傳：
    - `Path`：暫存 PDF 檔案路徑。
    """

    return _write_temporary_file(payload=payload, suffix=".pdf")


def _write_temporary_file(*, payload: bytes, suffix: str) -> Path:
    """將二進位內容寫入指定副檔名的暫存檔。

    參數：
    - `payload`：原始位元組內容。
    - `suffix`：暫存檔副檔名。

    回傳：
    - `Path`：暫存檔案路徑。
    """

    with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as temporary_file:
        temporary_file.write(payload)
        return Path(temporary_file.name)


def _normalize_worksheet_heading(*, metadata: object | None) -> str | None:
    """從 Unstructured metadata 擷取 worksheet 名稱。

    參數：
    - `metadata`：Unstructured element metadata。

    回傳：
    - `str | None`：標準化後的 worksheet 名稱。
    """

    if metadata is None:
        return None

    for attribute_name in ("page_name", "sheet_name", "text_as_html"):
        if attribute_name == "text_as_html":
            continue
        value = getattr(metadata, attribute_name, None)
        if isinstance(value, str):
            normalized_value = value.strip()
            if normalized_value:
                return normalized_value
    return None


class _HTMLBlockParser(HTMLParser):
    """最小 HTML parser，抽出 headings、文字 block 與表格 block。"""

    def __init__(self) -> None:
        """建立 HTML block parser。

        參數：
        - 無

        回傳：
        - `None`：初始化內部狀態。
        """

        super().__init__(convert_charrefs=True)
        self.block_inputs: list[tuple[str, str | None, str]] = []
        self.current_heading: str | None = None
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._text_tag_stack: list[str] = []
        self._text_parts: list[str] = []
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._table_row: list[str] = []
        self._cell_parts: list[str] = []
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """處理 HTML 開始標籤。

        參數：
        - `tag`：標籤名稱。
        - `attrs`：標籤屬性列表。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        del attrs
        if tag in {"h1", "h2", "h3"}:
            self._flush_text_block()
            self._heading_tag = tag
            self._heading_parts = []
            return
        if tag in {"p", "li"}:
            self._flush_text_block()
            self._text_tag_stack.append(tag)
            self._text_parts = []
            return
        if tag == "table":
            self._flush_text_block()
            self._in_table = True
            self._table_rows = []
            return
        if not self._in_table:
            return
        if tag == "tr":
            self._table_row = []
            return
        if tag in {"th", "td"}:
            self._in_cell = True
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        """處理 HTML 結束標籤。

        參數：
        - `tag`：標籤名稱。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        if tag in {"h1", "h2", "h3"} and self._heading_tag == tag:
            heading = _normalize_whitespace(" ".join(self._heading_parts))
            self.current_heading = heading or self.current_heading
            self._heading_tag = None
            self._heading_parts = []
            return
        if tag in {"p", "li"} and self._text_tag_stack:
            self._flush_text_block()
            self._text_tag_stack.pop()
            return
        if not self._in_table:
            return
        if tag in {"th", "td"} and self._in_cell:
            cell_text = _normalize_whitespace(" ".join(self._cell_parts))
            self._table_row.append(cell_text)
            self._cell_parts = []
            self._in_cell = False
            return
        if tag == "tr" and self._table_row:
            self._table_rows.append(self._table_row)
            self._table_row = []
            return
        if tag == "table":
            self._flush_table_block()
            self._in_table = False

    def handle_data(self, data: str) -> None:
        """處理 HTML 純文字內容。

        參數：
        - `data`：當前文字內容。

        回傳：
        - `None`：只更新 parser 狀態。
        """

        if self._heading_tag is not None:
            self._heading_parts.append(data)
            return
        if self._in_table and self._in_cell:
            self._cell_parts.append(data)
            return
        if self._text_tag_stack:
            self._text_parts.append(data)

    def close(self) -> None:
        """結束 parser 並 flush 殘留 block。

        參數：
        - 無

        回傳：
        - `None`：完成 parser 收尾。
        """

        super().close()
        self._flush_text_block()
        if self._in_table:
            self._flush_table_block()
            self._in_table = False

    def _flush_text_block(self) -> None:
        """將目前文字內容輸出為 text block。

        參數：
        - 無

        回傳：
        - `None`：若無內容則不輸出 block。
        """

        content = _normalize_whitespace(" ".join(self._text_parts))
        if content:
            self.block_inputs.append(("text", self.current_heading, content))
        self._text_parts = []

    def _flush_table_block(self) -> None:
        """將目前表格內容輸出為 table block。

        參數：
        - 無

        回傳：
        - `None`：若無有效列則不輸出 block。
        """

        if not self._table_rows:
            return
        table_content = _render_table_rows_as_markdown(self._table_rows)
        if table_content:
            self.block_inputs.append(("table", self.current_heading, table_content))
        self._table_rows = []
        self._table_row = []
        self._cell_parts = []
        self._in_cell = False


def _render_table_rows_as_markdown(rows: list[list[str]]) -> str:
    """將表格列渲染為穩定的 Markdown table 文字。

    參數：
    - `rows`：表格列資料。

    回傳：
    - `str`：Markdown table 文字內容。
    """

    normalized_rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not normalized_rows:
        return ""
    column_count = max(len(row) for row in normalized_rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in normalized_rows]
    header = padded_rows[0]
    delimiter = ["---"] * column_count
    body = padded_rows[1:]
    lines = [_render_markdown_row(header), _render_markdown_row(delimiter)]
    lines.extend(_render_markdown_row(row) for row in body)
    return "\n".join(lines).strip()


def _render_markdown_row(cells: list[str]) -> str:
    """將單列表格資料轉為 Markdown row。

    參數：
    - `cells`：單列 cell 內容。

    回傳：
    - `str`：Markdown table row。
    """

    return "| " + " | ".join(cell.replace("\n", " ").strip() for cell in cells) + " |"


def _render_markdown_delimiter_row(cells: list[str]) -> str:
    """將 delimiter cells 渲染為穩定的 Markdown delimiter row。

    參數：
    - `cells`：delimiter cell 清單。

    回傳：
    - `str`：Markdown delimiter row。
    """

    return "| " + " | ".join(cell.strip() or "---" for cell in cells) + " |"


def _normalize_whitespace(value: str) -> str:
    """將多餘空白壓平成單一空白。

    參數：
    - `value`：原始字串。

    回傳：
    - `str`：正規化後字串。
    """

    return " ".join(value.split()).strip()


def _clean_llamaparse_markdown(markdown: str) -> str:
    """清理 LlamaParse Markdown 中常見的頁碼與分隔噪音。

    參數：
    - `markdown`：LlamaParse 回傳的 Markdown 文字。

    回傳：
    - `str`：移除常見頁面噪音後的 Markdown。
    """

    return _clean_pdf_markdown(markdown=markdown, provider_name="LlamaParse")


def _clean_pdf_markdown(*, markdown: str, provider_name: str) -> str:
    """清理 PDF provider 回傳 Markdown 中常見的頁碼與分隔噪音。

    參數：
    - `markdown`：PDF provider 回傳的 Markdown 文字。
    - `provider_name`：目前清理的 provider 名稱，僅供錯誤訊息使用。

    回傳：
    - `str`：移除常見頁面噪音後的 Markdown。
    """

    cleaned_lines: list[str] = []
    previous_was_blank = True

    for line in markdown.splitlines():
        stripped = line.strip()
        if PDF_PAGE_LABEL_PATTERN.match(stripped) or PDF_PAGE_SEPARATOR_PATTERN.match(stripped):
            continue
        if not stripped:
            if previous_was_blank:
                continue
            cleaned_lines.append("")
            previous_was_blank = True
            continue

        cleaned_lines.append(line.rstrip())
        previous_was_blank = False

    cleaned_markdown = "\n".join(cleaned_lines).strip()
    if not cleaned_markdown:
        raise ValueError(f"{provider_name} Markdown 清理後沒有剩餘內容。")
    return cleaned_markdown
