"""API 使用的 rerank provider abstraction 與 Hugging Face / Cohere / self-hosted / deterministic 實作。"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import AppSettings

LOGGER = logging.getLogger(__name__)
# Hugging Face cross-encoder reranker 預設使用 512 token 輸入長度。
_HUGGINGFACE_SEQUENCE_RERANK_MAX_LENGTH = 512
# Hugging Face Qwen reranker 預設 instruction；依官方 model card 建議使用英文 instruction。
_HUGGINGFACE_QWEN_RERANK_DEFAULT_INSTRUCTION = "Given a web search query, retrieve relevant passages that answer the query"
# Hugging Face Qwen reranker 依官方範例預設使用 8192 token 上限。
_HUGGINGFACE_QWEN_RERANK_MAX_LENGTH = 8192
# Hugging Face Qwen reranker system prefix；限制輸出只能為 yes / no。
_HUGGINGFACE_QWEN_RERANK_SYSTEM_PREFIX = (
    '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the '
    'Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
# Hugging Face Qwen reranker assistant suffix；與官方範例一致。
_HUGGINGFACE_QWEN_RERANK_ASSISTANT_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


@dataclass(frozen=True, slots=True)
class _HuggingFaceRerankProfile:
    """Hugging Face reranker model 的推論設定。"""

    # 推論模式；`sequence_classification` 對應 cross-encoder，`causal_lm_yes_no` 對應 Qwen reranker。
    runtime_kind: Literal["sequence_classification", "causal_lm_yes_no"]


@dataclass(slots=True)
class RerankInputDocument:
    """rerank provider 使用的輸入文件結構。"""

    # 對應 retrieval candidate 的識別碼。
    candidate_id: str
    # 傳給 rerank provider 的文字內容。
    text: str


@dataclass(slots=True)
class RerankScore:
    """rerank provider 回傳的單筆分數結果。"""

    # 對應 retrieval candidate 的識別碼。
    candidate_id: str
    # rerank relevance score。
    score: float


class RerankProvider(ABC):
    """Rerank provider 抽象介面。"""

    @abstractmethod
    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """依照 query 對文件清單做 rerank。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 provider 排序後的分數結果。
        """


class DeterministicRerankProvider(RerankProvider):
    """供測試與離線環境使用的穩定 rerank provider。"""

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """以 query token overlap 與穩定雜湊建立可重現的 rerank 結果。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 deterministic 分數排序後的結果。
        """

        query_tokens = [token.strip().lower() for token in query.split() if token.strip()]
        scored_documents: list[RerankScore] = []
        for document in documents:
            normalized_text = document.text.lower()
            overlap_score = float(sum(normalized_text.count(token) for token in query_tokens))
            tie_breaker = _build_stable_fraction(seed=f"{query}\0{document.candidate_id}\0{document.text}")
            scored_documents.append(RerankScore(candidate_id=document.candidate_id, score=overlap_score + tie_breaker))

        return sorted(
            scored_documents,
            key=lambda item: (-item.score, item.candidate_id),
        )[:top_n]


class HuggingFaceRerankProvider(RerankProvider):
    """使用 Hugging Face 本機模型做 rerank 的 provider。"""

    def __init__(self, *, model: str) -> None:
        """初始化 Hugging Face rerank provider。

        參數：
        - `model`：Hugging Face model id 或本機模型路徑。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._model = model

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """使用 Hugging Face 本機 reranker 對候選文件重排。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 Hugging Face relevance score 排序後的結果。

        風險：
        - 此方法依賴本機 `torch + transformers` 與模型權重；首次載入可能有額外延遲與記憶體成本，
          並直接消耗當前 API 行程可用的 CPU / GPU 資源。
        """

        return _score_with_huggingface_reranker(
            query=query,
            documents=documents,
            top_n=top_n,
            model_name=self._model,
        )


