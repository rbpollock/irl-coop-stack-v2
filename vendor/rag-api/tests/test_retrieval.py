"""Internal retrieval service 與 rerank provider 測試。"""

from email.message import Message
from uuid import uuid4
from urllib.error import HTTPError

from fastapi import HTTPException
import pytest
from sqlalchemy import Integer, String, select

from app.auth.verifier import CurrentPrincipal
from app.db.models import (
    Area,
    AreaUserRole,
    ChunkStructureKind,
    ChunkType,
    Document,
    DocumentChunk,
    DocumentStatus,
    EvaluationQueryType,
    Role,
)
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS, Vector
from app.services.reranking import (
    CohereRerankProvider,
    DeterministicRerankProvider,
    HuggingFaceRerankProvider,
    RerankInputDocument,
    RerankScore,
    SelfHostedRerankProvider,
    _score_with_bge_reranker,
    _score_with_qwen_reranker,
    build_rerank_provider,
)
from app.services.retrieval_text import build_rerank_document_text
from app.services.retrieval_recall import (
    apply_python_rrf,
    build_match_chunks_rpc_statement,
)
from app.services.retrieval_rerank import apply_ranking_policy
from app.services.retrieval_runtime import retrieve_area_candidates
from app.services.retrieval_types import (
    RankedChunkMatch,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。"""

    return str(uuid4())


def test_build_rerank_provider_supports_deterministic_huggingface_cohere_and_self_hosted(app_settings) -> None:
    """rerank provider factory 應支援 deterministic、Hugging Face、Cohere 與 self-hosted。"""

    deterministic_settings = app_settings.model_copy(update={"rerank_provider": "deterministic"})
    huggingface_bge_settings = app_settings.model_copy(
        update={"rerank_provider": "bge", "rerank_model": "BAAI/bge-reranker-v2-m3"}
    )
    huggingface_qwen_settings = app_settings.model_copy(
        update={"rerank_provider": "qwen", "rerank_model": "Qwen/Qwen3-Reranker-0.6B"}
    )
    huggingface_generic_settings = app_settings.model_copy(
        update={"rerank_provider": "huggingface", "rerank_model": "BAAI/bge-reranker-v2-m3"}
    )
    cohere_settings = app_settings.model_copy(
        update={"rerank_provider": "cohere", "cohere_api_key": "test-key", "rerank_model": "rerank-v3.5"}
    )
    self_hosted_settings = app_settings.model_copy(
        update={
            "rerank_provider": "self-hosted",
            "self_hosted_rerank_base_url": "http://helper.local:8000",
            "self_hosted_rerank_api_key": "helper-key",
            "rerank_model": "BAAI/bge-reranker-v2-m3",
        }
    )

    deterministic_provider = build_rerank_provider(deterministic_settings)
    huggingface_bge_provider = build_rerank_provider(huggingface_bge_settings)
    huggingface_qwen_provider = build_rerank_provider(huggingface_qwen_settings)
    huggingface_generic_provider = build_rerank_provider(huggingface_generic_settings)
    cohere_provider = build_rerank_provider(cohere_settings)
    self_hosted_provider = build_rerank_provider(self_hosted_settings)

    assert isinstance(deterministic_provider, DeterministicRerankProvider)
    assert isinstance(huggingface_bge_provider, HuggingFaceRerankProvider)
    assert isinstance(huggingface_qwen_provider, HuggingFaceRerankProvider)
    assert isinstance(huggingface_generic_provider, HuggingFaceRerankProvider)
    assert isinstance(cohere_provider, CohereRerankProvider)
    assert isinstance(self_hosted_provider, SelfHostedRerankProvider)


def test_cohere_rerank_retries_only_on_http_429(monkeypatch) -> None:
    """Cohere rerank 只應在 HTTP 429 時等待並重試。"""

    call_count = {"value": 0}
    sleep_calls: list[float] = []
    headers = Message()
    headers["Retry-After"] = "1.5"

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """前兩次回 429，第三次成功。"""

        del request, timeout
        call_count["value"] += 1
        if call_count["value"] < 3:
            raise HTTPError(
                url="https://api.cohere.com/v2/rerank",
                code=429,
                msg="Too Many Requests",
                hdrs=headers,
                fp=None,
            )

        class _Response:
            """最小可用的 HTTP response 測試替身。"""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

            def read(self) -> bytes:
                return b'{\"results\": [{\"index\": 0, \"relevance_score\": 0.9}]}'

        return _Response()

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.reranking.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("app.services.reranking.random.uniform", lambda left, right: 1.1)

    provider = CohereRerankProvider(
        api_key="test-key",
        model="rerank-v3.5",
        retry_on_429_attempts=2,
        retry_on_429_backoff_seconds=2.0,
    )
    result = provider.rerank(
        query="alpha",
        documents=[RerankInputDocument(candidate_id="doc-1", text="alpha")],
        top_n=1,
    )

    assert [item.candidate_id for item in result] == ["doc-1"]
    assert call_count["value"] == 3
    assert sleep_calls == [pytest.approx(1.65), pytest.approx(1.65)]


def test_cohere_rerank_does_not_retry_non_429_http_error(monkeypatch) -> None:
    """Cohere rerank 不得對非 429 HTTP 錯誤重試。"""

    call_count = {"value": 0}
    sleep_calls: list[float] = []

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """固定回 500，模擬非可重試錯誤。"""

        del request, timeout
        call_count["value"] += 1
        raise HTTPError(
            url="https://api.cohere.com/v2/rerank",
            code=500,
            msg="Internal Server Error",
            hdrs=Message(),
            fp=None,
        )

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)
    monkeypatch.setattr("app.services.reranking.time.sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr("app.services.reranking.random.uniform", lambda left, right: 1.1)

    provider = CohereRerankProvider(
        api_key="test-key",
        model="rerank-v3.5",
        retry_on_429_attempts=3,
        retry_on_429_backoff_seconds=2.0,
    )

    try:
        provider.rerank(
            query="alpha",
            documents=[RerankInputDocument(candidate_id="doc-1", text="alpha")],
            top_n=1,
        )
    except RuntimeError as exc:
        assert "Cohere rerank API 呼叫失敗" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期 Cohere 非 429 錯誤應直接失敗。")

    assert call_count["value"] == 1
    assert sleep_calls == []


def test_build_rerank_provider_rejects_unsupported_provider(app_settings) -> None:
    """不支援的 rerank provider 應明確失敗。"""

    settings = app_settings.model_copy(update={"rerank_provider": "unsupported"})

    try:
        build_rerank_provider(settings)
    except ValueError as exc:
        assert "不支援的 rerank provider" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期 build_rerank_provider 應拋出 ValueError。")


def test_build_rerank_provider_requires_cohere_api_key(app_settings) -> None:
    """使用 Cohere rerank 前必須提供 API key。"""

    settings = app_settings.model_copy(update={"rerank_provider": "cohere", "cohere_api_key": None})

    try:
        build_rerank_provider(settings)
    except ValueError as exc:
        assert "COHERE_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 COHERE_API_KEY 時應拋出 ValueError。")


def test_build_rerank_provider_requires_self_hosted_base_url_and_api_key(app_settings) -> None:
    """使用 self-hosted rerank 前必須同時提供 base URL 與 API key。"""

    missing_base_url_settings = app_settings.model_copy(
        update={
            "rerank_provider": "self-hosted",
            "self_hosted_rerank_base_url": None,
            "self_hosted_rerank_api_key": "helper-key",
        }
    )
    missing_api_key_settings = app_settings.model_copy(
        update={
            "rerank_provider": "self-hosted",
            "self_hosted_rerank_base_url": "http://helper.local:8000",
            "self_hosted_rerank_api_key": None,
        }
    )

    try:
        build_rerank_provider(missing_base_url_settings)
    except ValueError as exc:
        assert "SELF_HOSTED_RERANK_BASE_URL" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 SELF_HOSTED_RERANK_BASE_URL 時應拋出 ValueError。")

    try:
        build_rerank_provider(missing_api_key_settings)
    except ValueError as exc:
        assert "SELF_HOSTED_RERANK_API_KEY" in str(exc)
    else:  # pragma: no cover - 失敗時才會進來。
        raise AssertionError("預期缺少 SELF_HOSTED_RERANK_API_KEY 時應拋出 ValueError。")


def test_self_hosted_rerank_provider_posts_contract_and_parses_scores(monkeypatch) -> None:
    """self-hosted rerank provider 應使用 `/v1/rerank` contract 並解析 `score` 欄位。"""

    captured_request: dict[str, object] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001
        """記錄 self-hosted request 並回傳最小成功 payload。"""

        headers = {key.lower(): value for key, value in request.header_items()}
        captured_request["timeout"] = timeout
        captured_request["url"] = request.full_url
        captured_request["method"] = request.get_method()
        captured_request["authorization"] = headers.get("authorization")
        captured_request["content_type"] = headers.get("content-type")
        captured_request["payload"] = request.data.decode("utf-8")

        class _Response:
            """最小可用的 HTTP response 測試替身。"""

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                del exc_type, exc, tb
                return False

            def read(self) -> bytes:
                return b'{\"results\": [{\"index\": 1, \"score\": 0.97}, {\"index\": 0, \"score\": 0.41}]}'

        return _Response()

    monkeypatch.setattr("app.services.reranking.urlopen", fake_urlopen)

    provider = SelfHostedRerankProvider(
        base_url="http://helper.local:8000/",
        api_key="helper-key",
        model="BAAI/bge-reranker-v2-m3",
        timeout_seconds=42.0,
    )
    results = provider.rerank(
        query="部署 rerank",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-1"]
    assert captured_request["timeout"] == 42.0
    assert captured_request["url"] == "http://helper.local:8000/v1/rerank"
    assert captured_request["method"] == "POST"
    assert captured_request["authorization"] == "Bearer helper-key"
    assert captured_request["content_type"] == "application/json"
    assert captured_request["payload"] == (
        '{"model": "BAAI/bge-reranker-v2-m3", "query": "\\u90e8\\u7f72 rerank", '
        '"documents": ["alpha", "beta"], "top_n": 2, "return_documents": false, "normalize": true}'
    )


def test_huggingface_rerank_provider_delegates_to_runtime_helper(monkeypatch) -> None:
    """Hugging Face rerank provider 應委派給通用 runtime helper 並回傳排序結果。"""

    captured_arguments: dict[str, object] = {}

    def fake_score_with_huggingface_reranker(*, query, documents, top_n, model_name):  # noqa: ANN001
        captured_arguments["query"] = query
        captured_arguments["documents"] = documents
        captured_arguments["top_n"] = top_n
        captured_arguments["model_name"] = model_name
        return [
            RerankScore(candidate_id="doc-2", score=0.9),
            RerankScore(candidate_id="doc-1", score=0.4),
        ]

    monkeypatch.setattr("app.services.reranking._score_with_huggingface_reranker", fake_score_with_huggingface_reranker)

    provider = HuggingFaceRerankProvider(model="BAAI/bge-reranker-v2-m3")
    results = provider.rerank(
        query="what is panda",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-1"]
    assert captured_arguments["model_name"] == "BAAI/bge-reranker-v2-m3"
    assert captured_arguments["top_n"] == 2


def test_score_with_bge_reranker_sorts_sigmoid_scores(monkeypatch) -> None:
    """BGE score helper 應將模型分數正規化後排序。"""

    class FakeTensor:
        """最小 tensor 測試替身。"""

        def __init__(self, values: list[float]) -> None:
            self._values = values

        def view(self, *_args) -> "FakeTensor":
            return self

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def float(self) -> "FakeTensor":
            return self

        def tolist(self) -> list[float]:
            return list(self._values)

    class FakeNoGrad:
        """模擬 torch.no_grad() context manager。"""

        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    class FakeTorchModule:
        """最小 torch 測試替身。"""

        @staticmethod
        def no_grad() -> FakeNoGrad:
            return FakeNoGrad()

        @staticmethod
        def sigmoid(tensor: FakeTensor) -> FakeTensor:
            del tensor
            return FakeTensor([0.2, 0.9, 0.6])

    class FakeTokenizer:
        """最小 tokenizer 測試替身。"""

        def __call__(self, pairs, *, padding, truncation, return_tensors, max_length):  # noqa: ANN001
            del padding, truncation, return_tensors, max_length
            assert pairs[0][0] == "which document"
            return {"input_ids": [1, 2, 3]}

    class FakeModel:
        """最小 model 測試替身。"""

        def __call__(self, **inputs):  # noqa: ANN003, ANN001
            del inputs

            class FakeOutput:
                """最小 logits 輸出替身。"""

                logits = FakeTensor([1.0, 3.0, 2.0])

            return FakeOutput()

    monkeypatch.setattr(
        "app.services.reranking._load_bge_reranker_runtime",
        lambda model_name: (FakeTokenizer(), FakeModel(), "cpu", FakeTorchModule()),
    )

    results = _score_with_bge_reranker(
        query="which document",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
            RerankInputDocument(candidate_id="doc-3", text="gamma"),
        ],
        top_n=2,
        model_name="BAAI/bge-reranker-v2-m3",
    )

    assert [item.candidate_id for item in results] == ["doc-2", "doc-3"]
    assert results[0].score == pytest.approx(0.9)


def test_score_with_qwen_reranker_formats_inputs_and_sorts_scores(monkeypatch) -> None:
    """Qwen score helper 應套用官方格式並依 yes 機率排序。"""

    class FakeTensor:
        """最小 tensor 測試替身。"""

        def __init__(self, values):
            self._values = values

        def __getitem__(self, key):  # noqa: ANN001
            if isinstance(key, tuple) and len(key) == 3:
                rows, last_index, columns = key
                del rows, columns
                if last_index == -1:
                    return FakeTensor([row[last_index] for row in self._values])
            if isinstance(key, tuple) and len(key) == 2:
                rows, column = key
                del rows
                if isinstance(column, int):
                    return FakeTensor([row[column] for row in self._values])
            raise TypeError("測試替身只支援欄位切片。")

        def exp(self) -> "FakeTensor":
            return self

        def detach(self) -> "FakeTensor":
            return self

        def cpu(self) -> "FakeTensor":
            return self

        def float(self) -> "FakeTensor":
            return self

        def tolist(self):
            return list(self._values)

    class FakeNoGrad:
        """模擬 torch.no_grad() context manager。"""

        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type, exc, tb) -> bool:
            del exc_type, exc, tb
            return False

    class FakeTorchModule:
        """最小 torch 測試替身。"""

        class nn:
            """最小 nn namespace。"""

            class functional:
                """最小 functional namespace。"""

                @staticmethod
                def log_softmax(tensor: FakeTensor, dim: int) -> FakeTensor:
                    del dim
                    return tensor

        @staticmethod
        def no_grad() -> FakeNoGrad:
            return FakeNoGrad()

        @staticmethod
        def stack(tensors, dim: int):  # noqa: ANN001
            del dim
            first_tensor, second_tensor = tensors
            return FakeTensor(
                [
                    [first_value, second_value]
                    for first_value, second_value in zip(first_tensor.tolist(), second_tensor.tolist(), strict=True)
                ]
            )

    class FakeTokenizer:
        """最小 tokenizer 測試替身。"""

        def __call__(
            self,
            inputs,
            *,
            padding=False,
            truncation=None,
            return_attention_mask=True,
            max_length=None,
            return_tensors=None,
        ):  # noqa: ANN001
            del padding, truncation, return_attention_mask, max_length, return_tensors
            if isinstance(inputs, list) and inputs and isinstance(inputs[0], str):
                assert "<Instruct>:" in inputs[0]
                return {"input_ids": [[11, 12], [21, 22]]}
            raise AssertionError("測試替身只預期收到格式化後的字串列表。")

        def pad(self, inputs, *, padding, return_tensors, max_length=None):  # noqa: ANN001
            del padding, return_tensors, max_length
            return {"input_ids": inputs["input_ids"]}

    class FakeModel:
        """最小 model 測試替身。"""

        def __call__(self, **inputs):  # noqa: ANN003, ANN001
            del inputs

            class FakeOutput:
                """最小 logits 輸出替身。"""

                logits = FakeTensor(
                    [
                        [[0.1, 0.8]],
                        [[0.1, 0.4]],
                    ]
                )

            return FakeOutput()

    monkeypatch.setattr(
        "app.services.reranking._load_qwen_reranker_runtime",
        lambda model_name: (
            FakeTokenizer(),
            FakeModel(),
            "cpu",
            FakeTorchModule(),
            [1, 2],
            [3, 4],
            0,
            1,
        ),
    )

    results = _score_with_qwen_reranker(
        query="which document",
        documents=[
            RerankInputDocument(candidate_id="doc-1", text="alpha"),
            RerankInputDocument(candidate_id="doc-2", text="beta"),
        ],
        top_n=2,
        model_name="Qwen/Qwen3-Reranker-0.6B",
    )

    assert [item.candidate_id for item in results] == ["doc-1", "doc-2"]
    assert results[0].score == pytest.approx(0.8)


def test_build_match_chunks_rpc_statement_uses_postgres_bind_types() -> None:
    """`match_chunks` RPC statement 應明確綁定 PostgreSQL 參數型別。"""

    statement = build_match_chunks_rpc_statement()
    bind_params = statement._bindparams
    query_embedding_type = bind_params["query_embedding"].type

    assert Vector is not None
    assert isinstance(query_embedding_type, Vector)
    assert getattr(query_embedding_type, "dim", None) == DEFAULT_EMBEDDING_DIMENSIONS
    assert isinstance(bind_params["query_text"].type, String)
    assert isinstance(bind_params["area_id"].type, String)
    assert isinstance(bind_params["vector_top_k"].type, Integer)
    assert isinstance(bind_params["fts_top_k"].type, Integer)


def test_retrieve_area_candidates_filters_non_ready_and_parent_chunks(db_session, app_settings) -> None:
    """retrieval 應只回 ready 文件的 child chunks，並保留 rerank metadata。"""

    area = Area(id=_uuid(), name="Retrieval Ready")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    ready_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="ready.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-ready/ready.md",
        status=DocumentStatus.ready,
    )
    uploaded_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="uploaded.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-uploaded/uploaded.md",
        status=DocumentStatus.uploaded,
    )
    db_session.add_all([ready_document, uploaded_document])
    ready_parent = DocumentChunk(
        id=_uuid(),
        document_id=ready_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Parent",
        content="中文檢索 parent",
        content_preview="中文檢索 parent",
        char_count=11,
        start_offset=0,
        end_offset=11,
    )
    ready_child = DocumentChunk(
        id=_uuid(),
        document_id=ready_document.id,
        parent_chunk_id=ready_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Ready Child",
        content="這是一段中文檢索內容 中文檢索",
        content_preview="這是一段中文檢索內容 中文檢索",
        char_count=15,
        start_offset=0,
        end_offset=15,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    uploaded_child = DocumentChunk(
        id=_uuid(),
        document_id=uploaded_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=0,
        heading="Uploaded Child",
        content="這是一段不該被看到的內容",
        content_preview="這是一段不該被看到的內容",
        char_count=12,
        start_offset=0,
        end_offset=12,
        embedding=[0.2] * app_settings.embedding_dimensions,
    )
    db_session.add_all([ready_parent, ready_child, uploaded_child])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="中文檢索",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == [ready_child.id]
    assert result.candidates[0].source == "hybrid"
    assert result.candidates[0].rrf_rank == 1
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[0].rerank_applied is True
    assert result.trace.query == "中文檢索"
    assert result.trace.candidates[0].chunk_id == ready_child.id


def test_retrieve_area_candidates_reranks_only_top_n_and_keeps_rest_in_rrf_order(db_session, app_settings) -> None:
    """rerank 應只重排前 top-n 筆，其他結果維持原 RRF 順序。"""

    settings = app_settings.model_copy(update={"rerank_top_n": 2})
    area = Area(id=_uuid(), name="Retrieval Rerank")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="rerank.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-rerank/rerank.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    alpha_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Alpha",
        content="alpha",
        content_preview="alpha",
        char_count=5,
        start_offset=0,
        end_offset=5,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    beta_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Beta",
        content="alpha alpha alpha",
        content_preview="alpha alpha alpha",
        char_count=17,
        start_offset=6,
        end_offset=23,
        embedding=[0.11] * settings.embedding_dimensions,
    )
    gamma_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=3,
        section_index=0,
        child_index=2,
        heading="Gamma",
        content="| item | value |\n| --- | --- |\n| alpha | 1 |",
        content_preview="| item | value |",
        char_count=46,
        start_offset=24,
        end_offset=70,
        embedding=[0.12] * settings.embedding_dimensions,
    )
    db_session.add_all([alpha_chunk, beta_chunk, gamma_chunk])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="alpha",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == [beta_chunk.id, alpha_chunk.id, gamma_chunk.id]
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[1].rerank_rank == 2
    assert result.candidates[2].rerank_rank is None
    assert result.candidates[2].rerank_applied is False


def test_apply_ranking_policy_downranks_table_of_contents_noise(db_session, app_settings) -> None:
    """ranking policy 應降低目錄噪音，避免商品 query 被目錄優先吃掉。"""

    document = Document(
        id=_uuid(),
        area_id=_uuid(),
        file_name="product-handbook.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="tests/product-handbook.md",
        status=DocumentStatus.ready,
    )
    toc_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=0,
        heading="目錄",
        content="十六、 保利美美元利率變動型終身壽險(NUIW6502)..................................................................123",
        content_preview="十六、 保利美美元利率變動型終身壽險(NUIW6502)..................................................................123",
        char_count=88,
        start_offset=100,
        end_offset=136,
    )
    body_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.table,
        position=1,
        section_index=1,
        child_index=0,
        heading="保利美美元利率變動型終身壽險",
        content="本險累計最高投保金額：美元 65 萬元。",
        content_preview="本險累計最高投保金額：美元 65 萬元。",
        char_count=21,
        start_offset=1000,
        end_offset=1021,
    )

    ranked = apply_ranking_policy(
        matches=[
            RankedChunkMatch(chunk=toc_chunk, vector_rank=1, fts_rank=1, rrf_rank=1, rrf_score=0.032),
            RankedChunkMatch(chunk=body_chunk, vector_rank=2, fts_rank=2, rrf_rank=2, rrf_score=0.031),
        ],
        query="保利美美元利率變動型終身壽險其累計最高投保金額為何",
        settings=app_settings,
    )

    assert ranked[0].chunk.id == body_chunk.id


def test_retrieve_area_candidates_falls_back_to_rrf_when_rerank_runtime_fails(
    db_session, app_settings, monkeypatch, caplog
) -> None:
    """rerank runtime 失敗時，retrieval 應回退到 RRF 結果。"""

    area = Area(id=_uuid(), name="Retrieval Fallback")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="fallback.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-fallback/fallback.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)
    fallback_chunk = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Fallback",
        content="fallback alpha",
        content_preview="fallback alpha",
        char_count=14,
        start_offset=0,
        end_offset=14,
        embedding=[0.2] * app_settings.embedding_dimensions,
    )
    db_session.add(fallback_chunk)
    db_session.commit()

    class FailingRerankProvider:
        """固定拋錯的 rerank provider 測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int):
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

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )

    assert [candidate.chunk_id for candidate in result.candidates] == [fallback_chunk.id]
    assert result.candidates[0].rerank_applied is False
    assert result.candidates[0].rerank_rank is None
    assert result.candidates[0].rerank_fallback_reason == "provider_error"
    assert result.trace.candidates[0].rerank_applied is False
    assert result.trace.candidates[0].rerank_fallback_reason == "provider_error"
    assert "Retrieval rerank provider failed; falling back to RRF order." in caplog.text


