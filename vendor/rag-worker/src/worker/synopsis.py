"""Worker 使用的 document synopsis 生成與輸入壓縮。"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypedDict

from worker.core.settings import WorkerSettings

if TYPE_CHECKING:
    from worker.db import DocumentChunk


# CJK 字元偵測，用來決定 synopsis 輸出語言。
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
# 壓縮多餘空白，避免 synopsis prompt 被 parser 噪音放大。
_WHITESPACE_PATTERN = re.compile(r"\s+")


class OpenAIReasoningPayload(TypedDict):
    """OpenAI Responses API 的 reasoning payload。"""

    # GPT-5 family reasoning effort。
    effort: str


class OpenAITextPayload(TypedDict):
    """OpenAI Responses API 的 text payload。"""

    # GPT-5 family text verbosity。
    verbosity: str


class OpenAIChatCompletionKwargs(TypedDict, total=False):
    """傳給 `chat.completions.create()` 的 kwargs。"""

    # 使用的模型名稱。
    model: str
    # chat completions 路徑的輸出 token 上限。
    max_completion_tokens: int
    # 非 GPT-5 路徑使用的溫度。
    temperature: float


class OpenAIResponsesKwargs(TypedDict):
    """傳給 `responses.create()` 的 kwargs。"""

    # 使用的模型名稱。
    model: str
    # Responses API 的輸出 token 上限。
    max_output_tokens: int
    # GPT-5 reasoning 設定。
    reasoning: OpenAIReasoningPayload
    # GPT-5 text 設定。
    text: OpenAITextPayload


class DocumentSynopsisProvider(ABC):
    """Document synopsis provider 抽象介面。"""

    @abstractmethod
    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """根據受控來源文字產生 document synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：可持久化的 document synopsis 文字。
        """

    @abstractmethod
    def generate_section_synopsis(
        self,
        *,
        file_name: str,
        heading_path: str | None,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """根據受控來源文字產生 section synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `heading_path`：目前 section 的階層路徑。
        - `source_text`：已做 path-aware 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：可持久化的 section synopsis 文字。
        """


class DeterministicDocumentSynopsisProvider(DocumentSynopsisProvider):
    """供測試與離線環境使用的穩定 synopsis provider。"""

    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """以規則式方式建立固定格式 synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：固定格式且長度受控的 synopsis。
        """

        headings = _extract_source_lines(source_text=source_text, prefix="Heading:")
        table_points = _extract_source_lines(source_text=source_text, prefix="Table/Structure:")
        body_points = _extract_source_lines(source_text=source_text, prefix="Excerpt:")

        if output_language == "zh-TW":
            synopsis = "\n".join(
                [
                    f"主題：{_truncate_text(_normalize_inline_text(file_name), 80)}",
                    "重要章節：" + ("；".join(headings[:4]) if headings else "未提供明確章節標題。"),
                    "主要結論：" + (body_points[0] if body_points else "未提供足夠內容。"),
                    "表格與結構重點：" + ("；".join(table_points[:3]) if table_points else "未偵測到明確表格重點。"),
                ]
            )
        else:
            synopsis = "\n".join(
                [
                    f"Topic: {_truncate_text(_normalize_inline_text(file_name), 80)}",
                    "Key sections: " + ("; ".join(headings[:4]) if headings else "No explicit section headings were detected."),
                    "Main conclusions: " + (body_points[0] if body_points else "No sufficient body content was detected."),
                    "Tables and structure: " + ("; ".join(table_points[:3]) if table_points else "No explicit table highlights were detected."),
                ]
            )
        return _finalize_synopsis_text(synopsis=synopsis, max_output_chars=max_output_chars)

    def generate_section_synopsis(
        self,
        *,
        file_name: str,
        heading_path: str | None,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """以規則式方式建立固定格式 section synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `heading_path`：目前 section 的階層路徑。
        - `source_text`：已做 path-aware 壓縮的輸入文字。
        - `output_language`：期望輸出語言。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：固定格式且長度受控的 section synopsis。
        """

        path_text = _normalize_inline_text(heading_path or file_name)
        excerpt_lines = _extract_source_lines(source_text=source_text, prefix="Excerpt:")
        structure_lines = _extract_source_lines(source_text=source_text, prefix="Table/Structure:")

        if output_language == "zh-TW":
            synopsis = "\n".join(
                [
                    f"章節主題：{_truncate_text(path_text, 80)}",
                    "章節路徑：" + _truncate_text(path_text, 100),
                    "區段重點：" + (excerpt_lines[0] if excerpt_lines else "未提供足夠內容。"),
                    "結構觀察：" + (structure_lines[0] if structure_lines else "未偵測到明確結構重點。"),
                ]
            )
        else:
            synopsis = "\n".join(
                [
                    f"Section topic: {_truncate_text(path_text, 80)}",
                    "Section path: " + _truncate_text(path_text, 100),
                    "Key points: " + (excerpt_lines[0] if excerpt_lines else "No sufficient section content was detected."),
                    "Structure notes: " + (structure_lines[0] if structure_lines else "No explicit structural highlight was detected."),
                ]
            )
        return _finalize_synopsis_text(synopsis=synopsis, max_output_chars=max_output_chars)


class OpenAIDocumentSynopsisProvider(DocumentSynopsisProvider):
    """使用 OpenAI API 生成 document synopsis。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_output_tokens: int,
        reasoning_effort: str,
        text_verbosity: str,
    ) -> None:
        """初始化 OpenAI synopsis provider。

        參數：
        - `api_key`：OpenAI API key。
        - `model`：要使用的 chat model 名稱。
        - `max_output_tokens`：Responses API 的硬性輸出 token 上限。
        - `reasoning_effort`：GPT-5 family 的 reasoning effort。
        - `text_verbosity`：GPT-5 family 的輸出冗長度。

        回傳：
        - `None`：此建構子只負責建立 client 與保存設定。
        """

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - 依賴缺失時於執行期明確失敗。
            raise RuntimeError("缺少 openai 套件，無法建立 document synopsis provider。") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._max_output_tokens = max(256, max_output_tokens)
        self._reasoning_effort = reasoning_effort
        self._text_verbosity = text_verbosity

    def _build_completion_kwargs(self, *, max_output_chars: int) -> OpenAIChatCompletionKwargs:
        """建立 OpenAI chat completion kwargs，並處理模型相容性。

        參數：
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `dict[str, object]`：可直接傳給 `chat.completions.create()` 的參數。
        """

        kwargs: OpenAIChatCompletionKwargs = {
            "model": self._model,
            "max_completion_tokens": max(256, min(1200, max_output_chars)),
        }
        if not _is_gpt5_family_model(self._model):
            kwargs["temperature"] = 0.1
        return kwargs

    def _build_responses_kwargs(self) -> OpenAIResponsesKwargs:
        """建立 GPT-5 family 使用的 Responses API kwargs。

        參數：
        - 無

        回傳：
        - `dict[str, object]`：可直接傳給 `responses.create()` 的參數。
        """

        kwargs: OpenAIResponsesKwargs = {
            "model": self._model,
            "max_output_tokens": self._max_output_tokens,
            "reasoning": {"effort": self._reasoning_effort},
            "text": {"verbosity": self._text_verbosity},
        }
        return kwargs

    def _create_synopsis_response(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_chars: int,
        failure_prefix: str,
    ) -> str:
        """依模型相容性呼叫對應 OpenAI API，並抽取 synopsis 文字。

        參數：
        - `system_prompt`：提供模型的系統指令。
        - `user_prompt`：提供模型的使用者內容。
        - `max_output_chars`：允許的 synopsis 最大字元數。
        - `failure_prefix`：失敗訊息前綴。

        回傳：
        - `str`：經驗證與長度控制後的 synopsis 文字。
        """

        try:
            if _is_gpt5_family_model(self._model):
                response = self._client.responses.create(
                    **self._build_responses_kwargs(),
                    instructions=system_prompt,
                    input=user_prompt,
                )
                content = _extract_response_output_text(response)
                if not isinstance(content, str) or not content.strip():
                    incomplete_reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
                    if incomplete_reason == "max_output_tokens":
                        raise ValueError(f"{failure_prefix}：模型在 max_output_tokens 內未產生可見輸出。")
                    raise ValueError(f"{failure_prefix}：LLM 未回傳有效內容。")
                return _finalize_synopsis_text(synopsis=content, max_output_chars=max_output_chars)

            response = self._client.chat.completions.create(
                **self._build_completion_kwargs(max_output_chars=max_output_chars),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except Exception as exc:  # pragma: no cover - network/provider failure path.
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"{failure_prefix}：{exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"{failure_prefix}：LLM 未回傳有效內容。")
        return _finalize_synopsis_text(synopsis=content, max_output_chars=max_output_chars)

    def generate_synopsis(
        self,
        *,
        file_name: str,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """呼叫 OpenAI 產生長度受控的 document synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `source_text`：已做全 parent coverage 壓縮的輸入文字。
        - `output_language`：期望輸出語言，正式支援 `zh-TW` 與 `en`。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：經驗證與長度控制後的 synopsis 文字。
        """

        language_label = "台灣繁體中文" if output_language == "zh-TW" else "English"
        system_prompt = (
            "You generate document-level synopses for retrieval. "
            "Keep the output factual, compact, and grounded only in the provided source summary."
        )
        user_prompt = (
            f"File name: {file_name}\n"
            f"Output language: {language_label}\n"
            f"Maximum characters: {max_output_chars}\n\n"
            "Write a document synopsis with exactly these sections in the requested language:\n"
            "1. Topic\n"
            "2. Key sections\n"
            "3. Main conclusions\n"
            "4. Tables and structure highlights\n\n"
            "Rules:\n"
            "- Stay within the maximum characters.\n"
            "- Use plain text only.\n"
            "- Do not invent facts not present in the source.\n"
            "- If the source is incomplete, state that conservatively.\n\n"
            "Compressed source:\n"
            f"{source_text}"
        )
        return self._create_synopsis_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_chars=max_output_chars,
            failure_prefix="document synopsis 生成失敗",
        )

    def generate_section_synopsis(
        self,
        *,
        file_name: str,
        heading_path: str | None,
        source_text: str,
        output_language: str,
        max_output_chars: int,
    ) -> str:
        """呼叫 OpenAI 產生長度受控的 section synopsis。

        參數：
        - `file_name`：目前文件檔名。
        - `heading_path`：目前 section 的階層路徑。
        - `source_text`：已做 path-aware 壓縮的輸入文字。
        - `output_language`：期望輸出語言。
        - `max_output_chars`：允許的 synopsis 最大字元數。

        回傳：
        - `str`：經驗證與長度控制後的 section synopsis 文字。
        """

        language_label = "台灣繁體中文" if output_language == "zh-TW" else "English"
        system_prompt = (
            "You generate section-level synopses for retrieval. "
            "Keep the output factual, compact, and grounded only in the provided section summary."
        )
        user_prompt = (
            f"File name: {file_name}\n"
            f"Heading path: {heading_path or '(no heading)'}\n"
            f"Output language: {language_label}\n"
            f"Maximum characters: {max_output_chars}\n\n"
            "Write a section synopsis with exactly these sections in the requested language:\n"
            "1. Section topic\n"
            "2. Section path\n"
            "3. Key points\n"
            "4. Structure notes\n\n"
            "Rules:\n"
            "- Stay within the maximum characters.\n"
            "- Use plain text only.\n"
            "- Do not invent facts not present in the source.\n"
            "- If the source is incomplete, state that conservatively.\n\n"
            "Compressed source:\n"
            f"{source_text}"
        )
        return self._create_synopsis_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_chars=max_output_chars,
            failure_prefix="section synopsis 生成失敗",
        )


