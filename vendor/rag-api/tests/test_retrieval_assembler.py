"""Table-aware retrieval assembler 測試。"""

from uuid import uuid4, UUID

from app.auth.verifier import CurrentPrincipal
from app.core.settings import AppSettings
from app.db.models import Area, AreaUserRole, ChunkStructureKind, ChunkType, Document, DocumentChunk, DocumentStatus, Role
from app.services.retrieval_assembler import (
    _load_child_chunks,
    _load_parent_chunks,
    assemble_retrieval_result,
)
from app.services.retrieval_runtime import retrieve_area_candidates
from app.services.retrieval_types import RetrievalCandidate, RetrievalResult, RetrievalTrace


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_assemble_retrieval_result_merges_text_children_with_same_parent(db_session, app_settings) -> None:
    """同一 parent 的多個 text children 應合併為單一 context。"""

    area = Area(id="area-assemble-text", name="Assemble Text")
    document = Document(
        id="document-assemble-text",
        area_id=area.id,
        file_name="text.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-text/text.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-text",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Section",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id="child-assemble-text-1",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Section",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id="child-assemble-text-2",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Section",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid"),
            _build_candidate(child_two, source="hybrid"),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert assembled.assembled_contexts[0].assembled_text == "alpha intro\n\nalpha details"
    assert [citation.chunk_id for citation in assembled.citations] == [child_one.id, child_two.id]
    assert assembled.trace.assembler.kept_chunk_ids == [child_one.id, child_two.id]


def test_assemble_retrieval_result_uses_full_parent_for_small_single_hit(db_session, app_settings) -> None:
    """小 parent 即使只命中單一 child，也應回完整 parent 內容。"""

    area = Area(id="area-assemble-full-parent", name="Assemble Full Parent")
    document = Document(
        id="document-assemble-full-parent",
        area_id=area.id,
        file_name="full-parent.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-full-parent/full-parent.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-full-parent",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Full Parent",
        content="alpha intro\n\nalpha evidence\n\nalpha closing",
        content_preview="alpha intro",
        char_count=41,
        start_offset=0,
        end_offset=41,
    )
    child = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-full-parent",
        position=1,
        section_index=0,
        child_index=1,
        heading="Full Parent",
        content="alpha evidence",
        start_offset=13,
        end_offset=27,
    )
    before = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-full-parent-before",
        position=2,
        section_index=0,
        child_index=0,
        heading="Full Parent",
        content="alpha intro",
        start_offset=0,
        end_offset=11,
    )
    after = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-full-parent-after",
        position=3,
        section_index=0,
        child_index=2,
        heading="Full Parent",
        content="alpha closing",
        start_offset=29,
        end_offset=41,
    )
    db_session.add_all([area, document, parent, before, child, after])
    db_session.commit()

    assembled = assemble_retrieval_result(
        session=db_session,
        settings=app_settings,
        retrieval_result=RetrievalResult(
            candidates=[_build_candidate(child, source="hybrid")],
            trace=_build_trace(query="alpha"),
        ),
    )

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].assembled_text == parent.content
    assert assembled.assembled_contexts[0].chunk_ids == [before.id, child.id, after.id]
    assert assembled.assembled_contexts[0].start_offset == parent.start_offset
    assert assembled.assembled_contexts[0].end_offset == parent.end_offset


def test_load_chunk_helpers_normalize_uuid_keys_to_strings(monkeypatch) -> None:
    """chunk 補查 helper 應將 ORM 的 UUID 識別碼正規化為字串 key。

    參數：
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 UUID/string lookup 相容性。
    """

    child_id = uuid4()
    parent_id = uuid4()

    class _FakeScalarResult:
        """模擬 SQLAlchemy scalar result。"""

        def __init__(self, values):
            self._values = values

        def all(self):
            """回傳預設 values。"""

            return self._values

    class _FakeSession:
        """模擬僅支援 scalars() 的 session。"""

        def __init__(self, values):
            self._values = values

        def scalars(self, _statement):
            """忽略 statement，直接回傳預設 chunks。"""

            return _FakeScalarResult(self._values)

    child = DocumentChunk(
        id=child_id,  # type: ignore[arg-type]
        document_id=uuid4(),  # type: ignore[arg-type]
        parent_chunk_id=parent_id,  # type: ignore[arg-type]
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="UUID Section",
        content="uuid content",
        content_preview="uuid content",
        char_count=12,
        start_offset=0,
        end_offset=12,
        embedding=[0.1] * 8,
    )
    parent = DocumentChunk(
        id=parent_id,  # type: ignore[arg-type]
        document_id=uuid4(),  # type: ignore[arg-type]
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="UUID Section",
        content="uuid content",
        content_preview="uuid content",
        char_count=12,
        start_offset=0,
        end_offset=12,
    )

    child_lookup = _load_child_chunks(session=_FakeSession([child]), chunk_ids=[str(child_id)])
    parent_lookup = _load_parent_chunks(session=_FakeSession([parent]), parent_chunk_ids=[str(parent_id)])

    assert list(child_lookup.keys()) == [str(child_id)]
    assert list(parent_lookup.keys()) == [str(parent_id)]
    assert child_lookup[str(child_id)] is child
    assert parent_lookup[str(parent_id)] is parent