def test_retrieve_area_candidates_returns_same_404_for_missing_and_unauthorized(db_session, app_settings) -> None:
    """未授權 area 與不存在 area 的 retrieval 都應回相同 404。"""

    area = Area(id=_uuid(), name="Retrieval Secret")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-admin", role=Role.admin))
    db_session.commit()

    outsider = CurrentPrincipal(sub="user-outsider", groups=("/group/outsider",))

    unauthorized_error: HTTPException | None = None
    missing_error: HTTPException | None = None
    try:
        retrieve_area_candidates(
            session=db_session,
            principal=outsider,
            settings=app_settings,
            area_id=area.id,
            query="secret",
        )
    except HTTPException as exc:
        unauthorized_error = exc

    try:
        retrieve_area_candidates(
            session=db_session,
            principal=outsider,
            settings=app_settings,
            area_id="missing-area",
            query="secret",
        )
    except HTTPException as exc:
        missing_error = exc

    assert unauthorized_error is not None
    assert missing_error is not None
    assert getattr(unauthorized_error, "status_code", None) == 404
    assert getattr(missing_error, "status_code", None) == 404
    assert getattr(unauthorized_error, "detail", None) == getattr(missing_error, "detail", None)


def test_build_rerank_document_text_adds_prefixes_and_truncates_to_cost_guardrail() -> None:
    """rerank 文件文字應帶有 header/content 前綴並受最大字元數限制。"""

    assert (
        build_rerank_document_text(heading=" Intro ", content="  abcdef  ", max_chars=128)
        == "Header: Intro\nContent:\nabcdef"
    )
    assert build_rerank_document_text(heading="Intro", content="abcdef", max_chars=10) == "Header: In"


