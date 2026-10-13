"""Worker ingest task 與 chunk tree 測試。"""

from dataclasses import dataclass
from pathlib import Path
from sqlalchemy import delete, select

from worker.chunking import ChunkingConfig, build_chunk_tree
from worker.core.settings import WorkerSettings
from worker.embedding_text import build_embedding_input_text
from worker.embeddings import EmbeddingProvider
from worker.db import (
    Base,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    IngestJob,
    IngestJobStatus,
    create_database_engine,
    create_session_factory,
)
from worker.parsers import ParsedBlock, ParsedDocument, _parse_markdown_text, parse_document
from worker.tasks.ingest import process_document_ingest
from worker.tasks.indexing import index_document_chunks


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


def build_settings(tmp_path: Path) -> WorkerSettings:
    """建立 worker 測試用設定。

    參數：
    - `tmp_path`：pytest 提供的暫存目錄。

    回傳：
    - `WorkerSettings`：供 worker 測試使用的設定物件。
    """

    return WorkerSettings(
        WORKER_SERVICE_NAME="deep-agent-worker-test",
        DATABASE_URL=f"sqlite+pysqlite:///{tmp_path / 'worker.sqlite'}",
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/1",
        CELERY_WORKER_POOL="solo",
        CELERY_WORKER_CONCURRENCY=1,
        CELERY_WORKER_PREFETCH_MULTIPLIER=1,
        CELERY_WORKER_MAX_TASKS_PER_CHILD=1,
        STORAGE_BACKEND="filesystem",
        LOCAL_STORAGE_PATH=tmp_path / "storage",
        MINIO_ENDPOINT="http://minio:9000",
        MINIO_ACCESS_KEY="minio",
        MINIO_SECRET_KEY="minio123",
        MINIO_BUCKET="documents",
        CHUNK_MIN_PARENT_SECTION_LENGTH=800,
        CHUNK_TARGET_CHILD_SIZE=800,
        CHUNK_CHILD_OVERLAP=120,
        CHUNK_CONTENT_PREVIEW_LENGTH=120,
        CHUNK_TXT_PARENT_GROUP_SIZE=4,
        CHUNK_TABLE_PRESERVE_MAX_CHARS=4000,
        CHUNK_TABLE_MAX_ROWS_PER_CHILD=20,
        PDF_PARSER_PROVIDER="opendataloader",
        OPENDATALOADER_USE_STRUCT_TREE=True,
        OPENDATALOADER_QUIET=True,
        DOCUMENT_SYNOPSIS_PROVIDER="deterministic",
        DOCUMENT_SYNOPSIS_MODEL="gpt-5.4-mini",
        DOCUMENT_SYNOPSIS_MAX_INPUT_CHARS=6000,
        DOCUMENT_SYNOPSIS_MAX_OUTPUT_CHARS=1600,
        LLAMAPARSE_API_KEY="",
        LLAMAPARSE_DO_NOT_CACHE=True,
        LLAMAPARSE_MERGE_CONTINUED_TABLES=False,
        EMBEDDING_PROVIDER="deterministic",
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSIONS=1536,
    )


def build_chunking_config(settings: WorkerSettings) -> ChunkingConfig:
    """將 worker 設定轉為 chunking config。

    參數：
    - `settings`：worker 測試設定。

    回傳：
    - `ChunkingConfig`：供測試直接呼叫 chunking 使用的參數物件。
    """

    return ChunkingConfig(
        min_parent_section_length=settings.chunk_min_parent_section_length,
        target_child_chunk_size=settings.chunk_target_child_size,
        child_chunk_overlap=settings.chunk_child_overlap,
        content_preview_length=settings.chunk_content_preview_length,
        txt_parent_group_size=settings.chunk_txt_parent_group_size,
        table_preserve_max_chars=settings.chunk_table_preserve_max_chars,
        table_max_rows_per_child=settings.chunk_table_max_rows_per_child,
        fact_heavy_refinement_enabled=settings.chunk_fact_heavy_refinement_enabled,
    )


def seed_job(
    session_factory,
    *,
    file_name: str,
    payload: bytes,
    status=DocumentStatus.uploaded,
    job_status=IngestJobStatus.queued,
):
    """建立測試用 document/job 與對應原始檔。

    參數：
    - `session_factory`：用來建立測試資料庫 session 的 factory。
    - `file_name`：測試文件檔名。
    - `payload`：測試文件原始內容。
    - `status`：文件初始狀態。
    - `job_status`：ingest job 初始狀態。

    回傳：
    - 包含 `Document` 與 `IngestJob` 的 tuple。
    """

    with session_factory() as session:
        document = Document(
            id="document-1",
            area_id="area-1",
            file_name=file_name,
            content_type="text/markdown",
            file_size=len(payload),
            storage_key="area-1/document-1/" + file_name,
            status=status,
        )
        job = IngestJob(id="job-1", document_id=document.id, status=job_status)
        session.add_all([document, job])
        session.commit()
        return document, job


