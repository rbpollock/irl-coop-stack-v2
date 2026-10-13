"""Worker parser provider 測試。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
import sys

from worker.parsers import (
    PdfParserConfig,
    _extract_pdf_content_with_opendataloader,
    parse_document,
    parse_document_from_artifact,
)


# 測試 local PDF provider 路徑的最小 PDF 樣本。
MINIMAL_TEXT_PDF = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 73 >>
stream
BT
/F1 18 Tf
50 100 Td
(Deep Agent PDF local parser sample) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000371 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
441
%%EOF
"""


def test_parse_document_supports_local_pdf_with_unstructured(monkeypatch) -> None:
    """local PDF provider 應能以 Unstructured elements 轉為 block-aware 內容。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured element metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured PDF element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    monkeypatch.setattr(
        "worker.parsers._extract_pdf_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Report", metadata=_FakeMetadata()),
            _FakeElement(category="NarrativeText", text="Deep Agent PDF local parser sample", metadata=_FakeMetadata()),
        ],
    )

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="local"),
    )

    assert parsed.source_format == "pdf"
    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].block_kind == "text"
    assert parsed.blocks[0].content == "Report"
    assert "Deep Agent PDF local parser sample" in parsed.blocks[1].content


def test_parse_document_uses_llamaparse_markdown_and_forwards_flags(monkeypatch) -> None:
    """llamaparse provider 應正確轉發設定，並沿用既有 Markdown parser。"""

    captured_kwargs: dict[str, object] = {}

    @dataclass
    class _FakeDocument:
        """模擬 LlamaParse 回傳文件。"""

        text: str

    class FakeLlamaParse:
        """模擬 LlamaParse client，記錄建構參數。"""

        def __init__(self, **kwargs) -> None:
            captured_kwargs.update(kwargs)

        def load_data(self, _path: str) -> list[_FakeDocument]:
            return [_FakeDocument("# Heading\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |")]

    monkeypatch.setitem(sys.modules, "llama_parse", SimpleNamespace(LlamaParse=FakeLlamaParse))

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(
            provider="llamaparse",
            llamaparse_api_key="test-key",
            llamaparse_do_not_cache=True,
            llamaparse_merge_continued_tables=True,
        ),
    )

    assert captured_kwargs["api_key"] == "test-key"
    assert captured_kwargs["result_type"] == "markdown"
    assert captured_kwargs["do_not_cache"] is True
    assert captured_kwargs["merge_tables_across_pages_in_markdown"] is True
    assert [block.block_kind for block in parsed.blocks] == ["table"]
    assert parsed.blocks[0].heading == "Heading"
    assert "| Alice | 95 |" in parsed.blocks[0].content
    assert [artifact.file_name for artifact in parsed.artifacts] == [
        "llamaparse.raw.md",
        "llamaparse.cleaned.md",
    ]


def test_parse_document_uses_opendataloader_json_markdown_and_preserves_regions(monkeypatch) -> None:
    """opendataloader provider 應產生 JSON+Markdown artifacts 並保留 regions。"""

    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (
            "# Heading\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
            {
                "markdown": "# Heading\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                "elements": [
                    {
                        "type": "table",
                        "markdown": "| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                        "page_number": 2,
                        "regions": [
                            {
                                "page_number": 2,
                                "left": 10,
                                "bottom": 20,
                                "right": 200,
                                "top": 120,
                            }
                        ],
                    }
                ],
            },
        ),
    )

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="opendataloader"),
    )

    assert [block.block_kind for block in parsed.blocks] == ["table"]
    assert parsed.blocks[0].heading == "Heading"
    assert parsed.blocks[0].page_start == 2
    assert parsed.blocks[0].page_end == 2
    assert parsed.blocks[0].regions is not None
    assert parsed.blocks[0].regions[0].page_number == 2
    assert [artifact.file_name for artifact in parsed.artifacts] == [
        "opendataloader.json",
        "opendataloader.cleaned.md",
    ]


def test_parse_document_cleans_opendataloader_page_noise(monkeypatch) -> None:
    """OpenDataLoader Markdown 中的常見頁碼與分隔符應在 parse 前被清理。"""

    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (
            "Page 1 of 2\n\n# Heading\n\n---\n\nUseful paragraph\n\nPage 2",
            {
                "markdown": "Page 1 of 2\n\n# Heading\n\n---\n\nUseful paragraph\n\nPage 2",
                "elements": [
                    {
                        "type": "paragraph",
                        "text": "Useful paragraph",
                        "page_number": 1,
                    }
                ],
            },
        ),
    )

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="opendataloader"),
    )

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].heading == "Heading"
    assert parsed.blocks[0].content == "Useful paragraph"


def test_parse_document_from_json_artifact_preserves_pdf_source_format() -> None:
    """OpenDataLoader JSON artifact 重建後仍應保留 `pdf` source_format。"""

    parsed = parse_document_from_artifact(
        file_name="sample.pdf",
        artifact_file_name="opendataloader.json",
        payload=(
            b'{"cleaned_markdown":"# Heading\\n\\n| Name | Score |\\n| --- | --- |\\n| Alice | 95 |",'
            b'"elements":[{"type":"table","markdown":"| Name | Score |\\n| --- | --- |\\n| Alice | 95 |","page_number":3,'
            b'"bbox":{"page_number":3,"left":1,"bottom":2,"right":3,"top":4}}]}'
        ),
    )

    assert parsed.source_format == "pdf"
    assert [block.block_kind for block in parsed.blocks] == ["table"]
    assert parsed.blocks[0].heading == "Heading"
    assert parsed.blocks[0].page_start == 3


def test_parse_document_from_html_artifact_preserves_office_source_format() -> None:
    """Office HTML artifact 重建後仍應保留原始 office source_format。"""

    parsed = parse_document_from_artifact(
        file_name="sample.docx",
        artifact_file_name="docx.extracted.html",
        payload=(
            b"<html><body><section><h1>Plan</h1><table><tr><th>Name</th></tr>"
            b"<tr><td>Alice</td></tr></table></section></body></html>"
        ),
    )

    assert parsed.source_format == "docx"
    assert [block.block_kind for block in parsed.blocks] == ["table"]
    assert parsed.blocks[0].heading == "Plan"


def test_parse_document_rejects_opendataloader_without_dependency() -> None:
    """缺少 OpenDataLoader 套件時應明確失敗。"""

    original_import = __import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("opendataloader_pdf"):
            raise ImportError("missing opendataloader")
        return original_import(name, globals, locals, fromlist, level)

    import builtins

    builtins_import = builtins.__import__
    builtins.__import__ = _fake_import
    try:
        parse_document(
            file_name="sample.pdf",
            payload=MINIMAL_TEXT_PDF,
            pdf_config=PdfParserConfig(provider="opendataloader"),
        )
    except ValueError as exc:
        assert "opendataloader-pdf" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 opendataloader-pdf 時應拋出 ValueError。")
    finally:
        builtins.__import__ = builtins_import


def test_extract_pdf_content_with_opendataloader_reads_output_files(monkeypatch, tmp_path) -> None:
    """OpenDataLoader wrapper 若僅寫檔不回傳 payload，仍應能讀回 JSON 與 Markdown。"""

    output_dir = tmp_path / "opendataloader-output"
    written_pdf_path: Path | None = None

    def _fake_mkdtemp(*, prefix: str) -> str:
        assert prefix == "opendataloader-output-"
        output_dir.mkdir()
        return str(output_dir)

    def _fake_write_temporary_pdf(*, payload: bytes) -> Path:
        del payload
        nonlocal written_pdf_path
        written_pdf_path = tmp_path / "input.pdf"
        written_pdf_path.write_bytes(MINIMAL_TEXT_PDF)
        return written_pdf_path

    def _fake_convert(**kwargs) -> None:
        assert kwargs["format"] == "json,markdown"
        assert kwargs["quiet"] is True
        assert kwargs["use_struct_tree"] is True
        assert kwargs["image_output"] == "off"
        assert kwargs["hybrid"] == "off"
        assert kwargs["include_header_footer"] is False
        (output_dir / "sample.json").write_text(
            json.dumps(
                {
                    "elements": [
                        {
                            "type": "paragraph",
                            "text": "Useful paragraph",
                            "page_number": 1,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (output_dir / "sample.md").write_text("# Heading\n\nUseful paragraph", encoding="utf-8")

    monkeypatch.setattr("worker.parsers.tempfile.mkdtemp", _fake_mkdtemp)
    monkeypatch.setattr("worker.parsers._write_temporary_pdf", _fake_write_temporary_pdf)
    monkeypatch.setitem(sys.modules, "opendataloader_pdf", SimpleNamespace(convert=_fake_convert))

    markdown, payload = _extract_pdf_content_with_opendataloader(
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="opendataloader"),
    )

    assert markdown == "# Heading\n\nUseful paragraph"
    assert payload["elements"][0]["text"] == "Useful paragraph"
    assert written_pdf_path is not None
    assert not written_pdf_path.exists()


def test_parse_document_cleans_llamaparse_page_noise(monkeypatch) -> None:
    """llamaparse Markdown 中的常見頁碼與分隔符應在 parse 前被清理。"""

    @dataclass
    class _FakeDocument:
        """模擬 LlamaParse 回傳文件。"""

        text: str

    class FakeLlamaParse:
        """回傳含頁碼噪音的 LlamaParse client。"""

        def __init__(self, **kwargs) -> None:
            del kwargs

        def load_data(self, _path: str) -> list[_FakeDocument]:
            return [_FakeDocument("Page 1 of 2\n\n# Heading\n\n---\n\nUseful paragraph\n\nPage 2")]

    monkeypatch.setitem(sys.modules, "llama_parse", SimpleNamespace(LlamaParse=FakeLlamaParse))

    parsed = parse_document(
        file_name="sample.pdf",
        payload=MINIMAL_TEXT_PDF,
        pdf_config=PdfParserConfig(provider="llamaparse", llamaparse_api_key="test-key"),
    )

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].heading == "Heading"
    assert parsed.blocks[0].content == "Useful paragraph"


def test_parse_document_rejects_llamaparse_without_api_key() -> None:
    """缺少 LlamaParse API key 時應明確失敗。"""

    try:
        parse_document(
            file_name="sample.pdf",
            payload=MINIMAL_TEXT_PDF,
            pdf_config=PdfParserConfig(provider="llamaparse"),
        )
    except ValueError as exc:
        assert "LLAMAPARSE_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 API key 時應拋出 ValueError。")


def test_parse_document_supports_xlsx_via_unstructured_html(monkeypatch) -> None:
    """XLSX parser 應能將 Unstructured worksheet HTML 轉為 table block。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured worksheet metadata。"""

        page_name: str
        text_as_html: str

    @dataclass
    class _FakeElement:
        """模擬 Unstructured worksheet element。"""

        metadata: _FakeMetadata
        text: str

    def _fake_partition_xlsx(*, filename: str) -> list[_FakeElement]:
        assert filename.endswith(".xlsx")
        return [
            _FakeElement(
                metadata=_FakeMetadata(
                    page_name="Budget",
                    text_as_html=(
                        "<table><tr><th>Name</th><th>Score</th></tr>"
                        "<tr><td>Alice</td><td>95</td></tr></table>"
                    ),
                ),
                text="Name Score Alice 95",
            )
        ]

    monkeypatch.setitem(sys.modules, "unstructured", ModuleType("unstructured"))
    monkeypatch.setitem(sys.modules, "unstructured.partition", ModuleType("unstructured.partition"))
    monkeypatch.setitem(
        sys.modules,
        "unstructured.partition.xlsx",
        SimpleNamespace(partition_xlsx=_fake_partition_xlsx),
    )

    parsed = parse_document(file_name="report.xlsx", payload=b"fake-xlsx")

    assert parsed.source_format == "xlsx"
    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].block_kind == "table"
    assert parsed.blocks[0].heading == "Budget"
    assert "Alice" in parsed.blocks[0].content
    assert [artifact.file_name for artifact in parsed.artifacts] == ["xlsx.extracted.html"]
    assert b"<h1>Budget</h1>" in parsed.artifacts[0].payload


def test_parse_document_supports_docx_via_unstructured(monkeypatch) -> None:
    """DOCX parser 應能將 Unstructured elements 轉為 text/table blocks。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured office metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured office element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    monkeypatch.setattr(
        "worker.parsers._extract_docx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Project Plan", metadata=_FakeMetadata()),
            _FakeElement(category="NarrativeText", text="Executive summary", metadata=_FakeMetadata()),
            _FakeElement(
                category="Table",
                text="Owner Status Alice Ready",
                metadata=_FakeMetadata(
                    text_as_html=(
                        "<table><tr><th>Owner</th><th>Status</th></tr>"
                        "<tr><td>Alice</td><td>Ready</td></tr></table>"
                    )
                ),
            ),
        ],
    )

    parsed = parse_document(file_name="plan.docx", payload=b"fake-docx")

    assert parsed.source_format == "docx"
    assert [block.block_kind for block in parsed.blocks] == ["text", "text", "table"]
    assert parsed.blocks[2].heading == "Project Plan"
    assert "Alice" in parsed.blocks[2].content
    assert [artifact.file_name for artifact in parsed.artifacts] == ["docx.extracted.html"]