def test_build_rerank_document_text_preserves_all_hit_children_when_bundle_exceeds_budget() -> None:
    """多個 hit child 超出 budget 時，rerank 文字仍應保留每個 child 的片段。"""

    rerank_text = build_rerank_document_text(
        heading="Large Parent",
        content="alpha-start " + ("a" * 120) + "\n\nomega-start " + ("b" * 120),
        matched_child_contents=[
            "alpha-start " + ("a" * 120),
            "omega-start " + ("b" * 120),
        ],
        max_chars=140,
    )

    assert len(rerank_text) <= 280
    assert "[Hit child 1]" in rerank_text
    assert "[Hit child 2]" in rerank_text
    assert "alpha-start" in rerank_text
    assert "omega-start" in rerank_text


def test_build_rerank_document_text_expands_budget_for_multi_hit_children_with_hard_cap() -> None:
    """多 hit child 應套用 soft budget，但仍受 hard cap 限制。"""

    double_hit_text = build_rerank_document_text(
        heading="Double Hit",
        content="\n\n".join(["alpha " + ("a" * 300), "beta " + ("b" * 300)]),
        matched_child_contents=[
            "alpha " + ("a" * 300),
            "beta " + ("b" * 300),
        ],
        max_chars=200,
    )
    triple_hit_text = build_rerank_document_text(
        heading="Triple Hit",
        content="\n\n".join(
            [
                "alpha " + ("a" * 1600),
                "beta " + ("b" * 1600),
                "gamma " + ("c" * 1600),
            ]
        ),
        matched_child_contents=[
            "alpha " + ("a" * 1600),
            "beta " + ("b" * 1600),
            "gamma " + ("c" * 1600),
        ],
        max_chars=2000,
    )

    assert len(double_hit_text) <= 400
    assert len(double_hit_text) > 200
    assert len(triple_hit_text) <= 5000
    assert len(triple_hit_text) > 2000