def test_assemble_retrieval_result_merges_table_children_with_single_header(db_session, app_settings) -> None:
    """同一 parent 的 table children 合併時應只保留一次表頭。"""

    area = Area(id="area-assemble-table", name="Assemble Table")
    document = Document(
        id="document-assemble-table",
        area_id=area.id,
        file_name="table.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-table/table.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-table",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.table,
        position=0,
        section_index=0,
        child_index=None,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |",
        content_preview="| item | value |",
        char_count=60,
        start_offset=0,
        end_offset=60,
    )
    child_one = DocumentChunk(
        id="child-assemble-table-1",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=0,
        child_index=0,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=0,
        end_offset=46,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id="child-assemble-table-2",
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=2,
        section_index=0,
        child_index=1,
        heading="Table Section",
        content="| item | value |\n| --- | --- |\n| beta | 2 |",
        content_preview="| item | value |",
        char_count=45,
        start_offset=47,
        end_offset=92,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_two, source="hybrid", rrf_rank=1),
            _build_candidate(child_one, source="hybrid", rrf_rank=2),
        ],
        trace=_build_trace(query="table"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert assembled.assembled_contexts[0].assembled_text.count("| item | value |") == 1
    assert "| alpha | 1 |" in assembled.assembled_contexts[0].assembled_text
    assert "| beta | 2 |" in assembled.assembled_contexts[0].assembled_text


def test_assemble_retrieval_result_expands_table_hit_with_adjacent_text(db_session, app_settings) -> None:
    """大 parent 命中 table 時，應補前後相鄰說明文字。"""

    settings = app_settings.model_copy(update={"assembler_max_chars_per_context": 180})
    area = Area(id="area-assemble-table-window", name="Assemble Table Window")
    document = Document(
        id="document-assemble-table-window",
        area_id=area.id,
        file_name="table-window.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-table-window/table-window.md",
        status=DocumentStatus.ready,
    )
    parent_content = (
        "投保規則說明與前置條件。\n\n"
        "| item | value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |\n\n"
        "續保與給付限制說明。"
    )
    parent = DocumentChunk(
        id="parent-assemble-table-window",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Coverage",
        content=parent_content,
        content_preview="投保規則說明",
        char_count=len(parent_content),
        start_offset=0,
        end_offset=len(parent_content),
    )
    intro = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-window-intro",
        position=1,
        section_index=0,
        child_index=0,
        heading="Coverage",
        content="投保規則說明與前置條件。",
        start_offset=0,
        end_offset=13,
    )
    table = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-window-table",
        position=2,
        section_index=0,
        child_index=1,
        heading="Coverage",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |",
        start_offset=15,
        end_offset=73,
    )
    outro = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-window-outro",
        position=3,
        section_index=0,
        child_index=2,
        heading="Coverage",
        content="續保與給付限制說明。",
        start_offset=75,
        end_offset=86,
    )
    db_session.add_all([area, document, parent, intro, table, outro])
    db_session.commit()

    assembled = assemble_retrieval_result(
        session=db_session,
        settings=settings,
        retrieval_result=RetrievalResult(
            candidates=[_build_candidate(table, source="hybrid")],
            trace=_build_trace(query="alpha"),
        ),
    )

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].structure_kind == ChunkStructureKind.text
    assert assembled.assembled_contexts[0].chunk_ids == [intro.id, table.id, outro.id]
    assert "投保規則說明與前置條件。" in assembled.assembled_contexts[0].assembled_text
    assert "| alpha | 1 |" in assembled.assembled_contexts[0].assembled_text
    assert "續保與給付限制說明。" in assembled.assembled_contexts[0].assembled_text


