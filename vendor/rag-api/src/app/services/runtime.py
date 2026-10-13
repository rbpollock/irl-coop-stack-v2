"""骨架 health 與依賴資訊回報使用的執行期輔助元件。"""

from urllib.parse import urlparse

from app.core.settings import AppSettings
from app.schemas.health import DependencySnapshot


def _sanitize_target(target: str) -> str:
    """在回傳依賴快照前移除 URL 內可能包含的帳密資訊。"""

    parsed = urlparse(target)
    if not parsed.scheme:
        return target
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""
    return f"{parsed.scheme}://{host}{port}{path}"


def build_dependency_snapshot(settings: AppSettings) -> list[DependencySnapshot]:
    """建立不含敏感資訊的依賴快照，供本機接線驗證使用。"""
    return [
        DependencySnapshot(name="postgres", target=_sanitize_target(settings.database_url)),
        DependencySnapshot(name="redis", target=_sanitize_target(settings.redis_url)),
        DependencySnapshot(name="minio", target=_sanitize_target(settings.minio_endpoint)),
        DependencySnapshot(name="keycloak", target=_sanitize_target(settings.keycloak_url)),
    ]