def test_retrieve_area_candidates_uses_parent_level_rerank_documents(db_session, app_settings, monkeypatch) -> None:
    """rerank 應以 parent-level 組裝文字為輸入，且帶有固定前綴。"""

    area = Area(id=_uuid(), name="Retrieval Parent Rerank")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="parent-rerank.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-parent-rerank/parent-rerank.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Section One",
        content="alpha intro\n\nalpha details",
        content_preview="alpha intro",
        char_count=27,
        start_offset=0,
        end_offset=27,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Section One",
        content="alpha intro",
        content_preview="alpha intro",
        char_count=11,
        start_offset=0,
        end_offset=11,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_one.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Section One",
        content="alpha details",
        content_preview="alpha details",
        char_count=13,
        start_offset=13,
        end_offset=26,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    parent_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=3,
        section_index=1,
        child_index=None,
        heading="Section Two",
        content="beta only",
        content_preview="beta only",
        char_count=9,
        start_offset=28,
        end_offset=37,
    )
    child_three = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent_two.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=4,
        section_index=1,
        child_index=0,
        heading="Section Two",
        content="beta only",
        content_preview="beta only",
        char_count=9,
        start_offset=28,
        end_offset=37,
        embedding=[0.2] * app_settings.embedding_dimensions,
    )
    db_session.add_all([parent_one, child_one, child_two, parent_two, child_three])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄 rerank 輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query
            del top_n
            captured_documents.extend(documents)
            return [
                type("Score", (), {"candidate_id": document.candidate_id, "score": float(len(documents) - index)})()
                for index, document in enumerate(documents)
            ]

    monkeypatch.setattr("app.services.retrieval_rerank.build_rerank_provider", lambda settings: CapturingRerankProvider())

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="alpha",
    )

    assert len(captured_documents) == 2
    assert captured_documents[0].text == "Header: Section One\nContent:\nalpha intro\n\nalpha details"
    assert captured_documents[1].text == "Header: Section Two\nContent:\nbeta only"
    assert result.candidates[0].chunk_id == child_one.id
    assert result.candidates[1].chunk_id == child_two.id
    assert result.candidates[0].rerank_rank == 1
    assert result.candidates[1].rerank_rank == 1


