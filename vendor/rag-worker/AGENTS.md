# AGENTS.md

此模組負責背景 ingest 與 indexing。

## 聚焦範圍
- Celery tasks
- loader selection
- chunking
- embeddings
- FTS `tsvector` generation
- status transitions
- reindex flow

## 關鍵規則
- 僅支援指定檔案類型
- OCR 不在範圍內
- 只有索引完成後才能標記 ready
- 失敗必須可觀測
- 所有 function / method docstring 都必須包含參數與回傳說明