def test_assemble_retrieval_result_prioritizes_complete_table_before_partial_adjacent_text(
    db_session, app_settings
) -> None:
    """table hit 在 budget 不足時，應先保完整表格，再盡量補相鄰文字。"""

    settings = app_settings.model_copy(update={"assembler_max_chars_per_context": 85})
    area = Area(id="area-assemble-table-budget", name="Assemble Table Budget")
    document = Document(
        id="document-assemble-table-budget",
        area_id=area.id,
        file_name="table-budget.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-table-budget/table-budget.md",
        status=DocumentStatus.ready,
    )
    intro_content = "I" * 20
    table_content = "| item | value |\n| --- | --- |\n| alpha | 1 |\n| beta | 2 |"
    outro_content = "O" * 20
    parent_content = f"{intro_content}\n\n{table_content}\n\n{outro_content}"
    parent = DocumentChunk(
        id="parent-assemble-table-budget",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Budgeted Coverage",
        content=parent_content,
        content_preview=intro_content,
        char_count=len(parent_content),
        start_offset=0,
        end_offset=len(parent_content),
    )
    intro = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-budget-intro",
        position=1,
        section_index=0,
        child_index=0,
        heading="Budgeted Coverage",
        content=intro_content,
        start_offset=0,
        end_offset=len(intro_content),
    )
    table = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-budget-table",
        position=2,
        section_index=0,
        child_index=1,
        heading="Budgeted Coverage",
        content=table_content,
        start_offset=len(intro_content) + 2,
        end_offset=len(intro_content) + 2 + len(table_content),
    )
    outro = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-table-budget-outro",
        position=3,
        section_index=0,
        child_index=2,
        heading="Budgeted Coverage",
        content=outro_content,
        start_offset=len(intro_content) + 2 + len(table_content) + 2,
        end_offset=len(parent_content),
    )
    db_session.add_all([area, document, parent, intro, table, outro])
    db_session.commit()

    assembled = assemble_retrieval_result(
        session=db_session,
        settings=settings,
        retrieval_result=RetrievalResult(
            candidates=[_build_candidate(table, source="hybrid")],
            trace=_build_trace(query="alpha"),
        ),
    )

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [intro.id, table.id]
    assert assembled.assembled_contexts[0].assembled_text == f"{intro_content}\n\n{table_content}"
    assert outro_content not in assembled.assembled_contexts[0].assembled_text
    assert assembled.trace.assembler.contexts[0].truncated is False