def test_retrieve_area_candidates_preserves_all_hit_children_in_rerank_documents_when_budget_is_small(
    db_session, app_settings, monkeypatch
) -> None:
    """多個 hit child 落在同一 parent 且 rerank budget 很小時，仍應保留每個 hit child 的片段。"""

    settings = app_settings.model_copy(update={"rerank_max_chars_per_doc": 150})
    area = Area(id=_uuid(), name="Retrieval Hit Child Bundle")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))
    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="hit-child-bundle.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/document-hit-child-bundle/hit-child-bundle.md",
        status=DocumentStatus.ready,
    )
    db_session.add(document)

    parent = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="Large Parent",
        content=("alpha-start " + ("a" * 180)) + "\n\n" + ("omega-start " + ("b" * 180)),
        content_preview="large parent",
        char_count=388,
        start_offset=0,
        end_offset=388,
    )
    child_one = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="Large Parent",
        content="alpha-start " + ("a" * 180),
        content_preview="alpha-start",
        char_count=192,
        start_offset=0,
        end_offset=192,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    child_two = DocumentChunk(
        id=_uuid(),
        document_id=document.id,
        parent_chunk_id=parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=0,
        child_index=1,
        heading="Large Parent",
        content="omega-start " + ("b" * 180),
        content_preview="omega-start",
        char_count=192,
        start_offset=194,
        end_offset=386,
        embedding=[0.1] * settings.embedding_dimensions,
    )
    db_session.add_all([parent, child_one, child_two])
    db_session.commit()

    captured_documents: list[RerankInputDocument] = []

    class CapturingRerankProvider:
        """記錄 rerank 輸入的測試替身。"""

        def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list:
            """保存輸入並回傳固定分數。

            參數：
            - `query`：使用者查詢文字。
            - `documents`：送入 rerank 的 parent-level 文件。
            - `top_n`：最多回傳筆數。

            回傳：
            - `list[RerankScore]`：依輸入順序建立的固定分數結果。
            """

            del query, top_n
            captured_documents.extend(documents)
            return [type("Score", (), {"candidate_id": document.candidate_id, "score": 1.0})() for document in documents]

    monkeypatch.setattr("app.services.retrieval_rerank.build_rerank_provider", lambda settings: CapturingRerankProvider())

    retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="start",
    )

    assert len(captured_documents) == 1
    assert len(captured_documents[0].text) <= settings.rerank_max_chars_per_doc * 2
    assert len(captured_documents[0].text) > settings.rerank_max_chars_per_doc
    assert "[Hit child 1]" in captured_documents[0].text
    assert "[Hit child 2]" in captured_documents[0].text
    assert "alpha-start" in captured_documents[0].text
    assert "omega-start" in captured_documents[0].text