def test_parse_document_supports_pptx_via_unstructured(monkeypatch) -> None:
    """PPTX parser 應能將 Unstructured elements 轉為 text blocks。"""

    @dataclass
    class _FakeMetadata:
        """模擬 Unstructured office metadata。"""

        text_as_html: str | None = None

    @dataclass
    class _FakeElement:
        """模擬 Unstructured office element。"""

        category: str
        text: str
        metadata: _FakeMetadata

    monkeypatch.setattr(
        "worker.parsers._extract_pptx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Quarterly Review", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Revenue up 15%", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Margin stable", metadata=_FakeMetadata()),
        ],
    )

    parsed = parse_document(file_name="review.pptx", payload=b"fake-pptx")

    assert parsed.source_format == "pptx"
    assert [block.block_kind for block in parsed.blocks] == ["text", "text", "text"]
    assert parsed.blocks[1].heading == "Quarterly Review"
    assert "Revenue up 15%" in parsed.blocks[1].content
    assert parsed.artifacts == []


def test_parse_document_normalizes_markdown_table_spacing_and_delimiter() -> None:
    """Markdown table 應在 parse 階段壓縮多餘空白與 delimiter 長度。"""

    parsed = parse_document(
        file_name="table.md",
        payload=(
            "# 規範\n\n"
            "| 當事人實際年齡          | 行為能力   | 簽名規範        |\n"
            "| ---------------- | ------ | ----------- |\n"
            "| 未滿 7 足歲          | 無行為能力  | 法定代理人代當事人簽名 |\n"
            "| 未成年者             |        | +法定代理人本人簽名  |\n"
        ).encode("utf-8"),
    )

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].block_kind == "table"
    assert parsed.blocks[0].content == "\n".join(
        [
            "| 當事人實際年齡 | 行為能力 | 簽名規範 |",
            "| --- | --- | --- |",
            "| 未滿 7 足歲 | 無行為能力 | 法定代理人代當事人簽名 |",
            "| 未成年者 |  | +法定代理人本人簽名 |",
        ]
    )
