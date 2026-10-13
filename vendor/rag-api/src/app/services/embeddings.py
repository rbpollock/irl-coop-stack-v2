"""API 使用的 embedding provider abstraction 與 hosted / self-hosted / Hugging Face embedding 實作。"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import AppSettings
from app.db.sql_types import DEFAULT_EMBEDDING_DIMENSIONS


# OpenRouter 的 OpenAI-compatible embeddings API base URL。
OPENROUTER_EMBEDDINGS_BASE_URL = "https://openrouter.ai/api/v1"
# Qwen3 embedding 官方建議的 retrieval query instruction。
HUGGINGFACE_EMBEDDING_QUERY_TASK_DESCRIPTION = "Given a web search query, retrieve relevant passages that answer the query"


@dataclass(frozen=True, slots=True)
class _HuggingFaceEmbeddingProfile:
    """Hugging Face embedding model 的推論設定。"""

    # tokenizer 預設 padding 方向。
    padding_side: str
    # 單次編碼允許的最大 token 長度。
    max_length: int
    # query 端要使用的 instruction；若為空值則不做 query prompt 包裝。
    query_task_description: str | None = None


class EmbeddingProvider(ABC):
    """Embedding provider 抽象介面。"""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """將多筆文字轉成 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

    def embed_query(self, query: str) -> list[float]:
        """將單筆查詢文字轉成 embedding。

        參數：
        - `query`：要送進 retrieval 的查詢文字。

        回傳：
        - `list[float]`：可直接用於 query embedding 的單筆向量。
        """

        return self.embed_texts([query])[0]


class DeterministicEmbeddingProvider(EmbeddingProvider):
    """供測試與離線環境使用的穩定假 embedding provider。"""

    def __init__(self, dimensions: int) -> None:
        """初始化 deterministic embedding provider。

        參數：
        - `dimensions`：輸出向量維度。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """將文字轉成可重現的假向量。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：可重現且已正規化的向量清單。
        """

        return [_build_deterministic_embedding(text=text, dimensions=self._dimensions) for text in texts]


class HostedEmbeddingProvider(EmbeddingProvider):
    """使用 OpenAI-compatible embeddings API 的 hosted provider 基底類別。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        provider_name: str,
        base_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        send_dimensions: bool = False,
        encoding_format: str | None = None,
    ) -> None:
        """初始化 hosted embedding provider。

        參數：
        - `api_key`：對應 provider 的 API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。
        - `provider_name`：目前 provider 的顯示名稱。
        - `base_url`：若需改用 OpenAI-compatible endpoint 時的 base URL。
        - `default_headers`：每次 request 都要帶上的額外 headers。
        - `send_dimensions`：是否在 request 中明確帶上 `dimensions`。
        - `encoding_format`：若 provider 需要指定 encoding format 時使用的值。

        回傳：
        - `None`：此建構子只負責建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError(f"缺少 openai 套件，無法建立 {provider_name} embedding provider。") from exc

        client_kwargs: dict[str, object] = {"api_key": api_key}
        if base_url is not None:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers

        self._client = OpenAI(**client_kwargs)
        self._model = model
        self._dimensions = dimensions
        self._provider_name = provider_name
        self._send_dimensions = send_dimensions
        self._encoding_format = encoding_format

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """呼叫 hosted embeddings API 產生 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

        request_kwargs: dict[str, object] = {"model": self._model, "input": texts}
        if self._send_dimensions:
            request_kwargs["dimensions"] = self._dimensions
        if self._encoding_format is not None:
            request_kwargs["encoding_format"] = self._encoding_format

        response = self._client.embeddings.create(**request_kwargs)
        embeddings = [list(item.embedding) for item in response.data]
        return [
            _normalize_embedding_dimensions(
                embedding=embedding,
                target_dimensions=self._dimensions,
                provider_name=self._provider_name,
            )
            for embedding in embeddings
        ]