def test_retrieve_area_candidates_resolves_single_document_summary_scope_and_filters_other_documents(
    db_session, app_settings
) -> None:
    """單文件摘要應透過文件名稱解析收斂到單一文件。"""

    area = Area(id=_uuid(), name="Single Summary Retrieval")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))

    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤加盟辦法.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="area/dantei-policy.pdf",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="丹堤門市手冊.pdf",
        content_type="application/pdf",
        file_size=100,
        storage_key="area/dantei-manual.pdf",
        status=DocumentStatus.ready,
    )
    first_parent = DocumentChunk(
        id=_uuid(),
        document_id=first_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="丹堤加盟辦法",
        content="加盟辦法內容",
        content_preview="加盟辦法內容",
        char_count=6,
        start_offset=0,
        end_offset=6,
    )
    second_parent = DocumentChunk(
        id=_uuid(),
        document_id=second_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=1,
        child_index=None,
        heading="丹堤門市手冊",
        content="門市手冊內容",
        content_preview="門市手冊內容",
        char_count=6,
        start_offset=0,
        end_offset=6,
    )
    first_child = DocumentChunk(
        id=_uuid(),
        document_id=first_document.id,
        parent_chunk_id=first_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="丹堤加盟辦法",
        content="加盟辦法內容",
        content_preview="加盟辦法內容",
        char_count=6,
        start_offset=0,
        end_offset=6,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    second_child = DocumentChunk(
        id=_uuid(),
        document_id=second_document.id,
        parent_chunk_id=second_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=3,
        section_index=1,
        child_index=0,
        heading="丹堤門市手冊",
        content="門市手冊內容",
        content_preview="門市手冊內容",
        char_count=6,
        start_offset=0,
        end_offset=6,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([first_document, second_document, first_parent, second_parent, first_child, second_child])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="請摘要丹堤加盟辦法",
    )

    assert result.trace.summary_scope == "single_document"
    assert result.trace.selected_profile == "document_summary_single_document_diversified_v1"
    assert result.trace.resolved_document_ids == [first_document.id]
    assert result.trace.selected_document_ids == [first_document.id]
    assert all(candidate.document_id == first_document.id for candidate in result.candidates)


def test_retrieve_area_candidates_filters_fact_lookup_to_mentioned_document_scope(db_session, app_settings) -> None:
    """fact lookup 若高信心提及文件名稱，也應收斂到該 ready 文件範圍。"""

    area = Area(id=_uuid(), name="Fact Lookup Scoped Retrieval")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))

    first_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="alpha-policy.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/alpha-policy.md",
        status=DocumentStatus.ready,
    )
    second_document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="beta-manual.md",
        content_type="text/markdown",
        file_size=100,
        storage_key="area/beta-manual.md",
        status=DocumentStatus.ready,
    )
    first_parent = DocumentChunk(
        id=_uuid(),
        document_id=first_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=0,
        section_index=0,
        child_index=None,
        heading="alpha policy",
        content="alpha deadline is Monday",
        content_preview="alpha deadline is Monday",
        char_count=24,
        start_offset=0,
        end_offset=24,
    )
    second_parent = DocumentChunk(
        id=_uuid(),
        document_id=second_document.id,
        parent_chunk_id=None,
        chunk_type=ChunkType.parent,
        structure_kind=ChunkStructureKind.text,
        position=2,
        section_index=1,
        child_index=None,
        heading="beta manual",
        content="beta deadline is Tuesday",
        content_preview="beta deadline is Tuesday",
        char_count=24,
        start_offset=0,
        end_offset=24,
    )
    first_child = DocumentChunk(
        id=_uuid(),
        document_id=first_document.id,
        parent_chunk_id=first_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=1,
        section_index=0,
        child_index=0,
        heading="alpha policy",
        content="alpha deadline is Monday",
        content_preview="alpha deadline is Monday",
        char_count=24,
        start_offset=0,
        end_offset=24,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    second_child = DocumentChunk(
        id=_uuid(),
        document_id=second_document.id,
        parent_chunk_id=second_parent.id,
        chunk_type=ChunkType.child,
        structure_kind=ChunkStructureKind.text,
        position=3,
        section_index=1,
        child_index=0,
        heading="beta manual",
        content="beta deadline is Tuesday",
        content_preview="beta deadline is Tuesday",
        char_count=24,
        start_offset=0,
        end_offset=24,
        embedding=[0.1] * app_settings.embedding_dimensions,
    )
    db_session.add_all([first_document, second_document, first_parent, second_parent, first_child, second_child])
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=app_settings,
        area_id=area.id,
        query="What is the deadline in alpha policy?",
    )

    assert result.trace.query_type == EvaluationQueryType.fact_lookup.value
    assert result.trace.resolved_document_ids == [first_document.id]
    assert result.candidates
    assert all(candidate.document_id == first_document.id for candidate in result.candidates)


