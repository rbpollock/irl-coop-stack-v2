# AGENTS.md

此模組負責 FastAPI 應用程式。

## 聚焦範圍
- routes
- schemas
- auth integration
- effective role logic
- SQL gate
- documents / job / chat APIs

## 關鍵規則
- deny-by-default 是強制要求
- 只有 ready 文件可以被檢索
- admin 可管理 access，maintainer 不可
- 避免洩漏受保護資源是否存在

## 實作風格
- route 要薄，service 要清楚
- auth / security-sensitive code 需有明確 docstring
- 反向路徑測試不可少
- ORM 查詢與 model 宣告必須使用 SQLAlchemy 2 寫法，例如 `Mapped[...]`、`mapped_column(...)`、`select(...)`、`session.scalars(...)`
- 所有 function / method docstring 都必須包含參數與回傳說明
- `__init__.py` 預設只放檔案說明，不做 package-level re-export
- import 一律直接指向實作檔，不透過 `__init__.py` 匯出中繼