class OpenAIEmbeddingProvider(HostedEmbeddingProvider):
    """使用 OpenAI embeddings API 的 provider。"""

    def __init__(self, *, api_key: str, model: str, dimensions: int) -> None:
        """初始化 OpenAI embedding provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。

        回傳：
        - `None`：此建構子只負責轉接到 hosted provider 基底類別。
        """

        super().__init__(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            provider_name="OpenAI",
            send_dimensions=True,
        )


class OpenRouterEmbeddingProvider(HostedEmbeddingProvider):
    """使用 OpenRouter embeddings API 的 provider。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int,
        http_referer: str | None,
        title: str | None,
    ) -> None:
        """初始化 OpenRouter embedding provider。

        參數：
        - `api_key`：OpenRouter API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度；會一併送進 OpenRouter request。
        - `http_referer`：可選的 `HTTP-Referer` header。
        - `title`：可選的 `X-OpenRouter-Title` header。

        回傳：
        - `None`：此建構子只負責轉接到 hosted provider 基底類別。
        """

        default_headers: dict[str, str] = {}
        if http_referer:
            default_headers["HTTP-Referer"] = http_referer
        if title:
            default_headers["X-OpenRouter-Title"] = title

        super().__init__(
            api_key=api_key,
            model=model,
            dimensions=dimensions,
            provider_name="OpenRouter",
            base_url=OPENROUTER_EMBEDDINGS_BASE_URL,
            default_headers=default_headers or None,
            send_dimensions=True,
            encoding_format="float",
        )


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """使用 Hugging Face 本機模型做 embedding 的 provider。"""

    def __init__(self, *, model: str, dimensions: int) -> None:
        """初始化 Hugging Face embedding provider。

        參數：
        - `model`：Hugging Face model id 或本機模型目錄路徑。
        - `dimensions`：預期輸出向量維度。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._model = model
        self._dimensions = dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """將文件文字清單轉成 embedding。

        參數：
        - `texts`：文件或 chunk 文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。

        風險：
        - 首次使用可能下載模型到本機 Hugging Face cache，並直接消耗當前行程可用的 CPU / GPU 記憶體。
        """

        return _embed_with_huggingface_model(
            model_name=self._model,
            texts=texts,
            target_dimensions=self._dimensions,
            input_kind="document",
        )

    def embed_query(self, query: str) -> list[float]:
        """將 retrieval query 轉成 embedding。

        參數：
        - `query`：使用者查詢文字。

        回傳：
        - `list[float]`：可直接送入 vector recall 的 query 向量。
        """

        return _embed_with_huggingface_model(
            model_name=self._model,
            texts=[query],
            target_dimensions=self._dimensions,
            input_kind="query",
        )[0]