def test_retrieve_area_candidates_compare_selection_can_fill_beyond_four_parents(db_session, app_settings) -> None:
    """compare lane 在 budget 足夠時應可超過四個 selected parents。"""

    settings = app_settings.model_copy(update={"assembler_max_contexts": 6})
    area = Area(id=_uuid(), name="Compare Fill Retrieval")
    db_session.add(area)
    db_session.add(AreaUserRole(area_id=area.id, user_sub="user-reader", role=Role.reader))

    documents = [
        Document(
            id=_uuid(),
            area_id=area.id,
            file_name="alpha-policy.md",
            content_type="text/markdown",
            file_size=100,
            storage_key="area/alpha-policy.md",
            status=DocumentStatus.ready,
        ),
        Document(
            id=_uuid(),
            area_id=area.id,
            file_name="beta-manual.md",
            content_type="text/markdown",
            file_size=100,
            storage_key="area/beta-manual.md",
            status=DocumentStatus.ready,
        ),
    ]
    db_session.add_all(documents)
    position = 0
    for document, prefix in zip(documents, ("alpha", "beta"), strict=True):
        for index in range(3):
            parent = DocumentChunk(
                id=_uuid(),
                document_id=document.id,
                parent_chunk_id=None,
                chunk_type=ChunkType.parent,
                structure_kind=ChunkStructureKind.text,
                position=position,
                section_index=position,
                child_index=None,
                heading=f"{prefix}-{index}",
                content=f"{prefix} content {index}",
                content_preview=f"{prefix} content {index}",
                char_count=len(f"{prefix} content {index}"),
                start_offset=0,
                end_offset=len(f"{prefix} content {index}"),
            )
            child = DocumentChunk(
                id=_uuid(),
                document_id=document.id,
                parent_chunk_id=parent.id,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=position + 1,
                section_index=position,
                child_index=0,
                heading=f"{prefix}-{index}",
                content=f"{prefix} content {index}",
                content_preview=f"{prefix} content {index}",
                char_count=len(f"{prefix} content {index}"),
                start_offset=0,
                end_offset=len(f"{prefix} content {index}"),
                embedding=[0.1] * settings.embedding_dimensions,
            )
            db_session.add_all([parent, child])
            position += 2
    db_session.commit()

    result = retrieve_area_candidates(
        session=db_session,
        principal=CurrentPrincipal(sub="user-reader", groups=("/group/reader",)),
        settings=settings,
        area_id=area.id,
        query="比較 alpha policy 和 beta manual 的差異",
    )

    assert result.trace.selected_profile == "cross_document_compare_diversified_v1"
    assert result.trace.selection_applied is True
    assert result.trace.selection_strategy == "compare_coverage_then_fill_v1"
    assert result.trace.selected_document_count == 2
    assert result.trace.selected_parent_count == 6