class BGERerankProvider(HuggingFaceRerankProvider):
    """向後相容的 BGE provider alias，內部實作已收斂為 Hugging Face rerank provider。"""

class QwenRerankProvider(HuggingFaceRerankProvider):
    """向後相容的 Qwen provider alias，內部實作已收斂為 Hugging Face rerank provider。"""


class CohereRerankProvider(RerankProvider):
    """使用 Cohere Rerank v4 HTTP API 的 provider。"""

    _endpoint = "https://api.cohere.com/v2/rerank"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        retry_on_429_attempts: int = 0,
        retry_on_429_backoff_seconds: float = 0.0,
    ) -> None:
        """初始化 Cohere rerank provider。

        參數：
        - `api_key`：Cohere API key。
        - `model`：要使用的 rerank model 名稱。
        - `retry_on_429_attempts`：遇到 HTTP 429 時最多額外重試幾次。
        - `retry_on_429_backoff_seconds`：HTTP 429 重試的基礎等待秒數。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        self._api_key = api_key
        self._model = model
        self._retry_on_429_attempts = max(0, retry_on_429_attempts)
        self._retry_on_429_backoff_seconds = max(0.0, retry_on_429_backoff_seconds)

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """呼叫 Cohere HTTP API 產生 rerank 結果。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 Cohere relevance score 排序後的結果。

        風險：
        - 此方法會呼叫外部 API，timeout、5xx 或網路中斷需由上層以 fail-open fallback 處理。
        """

        payload = json.dumps(
            {
                "model": self._model,
                "query": query,
                "documents": [document.text for document in documents],
                "top_n": top_n,
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

        response_payload = self._request_with_retry(
            request=request,
            query=query,
            candidate_count=len(documents),
        )

        raw_results = response_payload.get("results", [])
        rerank_scores: list[RerankScore] = []
        for item in raw_results:
            index = item.get("index")
            relevance_score = item.get("relevance_score")
            if not isinstance(index, int) or not isinstance(relevance_score, (int, float)):
                continue
            if index < 0 or index >= len(documents):
                continue
            rerank_scores.append(RerankScore(candidate_id=documents[index].candidate_id, score=float(relevance_score)))
        return rerank_scores

    def _request_with_retry(
        self,
        *,
        request: Request,
        query: str,
        candidate_count: int,
    ) -> dict[str, object]:
        """在必要時僅針對 HTTP 429 執行重試/backoff。

        參數：
        - `request`：已建好的 Cohere HTTP request。
        - `query`：目前 rerank query，供 log/trace 使用。
        - `candidate_count`：本次送進 rerank 的文件數量。

        回傳：
        - `dict[str, object]`：Cohere JSON response payload。

        風險：
        - 此方法只應在 `429 Too Many Requests` 時等待並重試；其他 HTTP/network 錯誤必須立即失敗，避免掩蓋非暫時性問題。
        """

        attempt = 0
        max_attempts = self._retry_on_429_attempts + 1
        while attempt < max_attempts:
            attempt += 1
            try:
                with urlopen(request, timeout=10) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code != 429 or attempt >= max_attempts:
                    raise RuntimeError("Cohere rerank API 呼叫失敗。") from exc
                wait_seconds = _resolve_retry_wait_seconds(
                    http_error=exc,
                    attempt=attempt,
                    base_backoff_seconds=self._retry_on_429_backoff_seconds,
                )
                LOGGER.warning(
                    "Cohere rerank hit HTTP 429; retrying after backoff.",
                    extra={
                        "query": query,
                        "candidate_count": candidate_count,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "wait_seconds": wait_seconds,
                    },
                )
                time.sleep(wait_seconds)
            except (URLError, TimeoutError) as exc:
                raise RuntimeError("Cohere rerank API 呼叫失敗。") from exc
        raise RuntimeError("Cohere rerank API 呼叫失敗。")


class SelfHostedRerankProvider(RerankProvider):
    """使用自架 `/v1/rerank` HTTP API 的 provider。"""

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float = 10.0) -> None:
        """初始化自架 rerank provider。

        參數：
        - `base_url`：自架 service 的 base URL，例如 `http://host:8000`。
        - `api_key`：自架 service 使用的 Bearer API key。
        - `model`：要使用的 rerank model 名稱。
        - `timeout_seconds`：每次 HTTP request 的 timeout 秒數。

        回傳：
        - `None`：此建構子只負責保存設定。
        """

        normalized_base_url = base_url.rstrip("/")
        self._endpoint = f"{normalized_base_url}/v1/rerank"
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = max(1.0, timeout_seconds)

    def rerank(self, *, query: str, documents: list[RerankInputDocument], top_n: int) -> list[RerankScore]:
        """呼叫自架 HTTP API 產生 rerank 結果。

        參數：
        - `query`：使用者查詢文字。
        - `documents`：要送進 rerank 的候選文件。
        - `top_n`：最多回傳前幾名結果。

        回傳：
        - `list[RerankScore]`：依 self-hosted relevance score 排序後的結果。

        風險：
        - 此方法會呼叫外部 API，timeout、5xx 或網路中斷需由上層以 fail-open fallback 處理。
        """

        payload = json.dumps(
            {
                "model": self._model,
                "query": query,
                "documents": [document.text for document in documents],
                "top_n": top_n,
                "return_documents": False,
                "normalize": True,
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
            raise RuntimeError("Self-hosted rerank API 呼叫失敗。") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("Self-hosted rerank API 呼叫失敗。") from exc

        raw_results = response_payload.get("results", [])
        rerank_scores: list[RerankScore] = []
        for item in raw_results:
            index = item.get("index")
            score = item.get("score")
            if not isinstance(index, int) or not isinstance(score, (int, float)):
                continue
            if index < 0 or index >= len(documents):
                continue
            rerank_scores.append(RerankScore(candidate_id=documents[index].candidate_id, score=float(score)))
        return rerank_scores


def _resolve_self_hosted_rerank_config(settings: AppSettings) -> tuple[str | None, str | None, float]:
    """解析自架 rerank provider 的設定。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `tuple[str | None, str | None, float]`：依序為 base URL、API key 與 timeout 秒數。
    """

    base_url = settings.self_hosted_rerank_base_url
    api_key = settings.self_hosted_rerank_api_key
    timeout_seconds = settings.self_hosted_rerank_timeout_seconds
    return base_url, api_key, timeout_seconds


def build_rerank_provider(settings: AppSettings) -> RerankProvider:
    """依照設定建立 rerank provider。

    參數：
    - `settings`：API 執行期設定。

    回傳：
    - `RerankProvider`：可供 internal retrieval 使用的 rerank provider。
    """

    provider = settings.rerank_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicRerankProvider()
    if provider in {"huggingface", "bge", "qwen"}:
        if not settings.rerank_model.strip():
            raise ValueError("使用 Hugging Face rerank 前必須提供 RERANK_MODEL。")
        return HuggingFaceRerankProvider(model=settings.rerank_model)
    if provider == "cohere":
        if not settings.cohere_api_key:
            raise ValueError("使用 Cohere rerank 前必須提供 COHERE_API_KEY。")
        return CohereRerankProvider(
            api_key=settings.cohere_api_key,
            model=settings.rerank_model,
            retry_on_429_attempts=settings.rerank_retry_on_429_attempts,
            retry_on_429_backoff_seconds=settings.rerank_retry_on_429_backoff_seconds,
        )
    if provider == "self-hosted":
        base_url, api_key, timeout_seconds = _resolve_self_hosted_rerank_config(settings)
        if not base_url:
            raise ValueError("使用 self-hosted rerank 前必須提供 SELF_HOSTED_RERANK_BASE_URL。")
        if not api_key:
            raise ValueError("使用 self-hosted rerank 前必須提供 SELF_HOSTED_RERANK_API_KEY。")
        if not settings.rerank_model.strip():
            raise ValueError("使用 self-hosted rerank 前必須提供 RERANK_MODEL。")
        return SelfHostedRerankProvider(
            base_url=base_url,
            api_key=api_key,
            model=settings.rerank_model,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"不支援的 rerank provider：{settings.rerank_provider}")


def _score_with_huggingface_reranker(
    *,
    query: str,
    documents: list[RerankInputDocument],
    top_n: int,
    model_name: str,
) -> list[RerankScore]:
    """使用 Hugging Face 本機 reranker 對 query/document pairs 計分。

    參數：
    - `query`：使用者查詢文字。
    - `documents`：要送進 rerank 的候選文件。
    - `top_n`：最多回傳前幾名結果。
    - `model_name`：Hugging Face model id 或本機模型路徑。

    回傳：
    - `list[RerankScore]`：依分數由高到低排序的 rerank 結果。
    """

    profile = _resolve_huggingface_rerank_profile(model_name=model_name)
    if profile.runtime_kind == "sequence_classification":
        return _score_with_huggingface_sequence_classification_reranker(
            query=query,
            documents=documents,
            top_n=top_n,
            model_name=model_name,
        )
    return _score_with_huggingface_causal_lm_reranker(
        query=query,
        documents=documents,
        top_n=top_n,
        model_name=model_name,
    )


def _score_with_huggingface_sequence_classification_reranker(
    *,
    query: str,
    documents: list[RerankInputDocument],
    top_n: int,
    model_name: str,
) -> list[RerankScore]:
    """使用 Hugging Face sequence-classification reranker 對 pairs 計分。"""

    if top_n <= 0 or not documents:
        return []

    tokenizer, model, device, torch_module = _load_huggingface_sequence_classification_reranker_runtime(
        model_name=model_name
    )
    pairs = [[query, document.text] for document in documents]
    tokenized_inputs = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors="pt",
        max_length=_HUGGINGFACE_SEQUENCE_RERANK_MAX_LENGTH,
    )
    model_inputs = _move_tokenized_inputs_to_device(tokenized_inputs=tokenized_inputs, device=device)

    with torch_module.no_grad():
        raw_scores = model(**model_inputs, return_dict=True).logits.view(-1)
        normalized_scores = torch_module.sigmoid(raw_scores)

    score_values = _tensor_to_float_list(tensor_like=normalized_scores)
    scored_documents = [
        RerankScore(candidate_id=document.candidate_id, score=score_values[index])
        for index, document in enumerate(documents)
    ]
    return sorted(scored_documents, key=lambda item: (-item.score, item.candidate_id))[:top_n]


def _score_with_huggingface_causal_lm_reranker(
    *,
    query: str,
    documents: list[RerankInputDocument],
    top_n: int,
    model_name: str,
) -> list[RerankScore]:
    """使用 Hugging Face causal-LM reranker 對 pairs 計分。"""

    if top_n <= 0 or not documents:
        return []

    (
        tokenizer,
        model,
        device,
        torch_module,
        prefix_tokens,
        suffix_tokens,
        token_false_id,
        token_true_id,
    ) = _load_huggingface_causal_lm_reranker_runtime(model_name=model_name)
    formatted_pairs = [
        _format_huggingface_qwen_reranker_input(
            instruction=_HUGGINGFACE_QWEN_RERANK_DEFAULT_INSTRUCTION,
            query=query,
            document=document.text,
        )
        for document in documents
    ]
    tokenized_inputs = tokenizer(
        formatted_pairs,
        padding=False,
        truncation="longest_first",
        return_attention_mask=False,
        max_length=_HUGGINGFACE_QWEN_RERANK_MAX_LENGTH - len(prefix_tokens) - len(suffix_tokens),
    )
    for index, input_ids in enumerate(tokenized_inputs["input_ids"]):
        tokenized_inputs["input_ids"][index] = prefix_tokens + input_ids + suffix_tokens
    padded_inputs = tokenizer.pad(
        tokenized_inputs,
        padding=True,
        return_tensors="pt",
    )
    model_inputs = _move_tokenized_inputs_to_device(tokenized_inputs=padded_inputs, device=device)

    with torch_module.no_grad():
        logits = model(**model_inputs).logits[:, -1, :]
        false_scores = logits[:, token_false_id]
        true_scores = logits[:, token_true_id]
        pair_scores = torch_module.stack([false_scores, true_scores], dim=1)
        normalized_scores = torch_module.nn.functional.log_softmax(pair_scores, dim=1)[:, 1].exp()

    score_values = _tensor_to_float_list(tensor_like=normalized_scores)
    scored_documents = [
        RerankScore(candidate_id=document.candidate_id, score=score_values[index])
        for index, document in enumerate(documents)
    ]
    return sorted(scored_documents, key=lambda item: (-item.score, item.candidate_id))[:top_n]


def _score_with_bge_reranker(
    *,
    query: str,
    documents: list[RerankInputDocument],
    top_n: int,
    model_name: str,
) -> list[RerankScore]:
    """向後相容的 BGE helper；保留原本 monkeypatch 與測試介面。"""

    if top_n <= 0 or not documents:
        return []

    tokenizer, model, device, torch_module = _load_bge_reranker_runtime(model_name=model_name)
    pairs = [[query, document.text] for document in documents]
    tokenized_inputs = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors="pt",
        max_length=_HUGGINGFACE_SEQUENCE_RERANK_MAX_LENGTH,
    )
    model_inputs = _move_tokenized_inputs_to_device(tokenized_inputs=tokenized_inputs, device=device)

    with torch_module.no_grad():
        raw_scores = model(**model_inputs, return_dict=True).logits.view(-1)
        normalized_scores = torch_module.sigmoid(raw_scores)

    score_values = _tensor_to_float_list(tensor_like=normalized_scores)
    scored_documents = [
        RerankScore(candidate_id=document.candidate_id, score=score_values[index])
        for index, document in enumerate(documents)
    ]
    return sorted(scored_documents, key=lambda item: (-item.score, item.candidate_id))[:top_n]


def _score_with_qwen_reranker(
    *,
    query: str,
    documents: list[RerankInputDocument],
    top_n: int,
    model_name: str,
) -> list[RerankScore]:
    """向後相容的 Qwen helper；保留原本 monkeypatch 與測試介面。"""

    if top_n <= 0 or not documents:
        return []

    (
        tokenizer,
        model,
        device,
        torch_module,
        prefix_tokens,
        suffix_tokens,
        token_false_id,
        token_true_id,
    ) = _load_qwen_reranker_runtime(model_name=model_name)
    formatted_pairs = [
        _format_qwen_reranker_input(
            instruction=_HUGGINGFACE_QWEN_RERANK_DEFAULT_INSTRUCTION,
            query=query,
            document=document.text,
        )
        for document in documents
    ]
    tokenized_inputs = tokenizer(
        formatted_pairs,
        padding=False,
        truncation="longest_first",
        return_attention_mask=False,
        max_length=_HUGGINGFACE_QWEN_RERANK_MAX_LENGTH - len(prefix_tokens) - len(suffix_tokens),
    )
    for index, input_ids in enumerate(tokenized_inputs["input_ids"]):
        tokenized_inputs["input_ids"][index] = prefix_tokens + input_ids + suffix_tokens
    padded_inputs = tokenizer.pad(
        tokenized_inputs,
        padding=True,
        return_tensors="pt",
    )
    model_inputs = _move_tokenized_inputs_to_device(tokenized_inputs=padded_inputs, device=device)

    with torch_module.no_grad():
        logits = model(**model_inputs).logits[:, -1, :]
        false_scores = logits[:, token_false_id]
        true_scores = logits[:, token_true_id]
        pair_scores = torch_module.stack([false_scores, true_scores], dim=1)
        normalized_scores = torch_module.nn.functional.log_softmax(pair_scores, dim=1)[:, 1].exp()

    score_values = _tensor_to_float_list(tensor_like=normalized_scores)
    scored_documents = [
        RerankScore(candidate_id=document.candidate_id, score=score_values[index])
        for index, document in enumerate(documents)
    ]
    return sorted(scored_documents, key=lambda item: (-item.score, item.candidate_id))[:top_n]


@lru_cache(maxsize=4)
def _load_huggingface_sequence_classification_reranker_runtime(model_name: str) -> tuple[Any, Any, Any, Any]:
    """載入並快取 Hugging Face sequence-classification reranker runtime。

    參數：
    - `model_name`：Hugging Face model id 或本機模型路徑。

    回傳：
    - `tuple[Any, Any, Any, Any]`：`tokenizer`、`model`、`device` 與 `torch` 模組。
    """

    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - 依安裝環境而定。
        raise RuntimeError("使用 Hugging Face rerank 前必須安裝 torch 與 transformers。") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name, torch_dtype=torch_dtype)
    model = model.to(device)
    model.eval()
    return tokenizer, model, device, torch


@lru_cache(maxsize=4)
def _load_huggingface_causal_lm_reranker_runtime(
    model_name: str,
) -> tuple[Any, Any, Any, Any, list[int], list[int], int, int]:
    """載入並快取 Hugging Face causal-LM reranker runtime。

    參數：
    - `model_name`：Hugging Face model id 或本機模型路徑。

    回傳：
    - `tuple[Any, Any, Any, Any, list[int], list[int], int, int]`：`tokenizer`、`model`、`device`、`torch`
      模組、prefix token ids、suffix token ids、`no` token id 與 `yes` token id。
    """

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - 依安裝環境而定。
        raise RuntimeError("使用 Hugging Face Qwen rerank 前必須安裝 torch 與 transformers>=4.51.0。") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(model_name, padding_side="left")
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch_dtype)
    model = model.to(device)
    model.eval()
    prefix_tokens = tokenizer.encode(_HUGGINGFACE_QWEN_RERANK_SYSTEM_PREFIX, add_special_tokens=False)
    suffix_tokens = tokenizer.encode(_HUGGINGFACE_QWEN_RERANK_ASSISTANT_SUFFIX, add_special_tokens=False)
    token_false_id = tokenizer.convert_tokens_to_ids("no")
    token_true_id = tokenizer.convert_tokens_to_ids("yes")
    return tokenizer, model, device, torch, prefix_tokens, suffix_tokens, token_false_id, token_true_id


def _resolve_huggingface_rerank_profile(*, model_name: str) -> _HuggingFaceRerankProfile:
    """解析 Hugging Face reranker model 對應的推論設定。

    參數：
    - `model_name`：Hugging Face model id 或本機模型目錄路徑。

    回傳：
    - `_HuggingFaceRerankProfile`：對應模型所需的 runtime 類型設定。
    """

    normalized_model_name = model_name.strip().lower()
    if "bge-reranker" in normalized_model_name:
        return _HuggingFaceRerankProfile(runtime_kind="sequence_classification")
    if "qwen3-reranker" in normalized_model_name:
        return _HuggingFaceRerankProfile(runtime_kind="causal_lm_yes_no")
    raise ValueError(
        "目前 Hugging Face rerank 僅支援 BGE Reranker 與 Qwen3 Reranker 系列模型；"
        f"收到不支援的 RERANK_MODEL={model_name!r}。"
    )


def _format_huggingface_qwen_reranker_input(*, instruction: str, query: str, document: str) -> str:
    """建立 Hugging Face Qwen reranker 單筆輸入文字。

    參數：
    - `instruction`：Qwen reranker 使用的 task instruction。
    - `query`：使用者查詢文字。
    - `document`：候選文件內容。

    回傳：
    - `str`：符合 Qwen 官方範例格式的 rerank 輸入文字。
    """

    return "<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}".format(
        instruction=instruction,
        query=query,
        document=document,
    )


def _load_bge_reranker_runtime(model_name: str) -> tuple[Any, Any, Any, Any]:
    """向後相容的 BGE runtime loader alias。"""

    return _load_huggingface_sequence_classification_reranker_runtime(model_name)


def _load_qwen_reranker_runtime(model_name: str) -> tuple[Any, Any, Any, Any, list[int], list[int], int, int]:
    """向後相容的 Qwen runtime loader alias。"""

    return _load_huggingface_causal_lm_reranker_runtime(model_name)


def _format_qwen_reranker_input(*, instruction: str, query: str, document: str) -> str:
    """向後相容的 Qwen 輸入格式化 alias。"""

    return _format_huggingface_qwen_reranker_input(
        instruction=instruction,
        query=query,
        document=document,
    )


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


def _tensor_to_float_list(*, tensor_like: Any) -> list[float]:
    """將 tensor-like 分數轉成 Python float list。

    參數：
    - `tensor_like`：torch tensor 或具 `tolist()` 能力的分數容器。

    回傳：
    - `list[float]`：轉換後的 float 分數列表。
    """

    current_value = tensor_like
    for attribute_name in ("detach", "cpu", "float"):
        if hasattr(current_value, attribute_name):
            current_value = getattr(current_value, attribute_name)()
    if hasattr(current_value, "tolist"):
        raw_values = current_value.tolist()
    elif isinstance(current_value, (list, tuple)):
        raw_values = list(current_value)
    else:  # pragma: no cover - 依第三方 runtime 形狀而定。
        raise RuntimeError("BGE rerank 分數格式不支援。")
    return [float(value) for value in raw_values]


def _resolve_retry_wait_seconds(*, http_error: HTTPError, attempt: int, base_backoff_seconds: float) -> float:
    """決定 HTTP 429 重試前要等待多久。

    參數：
    - `http_error`：Cohere 回傳的 HTTP 429 錯誤。
    - `attempt`：目前是第幾次嘗試，從 1 開始。
    - `base_backoff_seconds`：沒有 `Retry-After` header 時的基礎等待秒數。

    回傳：
    - `float`：下一次重試前要等待的秒數。
    """

    retry_after_header = http_error.headers.get("Retry-After") if http_error.headers else None
    base_wait_seconds: float | None = None
    if retry_after_header:
        try:
            retry_after_seconds = float(retry_after_header)
        except ValueError:
            retry_after_seconds = None
        else:
            if retry_after_seconds > 0:
                base_wait_seconds = retry_after_seconds
    if base_wait_seconds is None:
        base_wait_seconds = max(base_backoff_seconds, 0.0) * attempt
    return _apply_retry_jitter(base_wait_seconds=base_wait_seconds)


def _apply_retry_jitter(*, base_wait_seconds: float) -> float:
    """為 retry/backoff 等待秒數加入隨機抖動。

    參數：
    - `base_wait_seconds`：尚未加入 jitter 的基礎等待秒數。

    回傳：
    - `float`：加入 jitter 後實際要等待的秒數。
    """

    if base_wait_seconds <= 0:
        return 0.0
    jitter_multiplier = random.uniform(0.75, 1.25)
    return max(base_wait_seconds * jitter_multiplier, 0.1)


def _build_stable_fraction(*, seed: str) -> float:
    """根據 seed 建立穩定且可重現的小數分數。

    參數：
    - `seed`：用來產生穩定分數的字串。

    回傳：
    - `float`：介於 0 與 1 之間的小數。
    """

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return integer / float(2**64 - 1)