def test_assemble_retrieval_result_keeps_text_and_table_separate(db_session, app_settings) -> None:
    """text 與 table 命中不可混成同一 context。"""

    area = Area(id="area-assemble-mixed", name="Assemble Mixed")
    document = Document(
        id="document-assemble-mixed",
        area_id=area.id,
        file_name="mixed.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-mixed/mixed.md",
        status=DocumentStatus.ready,
    )
    text_parent = DocumentChunk(
        id="parent-assemble-text-mixed",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Text",
        content="alpha paragraph",
        content_preview="alpha paragraph",
        char_count=15,
        start_offset=0,
        end_offset=15,
    )
    table_parent = DocumentChunk(
        id="parent-assemble-table-mixed",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=1,
        child_index=None,
        heading="Table",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=17,
        end_offset=63,
    )
    text_child = DocumentChunk(
        id="child-assemble-text-mixed",
        document_id=document.id,
        parent_chunk_id=text_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=0,
        heading="Text",
        content="alpha paragraph",
        content_preview="alpha paragraph",
        char_count=15,
        start_offset=0,
        end_offset=15,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    table_child = DocumentChunk(
        id="child-assemble-table-mixed",
        document_id=document.id,
        parent_chunk_id=table_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=3,
        section_index=1,
        child_index=0,
        heading="Table",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=17,
        end_offset=63,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([area, document, text_parent, table_parent, text_child, table_child])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(text_child, source="vector"),
            _build_candidate(table_child, source="fts", rrf_rank=2, vector_rank=None, fts_rank=1),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 2
    assert [context.structure_kind for context in assembled.assembled_contexts] == [
        ChunkStructureKind.text,
        ChunkStructureKind.table,
    ]


def test_assemble_retrieval_result_enforces_budget_and_trace(db_session, app_settings) -> None:
    """assembler 應依 context、children 與字元 budget 留下 trace。"""

    settings = app_settings.model_copy(
        update={
            "assembler_max_contexts": 1,
            "assembler_max_chars_per_context": 19,
            "assembler_max_children_per_parent": 2,
        }
    )
    area = Area(id="area-assemble-budget", name="Assemble Budget")
    document = Document(
        id="document-assemble-budget",
        area_id=area.id,
        file_name="budget.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-budget/budget.md",
        status=DocumentStatus.ready,
    )
    parent_one = DocumentChunk(
        id="parent-budget-1",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Budget A",
        content="alpha one\n\nalpha two\n\nalpha three",
        content_preview="alpha one",
        char_count=31,
        start_offset=0,
        end_offset=31,
    )
    parent_two = DocumentChunk(
        id="parent-budget-2",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=1,
        child_index=None,
        heading="Budget B",
        content="beta final",
        content_preview="beta final",
        char_count=10,
        start_offset=33,
        end_offset=43,
    )
    child_one = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-1",
        position=2,
        section_index=0,
        child_index=0,
        heading="Budget A",
        content="alpha one",
        start_offset=0,
        end_offset=9,
    )
    child_two = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-2",
        position=3,
        section_index=0,
        child_index=1,
        heading="Budget A",
        content="alpha two",
        start_offset=11,
        end_offset=20,
    )
    child_three = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_id="child-budget-3",
        position=4,
        section_index=0,
        child_index=2,
        heading="Budget A",
        content="alpha three",
        start_offset=22,
        end_offset=33,
    )
    child_four = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent_two.id,
        chunk_id="child-budget-4",
        position=5,
        section_index=1,
        child_index=0,
        heading="Budget B",
        content="beta final",
        start_offset=35,
        end_offset=45,
    )
    db_session.add_all([area, document, parent_one, parent_two, child_one, child_two, child_three, child_four])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid"),
            _build_candidate(child_two, source="hybrid", rrf_rank=2),
            _build_candidate(child_three, source="hybrid", rrf_rank=3),
            _build_candidate(child_four, source="hybrid", rrf_rank=4),
        ],
        trace=_build_trace(query="alpha"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_one.id, child_two.id]
    assert len(assembled.assembled_contexts[0].assembled_text) == 19
    assert assembled.trace.assembler.dropped_chunk_ids == [child_three.id, child_four.id]
    assert assembled.trace.assembler.contexts[0].truncated is True


def test_assemble_retrieval_result_prefers_query_matching_anchor_within_parent(db_session, app_settings) -> None:
    """assembler 應優先保留 parent 內最像 query 的 hit child，而不是單看 child 順序。"""

    settings = app_settings.model_copy(
        update={
            "assembler_max_contexts": 1,
            "assembler_max_chars_per_context": 48,
            "assembler_max_children_per_parent": 1,
        }
    )
    area = Area(id="area-assemble-query-anchor", name="Assemble Query Anchor")
    document = Document(
        id="document-assemble-query-anchor",
        area_id=area.id,
        file_name="anchor.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-query-anchor/anchor.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-query-anchor",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Generative Model",
        content="intro\n\ntraining setup\n\nwe use the Yelp Challenge dataset\n\nclosing",
        content_preview="intro",
        char_count=68,
        start_offset=0,
        end_offset=68,
    )
    child_one = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-query-anchor-1",
        position=1,
        section_index=0,
        child_index=0,
        heading="Generative Model",
        content="intro section",
        start_offset=0,
        end_offset=13,
    )
    child_two = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-query-anchor-2",
        position=2,
        section_index=0,
        child_index=1,
        heading="Generative Model",
        content="training setup",
        start_offset=15,
        end_offset=29,
    )
    child_three = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-query-anchor-3",
        position=3,
        section_index=0,
        child_index=2,
        heading="Generative Model",
        content="we use the Yelp Challenge dataset",
        start_offset=31,
        end_offset=64,
    )
    db_session.add_all([area, document, parent, child_one, child_two, child_three])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid", rrf_rank=1),
            _build_candidate(child_two, source="hybrid", rrf_rank=2),
            _build_candidate(child_three, source="hybrid", rrf_rank=3),
        ],
        trace=_build_trace(query="Which dataset do they use a starting point in generating fake reviews?"),
    )

    assembled = assemble_retrieval_result(session=db_session, settings=settings, retrieval_result=retrieval_result)

    assert len(assembled.assembled_contexts) == 1
    assert assembled.assembled_contexts[0].chunk_ids == [child_three.id]
    assert assembled.trace.assembler.contexts[0].kept_chunk_ids == [child_three.id]
    assert assembled.trace.assembler.contexts[0].dropped_chunk_ids == [child_one.id, child_two.id]