def test_process_document_ingest_updates_ready_and_writes_chunks(monkeypatch, tmp_path: Path) -> None:
    """支援的 md 文件應推進到 ready/succeeded，並寫入 parent-child chunks。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "local"
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = f"# Title\n{'A' * 320}\n\n## Next\n{'B' * 340}".encode()
    document, job = seed_job(session_factory, file_name="notes.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.indexed_at is not None
        assert refreshed_document.normalized_text == parse_document(file_name="notes.md", payload=payload).normalized_text
        assert refreshed_document.display_text is not None
        assert refreshed_document.synopsis_text is not None
        assert refreshed_document.synopsis_embedding is not None
        assert refreshed_document.synopsis_updated_at is not None
        assert refreshed_document.display_text.startswith("## Title\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert refreshed_job.stage == "succeeded"
        assert refreshed_job.parent_chunk_count == 2
        assert refreshed_job.child_chunk_count == 2
        assert len(refreshed_chunks) == 4
        assert {chunk.structure_kind for chunk in refreshed_chunks} == {ChunkStructureKind.text}
        parent_chunks = [chunk for chunk in refreshed_chunks if chunk.chunk_type == ChunkType.parent]
        assert parent_chunks
        assert all(chunk.section_path_text is not None for chunk in parent_chunks)
        assert all(chunk.section_synopsis_text is None for chunk in parent_chunks)
        assert all(chunk.section_synopsis_embedding is None for chunk in parent_chunks)
        assert all(chunk.section_synopsis_updated_at is None for chunk in parent_chunks)
        child_chunks = [chunk for chunk in refreshed_chunks if chunk.chunk_type == ChunkType.child]
        assert child_chunks
        assert all(chunk.embedding is not None for chunk in child_chunks)


def test_parse_document_pdf_markdown_relaxes_short_table_delimiter_cells() -> None:
    """PDF Markdown 的短 delimiter cell 應仍可被 worker parser 視為 table block。"""

    parsed = _parse_markdown_text(
        text=(
            "版次：114 年 9 月版    66    修訂日期：114.9.1\n\n"
            "| 1    | 集體彙繳件保費折扣                           | ○         |   |\n"
            "| ---- | ----------------------------------- | --------- | - |\n"
            "| 2    | 「個人保險契約審閱期間」規定                      | ○         |   |\n"
            "| 共通規定 | 4                                   | 「投保聲明書」規定 | ○ |\n"
        ),
        source_format="pdf",
    )

    assert len(parsed.blocks) == 2
    assert parsed.blocks[0].block_kind == "text"
    assert parsed.blocks[1].block_kind == "table"
    assert parsed.blocks[1].content == "\n".join(
        [
            "| 1 | 集體彙繳件保費折扣 | ○ |  |",
            "| --- | --- | --- | --- |",
            "| 2 | 「個人保險契約審閱期間」規定 | ○ |  |",
            "| 共通規定 | 4 | 「投保聲明書」規定 | ○ |",
        ]
    )


def test_build_chunk_tree_keeps_canonical_table_inside_pdf_parent_cluster() -> None:
    """PDF `text -> table -> text` parent cluster 應保留 canonical table 文字。"""

    parsed = _parse_markdown_text(
        text=(
            "版次：114 年 9 月版    66    修訂日期：114.9.1\n\n"
            "| 1    | 集體彙繳件保費折扣                           | ○         |   |\n"
            "| ---- | ----------------------------------- | --------- | - |\n"
            "| 2    | 「個人保險契約審閱期間」規定                      | ○         |   |\n"
            "| 共通規定 | 4                                   | 「投保聲明書」規定 | ○ |\n\n"
            "1. 經核保評估加費≦EM400%可投保本險，次標準體承保須加費。\n"
        ),
        source_format="pdf",
    )

    chunk_tree = build_chunk_tree(parsed_document=parsed, config=build_chunking_config(build_settings(Path("/tmp"))))

    assert len(chunk_tree.parent_chunks) == 1
    assert chunk_tree.parent_chunks[0].content == "\n\n".join(
        [
            "版次：114 年 9 月版    66    修訂日期：114.9.1",
            "\n".join(
                [
                    "| 1 | 集體彙繳件保費折扣 | ○ |  |",
                    "| --- | --- | --- | --- |",
                    "| 2 | 「個人保險契約審閱期間」規定 | ○ |  |",
                    "| 共通規定 | 4 | 「投保聲明書」規定 | ○ |",
                ]
            ),
            "1. 經核保評估加費≦EM400%可投保本險，次標準體承保須加費。",
        ]
    )


def test_index_document_chunks_embeddings_include_heading(monkeypatch, tmp_path: Path) -> None:
    """worker indexing 建立 child embedding 時應將 heading 與 content 一起送入 provider。"""

    settings = build_settings(tmp_path)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    captured_texts: list[str] = []

    class CapturingEmbeddingProvider:
        """記錄 embedding 輸入的測試替身。"""

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            """保存輸入文字並回傳固定維度向量。

            參數：
            - `texts`：送入 embedding provider 的字串列表。

            回傳：
            - `list[list[float]]`：與 schema 維度一致的假向量。
            """

            captured_texts.extend(texts)
            return [[0.1] * settings.embedding_dimensions for _ in texts]

    monkeypatch.setattr(
        "worker.tasks.indexing.build_embedding_provider",
        lambda worker_settings: CapturingEmbeddingProvider(),
    )

    with session_factory() as session:
        document = Document(
            id="document-embedding-1",
            area_id="area-1",
            file_name="notes.md",
            content_type="text/markdown",
            file_size=10,
            storage_key="area-1/document-embedding-1/notes.md",
            status=DocumentStatus.processing,
        )
        session.add(document)
        session.flush()
        session.add_all(
            [
                DocumentChunk(
                    id="parent-embedding-1",
                    document_id=document.id,
                    parent_chunk_id=None,
                    chunk_type=ChunkType.parent,
                    structure_kind=ChunkStructureKind.text,
                    position=0,
                    section_index=0,
                    child_index=None,
                    heading="Intro",
                    content="Alpha body",
                    content_preview="Alpha body",
                    char_count=10,
                    start_offset=0,
                    end_offset=10,
                ),
                DocumentChunk(
                    id="child-embedding-1",
                    document_id=document.id,
                    parent_chunk_id="parent-embedding-1",
                    chunk_type=ChunkType.child,
                    structure_kind=ChunkStructureKind.text,
                    position=1,
                    section_index=0,
                    child_index=0,
                    heading="Intro",
                    content="Alpha body",
                    content_preview="Alpha body",
                    char_count=10,
                    start_offset=0,
                    end_offset=10,
                ),
                DocumentChunk(
                    id="child-embedding-2",
                    document_id=document.id,
                    parent_chunk_id="parent-embedding-1",
                    chunk_type=ChunkType.child,
                    structure_kind=ChunkStructureKind.table,
                    position=2,
                    section_index=0,
                    child_index=1,
                    heading="Budget",
                    content="| item | value |\n| --- | --- |\n| alpha | 1 |",
                    content_preview="| item | value |",
                    char_count=46,
                    start_offset=11,
                    end_offset=57,
                ),
            ]
        )
        session.commit()

        index_document_chunks(session=session, document=document, settings=settings)

    assert captured_texts[:2] == [
        build_embedding_input_text(heading="Intro", content="Alpha body"),
        build_embedding_input_text(
            heading="Budget",
            content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        ),
    ]
    assert len(captured_texts) == 3
    assert "Topic:" in captured_texts[2]


def test_process_document_ingest_marks_failed_for_embedding_provider_error(monkeypatch, tmp_path: Path) -> None:
    """embedding provider 永久失敗時應轉為受控 failed，而非 unexpected exception。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)

    class FailingEmbeddingProvider(EmbeddingProvider):
        """固定拋出受控 provider 錯誤的測試替身。"""

        def embed_texts(self, texts: list[str]) -> list[list[float]]:
            """模擬 OpenAI embedding 永久性失敗。

            參數：
            - `texts`：原本要送入 provider 的文字清單。

            回傳：
            - `list[list[float]]`：此測試替身固定失敗，不會回傳結果。
            """

            del texts
            raise ValueError("OpenAI embeddings 失敗：Invalid 'input': maximum request size is 300000 tokens per request.")

    monkeypatch.setattr("worker.tasks.indexing.build_embedding_provider", lambda worker_settings: FailingEmbeddingProvider())

    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = f"# Title\n{'A' * 320}\n\n## Next\n{'B' * 340}".encode()
    document, job = seed_job(session_factory, file_name="notes.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        stored_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.failed
        assert refreshed_document.display_text is None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.error_message is not None
        assert "maximum request size is 300000 tokens per request" in refreshed_job.error_message
        assert stored_chunks == []


def test_process_document_ingest_supports_local_pdf(monkeypatch, tmp_path: Path) -> None:
    """local PDF provider 應能以 Unstructured local 路徑將 PDF 推進到 ready。"""

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
            _FakeElement(category="Title", text="Guide", metadata=_FakeMetadata()),
            _FakeElement(
                category="NarrativeText",
                text="Deep Agent PDF local parser sample",
                metadata=_FakeMetadata(),
            ),
        ],
    )

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "local"
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("Guide\n\n## Guide\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any("Deep Agent PDF local parser sample" in chunk.content for chunk in refreshed_chunks)


def test_process_document_ingest_supports_xlsx(monkeypatch, tmp_path: Path) -> None:
    """XLSX parser 應能將 worksheet 推進到 ready 並寫出 table-aware chunks。"""

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

    settings = build_settings(tmp_path)
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_xlsx_elements_with_unstructured",
        lambda *, payload: [
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
        ],
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-xlsx"
    document, job = seed_job(session_factory, file_name="budget.xlsx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Budget\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
        assert refreshed_job.parent_chunk_count == 1
        assert refreshed_job.child_chunk_count == 1
        assert len(refreshed_chunks) == 2
        assert refreshed_chunks[0].content
        artifact_path = storage_path.parent / "artifacts" / "xlsx.extracted.html"
        assert artifact_path.exists()
        assert "<h1>Budget</h1>" in artifact_path.read_text(encoding="utf-8")


def test_process_document_ingest_supports_docx(monkeypatch, tmp_path: Path) -> None:
    """DOCX parser 應能將文件推進到 ready 並寫出 text/table chunks。"""

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

    settings = build_settings(tmp_path)
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
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
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-docx"
    document, job = seed_job(session_factory, file_name="plan.docx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("Project Plan\n\n## Project Plan\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
        artifact_path = storage_path.parent / "artifacts" / "docx.extracted.html"
        assert artifact_path.exists()
        assert "Owner" in artifact_path.read_text(encoding="utf-8")


def test_process_document_ingest_supports_pptx(monkeypatch, tmp_path: Path) -> None:
    """PPTX parser 應能將文件推進到 ready 並寫出文字 chunks。"""

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

    settings = build_settings(tmp_path)
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pptx_elements_with_unstructured",
        lambda *, payload: [
            _FakeElement(category="Title", text="Quarterly Review", metadata=_FakeMetadata()),
            _FakeElement(category="ListItem", text="Revenue up 15%", metadata=_FakeMetadata()),
        ],
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-pptx"
    document, job = seed_job(session_factory, file_name="review.pptx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("Quarterly Review\n\n## Quarterly Review\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert all(chunk.structure_kind == ChunkStructureKind.text for chunk in refreshed_chunks)


def test_process_document_ingest_supports_llamaparse_pdf(monkeypatch, tmp_path: Path) -> None:
    """llamaparse provider 應能將 Markdown 結果交回既有 chunking 流程。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "llamaparse"
    settings.llamaparse_api_key = "test-key"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_markdown_with_llamaparse",
        lambda *, payload, pdf_config: "# PDF Report\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## PDF Report\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
        raw_artifact_path = storage_path.parent / "artifacts" / "llamaparse.raw.md"
        cleaned_artifact_path = storage_path.parent / "artifacts" / "llamaparse.cleaned.md"
        assert raw_artifact_path.exists()
        assert cleaned_artifact_path.exists()
        assert "| Alice | 95 |" in cleaned_artifact_path.read_text(encoding="utf-8")


def test_process_document_ingest_supports_opendataloader_pdf(monkeypatch, tmp_path: Path) -> None:
    """opendataloader provider 應能將 JSON+Markdown 結果交回既有 chunking 流程。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "opendataloader"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (
            "# PDF Report\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
            {
                "markdown": "# PDF Report\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                "elements": [
                    {
                        "type": "table",
                        "markdown": "| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                        "page_number": 1,
                        "bbox": {"page_number": 1, "left": 1, "bottom": 2, "right": 3, "top": 4},
                    }
                ],
            },
        ),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## PDF Report\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)
        markdown_artifact_path = storage_path.parent / "artifacts" / "opendataloader.cleaned.md"
        json_artifact_path = storage_path.parent / "artifacts" / "opendataloader.json"
        assert markdown_artifact_path.exists()
        assert json_artifact_path.exists()
        assert markdown_artifact_path.read_text(encoding="utf-8").strip().startswith("# PDF Report")


def test_process_document_ingest_reuses_existing_opendataloader_json_artifact_on_reindex(monkeypatch, tmp_path: Path) -> None:
    """reindex 若已存在 OpenDataLoader JSON artifact，應直接重建 chunks 而不重跑 parser。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "opendataloader"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (_ for _ in ()).throw(AssertionError("不應重跑 opendataloader parser")),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)
    artifact_path = storage_path.parent / "artifacts" / "opendataloader.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        (
            '{"cleaned_markdown":"# Reused Report\\n\\n| Name | Score |\\n| --- | --- |\\n| Alice | 95 |",'
            '"elements":[{"type":"table","markdown":"| Name | Score |\\n| --- | --- |\\n| Alice | 95 |","page_number":1}]}'
        ),
        encoding="utf-8",
    )

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert refreshed_document.normalized_text.startswith("| Name | Score |")
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Reused Report\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)


def test_process_document_ingest_force_reparse_ignores_existing_opendataloader_artifact(monkeypatch, tmp_path: Path) -> None:
    """force_reparse 應忽略既有 OpenDataLoader artifact 並重跑 parser。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "opendataloader"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (
            "# Fresh Report\n\n| Name | Score |\n| --- | --- |\n| Bob | 88 |",
            {
                "markdown": "# Fresh Report\n\n| Name | Score |\n| --- | --- |\n| Bob | 88 |",
                "elements": [{"type": "table", "markdown": "| Name | Score |\n| --- | --- |\n| Bob | 88 |", "page_number": 1}],
            },
        ),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)
    artifact_path = storage_path.parent / "artifacts" / "opendataloader.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        (
            '{"cleaned_markdown":"# Stale Report\\n\\n| Name | Score |\\n| --- | --- |\\n| Alice | 95 |",'
            '"elements":[{"type":"table","markdown":"| Name | Score |\\n| --- | --- |\\n| Alice | 95 |","page_number":1}]}'
        ),
        encoding="utf-8",
    )

    result = process_document_ingest(job.id, force_reparse=True)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        assert result == "succeeded"
        assert refreshed_document is not None
        assert "| Bob | 88 |" in refreshed_document.normalized_text
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Fresh Report\n\n")
        assert "| Alice | 95 |" not in refreshed_document.normalized_text
        assert "| Bob | 88 |" in artifact_path.read_text(encoding="utf-8")


