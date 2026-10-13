"""Document synopsis 壓縮與 provider 測試。"""

from types import SimpleNamespace

from worker.synopsis import (
    DeterministicDocumentSynopsisProvider,
    OpenAIDocumentSynopsisProvider,
    build_document_synopsis_source_text,
    build_section_synopsis_source_text,
)


def _build_parent_chunk(*, heading: str, content: str, structure_kind: str = "text"):
    """建立 synopsis 測試使用的最小 parent chunk 替身。

    參數：
    - `heading`：parent heading。
    - `content`：parent content。
    - `structure_kind`：內容結構型別。

    回傳：
    - 具備 synopsis helper 所需欄位的測試替身。
    """

    return SimpleNamespace(
        heading=heading,
        content=content,
        structure_kind=SimpleNamespace(value=structure_kind),
    )


def test_build_document_synopsis_source_text_keeps_all_parent_headings() -> None:
    """全 parent coverage 壓縮應保留每個 parent 的 heading。"""

    source_text = build_document_synopsis_source_text(
        file_name="policy.md",
        parent_chunks=[
            _build_parent_chunk(heading="Overview", content="Alpha body " * 20),
            _build_parent_chunk(heading="Budget Table", content="| item | value |", structure_kind="table"),
            _build_parent_chunk(heading="Conclusion", content="Beta closing " * 20),
        ],
        max_input_chars=1200,
    )

    assert "Heading: Overview" in source_text
    assert "Heading: Budget Table" in source_text
    assert "Heading: Conclusion" in source_text


def test_deterministic_document_synopsis_provider_respects_output_cap() -> None:
    """deterministic synopsis provider 應輸出固定結構且長度受控。"""

    provider = DeterministicDocumentSynopsisProvider()

    synopsis = provider.generate_synopsis(
        file_name="policy.md",
        source_text=(
            "Heading: Overview\n"
            "Excerpt: Alpha overview.\n"
            "Table/Structure: Primarily narrative text.\n\n"
            "Heading: Budget\n"
            "Excerpt: Budget summary.\n"
            "Table/Structure: Contains table-like structure."
        ),
        output_language="en",
        max_output_chars=180,
    )

    assert "Topic:" in synopsis
    assert "Key sections:" in synopsis
    assert len(synopsis) <= 180


def test_build_section_synopsis_source_text_keeps_path_aware_context() -> None:
    """section synopsis 壓縮應保留 file/path/structure 三種訊息。"""

    source_text = build_section_synopsis_source_text(
        file_name="policy.md",
        heading_path="Policy / Leave",
        section_path_text="Policy / Leave",
        content="Leave policy covers eligibility and approval flow.",
        structure_kind="text",
        max_input_chars=400,
    )

    assert "File: policy.md" in source_text
    assert "Heading Path: Policy / Leave" in source_text
    assert "Section Path: Policy / Leave" in source_text
    assert "Excerpt:" in source_text


def test_openai_document_synopsis_provider_omits_temperature_for_gpt5_models(monkeypatch) -> None:
    """GPT-5 系列模型應走 Responses API，並省略自訂 temperature。"""

    captured_kwargs: dict[str, object] = {}

    class FakeOpenAI:
        """模擬 OpenAI client。"""

        def __init__(self, *, api_key: str) -> None:
            """初始化假 client。"""

            del api_key
            self.responses = SimpleNamespace(create=self._create)
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=self._unexpected_chat_create),
            )

        def _create(self, **kwargs):
            """保存 responses.create kwargs 並回傳最小成功結果。"""

            captured_kwargs.update(kwargs)
            return SimpleNamespace(output_text="Topic: policy\nKey sections: overview", incomplete_details=None)

        def _unexpected_chat_create(self, **kwargs):
            """若 GPT-5 path 誤走 chat completions，直接讓測試失敗。"""

            del kwargs
            raise AssertionError("GPT-5 synopsis path 不應使用 chat.completions.create。")

    monkeypatch.setitem(__import__("sys").modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    provider = OpenAIDocumentSynopsisProvider(
        api_key="test-key",
        model="gpt-5.4-mini",
        max_output_tokens=2000,
        reasoning_effort="minimal",
        text_verbosity="low",
    )

    synopsis = provider.generate_synopsis(
        file_name="policy.md",
        source_text="Heading: Overview\nExcerpt: Alpha overview.",
        output_language="en",
        max_output_chars=180,
    )

    assert "temperature" not in captured_kwargs
    assert captured_kwargs["model"] == "gpt-5.4-mini"
    assert captured_kwargs["max_output_tokens"] == 2000
    assert captured_kwargs["reasoning"] == {"effort": "minimal"}
    assert captured_kwargs["text"] == {"verbosity": "low"}
    assert captured_kwargs["instructions"] is not None
    assert captured_kwargs["input"] is not None
    assert "Topic:" in synopsis


def test_openai_document_synopsis_provider_surfaces_incomplete_reason_for_gpt5(monkeypatch) -> None:
    """GPT-5 synopsis 若撞到 max_output_tokens，應保留較清楚的失敗原因。"""

    class FakeOpenAI:
        """模擬回傳空輸出且帶 incomplete_details 的 OpenAI client。"""

        def __init__(self, *, api_key: str) -> None:
            """初始化假 client。"""

            del api_key
            self.responses = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            """回傳 max_output_tokens 截斷但無可見輸出的最小結果。"""

            del kwargs
            return SimpleNamespace(
                output_text="",
                incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            )

    monkeypatch.setitem(__import__("sys").modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    provider = OpenAIDocumentSynopsisProvider(
        api_key="test-key",
        model="gpt-5.4-mini",
        max_output_tokens=2000,
        reasoning_effort="minimal",
        text_verbosity="low",
    )

    try:
        provider.generate_section_synopsis(
            file_name="policy.md",
            heading_path="Policy / Leave",
            source_text="Excerpt: Alpha overview.",
            output_language="en",
            max_output_chars=180,
        )
    except ValueError as exc:
        assert "max_output_tokens" in str(exc)
    else:  # pragma: no cover - defensive assertion branch.
        raise AssertionError("預期 GPT-5 incomplete output 應拋出 ValueError。")