def test_assemble_retrieval_result_accepts_dict_trace_for_query_aware_anchor(db_session, app_settings) -> None:
    """assembler 在 evaluation 路徑收到 dict trace 時仍應可做 query-aware anchor 選擇。"""

    settings = app_settings.model_copy(
        update={
            "assembler_max_contexts": 1,
            "assembler_max_chars_per_context": 48,
            "assembler_max_children_per_parent": 1,
        }
    )
    area = Area(id="area-assemble-dict-trace", name="Assemble Dict Trace")
    document = Document(
        id="document-assemble-dict-trace",
        area_id=area.id,
        file_name="dict-trace.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-dict-trace/dict-trace.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-dict-trace",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Generative Model",
        content="intro\n\ntraining setup\n\nwe use the Yelp Challenge dataset\n\nclosing",
        content_preview="intro",
        char_count=68,
        start_offset=0,
        end_offset=68,
    )
    child_one = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-dict-trace-1",
        position=1,
        section_index=0,
        child_index=0,
        heading="Generative Model",
        content="intro section",
        start_offset=0,
        end_offset=13,
    )
    child_two = _build_ready_child(
        app_settings=settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-dict-trace-2",
        position=2,
        section_index=0,
        child_index=1,
        heading="Generative Model",
        content="we use the Yelp Challenge dataset",
        start_offset=31,
        end_offset=64,
    )
    db_session.add_all([area, document, parent, child_one, child_two])
    db_session.commit()

    retrieval_result = RetrievalResult(
        candidates=[
            _build_candidate(child_one, source="hybrid", rrf_rank=1),
            _build_candidate(child_two, source="hybrid", rrf_rank=2),
        ],
        trace={"query": "Which dataset do they use a starting point in generating fake reviews?"},
    )

    assembled = assemble_retrieval_result(session=db_session, settings=settings, retrieval_result=retrieval_result)

    assert assembled.assembled_contexts[0].chunk_ids == [child_two.id]


def test_assemble_retrieval_result_preserves_citation_offsets(db_session, app_settings) -> None:
    """citation metadata 應保留原始 child offsets。"""

    area = Area(id="area-assemble-citation", name="Assemble Citation")
    document = Document(
        id="document-assemble-citation",
        area_id=area.id,
        file_name="citation.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-citation/citation.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-citation",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Citation",
        content="alpha excerpt",
        content_preview="alpha excerpt",
        char_count=13,
        start_offset=0,
        end_offset=13,
    )
    child = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-citation",
        position=1,
        section_index=0,
        child_index=0,
        heading="Citation",
        content="alpha excerpt",
        start_offset=2,
        end_offset=11,
    )
    db_session.add_all([area, document, parent, child])
    db_session.commit()

    assembled = assemble_retrieval_result(
        session=db_session,
        settings=app_settings,
        retrieval_result=RetrievalResult(
            candidates=[_build_candidate(child, source="hybrid")],
            trace=_build_trace(query="alpha"),
        ),
    )

    assert assembled.citations[0].start_offset == 2
    assert assembled.citations[0].end_offset == 11
    assert assembled.citations[0].excerpt == "alpha excerpt"


