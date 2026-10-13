"""官方 UDA full-source normalization CLI 測試。"""

from __future__ import annotations

import json
from pathlib import Path

from app.scripts.prepare_uda_full_source import normalize_uda_full_source, parse_subset_names, resolve_bench_root


def test_normalize_uda_full_source_outputs_row_contract(tmp_path: Path) -> None:
    """UDA helper 應可輸出現有 prepare-source 可吃的 row contract。

    參數：
    - `tmp_path`：pytest 暫存目錄。

    回傳：
    - `None`：以斷言驗證輸出欄位。
    """

    dataset_dir = tmp_path / "dataset"
    bench_dir = dataset_dir / "extended_qa_info_bench"
    bench_dir.mkdir(parents=True, exist_ok=True)
    source_dir = tmp_path / "source_docs" / "fin_docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_file = source_dir / "GS_2016.pdf"
    source_file.write_bytes(b"%PDF-1.4\n%test\n")

    (bench_dir / "bench_fin_qa.json").write_text(
        json.dumps(
            {
                "GS_2016": [
                    {
                        "q_uid": "GS/2016/page_79.pdf-3",
                        "question": "what percentage of total long-term assets under supervision are comprised of fixed income in 2015?",
                        "answers": {"str_answer": "57%", "exe_answer": 0.57484},
                        "evidence": {"table_3": "fixed income is 530", "table_4": "total long-term assets is 922"},
                        "program": "divide(530, 922)",
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "uda_rows.jsonl"
    summary = normalize_uda_full_source(
        bench_root=resolve_bench_root(dataset_dir),
        source_doc_root=(tmp_path / "source_docs"),
        subset_names=parse_subset_names("fin"),
        output_path=output_path,
        max_rows=None,
    )

    assert summary["row_count"] == 1
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert rows[0]["document_id"] == "GS_2016"
    assert rows[0]["question"].startswith("what percentage")
    assert rows[0]["answer"] == "57%"
    assert "fixed income is 530" in rows[0]["evidence"]
    assert rows[0]["source_file"].endswith("GS_2016.pdf")
    assert rows[0]["source_metadata"]["subset"] == "fin"
