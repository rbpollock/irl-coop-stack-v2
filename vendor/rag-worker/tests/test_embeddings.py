"""Embedding provider 行為測試。"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from worker.embeddings import (
    HuggingFaceEmbeddingProvider,
    OpenAIEmbeddingProvider,
    OpenRouterEmbeddingProvider,
    SelfHostedEmbeddingProvider,
)


class _FakeTooLargeError(Exception):
    """模擬 hosted embedding request size 超限錯誤。"""

    status_code = 400


class _FakeRateLimitError(Exception):
    """模擬 hosted embedding rate limit 暫時性錯誤。"""

    status_code = 429


class _FakeEmbeddingsClient:
    """模擬 OpenAI-compatible embeddings.create 行為。"""

    def __init__(self, responder) -> None:
        """建立測試用 embeddings client。

        參數：
        - `responder`：根據 request kwargs 決定回傳或拋錯的 callable。

        回傳：
        - `None`：此建構子只負責保存 responder。
        """

        self._responder = responder
        self.calls: list[dict[str, object]] = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        """記錄呼叫參數，並回傳 responder 指定結果。

        參數：
        - `**kwargs`：模擬 OpenAI SDK `embeddings.create()` 的 request kwargs。

        回傳：
        - 任意：模擬 embeddings API response。
        """

        request_kwargs = dict(kwargs)
        self.calls.append(request_kwargs)
        return self._responder(request_kwargs)


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


def _build_openai_provider(*, client, dimensions: int = 4, max_batch_texts: int = 64) -> OpenAIEmbeddingProvider:
    """建立不經真實 OpenAI client 初始化的 OpenAI provider 測試實例。

    參數：
    - `client`：要注入的假 client。
    - `dimensions`：目標 schema 維度。
    - `max_batch_texts`：每批最大文字數。

    回傳：
    - `OpenAIEmbeddingProvider`：已注入假 client 的 provider。
    """

    provider = object.__new__(OpenAIEmbeddingProvider)
    provider._client = client
    provider._model = "text-embedding-3-small"
    provider._dimensions = dimensions
    provider._max_batch_texts = max_batch_texts
    provider._retry_max_attempts = 3
    provider._retry_base_delay_seconds = 0.0
    provider._provider_name = "OpenAI"
    provider._send_dimensions = False
    provider._encoding_format = None
    return provider


def _build_openrouter_provider(*, client, dimensions: int = 1024, max_batch_texts: int = 64) -> OpenRouterEmbeddingProvider:
    """建立不經真實 OpenAI client 初始化的 OpenRouter provider 測試實例。

    參數：
    - `client`：要注入的假 client。
    - `dimensions`：目標 schema 維度。
    - `max_batch_texts`：每批最大文字數。

    回傳：
    - `OpenRouterEmbeddingProvider`：已注入假 client 的 provider。
    """

    provider = object.__new__(OpenRouterEmbeddingProvider)
    provider._client = client
    provider._model = "qwen/qwen3-embedding-0.6b"
    provider._dimensions = dimensions
    provider._max_batch_texts = max_batch_texts
    provider._retry_max_attempts = 3
    provider._retry_base_delay_seconds = 0.0
    provider._provider_name = "OpenRouter"
    provider._send_dimensions = True
    provider._encoding_format = "float"
    return provider


def test_openai_embedding_provider_splits_oversized_batch_recursively() -> None:
    """當單批請求超過上限時，provider 應自動拆小後重送。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證 batch splitting 行為。
    """

    def responder(request_kwargs: dict[str, object]):
        batch = list(request_kwargs["input"])
        if len(batch) > 1:
            raise _FakeTooLargeError("Invalid 'input': maximum request size is 300000 tokens per request.")
        return _build_response(batch, dimensions=4)

    client = _FakeEmbeddingsClient(responder)
    provider = _build_openai_provider(client=client, max_batch_texts=8)

    embeddings = provider.embed_texts(["alpha", "beta", "gamma"])

    assert [call["input"] for call in client.calls] == [
        ["alpha", "beta", "gamma"],
        ["alpha"],
        ["beta", "gamma"],
        ["beta"],
        ["gamma"],
    ]
    assert embeddings == [
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0, 1.0],
    ]


def test_openai_embedding_provider_retries_transient_error() -> None:
    """暫時性 hosted embedding 失敗應在 provider 內重試後成功。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證 retry 行為。
    """

    attempts = {"count": 0}

    def responder(request_kwargs: dict[str, object]):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _FakeRateLimitError("rate limit")
        return _build_response(list(request_kwargs["input"]), dimensions=4)

    client = _FakeEmbeddingsClient(responder)
    provider = _build_openai_provider(client=client, max_batch_texts=8)

    embeddings = provider.embed_texts(["alpha"])

    assert attempts["count"] == 2
    assert [call["input"] for call in client.calls] == [["alpha"], ["alpha"]]
    assert embeddings == [[1.0, 1.0, 1.0, 1.0]]


def test_openai_embedding_provider_zero_pads_shorter_vectors() -> None:
    """當 provider 回傳維度小於 schema 時應自動零補齊。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證升維後的相容行為。
    """

    client = _FakeEmbeddingsClient(lambda request_kwargs: _build_response(list(request_kwargs["input"]), dimensions=3))
    provider = _build_openai_provider(client=client, dimensions=5)

    embeddings = provider.embed_texts(["alpha"])

    assert embeddings == [[1.0, 1.0, 1.0, 0.0, 0.0]]


def test_openrouter_embedding_provider_sends_dimensions_and_float_encoding() -> None:
    """OpenRouter request 應明確帶上 model、dimensions 與 `encoding_format=float`。

    參數：
    - 無

    回傳：
    - `None`：以斷言驗證 OpenRouter request payload。
    """

    client = _FakeEmbeddingsClient(lambda request_kwargs: _build_response(list(request_kwargs["input"]), dimensions=1024))
    provider = _build_openrouter_provider(client=client, dimensions=1024)

    embeddings = provider.embed_texts(["alpha"])

    assert client.calls == [
        {
            "model": "qwen/qwen3-embedding-0.6b",
            "input": ["alpha"],
            "dimensions": 1024,
            "encoding_format": "float",
        }
    ]
    assert len(embeddings[0]) == 1024


def test_openrouter_embedding_provider_uses_openrouter_client_options(monkeypatch) -> None:
    """OpenRouter provider 建構時應注入 base URL 與可選 headers。

    參數：
    - `monkeypatch`：pytest 提供的 monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 OpenAI client 建構參數。
    """

    openai_init_calls: list[dict[str, object]] = []

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
            self.embeddings = SimpleNamespace(
                create=lambda **request_kwargs: _build_response(list(request_kwargs["input"]), dimensions=1024)
            )

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    provider = OpenRouterEmbeddingProvider(
        api_key="openrouter-key",
        model="qwen/qwen3-embedding-0.6b",
        dimensions=1024,
        max_batch_texts=8,
        retry_max_attempts=3,
        retry_base_delay_seconds=0.0,
        http_referer="https://example.com",
        title="Deep Agent",
    )

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
    assert len(embeddings[0]) == 1024


def test_self_hosted_embedding_provider_uses_http_contract(monkeypatch) -> None:
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

    monkeypatch.setattr("worker.embeddings.urlopen", fake_urlopen)

    provider = SelfHostedEmbeddingProvider(
        base_url="http://helper.local:8000",
        api_key="embed-key",
        model="Qwen/Qwen3-Embedding-0.6B",
        dimensions=1024,
        max_batch_texts=8,
        retry_max_attempts=3,
        retry_base_delay_seconds=0.0,
        timeout_seconds=12.0,
    )

    embeddings = provider.embed_texts(["alpha"])

    assert captured_request["url"] == "http://helper.local:8000/v1/embeddings"
    assert captured_request["timeout"] == 12.0
    assert captured_request["headers"]["Authorization"] == "Bearer embed-key"
    assert '"model": "Qwen/Qwen3-Embedding-0.6B"' in captured_request["body"]
    assert embeddings == [[1.0, 1.0, 1.0] + [0.0] * 1021]


def test_huggingface_embedding_provider_uses_local_runtime_helper(monkeypatch) -> None:
    """Hugging Face embedding provider 應委派到本機模型 helper。"""

    captured_calls: list[dict[str, object]] = []

    def fake_embed_with_huggingface_model(*, model_name, texts, target_dimensions, input_kind):  # noqa: ANN001
        captured_calls.append(
            {
                "model_name": model_name,
                "texts": list(texts),
                "target_dimensions": target_dimensions,
                "input_kind": input_kind,
            }
        )
        return [[0.2] * target_dimensions for _ in texts]

    monkeypatch.setattr("worker.embeddings._embed_with_huggingface_model", fake_embed_with_huggingface_model)

    provider = HuggingFaceEmbeddingProvider(
        model="Qwen/Qwen3-Embedding-0.6B",
        dimensions=1024,
        max_batch_texts=2,
    )

    embeddings = provider.embed_texts(["alpha", "beta", "gamma"])

    assert captured_calls == [
        {
            "model_name": "Qwen/Qwen3-Embedding-0.6B",
            "texts": ["alpha", "beta"],
            "target_dimensions": 1024,
            "input_kind": "document",
        },
        {
            "model_name": "Qwen/Qwen3-Embedding-0.6B",
            "texts": ["gamma"],
            "target_dimensions": 1024,
            "input_kind": "document",
        },
    ]
    assert embeddings == [[0.2] * 1024, [0.2] * 1024, [0.2] * 1024]
