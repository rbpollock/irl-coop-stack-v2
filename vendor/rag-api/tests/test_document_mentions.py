"""文件名稱提及解析與 summary scope 判定測試。"""

from uuid import uuid4

from app.auth.verifier import CurrentPrincipal
from app.db.models import Area, AreaUserRole, Document, DocumentStatus, EvaluationQueryType, Role
from app.services.document_mentions import resolve_document_mentions, resolve_summary_scope


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_document_mention_resolver_returns_single_document_for_unique_basename(db_session) -> None:
    """唯一高信心 basename 命中時，應解析為單一文件。"""

    area = Area(id=_uuid(), name="Document Mention Area")
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤加盟辦法.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="documents/dantei-policy.pdf",
        status=DocumentStatus.ready,
    )
    db_session.add_all([area, AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader), document])
    db_session.commit()

    result = resolve_document_mentions(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        area_id=area.id,
        query="請摘要丹堤加盟辦法",
    )

    assert result.resolved_document_ids == (document.id,)
    assert resolve_summary_scope(
        query_type=EvaluationQueryType.document_summary,
        mention_resolution=result,
    ) == "single_document"


def test_document_mention_resolver_prefers_unique_suffix_after_summary_prefix_cleanup(db_session) -> None:
    """摘要前綴與版次尾碼不應阻止唯一 suffix 文件被判為 single-document。"""

    area = Area(id=_uuid(), name="Document Mention Prefix Cleanup Area")
    target_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="新契約個人保險投保規則手冊-核保及行政篇(114年9月版).pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="documents/underwriting-admin.pdf",
        status=DocumentStatus.ready,
    )
    sibling_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="新契約個人保險投保規則手冊-商品篇(114年9月版).pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="documents/product-chapter.pdf",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            target_document,
            sibling_document,
        ]
    )
    db_session.commit()

    result = resolve_document_mentions(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        area_id=area.id,
        query="總結一下 新契約個人保險投保規則手冊-核保及行政篇",
    )

    assert result.resolved_document_ids == (target_document.id,)
    assert result.candidates[0].document_id == target_document.id


def test_document_mention_resolver_returns_multi_document_for_two_explicit_file_mentions(db_session) -> None:
    """精準提到兩份文件時，應解析為 multi-document。"""

    area = Area(id=_uuid(), name="Multi Document Mention Area")
    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤加盟辦法.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="documents/dantei-policy.pdf",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤門市手冊.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=100,
        storage_key="documents/dantei-manual.docx",
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

    result = resolve_document_mentions(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        area_id=area.id,
        query="請摘要丹堤加盟辦法和丹堤門市手冊",
    )

    assert result.resolved_document_ids == (first_document.id, second_document.id)
    assert resolve_summary_scope(
        query_type=EvaluationQueryType.document_summary,
        mention_resolution=result,
    ) == "multi_document"


def test_document_mention_resolver_returns_multi_document_for_ambiguous_short_query(db_session) -> None:
    """短且模糊的 query 命中多份文件時，不得誤判為 single-document。"""

    area = Area(id=_uuid(), name="Ambiguous Document Mention Area")
    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤加盟辦法.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="documents/dantei-policy.pdf",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤門市手冊.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size=100,
        storage_key="documents/dantei-manual.docx",
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

    result = resolve_document_mentions(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        area_id=area.id,
        query="請摘要丹堤",
    )

    assert result.resolved_document_ids == ()


def test_document_mention_resolver_ignores_unauthorized_and_non_ready_documents(db_session) -> None:
    """resolver 只能看見已授權且 ready 的文件。"""

    area = Area(id=_uuid(), name="Mention Authorization Area")
    visible_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="公開作業規範.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="documents/public-rules.md",
        status=DocumentStatus.ready,
    )
    hidden_not_ready_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="公開作業規範-草稿.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="documents/public-rules-draft.md",
        status=DocumentStatus.processing,
    )
    hidden_other_area = Area(id=_uuid(), name="Hidden Area")
    hidden_document = Document(
        id=_uuid(),
        area_id=hidden_other_area.id,
        file_name="公開作業規範-機密.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="documents/public-rules-secret.md",
        status=DocumentStatus.ready,
    )
    db_session.add_all(
        [
            area,
            hidden_other_area,
            AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader),
            visible_document,
            hidden_not_ready_document,
            hidden_document,
        ]
    )
    db_session.commit()

    result = resolve_document_mentions(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        area_id=area.id,
        query="請摘要公開作業規範",
    )

    assert result.resolved_document_ids == (visible_document.id,)
    assert all(candidate["document_id"] != hidden_document.id for candidate in [
        {
            "document_id": item.document_id,
            "file_name": item.file_name,
        }
        for item in result.candidates
    ])