def build_document_synopsis_provider(settings: WorkerSettings) -> DocumentSynopsisProvider:
    """依照設定建立 document synopsis provider。

    參數：
    - `settings`：worker 執行期設定。

    回傳：
    - `DocumentSynopsisProvider`：對應的 synopsis provider。
    """

    provider = settings.document_synopsis_provider.strip().lower()
    if provider == "deterministic":
        return DeterministicDocumentSynopsisProvider()
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("使用 OpenAI document synopsis 前必須提供 OPENAI_API_KEY。")
        return OpenAIDocumentSynopsisProvider(
            api_key=settings.openai_api_key,
            model=settings.document_synopsis_model,
            max_output_tokens=settings.document_synopsis_max_output_tokens,
            reasoning_effort=settings.document_synopsis_reasoning_effort,
            text_verbosity=settings.document_synopsis_text_verbosity,
        )
    raise ValueError(f"不支援的 document synopsis provider：{settings.document_synopsis_provider}")


def build_document_synopsis_source_text(
    *,
    file_name: str,
    parent_chunks: list[DocumentChunk],
    max_input_chars: int,
) -> str:
    """以全 parent coverage 方式建立 synopsis 輸入文字。

    參數：
    - `file_name`：目前文件檔名。
    - `parent_chunks`：依文件順序排列的 parent chunks。
    - `max_input_chars`：允許的最大輸入字元數。

    回傳：
    - `str`：可送入 synopsis provider 的受控來源文字。
    """

    if not parent_chunks:
        raise ValueError("document synopsis 來源不可缺少 parent chunks。")

    normalized_file_name = _normalize_inline_text(file_name)
    headings = [chunk.heading for chunk in parent_chunks]
    has_tables = any(str(chunk.structure_kind.value) == "table" for chunk in parent_chunks)
    for heading_chars, content_chars in ((72, 200), (48, 120), (32, 72), (20, 40)):
        sections: list[str] = [
            f"File: {normalized_file_name}",
            f"Parent count: {len(parent_chunks)}",
            f"Contains table parents: {'yes' if has_tables else 'no'}",
        ]
        for index, chunk in enumerate(parent_chunks, start=1):
            structure_label = "table" if str(chunk.structure_kind.value) == "table" else "text"
            heading = _truncate_text(_normalize_inline_text(chunk.heading or "(no heading)"), heading_chars)
            content = _truncate_text(_normalize_inline_text(chunk.content), content_chars)
            sections.append(
                "\n".join(
                    [
                        f"[{index}] Type: {structure_label}",
                        f"Heading: {heading}",
                        f"Excerpt: {content}",
                        f"Table/Structure: {'Contains table-like structure.' if structure_label == 'table' else 'Primarily narrative text.'}",
                    ]
                )
            )
        candidate = "\n\n".join(sections)
        if len(candidate) <= max_input_chars:
            return candidate

    return _truncate_text(candidate, max_input_chars)


