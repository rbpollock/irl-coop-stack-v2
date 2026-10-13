"""Worker 文件 chunk indexing 與 retrieval preparation (Phase 6 PGroonga 版)。"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import repeat

from sqlalchemy import func, select, update

from worker.core.settings import WorkerSettings
from worker.db import (
    ChunkType,
    Document,
    DocumentChunk,
)
from worker.embedding_text import build_embedding_input_text
from worker.embeddings import build_embedding_provider
from worker.synopsis import (
    build_document_synopsis_provider,
    build_document_synopsis_source_text,
    build_section_synopsis_source_text,
    detect_synopsis_language,
    detect_section_synopsis_language,
)


def index_document_chunks(*, session, document: Document, settings: WorkerSettings) -> None:
    """對指定文件的 child chunks 寫入 embedding。
    
    在 Phase 6 中，全文檢索已切換為 PGroonga，它會直接在 `content` 欄位上自動建立索引，
    因此此處不再需要手動寫入 FTS payload。

    參數：
    - `session`：目前資料庫 session。
    - `document`：要建立 retrieval payload 的文件。
    - `settings`：worker 執行期設定。

    回傳：
    - `None`：此函式只負責更新 chunks 的向量資訊。
    """

    child_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.child)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not child_chunks:
        raise ValueError("文件沒有可供 retrieval 使用的 child chunks。")
    parent_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id, DocumentChunk.chunk_type == ChunkType.parent)
        .order_by(DocumentChunk.position.asc())
    ).all()
    if not parent_chunks:
        raise ValueError("文件沒有可供 document synopsis 使用的 parent chunks。")

    # 執行向量編碼
    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(
        [
            build_embedding_input_text(
                heading=chunk.heading,
                content=chunk.content,
            )
            for chunk in child_chunks
        ]
    )
    
    # 更新 embedding 欄位
    for chunk, embedding in zip(child_chunks, embeddings, strict=True):
        chunk.embedding = embedding

    if settings.document_section_synopsis_enabled:
        section_synopsis_texts = _generate_section_synopsis_texts(
            settings=settings,
            file_name=document.file_name,
            parent_chunks=parent_chunks,
        )
        section_synopsis_embeddings = provider.embed_texts(section_synopsis_texts)
        section_synopsis_updated_at = datetime.now(UTC)
        for parent_chunk, synopsis_text, synopsis_embedding in zip(
            parent_chunks,
            section_synopsis_texts,
            section_synopsis_embeddings,
            strict=True,
        ):
            parent_chunk.section_synopsis_text = synopsis_text
            parent_chunk.section_synopsis_embedding = synopsis_embedding
            parent_chunk.section_synopsis_updated_at = section_synopsis_updated_at
    else:
        for parent_chunk in parent_chunks:
            parent_chunk.section_synopsis_text = None
            parent_chunk.section_synopsis_embedding = None
            parent_chunk.section_synopsis_updated_at = None

    if settings.document_synopsis_enabled:
        synopsis_provider = build_document_synopsis_provider(settings)
        synopsis_source_text = build_document_synopsis_source_text(
            file_name=document.file_name,
            parent_chunks=parent_chunks,
            max_input_chars=settings.document_synopsis_max_input_chars,
        )
        synopsis_text = synopsis_provider.generate_synopsis(
            file_name=document.file_name,
            source_text=synopsis_source_text,
            output_language=detect_synopsis_language(parent_chunks=parent_chunks, file_name=document.file_name),
            max_output_chars=settings.document_synopsis_max_output_chars,
        )
        document.synopsis_text = synopsis_text
        document.synopsis_embedding = provider.embed_texts([synopsis_text])[0]
        document.synopsis_updated_at = datetime.now(UTC)
    else:
        document.synopsis_text = None
        document.synopsis_embedding = None
        document.synopsis_updated_at = None

    session.flush()


def _generate_section_synopsis_texts(
    *,
    settings: WorkerSettings,
    file_name: str,
    parent_chunks: list[DocumentChunk],
) -> list[str]:
    """以受控並發方式生成 parent-level section synopsis。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `parent_chunks`：依文件順序排列的 parent chunks。

    回傳：
    - `list[str]`：與 `parent_chunks` 順序一致的 section synopsis 文字。
    """

    heading_paths = [parent_chunk.heading_path for parent_chunk in parent_chunks]
    source_texts = [
        build_section_synopsis_source_text(
            file_name=file_name,
            heading_path=parent_chunk.heading_path,
            section_path_text=parent_chunk.section_path_text,
            content=parent_chunk.content,
            structure_kind=str(parent_chunk.structure_kind.value),
            max_input_chars=settings.document_synopsis_max_input_chars,
        )
        for parent_chunk in parent_chunks
    ]
    output_languages = [
        detect_section_synopsis_language(
            file_name=file_name,
            heading_path=parent_chunk.heading_path,
            content=parent_chunk.content,
        )
        for parent_chunk in parent_chunks
    ]
    max_workers = max(1, min(settings.document_synopsis_parallelism, len(parent_chunks)))
    if max_workers == 1:
        return [
            _generate_single_section_synopsis(
                settings,
                file_name,
                heading_path,
                source_text,
                output_language,
                settings.document_synopsis_max_output_chars,
            )
            for heading_path, source_text, output_language in zip(
                heading_paths,
                source_texts,
                output_languages,
                strict=True,
            )
        ]

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="section-synopsis") as executor:
        return list(
            executor.map(
                _generate_single_section_synopsis,
                repeat(settings),
                repeat(file_name),
                heading_paths,
                source_texts,
                output_languages,
                repeat(settings.document_synopsis_max_output_chars),
            )
        )


def _generate_single_section_synopsis(
    settings: WorkerSettings,
    file_name: str,
    heading_path: str | None,
    source_text: str,
    output_language: str,
    max_output_chars: int,
) -> str:
    """生成單一 section synopsis，供受控並發路徑重複呼叫。

    參數：
    - `settings`：worker 執行期設定。
    - `file_name`：目前文件檔名。
    - `heading_path`：目前 section 的階層路徑。
    - `source_text`：已做 path-aware 壓縮的輸入文字。
    - `output_language`：期望輸出語言。
    - `max_output_chars`：允許的 synopsis 最大字元數。

    回傳：
    - `str`：單一 parent chunk 的 section synopsis。
    """

    synopsis_provider = build_document_synopsis_provider(settings)
    return synopsis_provider.generate_section_synopsis(
        file_name=file_name,
        heading_path=heading_path,
        source_text=source_text,
        output_language=output_language,
        max_output_chars=max_output_chars,
    )
