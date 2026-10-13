"""外部 benchmark curation pipeline 測試。"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.db.models import Area, Document, DocumentStatus
from app.scripts.import_benchmark_snapshot import import_snapshot
from app.scripts.prepare_external_benchmark import (
    ALIGNMENT_CANDIDATES_FILE,
    ALIGNMENT_REVIEW_QUEUE_FILE,
    FILTER_REPORT_FILE,
    OPTIONAL_SNAPSHOT_AUXILIARY_FILES,
    PREPARED_DOCUMENTS_FILE,
    PREPARED_ITEMS_FILE,
    REVIEW_OVERRIDES_FILE,
    build_report,
    build_snapshot,
    filter_items,
    prepare_source,
    align_spans,
)


def _uuid() -> str:
    """建立測試用 UUID 字串。

    參數：
    - 無。

    回傳：
    - `str`：新的 UUID 字串。
    """

    return str(uuid4())


def test_prepare_qasper_source_and_filter(tmp_path: Path) -> None:
    """QASPER prepare/filter 應只保留 extractive fact lookup 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "qasper-workspace"
    input_path = tmp_path / "qasper.json"
    input_path.write_text(
        json.dumps(
            {
                "paper-1": {
                    "paper_id": "paper-1",
                    "title": "Paper One",
                    "abstract": "A short abstract.",
                    "full_text": [
                        {"section_name": "Introduction", "paragraphs": ["Alpha evidence sentence."]},
                    ],
                    "qas": [
                        {
                            "question": "What sentence is important?",
                            "answers": [
                                {
                                    "answer": {
                                        "extractive_spans": ["Alpha evidence sentence."],
                                        "free_form_answer": "Alpha evidence sentence.",
                                        "unanswerable": False,
                                    }
                                }
                            ],
                        },
                        {
                            "question": "Is the result good?",
                            "answers": [
                                {
                                    "answer": {
                                        "yes_no": True,
                                        "free_form_answer": "yes",
                                        "unanswerable": False,
                                    }
                                }
                            ],
                        },
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="qasper",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )
    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 2

    filter_summary = filter_items(workspace_dir=workspace_dir)
    assert filter_summary["kept_item_count"] == 1
    filtered_rows = [
        json.loads(line)
        for line in (workspace_dir / "filtered_items.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert filtered_rows[0]["query_text"] == "What sentence is important?"


def test_prepare_msmarco_source_from_jsonl(tmp_path: Path) -> None:
    """MS MARCO prepare-source 應能從 row contract 產出 markdown 文件與題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "msmarco-workspace"
    input_path = tmp_path / "msmarco.jsonl"
    input_rows = [
        {
            "query_id": 1001,
            "query": "what is the boiling point of water",
            "query_type": "description",
            "answers": ["100 °C at 1 atmosphere."],
            "wellFormedAnswers": ["100 degrees Celsius at 1 atmosphere."],
            "passages": {
                "is_selected": [1, 0],
                "passage_text": [
                    "At standard atmospheric pressure, water boils at 100 degrees Celsius.",
                    "Water can also boil at lower temperatures when pressure drops.",
                ],
                "url": [
                    "https://example.com/boiling-point",
                    "https://example.com/pressure",
                ],
            },
        },
        {
            "query_id": 1002,
            "query": "question without selected passage",
            "query_type": "description",
            "answers": ["This row should be skipped."],
            "wellFormedAnswers": [],
            "passages": {
                "is_selected": [0],
                "passage_text": ["Only context passage."],
                "url": ["https://example.com/context"],
            },
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in input_rows) + "\n",
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="msmarco",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_documents = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_DOCUMENTS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert prepared_documents[0]["dataset"] == "msmarco"
    assert prepared_documents[0]["file_name"] == "msmarco-1001.md"
    assert prepared_items[0]["answer_text"] == "100 degrees Celsius at 1 atmosphere."
    assert prepared_items[0]["source_metadata"]["query_id"] == "1001"
    assert prepared_items[0]["source_metadata"]["selected_passage_count"] == 1
    assert prepared_items[0]["source_metadata"]["context_passage_count"] == 1
    document_text = (workspace_dir / "source_documents" / "msmarco-1001.md").read_text(encoding="utf-8")
    assert "Selected Passage 1" in document_text
    assert "Context Passage 1" in document_text
    assert "what is the boiling point of water" not in document_text


def test_prepare_nq_source_from_jsonl(tmp_path: Path) -> None:
    """NQ prepare-source 應可輸出乾淨 markdown 文件與 short-answer 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "nq-workspace"
    input_path = tmp_path / "nq.jsonl"
    input_rows = [
        {
            "id": "nq-row-1",
            "document": {
                "title": "Sample Nobel Article",
                "url": "https://example.com/nobel?foo=1&amp;bar=2",
                "tokens": {
                    "token": [
                        "<H1>",
                        "Sample",
                        "Nobel",
                        "Article",
                        "</H1>",
                        "<P>",
                        "Wilhelm",
                        "Conrad",
                        "Röntgen",
                        ",",
                        "of",
                        "Germany",
                        ",",
                        "received",
                        "the",
                        "first",
                        "Nobel",
                        "Prize",
                        "in",
                        "Physics",
                        ".",
                        "</P>",
                    ],
                    "is_html": [
                        True,
                        False,
                        False,
                        False,
                        True,
                        True,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                        True,
                    ],
                    "start_byte": list(range(22)),
                    "end_byte": list(range(1, 23)),
                },
            },
            "question": {
                "text": "who got the first nobel prize in physics",
                "tokens": ["who", "got", "the", "first", "nobel", "prize", "in", "physics"],
            },
            "annotations": {
                "id": ["ann-empty", "ann-good"],
                "long_answer": [
                    {"candidate_index": -1, "start_token": -1, "end_token": -1, "start_byte": -1, "end_byte": -1},
                    {"candidate_index": 0, "start_token": 6, "end_token": 21, "start_byte": 0, "end_byte": 0},
                ],
                "short_answers": [
                    {"start_token": [], "end_token": [], "start_byte": [], "end_byte": [], "text": []},
                    {
                        "start_token": [6],
                        "end_token": [12],
                        "start_byte": [0],
                        "end_byte": [0],
                        "text": ["Wilhelm Conrad Röntgen, of Germany"],
                    },
                ],
                "yes_no_answer": [-1, -1],
            },
            "long_answer_candidates": {
                "start_token": [6],
                "end_token": [21],
                "start_byte": [0],
                "end_byte": [0],
                "top_level": [True],
            },
        },
        {
            "id": "nq-row-2",
            "document": {
                "title": "Ignored Yes No",
                "url": "https://example.com/ignored",
                "tokens": {
                    "token": ["<P>", "Yes", "</P>"],
                    "is_html": [True, False, True],
                    "start_byte": [0, 1, 2],
                    "end_byte": [1, 2, 3],
                },
            },
            "question": {"text": "is this ignored", "tokens": ["is", "this", "ignored"]},
            "annotations": {
                "id": ["ann-ignored"],
                "long_answer": [{"candidate_index": -1, "start_token": -1, "end_token": -1, "start_byte": -1, "end_byte": -1}],
                "short_answers": [{"start_token": [], "end_token": [], "start_byte": [], "end_byte": [], "text": []}],
                "yes_no_answer": [1],
            },
            "long_answer_candidates": {"start_token": [], "end_token": [], "start_byte": [], "end_byte": [], "top_level": []},
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in input_rows) + "\n",
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="nq",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_documents = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_DOCUMENTS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert prepared_documents[0]["dataset"] == "nq"
    assert prepared_documents[0]["file_name"] == "Sample-Nobel-Article.md"
    assert prepared_items[0]["answer_text"] == "Wilhelm Conrad Röntgen, of Germany"
    assert prepared_items[0]["source_metadata"]["nq_id"] == "nq-row-1"
    assert prepared_items[0]["source_metadata"]["document_url"] == "https://example.com/nobel?foo=1&bar=2"
    assert "received the first Nobel Prize in Physics" in prepared_items[0]["evidence_texts"][0]

    document_text = (workspace_dir / "source_documents" / "Sample-Nobel-Article.md").read_text(encoding="utf-8")
    assert document_text.startswith("# Sample Nobel Article")
    assert "Source URL: https://example.com/nobel?foo=1&bar=2" in document_text
    assert "Wilhelm Conrad Röntgen, of Germany, received the first Nobel Prize in Physics." in document_text


def test_prepare_dureader_source_from_jsonl(tmp_path: Path) -> None:
    """DuReader prepare-source 應可輸出 bundle markdown 文件與中文 fact lookup 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "dureader-workspace"
    input_path = tmp_path / "search.dev.json"
    input_rows = [
        {
            "question_id": "du-1",
            "question": "微信裡分享連結後怎麼開啟第三方 app？",
            "question_type": "DESCRIPTION",
            "fact_or_opinion": "FACT",
            "answers": ["可以使用 iOS 9 的 Universal Link。"],
            "fake_answers": ["Universal Link"],
            "documents": [
                {
                    "is_selected": True,
                    "title": "微信開啟第三方 app 方法",
                    "most_related_para": 0,
                    "paragraphs": [
                        "方法一：微信 API。方法二：iOS 9 Universal Link。（參考 app - 蘑菇街）",
                    ],
                }
            ],
        },
        {
            "question_id": "du-2",
            "question": "這是一題意見題嗎？",
            "question_type": "DESCRIPTION",
            "fact_or_opinion": "OPINION",
            "answers": ["我認為是。"],
            "documents": [
                {
                    "is_selected": True,
                    "title": "Opinion Only",
                    "most_related_para": 0,
                    "paragraphs": ["純意見題，不應納入 benchmark。"],
                }
            ],
        },
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in input_rows) + "\n",
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="dureader",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_documents = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_DOCUMENTS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert prepared_documents[0]["dataset"] == "dureader"
    assert prepared_documents[0]["file_name"] == "dureader-du-1.md"
    assert prepared_items[0]["language"] == "zh-TW"
    assert prepared_items[0]["answer_text"] == "Universal Link"
    assert prepared_items[0]["source_metadata"]["source_split"] == "search.dev"
    assert prepared_items[0]["source_metadata"]["fact_or_opinion"] == "FACT"
    assert "Universal Link" in prepared_items[0]["evidence_texts"][0]

    document_text = (workspace_dir / "source_documents" / "dureader-du-1.md").read_text(encoding="utf-8")
    assert document_text.startswith("# DuReader Bundle du-1")
    assert "## Document 1: 微信開啟第三方 app 方法" in document_text
    assert "方法二：iOS 9 Universal Link" in document_text


def test_prepare_dureader_robust_source_from_jsonl(tmp_path: Path) -> None:
    """DuReader-robust schema 也應可透過同一個 `dureader` handler 產出 benchmark 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "dureader-robust-workspace"
    input_path = tmp_path / "dureader_robust-dev.json"
    input_rows = [
        {
            "title": "糖尿病患者可以吃什麼水果",
            "context": "糖尿病病人應多選擇低生糖指數的水果，有助於保持血糖穩定。",
            "question": "糖尿病患者可以吃什麼水果？",
            "id": "robust-1",
            "answers": {
                "text": ["低生糖指數的水果"],
                "answer_start": [11],
            },
        }
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in input_rows) + "\n",
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="dureader",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert prepared_items[0]["answer_text"] == "低生糖指數的水果"
    assert prepared_items[0]["source_metadata"]["schema_variant"] == "robust"
    assert prepared_items[0]["source_metadata"]["source_split"] == "dureader_robust-dev"
    assert "低生糖指數的水果" in prepared_items[0]["evidence_texts"][0]

    document_text = (workspace_dir / "source_documents" / "dureader-robust-1.md").read_text(encoding="utf-8")
    assert document_text.startswith("# 糖尿病患者可以吃什麼水果")
    assert "## Context" in document_text
    assert "糖尿病病人應多選擇低生糖指數的水果" in document_text


def test_prepare_dureader_robust_article_wrapper_from_json(tmp_path: Path) -> None:
    """官方 DuReader-robust article wrapper 也應透過 `dureader` handler 產出 paragraph 文件。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "dureader-wrapper-workspace"
    input_path = tmp_path / "dev.json"
    input_payload = {
        "data": [
            {
                "title": "韓國",
                "paragraphs": [
                    {
                        "context": "韓國全稱大韓民國，位於朝鮮半島南部。",
                        "qas": [
                            {
                                "question": "韓國全稱是什麼？",
                                "id": "qa-1",
                                "answers": [{"text": "大韓民國", "answer_start": 4}],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    input_path.write_text(json.dumps(input_payload, ensure_ascii=False), encoding="utf-8")

    prepare_summary = prepare_source(
        dataset="dureader",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert prepared_items[0]["answer_text"] == "大韓民國"
    assert prepared_items[0]["source_metadata"]["schema_variant"] == "robust"
    assert prepared_items[0]["source_metadata"]["paragraph_index"] == 0

    document_text = (workspace_dir / "source_documents" / "dureader-0-0.md").read_text(encoding="utf-8")
    assert document_text.startswith("# 韓國")
    assert "韓國全稱大韓民國" in document_text


def test_prepare_drcd_source_from_jsonl(tmp_path: Path) -> None:
    """DRCD prepare-source 應可輸出繁中 markdown 文件與 fact lookup 題目。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出。
    """

    workspace_dir = tmp_path / "drcd-workspace"
    input_path = tmp_path / "drcd.jsonl"
    input_rows = [
        {
            "title": "梵文",
            "id": "1147",
            "paragraphs": [
                {
                    "context": "在歐洲，梵語的學術研究，由德國學者陸特和漢斯雷頓開創。",
                    "id": "1147-5",
                    "qas": [
                        {
                            "id": "1147-5-1",
                            "question": "陸特和漢斯雷頓開創了哪一地區對梵語的學術研究？",
                            "answers": [
                                {"answer_start": 1, "id": "1", "text": "歐洲"},
                                {"answer_start": 1, "id": "2", "text": "歐洲"},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    input_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in input_rows) + "\n",
        encoding="utf-8",
    )

    prepare_summary = prepare_source(
        dataset="drcd",
        input_path=input_path,
        workspace_dir=workspace_dir,
        limit_documents=None,
        limit_items=None,
    )

    assert prepare_summary["document_count"] == 1
    assert prepare_summary["item_count"] == 1

    prepared_documents = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_DOCUMENTS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prepared_items = [
        json.loads(line)
        for line in (workspace_dir / PREPARED_ITEMS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert prepared_documents[0]["dataset"] == "drcd"
    assert prepared_documents[0]["file_name"] == "drcd-1147.md"
    assert prepared_items[0]["language"] == "zh-TW"
    assert prepared_items[0]["answer_text"] == "歐洲"
    assert prepared_items[0]["source_metadata"]["paragraph_id"] == "1147-5"
    assert "在歐洲，梵語的學術研究" in prepared_items[0]["evidence_texts"][0]

    document_text = (workspace_dir / "source_documents" / "drcd-1147.md").read_text(encoding="utf-8")
    assert document_text.startswith("# 梵文")
    assert "## Paragraph 1" in document_text
    assert "在歐洲，梵語的學術研究，由德國學者陸特和漢斯雷頓開創。" in document_text


def test_align_build_snapshot_and_import_round_trip(app, db_session, app_settings, tmp_path: Path, monkeypatch) -> None:
    """alignment/build-snapshot 應可產出現有 import snapshot 可接受的 package。

    參數：
    - `app`：測試用 FastAPI app。
    - `db_session`：測試資料庫 session。
    - `app_settings`：測試設定。
    - `tmp_path`：pytest 暫存目錄。
    - `monkeypatch`：pytest monkeypatch fixture。

    回傳：
    - `None`：以斷言驗證 pipeline 正常。
    """

    area = Area(id=_uuid(), name="Benchmark Area")
    import_area = Area(id=_uuid(), name="Import Area")
    db_session.add_all([area, import_area])

    document = Document(
        id=_uuid(),
        area_id=area.id,
        file_name="paper-1.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="benchmark/paper-1.md",
        display_text="Alpha unique evidence sentence.\n\nAlpha review sentence.\n\nAlpha review sentence.\n\nUnique fuzzy evidence text.",
        normalized_text="Alpha unique evidence sentence.\n\nAlpha review sentence.\n\nAlpha review sentence.\n\nUnique fuzzy evidence text.",
        status=DocumentStatus.ready,
    )
    import_document = Document(
        id=_uuid(),
        area_id=import_area.id,
        file_name="paper-1.md",
        content_type="text/markdown",
        file_size=128,
        storage_key="benchmark/import-paper-1.md",
        display_text=document.display_text,
        normalized_text=document.normalized_text,
        status=DocumentStatus.ready,
    )
    db_session.add_all([document, import_document])
    db_session.commit()

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-1.md"
    source_file.write_text(document.display_text or "", encoding="utf-8")

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        json.dumps(
            {
                "dataset": "qasper",
                "source_document_id": "paper-1",
                "file_name": "paper-1.md",
                "title": "Paper One",
                "source_path": str(source_file),
                "content_type": "text/markdown",
                "created_at": "2026-04-02T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    prepared_rows = [
        {
            "item_id": "item-exact",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "What is the alpha evidence?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha unique evidence sentence.",
            "evidence_texts": ["Alpha unique evidence sentence."],
            "answer_type": "extractive",
            "source_question_index": 0,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
        {
            "item_id": "item-fuzzy",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "What is the unique fuzzy evidence?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Unique fuzzy evidence text.",
            "evidence_texts": ["Unique fuzzy evidence tex"],
            "answer_type": "extractive",
            "source_question_index": 1,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
        {
            "item_id": "item-review",
            "dataset": "qasper",
            "source_document_id": "paper-1",
            "file_name": "paper-1.md",
            "query_text": "Which alpha mention is near the duplicate context?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha review sentence.",
            "evidence_texts": ["Alpha review sentence."],
            "answer_type": "extractive",
            "source_question_index": 2,
            "source_metadata": {"paper_id": "paper-1"},
            "created_at": "2026-04-02T00:00:00+00:00",
        },
    ]
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_rows) + "\n",
        encoding="utf-8",
    )

    filter_summary = filter_items(workspace_dir=workspace_dir)
    assert filter_summary["kept_item_count"] == 3

    monkeypatch.setattr("app.scripts.prepare_external_benchmark.get_settings", lambda: app_settings)
    monkeypatch.setattr("app.scripts.import_benchmark_snapshot.get_settings", lambda: app_settings)
    align_summary = align_spans(workspace_dir=workspace_dir, area_id=area.id)
    assert align_summary["status_counts"]["auto_matched"] == 2
    assert align_summary["status_counts"]["needs_review"] == 1

    review_overrides = [
        {
            "item_id": "item-review",
            "decision": "approved",
            "spans": [
                {
                    "start_offset": len("Alpha unique evidence sentence.\n\n"),
                    "end_offset": len("Alpha unique evidence sentence.\n\n") + len("Alpha review sentence."),
                }
            ],
        }
    ]
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in review_overrides) + "\n",
        encoding="utf-8",
    )

    snapshot_dir = tmp_path / "snapshot"
    snapshot_summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=snapshot_dir,
        benchmark_name="qasper-curated-v1",
        include_review_items=False,
    )
    assert snapshot_summary["question_count"] == 3
    assert snapshot_summary["question_with_gold_span_count"] == 3
    assert (snapshot_dir / "manifest.json").exists()
    assert (snapshot_dir / ALIGNMENT_CANDIDATES_FILE).exists()
    assert (snapshot_dir / ALIGNMENT_REVIEW_QUEUE_FILE).exists()
    assert (snapshot_dir / FILTER_REPORT_FILE).exists()

    import_summary = import_snapshot(
        snapshot_dir=snapshot_dir,
        area_id=import_area.id,
        dataset_name_override="qasper-curated-import",
        actor_sub="user-admin",
        replace=True,
    )
    assert import_summary["question_count"] == 3
    assert import_summary["span_count"] == 3

    report = build_report(workspace_dir=workspace_dir)
    assert report["approved_override_count"] == 1
    assert report["status_counts"]["needs_review"] == 1


def test_build_snapshot_can_include_reviewed_item_not_in_filtered_set(tmp_path: Path) -> None:
    """build_snapshot 應可納入僅存在 prepared_items 的 reviewed item。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證 snapshot 可正常建立。
    """

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-2.md"
    source_file.write_text("Alpha answer evidence.", encoding="utf-8")

    prepared_documents = [
        {
            "dataset": "uda",
            "source_document_id": "paper-2",
            "file_name": "paper-2.md",
            "title": "Paper Two",
            "source_path": str(source_file),
            "content_type": "text/markdown",
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]
    prepared_items = [
        {
            "item_id": "item-prepared-only",
            "dataset": "uda",
            "source_document_id": "paper-2",
            "file_name": "paper-2.md",
            "query_text": "What is the alpha answer?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha answer evidence.",
            "evidence_texts": [],
            "answer_type": "short_answer",
            "source_question_index": 0,
            "source_metadata": {"row_index": 0},
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_documents) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "filtered_items.jsonl").write_text("", encoding="utf-8")
    (workspace_dir / ALIGNMENT_CANDIDATES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-prepared-only",
                "dataset": "uda",
                "file_name": "paper-2.md",
                "query_text": "What is the alpha answer?",
                "answer_text": "Alpha answer evidence.",
                "language": "en",
                "query_type": "fact_lookup",
                "status": "needs_review",
                "accepted_spans": [],
                "review_candidates": [],
                "rejected_evidences": [],
                "source_metadata": {"row_index": 0},
                "generated_at": "2026-04-04T00:00:00+00:00",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-prepared-only",
                "decision": "approved",
                "spans": [{"start_offset": 0, "end_offset": len("Alpha answer evidence.")}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "snapshot"
    summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        benchmark_name="prepared-only-reviewed",
        include_review_items=False,
    )

    assert summary["question_count"] == 1
    assert summary["span_count"] == 1
    questions = [
        json.loads(line)
        for line in (output_dir / "questions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert questions[0]["question"] == "What is the alpha answer?"


def test_build_snapshot_can_limit_question_count_and_copy_optional_review_files(tmp_path: Path) -> None:
    """build_snapshot 應可限制題數並複製可選 review 證據檔。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證 manifest 與輸出檔案正確。
    """

    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    source_dir = workspace_dir / "source_documents"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "paper-3.md"
    source_file.write_text("Alpha one.\n\nBeta two.\n", encoding="utf-8")

    prepared_documents = [
        {
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "title": "Paper Three",
            "source_path": str(source_file),
            "content_type": "text/markdown",
            "created_at": "2026-04-04T00:00:00+00:00",
        }
    ]
    prepared_items = [
        {
            "item_id": "item-1",
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "query_text": "What is alpha?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Alpha one.",
            "evidence_texts": ["Alpha one."],
            "answer_type": "extractive",
            "source_question_index": 0,
            "source_metadata": {"paper_id": "paper-3"},
            "created_at": "2026-04-04T00:00:00+00:00",
        },
        {
            "item_id": "item-2",
            "dataset": "qasper",
            "source_document_id": "paper-3",
            "file_name": "paper-3.md",
            "query_text": "What is beta?",
            "language": "en",
            "query_type": "fact_lookup",
            "answer_text": "Beta two.",
            "evidence_texts": ["Beta two."],
            "answer_type": "extractive",
            "source_question_index": 1,
            "source_metadata": {"paper_id": "paper-3"},
            "created_at": "2026-04-04T00:00:00+00:00",
        },
    ]

    (workspace_dir / PREPARED_DOCUMENTS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_documents) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / PREPARED_ITEMS_FILE).write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / "filtered_items.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in prepared_items) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / ALIGNMENT_CANDIDATES_FILE).write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "item_id": "item-1",
                        "dataset": "qasper",
                        "file_name": "paper-3.md",
                        "query_text": "What is alpha?",
                        "answer_text": "Alpha one.",
                        "language": "en",
                        "query_type": "fact_lookup",
                        "status": "auto_matched",
                        "accepted_spans": [{"start_offset": 0, "end_offset": len("Alpha one.")}],
                        "review_candidates": [],
                        "rejected_evidences": [],
                        "source_metadata": {"paper_id": "paper-3"},
                        "generated_at": "2026-04-04T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "item_id": "item-2",
                        "dataset": "qasper",
                        "file_name": "paper-3.md",
                        "query_text": "What is beta?",
                        "answer_text": "Beta two.",
                        "language": "en",
                        "query_type": "fact_lookup",
                        "status": "needs_review",
                        "accepted_spans": [],
                        "review_candidates": [],
                        "rejected_evidences": [],
                        "source_metadata": {"paper_id": "paper-3"},
                        "generated_at": "2026-04-04T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workspace_dir / ALIGNMENT_REVIEW_QUEUE_FILE).write_text(
        json.dumps({"item_id": "item-2"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / FILTER_REPORT_FILE).write_text(
        json.dumps({"kept_item_count": 2}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (workspace_dir / REVIEW_OVERRIDES_FILE).write_text(
        json.dumps(
            {
                "item_id": "item-2",
                "decision": "approved",
                "spans": [{"start_offset": len("Alpha one.\n\n"), "end_offset": len("Alpha one.\n\nBeta two.")}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    openai_log_file = workspace_dir / OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1]
    openai_log_file.write_text(
        json.dumps({"item_id": "item-2", "decision": "approved"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "snapshot"
    summary = build_snapshot(
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        benchmark_name="limited-reviewed",
        include_review_items=False,
        target_question_count=1,
        reference_evaluation_profile="production_like_v1",
    )

    assert summary["question_count"] == 1
    assert summary["reference_evaluation_profile"] == "production_like_v1"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference"]["evaluation_profile"] == "production_like_v1"
    assert manifest["stats"]["question_count"] == 1
    assert REVIEW_OVERRIDES_FILE in manifest["snapshot_files"]
    assert OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1] in manifest["snapshot_files"]
    assert (output_dir / REVIEW_OVERRIDES_FILE).exists()
    assert (output_dir / OPTIONAL_SNAPSHOT_AUXILIARY_FILES[1]).exists()