def build_section_synopsis_source_text(
    *,
    file_name: str,
    heading_path: str | None,
    section_path_text: str | None,
    content: str,
    structure_kind: str,
    max_input_chars: int,
) -> str:
    """建立 path-aware section synopsis 輸入文字。

    參數：
    - `file_name`：目前文件檔名。
    - `heading_path`：目前 section 的階層路徑。
    - `section_path_text`：供 recall 使用的 path-aware section 文字。
    - `content`：目前 section 原始內容。
    - `structure_kind`：目前 section 的結構型別。
    - `max_input_chars`：允許的最大輸入字元數。

    回傳：
    - `str`：可送入 synopsis provider 的受控來源文字。
    """

    normalized_file_name = _normalize_inline_text(file_name)
    normalized_heading_path = _normalize_inline_text(heading_path or section_path_text or "(no heading)")
    normalized_section_path = _normalize_inline_text(section_path_text or heading_path or "(no section path)")
    normalized_content = _normalize_inline_text(content)
    structure_label = "table" if structure_kind == "table" else "text"

    for excerpt_chars in (280, 180, 120, 72):
        candidate = "\n".join(
            [
                f"File: {normalized_file_name}",
                f"Heading Path: {normalized_heading_path}",
                f"Section Path: {normalized_section_path}",
                f"Type: {structure_label}",
                f"Excerpt: {_truncate_text(normalized_content, excerpt_chars)}",
                f"Table/Structure: {'Contains table-like structure.' if structure_label == 'table' else 'Primarily narrative text.'}",
            ]
        )
        if len(candidate) <= max_input_chars:
            return candidate

    return _truncate_text(candidate, max_input_chars)


