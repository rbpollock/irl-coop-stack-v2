"""API embedding provider 測試。"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from app.core.settings import AppSettings
from app.services.embeddings import (
    HuggingFaceEmbeddingProvider,
    OpenAIEmbeddingProvider,
    SelfHostedEmbeddingProvider,
    build_embedding_provider,
)


def _build_response(batch: list[str], *, dimensions: int):
    """建立與 OpenAI SDK 相容的假 response 物件。

    參數：
    - `batch`：本次回應對應的輸入批次。
    - `dimensions`：每筆向量的維度。

    回傳：
    - 任意：帶有 `data[].embedding` 結構的假 response。
    """

    return SimpleNamespace(
        data=[SimpleNamespace(embedding=[float(index)] * dimensions) for index, _ in enumerate(batch, start=1)]
    )


def test_openai_embedding_provider_zero_pads_shorter_vectors() -> None:
    """OpenAI-compatible provider 回傳較短向量時應自動零補齊到 schema 維度。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證升維後的相容行為。
    """

    provider = object.__new__(OpenAIEmbeddingProvider)
    provider._client = SimpleNamespace(
        embeddings=SimpleNamespace(create=lambda **request_kwargs: _build_response(list(request_kwargs["input"]), dimensions=3))
    )
    provider._model = "text-embedding-3-small"
    provider._dimensions = 5
    provider._provider_name = "OpenAI"
    provider._send_dimensions = False
    provider._encoding_format = None

    embeddings = provider.embed_texts(["alpha"])

    assert embeddings == [[1.0, 1.0, 1.0, 0.0, 0.0]]


def test_build_embedding_provider_openrouter_uses_openrouter_client_options(monkeypatch) -> None:
    """OpenRouter provider factory 應注入 base URL、headers 與 1024 維 request。

    參數：
    - `monkeypatch`：pytest 提供的 monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 OpenRouter provider factory 行為。
    """

    openai_init_calls: list[dict[str, object]] = []
    request_calls: list[dict[str, object]] = []

    class FakeOpenAI:
        """模擬 `openai.OpenAI` client。"""

        def __init__(self, **kwargs) -> None:
            """記錄 client 初始化參數。

            參數：
            - `**kwargs`：傳入 `OpenAI(...)` 的建構參數。

            回傳：
            - `None`：此建構子只負責記錄參數。
            """

            openai_init_calls.append(dict(kwargs))
            self.embeddings = SimpleNamespace(create=self.create)

        def create(self, **kwargs):
            """記錄 embeddings request，並回傳 1024 維向量。

            參數：
            - `**kwargs`：傳入 `embeddings.create(...)` 的 request 參數。

            回傳：
            - 任意：模擬 OpenRouter embeddings response。
            """

            request_calls.append(dict(kwargs))
            return _build_response(list(kwargs["input"]), dimensions=1024)

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    settings = AppSettings(
        _env_file=None,
        EMBEDDING_PROVIDER="openrouter",
        EMBEDDING_MODEL="qwen/qwen3-embedding-0.6b",
        EMBEDDING_DIMENSIONS=1536,
        OPENROUTER_API_KEY="openrouter-key",
        OPENROUTER_HTTP_REFERER="https://example.com",
        OPENROUTER_TITLE="Deep Agent",
    )

    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(["alpha"])

    assert openai_init_calls == [
        {
            "api_key": "openrouter-key",
            "base_url": "https://openrouter.ai/api/v1",
            "default_headers": {
                "HTTP-Referer": "https://example.com",
                "X-OpenRouter-Title": "Deep Agent",
            },
        }
    ]
    assert request_calls == [
        {
            "model": "qwen/qwen3-embedding-0.6b",
            "input": ["alpha"],
            "dimensions": 1536,
            "encoding_format": "float",
        }
    ]
    assert len(embeddings[0]) == 1536


def test_build_embedding_provider_self_hosted_uses_http_contract(monkeypatch) -> None:
    """self-hosted embedding provider 應使用 `/v1/embeddings` contract。

    參數：
    - `monkeypatch`：pytest 提供的 monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 self-hosted request 與回應解析。
    """

    captured_request: dict[str, object] = {}

    class FakeResponse:
        """模擬 `urlopen()` 回傳物件。"""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'{"object":"list","model":"Qwen/Qwen3-Embedding-0.6B","data":[{"object":"embedding","index":0,"embedding":[1.0,1.0,1.0]}]}'
            )

    def fake_urlopen(request, timeout):
        captured_request["url"] = request.full_url
        captured_request["timeout"] = timeout
        captured_request["headers"] = dict(request.header_items())
        captured_request["body"] = request.data.decode("utf-8")
        return FakeResponse()

    monkeypatch.setattr("app.services.embeddings.urlopen", fake_urlopen)

    settings = AppSettings(
        _env_file=None,
        EMBEDDING_PROVIDER="self-hosted",
        EMBEDDING_MODEL="Qwen/Qwen3-Embedding-0.6B",
        EMBEDDING_DIMENSIONS=1536,
        SELF_HOSTED_EMBEDDING_BASE_URL="http://helper.local:8000",
        SELF_HOSTED_EMBEDDING_API_KEY="embed-key",
        SELF_HOSTED_EMBEDDING_TIMEOUT_SECONDS=12.0,
    )

    provider = build_embedding_provider(settings)
    embeddings = provider.embed_texts(["alpha"])

    assert isinstance(provider, SelfHostedEmbeddingProvider)
    assert captured_request["url"] == "http://helper.local:8000/v1/embeddings"
    assert captured_request["timeout"] == 12.0
    assert captured_request["headers"]["Authorization"] == "Bearer embed-key"
    assert '"model": "Qwen/Qwen3-Embedding-0.6B"' in captured_request["body"]
    assert embeddings == [[1.0, 1.0, 1.0] + [0.0] * 1533]


def test_build_embedding_provider_huggingface_uses_local_runtime_helper(monkeypatch) -> None:
    """Hugging Face embedding provider 應委派到本機模型 helper。"""

    captured_call: dict[str, object] = {}

    def fake_embed_with_huggingface_model(*, model_name, texts, target_dimensions, input_kind):  # noqa: ANN001
        captured_call["model_name"] = model_name
        captured_call["texts"] = list(texts)
        captured_call["target_dimensions"] = target_dimensions
        captured_call["input_kind"] = input_kind
        return [[0.1] * target_dimensions]

    monkeypatch.setattr("app.services.embeddings._embed_with_huggingface_model", fake_embed_with_huggingface_model)

    settings = AppSettings(
        _env_file=None,
        EMBEDDING_PROVIDER="huggingface",
        EMBEDDING_MODEL="Qwen/Qwen3-Embedding-0.6B",
        EMBEDDING_DIMENSIONS=1536,
    )

    provider = build_embedding_provider(settings)
    embedding = provider.embed_query("alpha question")

    assert isinstance(provider, HuggingFaceEmbeddingProvider)
    assert captured_call == {
        "model_name": "Qwen/Qwen3-Embedding-0.6B",
        "texts": ["alpha question"],
        "target_dimensions": 1536,
        "input_kind": "query",
    }
    assert embedding == [0.1] * 1536