class SelfHostedEmbeddingProvider(EmbeddingProvider):
    """使用自架 `/v1/embeddings` HTTP API 的 provider。"""

    def __init__(self, *, base_url: str, api_key: str, model: str, dimensions: int, timeout_seconds: float = 60.0) -> None:
        """初始化自架 embedding provider。

        參數：
        - `base_url`：自架 service 的 base URL，例如 `http://host:8000`。
        - `api_key`：自架 service 使用的 Bearer API key。
        - `model`：要使用的 embedding model 名稱。
        - `dimensions`：預期輸出向量維度。
        - `timeout_seconds`：每次 HTTP request 的 timeout 秒數。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        normalized_base_url = base_url.rstrip("/")
        self._endpoint = f"{normalized_base_url}/v1/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout_seconds = max(1.0, timeout_seconds)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """呼叫自架 HTTP API 產生 embeddings。

        參數：
        - `texts`：要嵌入的文字清單。

        回傳：
        - `list[list[float]]`：與輸入順序一致的向量結果。
        """

        payload = json.dumps(
            {
                "model": self._model,
                "input": texts,
            }
        ).encode("utf-8")
        request = Request(
            self._endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ValueError(f"Self-hosted embeddings 失敗：{exc}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Self-hosted embeddings API 呼叫失敗。") from exc

        raw_data = response_payload.get("data", [])
        embeddings: list[list[float]] = []
        for item in raw_data:
            embedding = item.get("embedding")
            if isinstance(embedding, list) and all(isinstance(value, (int, float)) for value in embedding):
                embeddings.append([float(value) for value in embedding])
        return [
            _normalize_embedding_dimensions(
                embedding=embedding,
                target_dimensions=self._dimensions,
                provider_name="Self-hosted",
            )
            for embedding in embeddings
        ]


def _resolve_self_hosted_embedding_config(settings: AppSettings) -> tuple[str | None, str | None, float]:
    """解析自架 embedding provider 的設定。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `tuple[str | None, str | None, float]`：依序為 base URL、API key 與 timeout 秒數。
    """

    base_url = settings.self_hosted_embedding_base_url or settings.self_hosted_rerank_base_url
    api_key = settings.self_hosted_embedding_api_key or settings.self_hosted_rerank_api_key
    timeout_seconds = settings.self_hosted_embedding_timeout_seconds or settings.self_hosted_rerank_timeout_seconds or 60.0
    return base_url, api_key, timeout_seconds


def build_embedding_provider(settings: AppSettings) -> EmbeddingProvider:
    """依照設定建立 embedding provider。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `EmbeddingProvider`：可供 retrieval 與 inline ingest 使用的 provider。
    """

    if settings.embedding_dimensions != DEFAULT_EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"目前 schema 固定使用 {DEFAULT_EMBEDDING_DIMENSIONS} 維 embedding，"
            f"不支援設定為 {settings.embedding_dimensions}。"
        )

    provider = settings.embedding_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicEmbeddingProvider(dimensions=settings.embedding_dimensions)
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("使用 OpenAI embeddings 前必須提供 OPENAI_API_KEY。")
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("使用 OpenRouter embeddings 前必須提供 OPENROUTER_API_KEY。")
        return OpenRouterEmbeddingProvider(
            api_key=settings.openrouter_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            http_referer=settings.openrouter_http_referer,
            title=settings.openrouter_title,
        )
    if provider == "huggingface":
        if not settings.embedding_model.strip():
            raise ValueError("使用 Hugging Face embeddings 前必須提供 EMBEDDING_MODEL。")
        return HuggingFaceEmbeddingProvider(
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    if provider == "self-hosted":
        base_url, api_key, timeout_seconds = _resolve_self_hosted_embedding_config(settings)
        if not base_url:
            raise ValueError("使用 self-hosted embeddings 前必須提供 SELF_HOSTED_EMBEDDING_BASE_URL 或 SELF_HOSTED_RERANK_BASE_URL。")
        if not api_key:
            raise ValueError("使用 self-hosted embeddings 前必須提供 SELF_HOSTED_EMBEDDING_API_KEY 或 SELF_HOSTED_RERANK_API_KEY。")
        return SelfHostedEmbeddingProvider(
            base_url=base_url,
            api_key=api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"不支援的 embedding provider：{settings.embedding_provider}")


def _embed_with_huggingface_model(
    *,
    model_name: str,
    texts: list[str],
    target_dimensions: int,
    input_kind: Literal["query", "document"],
) -> list[list[float]]:
    """使用本機 Hugging Face 模型將文字清單轉成 embeddings。

    參數：
    - `model_name`：Hugging Face model id 或本機模型目錄路徑。
    - `texts`：要編碼的文字清單。
    - `target_dimensions`：schema 固定要求的向量維度。
    - `input_kind`：目前輸入是 query 或 document，用於決定是否加 instruction。

    回傳：
    - `list[list[float]]`：與輸入順序一致、且已對齊 schema 維度的向量。
    """

    if not texts:
        return []

    profile = _resolve_huggingface_embedding_profile(model_name=model_name)
    tokenizer, model, device, torch_module = _load_huggingface_embedding_runtime(model_name=model_name)
    prepared_texts = [
        _format_huggingface_embedding_text(
            text=text,
            input_kind=input_kind,
            query_task_description=profile.query_task_description,
        )
        for text in texts
    ]
    tokenized_inputs = tokenizer(
        prepared_texts,
        padding=True,
        truncation=True,
        max_length=profile.max_length,
        return_tensors="pt",
    )
    model_inputs = _move_tokenized_inputs_to_device(tokenized_inputs=tokenized_inputs, device=device)

    with torch_module.no_grad():
        outputs = model(**model_inputs)
        pooled_embeddings = _last_token_pool(
            last_hidden_states=outputs.last_hidden_state,
            attention_mask=model_inputs["attention_mask"],
            torch_module=torch_module,
        )
        normalized_embeddings = torch_module.nn.functional.normalize(pooled_embeddings, p=2, dim=1)

    return [
        _normalize_embedding_dimensions(
            embedding=embedding,
            target_dimensions=target_dimensions,
            provider_name="Hugging Face",
        )
        for embedding in _tensor_rows_to_float_lists(tensor_like=normalized_embeddings)
    ]


def _resolve_huggingface_embedding_profile(*, model_name: str) -> _HuggingFaceEmbeddingProfile:
    """解析 Hugging Face embedding model 對應的推論設定。

    參數：
    - `model_name`：Hugging Face model id 或本機模型目錄路徑。

    回傳：
    - `_HuggingFaceEmbeddingProfile`：對應模型所需的 pooling / prompt 設定。
    """

    normalized_model_name = model_name.strip().lower()
    if "qwen3-embedding" in normalized_model_name:
        return _HuggingFaceEmbeddingProfile(
            padding_side="left",
            max_length=8192,
            query_task_description=HUGGINGFACE_EMBEDDING_QUERY_TASK_DESCRIPTION,
        )
    raise ValueError(
        "目前 Hugging Face embeddings 僅支援 Qwen3 Embedding 系列模型；"
        f"收到不支援的 EMBEDDING_MODEL={model_name!r}。"
    )


def _format_huggingface_embedding_text(
    *,
    text: str,
    input_kind: Literal["query", "document"],
    query_task_description: str | None,
) -> str:
    """依 Hugging Face model profile 格式化 embedding 輸入文字。

    參數：
    - `text`：原始輸入文字。
    - `input_kind`：目前輸入是 query 或 document。
    - `query_task_description`：query 端使用的 instruction；若為空值則不包裝。

    回傳：
    - `str`：實際送進 tokenizer 的文字。
    """

    if input_kind != "query" or not query_task_description:
        return text
    return f"Instruct: {query_task_description}\nQuery:{text}"


@lru_cache(maxsize=4)
def _load_huggingface_embedding_runtime(model_name: str) -> tuple[Any, Any, Any, Any]:
    """載入 Hugging Face embedding runtime。

    參數：
    - `model_name`：Hugging Face model id 或本機模型目錄路徑。

    回傳：
    - `tuple[Any, Any, Any, Any]`：`tokenizer`、`model`、`device` 與 `torch` 模組。
    """

    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - 依安裝環境而定。
        raise RuntimeError("使用 Hugging Face embeddings 前必須安裝 torch 與 transformers>=4.51.0。") from exc

    profile = _resolve_huggingface_embedding_profile(model_name=model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side=profile.padding_side)
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModel.from_pretrained(model_name, torch_dtype=torch_dtype)
    model = model.to(device)
    model.eval()
    return tokenizer, model, device, torch


def _move_tokenized_inputs_to_device(*, tokenized_inputs: Any, device: Any) -> Any:
    """將 tokenizer 輸出搬移到指定裝置。

    參數：
    - `tokenized_inputs`：tokenizer 產出的 tensor dict 或 batch encoding。
    - `device`：目標裝置名稱或 torch device。

    回傳：
    - `Any`：已搬移到指定裝置的輸入。
    """

    if hasattr(tokenized_inputs, "to"):
        return tokenized_inputs.to(device)
    if isinstance(tokenized_inputs, dict):
        return {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in tokenized_inputs.items()
        }
    return tokenized_inputs


def _last_token_pool(*, last_hidden_states: Any, attention_mask: Any, torch_module: Any) -> Any:
    """依 Qwen3 embedding 官方建議做 last-token pooling。

    參數：
    - `last_hidden_states`：模型輸出的最後一層 hidden states。
    - `attention_mask`：對應輸入的 attention mask。
    - `torch_module`：目前使用的 torch 模組。

    回傳：
    - `Any`：每筆輸入對應的 pooled embedding tensor。
    """

    left_padding = bool((attention_mask[:, -1].sum() == attention_mask.shape[0]).item())
    if left_padding:
        return last_hidden_states[:, -1]
    sequence_lengths = attention_mask.sum(dim=1) - 1
    batch_size = last_hidden_states.shape[0]
    positions = torch_module.arange(batch_size, device=last_hidden_states.device)
    return last_hidden_states[positions, sequence_lengths]


def _tensor_rows_to_float_lists(*, tensor_like: Any) -> list[list[float]]:
    """將 tensor-like embedding 結果轉成 Python float list rows。

    參數：
    - `tensor_like`：torch tensor 或具 `tolist()` 能力的 embedding 容器。

    回傳：
    - `list[list[float]]`：轉換後的二維 float 清單。
    """

    current_value = tensor_like
    for attribute_name in ("detach", "cpu", "float"):
        if hasattr(current_value, attribute_name):
            current_value = getattr(current_value, attribute_name)()
    if hasattr(current_value, "tolist"):
        raw_values = current_value.tolist()
    else:  # pragma: no cover - 依第三方 runtime 形狀而定。
        raise RuntimeError("Hugging Face embeddings 格式不支援。")
    return [[float(value) for value in row] for row in raw_values]


def _normalize_embedding_dimensions(
    *,
    embedding: list[float],
    target_dimensions: int,
    provider_name: str,
) -> list[float]:
    """將 provider 回傳向量正規化為 schema 固定維度。

    參數：
    - `embedding`：provider 原始回傳向量。
    - `target_dimensions`：目前 schema 固定要求的向量維度。
    - `provider_name`：目前 provider 名稱，供錯誤訊息使用。

    回傳：
    - `list[float]`：可直接寫入 schema 的固定維度向量。
    """

    current_dimensions = len(embedding)
    if current_dimensions == target_dimensions:
        return embedding
    if current_dimensions > target_dimensions:
        raise ValueError(
            f"{provider_name} embeddings 維度超出 schema 上限，預期最多 {target_dimensions}，實際 {current_dimensions}。"
        )
    return embedding + [0.0] * (target_dimensions - current_dimensions)


def _build_deterministic_embedding(*, text: str, dimensions: int) -> list[float]:
    """根據文字內容建立穩定且已正規化的假向量。

    參數：
    - `text`：輸入文字。
    - `dimensions`：輸出向量維度。

    回傳：
    - `list[float]`：可重現的單位向量。
    """

    raw_values: list[float] = []
    counter = 0
    while len(raw_values) < dimensions:
        digest = hashlib.sha256(f"{text}\0{counter}".encode("utf-8")).digest()
        for offset in range(0, len(digest), 4):
            block = digest[offset : offset + 4]
            integer = int.from_bytes(block, byteorder="big", signed=False)
            raw_values.append((integer / 0xFFFFFFFF) * 2.0 - 1.0)
            if len(raw_values) == dimensions:
                break
        counter += 1

    norm = math.sqrt(sum(value * value for value in raw_values)) or 1.0
    return [value / norm for value in raw_values]