def detect_synopsis_language(*, parent_chunks: list[DocumentChunk], file_name: str) -> str:
    """依文件內容與檔名偵測 synopsis 預設輸出語言。

    參數：
    - `parent_chunks`：依文件順序排列的 parent chunks。
    - `file_name`：目前文件檔名。

    回傳：
    - `str`：`zh-TW` 或 `en`。
    """

    combined_text = "\n".join(filter(None, [file_name, *[(chunk.heading or "") + "\n" + chunk.content for chunk in parent_chunks[:6]]]))
    return "zh-TW" if _CJK_PATTERN.search(combined_text) else "en"


def detect_section_synopsis_language(*, file_name: str, heading_path: str | None, content: str) -> str:
    """依 section 內容與檔名偵測 section synopsis 預設輸出語言。"""

    combined_text = "\n".join(filter(None, [file_name, heading_path or "", content[:600]]))
    return "zh-TW" if _CJK_PATTERN.search(combined_text) else "en"


def _extract_source_lines(*, source_text: str, prefix: str) -> list[str]:
    """從 synopsis 壓縮輸入中抽出指定前綴的行。"""

    lines: list[str] = []
    for raw_line in source_text.splitlines():
        if not raw_line.startswith(prefix):
            continue
        line = raw_line.removeprefix(prefix).strip()
        if line:
            lines.append(line)
    return lines