def test_deterministic_rerank_provider_returns_stable_sorted_scores() -> None:
    """deterministic rerank provider 應回傳可重現且排序穩定的結果。"""

    provider = DeterministicRerankProvider()
    documents = [
        RerankInputDocument(candidate_id="a", text="alpha"),
        RerankInputDocument(candidate_id="b", text="alpha alpha"),
    ]

    first_scores = provider.rerank(query="alpha", documents=documents, top_n=2)
    second_scores = provider.rerank(query="alpha", documents=documents, top_n=2)

    assert [item.candidate_id for item in first_scores] == ["b", "a"]
    assert first_scores == second_scores


def test_apply_python_rrf_merges_vector_and_fts_ranks_stably(app_settings) -> None:
    """Python RRF 應能穩定合併 vector 與 FTS ranks。"""

    document = Document(
        id=_uuid(),
        area_id=_uuid(),
        file_name="rrf.md",
        content_type="text/markdown",
        file_size=10,
        storage_key="area/rrf/rrf.md",
        status=DocumentStatus.ready,
    )
    vector_only = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=2,
            section_index=0,
            child_index=1,
            heading="Vector",
            content="vector",
            content_preview="vector",
            char_count=6,
            start_offset=0,
            end_offset=6,
        ),
        vector_rank=1,
    )
    hybrid = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=1,
            section_index=0,
            child_index=0,
            heading="Hybrid",
            content="hybrid",
            content_preview="hybrid",
            char_count=6,
            start_offset=7,
            end_offset=13,
        ),
        vector_rank=3,
        fts_rank=1,
    )
    fts_only = RankedChunkMatch(
        chunk=DocumentChunk(
            id=_uuid(),
            document_id=document.id,
            parent_chunk_id=None,
            chunk_type=ChunkType.child,
            structure_kind=ChunkStructureKind.text,
            position=3,
            section_index=0,
            child_index=2,
            heading="FTS",
            content="fts",
            content_preview="fts",
            char_count=3,
            start_offset=14,
            end_offset=17,
        ),
        fts_rank=2,
    )

    merged = apply_python_rrf(matches=[vector_only, hybrid, fts_only], settings=app_settings)

    assert [match.chunk.heading for match in merged] == ["Hybrid", "Vector", "FTS"]
    assert [match.rrf_rank for match in merged] == [1, 2, 3]
    assert merged[0].rrf_score > merged[1].rrf_score > merged[2].rrf_score


def test_apply_ranking_policy_keeps_single_match_identity(app_settings) -> None:
    """ranking policy 在單一候選時應維持原候選內容。"""

    matches = [
        RankedChunkMatch(
            chunk=DocumentChunk(
                id=_uuid(),
                document_id=_uuid(),
                parent_chunk_id=None,
                chunk_type=ChunkType.child,
                structure_kind=ChunkStructureKind.text,
                position=1,
                section_index=0,
                child_index=0,
                heading="Policy",
                content="policy",
                content_preview="policy",
                char_count=6,
                start_offset=0,
                end_offset=6,
            ),
            vector_rank=1,
            rrf_rank=1,
            rrf_score=0.9,
        )
    ]

    ranked = apply_ranking_policy(matches=matches, query="policy", settings=app_settings)

    assert len(ranked) == 1
    assert ranked[0] is matches[0]