def test_process_document_ingest_reuses_existing_html_artifact_on_reindex(monkeypatch, tmp_path: Path) -> None:
    """reindex 若已存在 office HTML artifact，應直接重建 chunks 而不重跑 parser。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_docx_elements_with_unstructured",
        lambda *, payload: (_ for _ in ()).throw(AssertionError("不應重跑 docx parser")),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"fake-docx"
    document, job = seed_job(session_factory, file_name="plan.docx", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)
    artifact_path = storage_path.parent / "artifacts" / "docx.extracted.html"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        (
            "<html><body><section><h1>Plan</h1><p>Executive summary</p>"
            "<table><tr><th>Owner</th><th>Status</th></tr>"
            "<tr><td>Alice</td><td>Ready</td></tr></table></section></body></html>"
        ),
        encoding="utf-8",
    )

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunks = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.ready
        assert "Executive summary" in refreshed_document.normalized_text
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Plan\n\n")
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.succeeded
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)


def test_process_document_ingest_marks_failed_for_opendataloader_missing_dependency(monkeypatch, tmp_path: Path) -> None:
    """opendataloader provider 缺少依賴時應轉為受控 failed。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "opendataloader"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    monkeypatch.setattr(
        "worker.parsers._extract_pdf_content_with_opendataloader",
        lambda *, payload, pdf_config: (_ for _ in ()).throw(
            ValueError("opendataloader provider 需要安裝 opendataloader-pdf 與 Java 11+。")
        ),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunk_count = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count()
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.failed
        assert refreshed_document.normalized_text is None
        assert refreshed_document.display_text is None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.error_message is not None
        assert "opendataloader-pdf" in refreshed_job.error_message.lower()
        assert refreshed_chunk_count == 0


def test_process_document_ingest_truncates_chunk_heading_and_preview(monkeypatch, tmp_path: Path) -> None:
    """ingest 寫入 chunk 時應裁切過長 heading 與 content preview，避免超出 schema。"""

    settings = build_settings(tmp_path)
    settings.chunk_content_preview_length = 400
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    long_heading = "H" * 320
    long_body = "A" * 420
    payload = f"# {long_heading}\n{long_body}".encode()
    document, job = seed_job(session_factory, file_name="long-heading.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        stored_chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position.asc())
            .all()
        )
        assert result == "succeeded"
        assert stored_chunks
        assert all(chunk.heading == long_heading[:255] for chunk in stored_chunks)
        assert all(len(chunk.content_preview) == 255 for chunk in stored_chunks)


def test_process_document_ingest_marks_failed_for_llamaparse_missing_key(monkeypatch, tmp_path: Path) -> None:
    """llamaparse provider 缺少 API key 時應轉為受控 failed。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "llamaparse"
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="deck.pdf", payload=MINIMAL_TEXT_PDF)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(MINIMAL_TEXT_PDF)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        refreshed_chunk_count = session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).count()
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.failed
        assert refreshed_document.normalized_text is None
        assert refreshed_document.display_text is None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.error_message is not None
        assert (
            "LLAMAPARSE_API_KEY" in refreshed_job.error_message
            or "llama-parse" in refreshed_job.error_message.lower()
        )
        assert refreshed_chunk_count == 0


def test_process_document_ingest_skips_non_queued_job(monkeypatch, tmp_path: Path) -> None:
    """非 queued 的 job 不應重複處理。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(
        session_factory,
        file_name="notes.md",
        payload=b"# Title\ncontent",
        job_status=IngestJobStatus.processing,
    )

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "job-skipped"
        assert refreshed_document is not None
        assert refreshed_document.status == DocumentStatus.uploaded
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.processing


def test_process_document_ingest_fails_safely_when_document_was_deleted(monkeypatch, tmp_path: Path) -> None:
    """job 指向已刪文件時應安全失敗，且不得復活任何資料。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    _, job = seed_job(session_factory, file_name="notes.md", payload=b"# Title\ncontent")

    with session_factory() as session:
        document = session.get(Document, "document-1")
        assert document is not None
        session.delete(document)
        session.commit()

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, "document-1")
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "document-missing"
        assert refreshed_document is None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed
        assert refreshed_job.stage == "failed"
        assert refreshed_job.error_message == "找不到對應的 document。"


def test_reprocessing_replaces_existing_chunks(monkeypatch, tmp_path: Path) -> None:
    """同一文件再處理時應替換舊 chunks，而不是殘留舊資料。"""

    settings = build_settings(tmp_path)
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    document, job = seed_job(session_factory, file_name="notes.md", payload=b"# Title\ncontent")
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(b"# Title\ncontent")

    assert process_document_ingest(job.id) == "succeeded"

    with session_factory() as session:
        original_chunk_ids = {
            chunk.id for chunk in session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        }
        refreshed_document = session.get(Document, document.id)
        assert refreshed_document is not None
        refreshed_document.status = DocumentStatus.uploaded
        second_job = IngestJob(id="job-2", document_id=document.id, status=IngestJobStatus.queued)
        session.add(second_job)
        session.commit()

    storage_path.write_bytes(b"# Title\nupdated\n\n## Next\nmore")
    assert process_document_ingest("job-2") == "succeeded"

    with session_factory() as session:
        refreshed_chunk_ids = {
            chunk.id for chunk in session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).all()
        }
        refreshed_document = session.get(Document, document.id)
        assert original_chunk_ids.isdisjoint(refreshed_chunk_ids)
        assert refreshed_document is not None
        session.refresh(refreshed_document)
        assert (
            refreshed_document.normalized_text
            == parse_document(file_name="notes.md", payload=b"# Title\nupdated\n\n## Next\nmore").normalized_text
        )
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Title\n\n")
        assert "## Next\n\nmore" in refreshed_document.display_text


def test_build_chunk_tree_merges_short_parent_with_following_section() -> None:
    """過短 parent section 應在切 child 前先與後續 section 合併。"""

    text = "# Short\nshort\n\n## Long\n" + ("A" * 400)

    settings = build_settings(Path("/tmp"))
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].heading == "Short / Long"
    assert "short" in result.parent_chunks[0].content
    assert "A" * 50 in result.parent_chunks[0].content
    assert len(result.child_chunks) == 1


def test_build_chunk_tree_keeps_merging_until_parent_reaches_threshold() -> None:
    """過短 parent 應持續合併，而不是只做一次相鄰合併。"""

    text = "# One\n" + ("A" * 260) + "\n\n## Two\n" + ("B" * 280) + "\n\n## Three\n" + ("C" * 300)

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].heading == "One / Two / Three"
    assert len(result.parent_chunks[0].content) >= 800


def test_build_chunk_tree_uses_langchain_child_splitter_with_stable_offsets() -> None:
    """LangChain child splitter 應保留穩定順序與正確 offsets。"""

    repeated_sentence = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu " * 20).strip()
    text = f"# Intro\n{repeated_sentence}"

    settings = build_settings(Path("/tmp"))
    settings.chunk_target_child_size = 120
    settings.chunk_child_overlap = 20

    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert len(result.child_chunks) >= 2

    parent = result.parent_chunks[0]
    previous_end = -1
    for index, child in enumerate(result.child_chunks):
        assert child.child_index == index
        assert child.content == child.content.strip()
        assert child.start_offset < child.end_offset
        assert child.start_offset >= parent.start_offset
        assert child.end_offset <= parent.end_offset
        assert result.display_text[child.start_offset:child.end_offset] == child.content
        assert child.start_offset > previous_end - settings.chunk_child_overlap
        previous_end = child.end_offset


def test_build_chunk_tree_merges_short_markdown_table_parent_with_adjacent_text() -> None:
    """過短 Markdown table parent 應與相鄰同 heading 文字合併。"""

    text = "\n".join(
        [
            "# Report",
            "Summary paragraph",
            "",
            "| Name | Score |",
            "| --- | ---: |",
            "| Alice | 95 |",
            "| Bob | 88 |",
            "",
            "Closing paragraph",
        ]
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 500
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="report.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].structure_kind == "text"
    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table", "text"]


def test_build_chunk_tree_consolidates_short_pdf_text_blocks_with_same_heading() -> None:
    """PDF source 的同 heading 短 text/table blocks 應收斂成單一 mixed parent。"""

    parsed_document = ParsedDocument(
        normalized_text="Intro A\n\nIntro B\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |",
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro A",
                start_offset=0,
                end_offset=7,
            ),
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro B",
                start_offset=9,
                end_offset=16,
            ),
            ParsedBlock(
                block_kind="table",
                heading="Overview",
                content="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                start_offset=18,
                end_offset=64,
            ),
        ],
        artifacts=[],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.parent_chunks) == 1
    parent = result.parent_chunks[0]
    assert parent.structure_kind == "text"
    assert parent.heading == "Overview"
    assert "Intro A\n\nIntro B" in parent.content
    assert "| Alice | 95 |" in parent.content
    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table"]


def test_build_chunk_tree_materializes_display_text_with_heading_prefix() -> None:
    """parent locator 應只在前綴實際匹配時包含 heading。"""

    text = "# Intro\n" + ("Alpha body " * 40).strip()
    settings = build_settings(Path("/tmp"))
    settings.chunk_target_child_size = 120
    settings.chunk_child_overlap = 20
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="notes.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert result.display_text.startswith("## Intro\n\n")
    parent = result.parent_chunks[0]
    assert result.display_text[parent.start_offset:parent.start_offset + len("## Intro\n\n")] == "## Intro\n\n"
    assert parent.start_offset == 0
    assert parent.content in result.display_text
    assert result.child_chunks[0].start_offset == len("## Intro\n\n")


def test_build_chunk_tree_refines_fact_heavy_dataset_section_into_sentence_windows() -> None:
    """fact-heavy dataset section 在開關啟用時應切成較細 child。"""

    parsed_document = ParsedDocument(
        normalized_text=(
            "Our dataset is annotated based on pathology reports. "
            "It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs. "
            "All question-answer pairs are annotated and reviewed by four clinicians. "
            "There are three types of questions: tumor size, proximal resection margin and distal resection margin."
        ),
        source_format="markdown",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Experimental Studies ::: Dataset and Evaluation Metrics",
                content=(
                    "Our dataset is annotated based on pathology reports. "
                    "It contains 17,833 sentences, 826,987 characters and 2,714 question-answer pairs. "
                    "All question-answer pairs are annotated and reviewed by four clinicians. "
                    "There are three types of questions: tumor size, proximal resection margin and distal resection margin."
                ),
                start_offset=0,
                end_offset=300,
            )
        ],
        artifacts=[],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_fact_heavy_refinement_enabled = True
    settings.chunk_target_child_size = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.child_chunks) >= 3
    assert any("17,833 sentences" in chunk.content for chunk in result.child_chunks)
    assert any("three types of questions" in chunk.content for chunk in result.child_chunks)


def test_build_chunk_tree_keeps_child_offset_after_derived_heading_prefix() -> None:
    """child offset 應維持正文起點，不因 heading 前綴而往前擴張。"""

    parsed_document = ParsedDocument(
        normalized_text="Intro note\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |\n\nClosing note",
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro note",
                start_offset=0,
                end_offset=10,
            ),
            ParsedBlock(
                block_kind="table",
                heading="Overview",
                content="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                start_offset=12,
                end_offset=58,
            ),
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Closing note",
                start_offset=60,
                end_offset=72,
            ),
        ],
        artifacts=[],
    )
    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert result.display_text.startswith("## Overview\n\n")
    parent = result.parent_chunks[0]
    first_child = result.child_chunks[0]
    assert parent.start_offset == 0
    assert first_child.start_offset == len("## Overview\n\n")
    assert result.display_text[first_child.start_offset:first_child.end_offset] == first_child.content


def test_build_chunk_tree_clusters_pdf_text_table_text_under_same_heading() -> None:
    """PDF 的 `text -> table -> text` 短區塊應合併為單一 parent cluster。"""

    parsed_document = ParsedDocument(
        normalized_text="Intro note\n\n| Name | Score |\n| --- | --- |\n| Alice | 95 |\n\nClosing note",
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Intro note",
                start_offset=0,
                end_offset=10,
            ),
            ParsedBlock(
                block_kind="table",
                heading="Overview",
                content="| Name | Score |\n| --- | --- |\n| Alice | 95 |",
                start_offset=12,
                end_offset=58,
            ),
            ParsedBlock(
                block_kind="text",
                heading="Overview",
                content="Closing note",
                start_offset=60,
                end_offset=72,
            ),
        ],
        artifacts=[],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 800
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.parent_chunks) == 1
    parent = result.parent_chunks[0]
    assert parent.structure_kind == "text"
    assert parent.heading == "Overview"
    assert "Intro note" in parent.content
    assert "| Alice | 95 |" in parent.content
    assert "Closing note" in parent.content

    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table", "text"]
    assert [chunk.child_index for chunk in result.child_chunks] == [0, 1, 2]
    for child in result.child_chunks:
        assert result.display_text[child.start_offset:child.end_offset] == child.content


def test_build_chunk_tree_merges_short_table_with_adjacent_text_same_heading() -> None:
    """過短 table parent 應與相鄰同 heading 文字合併為 mixed parent。"""

    text = "\n".join(
        [
            "# Coverage",
            "投保規則說明。",
            "",
            "| 投保年齡 | 投保金額 |",
            "| --- | --- |",
            "| 15足歲(不含)以下 | 美元35萬元 |",
            "| 15足歲(含)以上 | 美元1,000萬元 |",
            "",
            "續保與繳費方式另見下列說明。",
        ]
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 220
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="coverage.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    parent = result.parent_chunks[0]
    assert parent.structure_kind == "text"
    assert "投保規則說明。" in parent.content
    assert "| 15足歲(含)以上 | 美元1,000萬元 |" in parent.content
    assert "續保與繳費方式另見下列說明。" in parent.content
    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table", "text"]


def test_build_chunk_tree_merges_short_sections_when_heading_is_parent_path_prefix() -> None:
    """短 PDF sections 若 heading 為同一條 path family，應合併為單一 mixed parent。"""

    parsed_document = ParsedDocument(
        normalized_text=(
            "繳費年期及 6 年\n\n"
            "投保年齡 0 歲~74 歲\n\n"
            "(以元為單位)\n\n"
            "1. 最低投保金額：美元 7,000 元。\n\n"
            "1. 本險累計最高投保金額：\n\n"
            "| 投保年齡 | 投保金額 |\n"
            "| --- | --- |\n"
            "| 15足歲(不含)以下 | 美元35萬元 |\n"
            "| 15足歲(含)以上 | 美元1000萬元 |"
        ),
        source_format="pdf",
        blocks=[
            ParsedBlock(
                block_kind="text",
                heading="十六、 保利美美元利率變動型終身壽險(NUIW6502)",
                content="繳費年期及 6 年\n\n投保年齡 0 歲~74 歲",
                start_offset=0,
                end_offset=23,
            ),
            ParsedBlock(
                block_kind="text",
                heading="十六、 保利美美元利率變動型終身壽險(NUIW6502) / 投保金額",
                content="(以元為單位)\n\n1. 最低投保金額：美元 7,000 元。\n\n1. 本險累計最高投保金額：",
                start_offset=25,
                end_offset=71,
            ),
            ParsedBlock(
                block_kind="table",
                heading="十六、 保利美美元利率變動型終身壽險(NUIW6502)",
                content=(
                    "| 投保年齡 | 投保金額 |\n"
                    "| --- | --- |\n"
                    "| 15足歲(不含)以下 | 美元35萬元 |\n"
                    "| 15足歲(含)以上 | 美元1000萬元 |"
                ),
                start_offset=73,
                end_offset=145,
            ),
        ],
        artifacts=[],
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 220
    result = build_chunk_tree(parsed_document=parsed_document, config=build_chunking_config(settings))

    assert len(result.parent_chunks) == 1
    parent = result.parent_chunks[0]
    assert parent.structure_kind == "text"
    assert parent.heading == "十六、 保利美美元利率變動型終身壽險(NUIW6502)"
    assert "本險累計最高投保金額：" in parent.content
    assert "| 15足歲(含)以上 | 美元1000萬元 |" in parent.content
    assert [chunk.structure_kind for chunk in result.child_chunks] == ["text", "table"]


def test_build_chunk_tree_keeps_short_table_separate_when_heading_differs() -> None:
    """過短 table parent 若前後 heading 不同，不應跨 heading 合併。"""

    text = "\n".join(
        [
            "# Coverage",
            "投保規則說明。",
            "",
            "## 體檢額度",
            "| 投保年齡 | 投保金額 |",
            "| --- | --- |",
            "| 70 歲(含)以下 | 美元 200 萬元 |",
            "",
            "## 繳費方式",
            "續保與繳費方式另見下列說明。",
        ]
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_min_parent_section_length = 220
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="coverage-headings.md", payload=text.encode()),
        config=build_chunking_config(settings),
    )

    assert [chunk.structure_kind for chunk in result.parent_chunks] == ["text", "table", "text"]
    assert result.parent_chunks[1].structure_kind == "table"


def test_build_chunk_tree_splits_large_table_by_row_group_and_repeats_header() -> None:
    """大型表格應依 row groups 切成多個 table child，且每個 child 重複表頭。"""

    rows = [f"| item-{index} | value-{index} |" for index in range(5)]
    table_text = "\n".join(
        [
            "| Name | Value |",
            "| --- | --- |",
            *rows,
        ]
    )

    settings = build_settings(Path("/tmp"))
    settings.chunk_table_preserve_max_chars = 10
    settings.chunk_table_max_rows_per_child = 2
    result = build_chunk_tree(
        parsed_document=parse_document(file_name="table.md", payload=table_text.encode()),
        config=build_chunking_config(settings),
    )

    assert len(result.parent_chunks) == 1
    assert result.parent_chunks[0].structure_kind == "table"
    assert len(result.child_chunks) == 3
    for child in result.child_chunks:
        assert child.structure_kind == "table"
        assert child.content.splitlines()[0] == "| Name | Value |"
        assert child.content.splitlines()[1] == "| --- | --- |"
    assert "| item-0 | value-0 |" in result.child_chunks[0].content
    assert "| item-2 | value-2 |" in result.child_chunks[1].content
    assert "| item-4 | value-4 |" in result.child_chunks[2].content


def test_process_document_ingest_supports_html_table_blocks(monkeypatch, tmp_path: Path) -> None:
    """HTML 文件中的 table 應被辨識為 table structure_kind。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"""
    <h1>Quarterly Report</h1>
    <p>Summary paragraph</p>
    <table>
      <tr><th>Name</th><th>Score</th></tr>
      <tr><td>Alice</td><td>95</td></tr>
      <tr><td>Bob</td><td>88</td></tr>
    </table>
    <p>Closing note</p>
    """
    document, job = seed_job(session_factory, file_name="report.html", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.position.asc())
            .all()
        )
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Quarterly Report\n\n")
        assert any(chunk.structure_kind == ChunkStructureKind.table for chunk in refreshed_chunks)