def test_assemble_retrieval_result_works_after_rerank_fallback(db_session, app_settings, monkeypatch) -> None:
    """rerank fail-open fallback 後仍應可組裝 assembler 結果。"""

    area = Area(id="area-assemble-fallback", name="Assemble Fallback")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id="document-assemble-fallback",
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-assemble-fallback/fallback.md",
        status=DocumentStatus.ready,
    )
    parent = DocumentChunk(
        id="parent-assemble-fallback",
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Fallback",
        content="fallback alpha",
        content_preview="fallback alpha",
        char_count=14,
        start_offset=0,
        end_offset=14,
    )
    child = _build_ready_child(
        app_settings=app_settings,
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_id="child-assemble-fallback",
        position=1,
        section_index=0,
        child_index=0,
        heading="Fallback",
        content="fallback alpha",
        start_offset=0,
        end_offset=14,
    )
    db_session.add_all([document, parent, child])
    db_session.commit()

    class FailingRerankProvider:
        """固定拋錯的 rerank provider 測試替身。"""

        def rerank(self, *, query: str, documents: list[object], top_n: int):
            """模擬 provider runtime failure。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 provider 的文件清單。
            - `top_n`：最多回傳筆數。

            回傳：
            - 不會回傳；固定拋出錯誤。
            """

            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.retrieval_rerank.build_rerank_provider", lambda settings: FailingRerankProvider())

    retrieval_result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )
    assembled = assemble_retrieval_result(session=db_session, settings=app_settings, retrieval_result=retrieval_result)

    assert retrieval_result.candidates[0].rerank_applied is False
    assert assembled.assembled_contexts[0].chunk_ids == [child.id]


def _build_candidate(
    chunk: DocumentChunk,
    *,
    source: str,
    rrf_rank: int = 1,
    vector_rank: int | None = 1,
    fts_rank: int | None = 1,
) -> RetrievalCandidate:
    """建立測試用 retrieval candidate。

    參數：
    - `chunk`：對應的 child chunk。
    - `source`：candidate 來源。
    - `rrf_rank`：RRF 排名。
    - `vector_rank`：vector recall 排名。
    - `fts_rank`：FTS recall 排名。

    回傳：
    - `RetrievalCandidate`：供 assembler 測試使用的 candidate。
    """

    return RetrievalCandidate(
        document_id=chunk.document_id,
        chunk_id=chunk.id,
        parent_chunk_id=chunk.parent_chunk_id,
        structure_kind=chunk.structure_kind,
        heading=chunk.heading,
        content=chunk.content,
        start_offset=chunk.start_offset,
        end_offset=chunk.end_offset,
        source=source,
        vector_rank=vector_rank,
        fts_rank=fts_rank,
        rrf_rank=rrf_rank,
        rrf_score=1.0 / (60 + rrf_rank),
        rerank_rank=rrf_rank,
        rerank_score=1.0,
        rerank_applied=True,
        rerank_fallback_reason=None,
    )


def _build_trace(*, query: str) -> RetrievalTrace:
    """建立測試用 retrieval trace。

    參數：
    - `query`：查詢文字。

    回傳：
    - `RetrievalTrace`：最小 trace 結構。
    """

    return RetrievalTrace(
        query=query,
        vector_top_k=8,
        fts_top_k=8,
        max_candidates=12,
        rerank_top_n=6,
        candidates=[],
    )


def _build_ready_child(
    *,
    app_settings: AppSettings,
    document_id: str,
    parent_chunk_id: str,
    chunk_id: str,
    position: int,
    section_index: int,
    child_index: int,
    heading: str,
    content: str,
    start_offset: int,
    end_offset: int,
) -> DocumentChunk:
    """建立測試用 ready child chunk。

    參數：
    - `app_settings`：測試設定，用於 embedding 維度。
    - `document_id`：文件識別碼。
    - `parent_chunk_id`：parent chunk 識別碼。
    - `chunk_id`：child chunk 識別碼。
    - `position`：chunk 排序位置。
    - `section_index`：section 順序。
    - `child_index`：parent 下 child 順序。
    - `heading`：段落標題。
    - `content`：chunk 內容。
    - `start_offset`：起始 offset。
    - `end_offset`：結束 offset。

    回傳：
    - `DocumentChunk`：可直接寫入資料庫的 child chunk。
    """

    return DocumentChunk(
        id=chunk_id,
        document_id=document_id,
        parent_chunk_id=parent_chunk_id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table if content.strip().startswith("|") else ChunkStructureKind.text,
        position=position,
        section_index=section_index,
        child_index=child_index,
        heading=heading,
        content=content,
        content_preview=content[:120],
        char_count=len(content),
        start_offset=start_offset,
        end_offset=end_offset,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