def _normalize_inline_text(value: str) -> str:
    """將文字壓縮為適合單行 synopsis 的格式。"""

    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _truncate_text(value: str, max_chars: int) -> str:
    """以字元數裁切文字，避免超出受控 budget。"""

    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    if max_chars <= 1:
        return value[:max_chars]
    return value[: max_chars - 1].rstrip() + "…"


def _finalize_synopsis_text(*, synopsis: str, max_output_chars: int) -> str:
    """清理並驗證 synopsis 最終文字。"""

    normalized_synopsis = synopsis.strip()
    if not normalized_synopsis:
        raise ValueError("document synopsis 生成失敗：輸出為空白。")
    return _truncate_text(normalized_synopsis, max_output_chars)


def _extract_response_output_text(response: object) -> str | None:
    """從 OpenAI Responses API 回傳中抽取可見文字。

    參數：
    - `response`：OpenAI Responses API 回傳物件。

    回傳：
    - `str | None`：若成功抽取文字則回傳內容，否則回傳空值。
    """

    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    output_items = getattr(response, "output", None)
    if not isinstance(output_items, list):
        return None
    for item in output_items:
        if getattr(item, "type", None) != "message":
            continue
        for content_item in getattr(item, "content", []):
            text_value = getattr(content_item, "text", None)
            if isinstance(text_value, str):
                return text_value
    return None


def _is_gpt5_family_model(model: str) -> bool:
    """判斷模型是否屬於目前不接受自訂 temperature 的 GPT-5 系列。"""

    normalized_model = model.strip().lower()
    return normalized_model.startswith("gpt-5")