def test_process_document_ingest_persists_display_text_and_normalized_text(monkeypatch, tmp_path: Path) -> None:
    """成功 ingest 後應保存 normalized_text 與 display_text。"""

    settings = build_settings(tmp_path)
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"# Title\nAlpha body\n\n## Next\nBeta body\n"
    document, job = seed_job(session_factory, file_name="preview.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        assert result == "succeeded"
        assert refreshed_document is not None
        assert refreshed_document.normalized_text == parse_document(
            file_name="preview.md",
            payload=payload,
        ).normalized_text
        assert refreshed_document.display_text is not None
        assert refreshed_document.display_text.startswith("## Title\n\n")
        assert "Alpha body" in refreshed_document.display_text
        assert "## Next" in refreshed_document.display_text
        assert "Beta body" in refreshed_document.display_text


def test_process_document_ingest_clears_display_text_on_failure(monkeypatch, tmp_path: Path) -> None:
    """ingest 失敗時應清空舊 normalized_text 與 display_text，避免 preview 看到過期內容。"""

    settings = build_settings(tmp_path)
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"\xff\xfe\x00"
    document, job = seed_job(session_factory, file_name="broken.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    with session_factory() as session:
        stored_document = session.get(Document, document.id)
        assert stored_document is not None
        stored_document.normalized_text = "stale text"
        stored_document.display_text = "stale display text"
        session.commit()

    result = process_document_ingest(job.id)

    with session_factory() as session:
        refreshed_document = session.get(Document, document.id)
        refreshed_job = session.get(IngestJob, job.id)
        assert result == "failed"
        assert refreshed_document is not None
        assert refreshed_document.normalized_text is None
        assert refreshed_document.display_text is None
        assert refreshed_job is not None
        assert refreshed_job.status == IngestJobStatus.failed


def test_process_document_ingest_reindex_keeps_display_text_offsets_stable(monkeypatch, tmp_path: Path) -> None:
    """同文件重跑 ingest 後，display_text 與 child offsets 應維持穩定。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "local"
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"# Intro\nAlpha body\n\n## Next\nBeta body"
    document, job = seed_job(session_factory, file_name="stable.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    assert process_document_ingest(job.id) == "succeeded"

    with session_factory() as session:
        first_document = session.get(Document, document.id)
        first_children = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
            .order_by(DocumentChunk.position.asc())
        ).all()
        assert first_document is not None
        first_display_text = first_document.display_text
        first_offsets = [(chunk.start_offset, chunk.end_offset, chunk.content) for chunk in first_children]

        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        first_document.status = DocumentStatus.uploaded
        first_document.display_text = None
        first_document.normalized_text = None
        session.add(IngestJob(id="job-2", document_id=document.id, status=IngestJobStatus.queued))
        session.commit()

    assert process_document_ingest("job-2") == "succeeded"

    with session_factory() as session:
        second_document = session.get(Document, document.id)
        second_children = session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
            .order_by(DocumentChunk.position.asc())
        ).all()
        assert second_document is not None
        assert second_document.display_text == first_display_text
        second_offsets = [(chunk.start_offset, chunk.end_offset, chunk.content) for chunk in second_children]
        assert second_offsets == first_offsets


def test_process_document_ingest_reindex_refreshes_synopsis_timestamp(monkeypatch, tmp_path: Path) -> None:
    """同文件重跑 ingest 後，synopsis_updated_at 應更新且 synopsis 內容保持穩定。"""

    settings = build_settings(tmp_path)
    settings.pdf_parser_provider = "local"
    settings.chunk_min_parent_section_length = 1
    monkeypatch.setattr("worker.tasks.ingest.get_settings", lambda: settings)
    engine = create_database_engine(settings)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)

    payload = b"# Intro\nAlpha body\n\n## Next\nBeta body"
    document, job = seed_job(session_factory, file_name="synopsis-stable.md", payload=payload)
    storage_path = Path(settings.local_storage_path) / document.storage_key
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_bytes(payload)

    assert process_document_ingest(job.id) == "succeeded"

    with session_factory() as session:
        first_document = session.get(Document, document.id)
        assert first_document is not None
        first_synopsis_text = first_document.synopsis_text
        first_synopsis_updated_at = first_document.synopsis_updated_at

        session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        first_document.status = DocumentStatus.uploaded
        first_document.display_text = None
        first_document.normalized_text = None
        first_document.synopsis_text = None
        first_document.synopsis_embedding = None
        first_document.synopsis_updated_at = None
        session.add(IngestJob(id="job-2", document_id=document.id, status=IngestJobStatus.queued))
        session.commit()

    assert process_document_ingest("job-2") == "succeeded"

    with session_factory() as session:
        second_document = session.get(Document, document.id)
        assert second_document is not None
        assert second_document.synopsis_text == first_synopsis_text
        assert first_synopsis_updated_at is not None
        assert second_document.synopsis_updated_at is not None
        assert second_document.synopsis_updated_at > first_synopsis_updated_at
