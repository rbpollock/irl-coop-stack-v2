"""Worker 使用的原始檔儲存讀取抽象。"""

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
import shutil

from minio import Minio
from minio.error import S3Error

from worker.core.settings import WorkerSettings


class StorageError(RuntimeError):
    """代表儲存讀取失敗。"""


class ObjectStorageReader(ABC):
    """提供 worker 讀取文件原始檔的最小介面。"""

    @abstractmethod
    def get_object(self, *, object_key: str) -> bytes:
        """讀取指定物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

    @abstractmethod
    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """寫入指定物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：物件 MIME 類型。

        回傳：
        - `None`：此函式只負責寫入物件。
        """

    @abstractmethod
    def delete_prefix(self, *, prefix: str) -> None:
        """刪除指定前綴下的所有物件。

        參數：
        - `prefix`：物件儲存中的前綴路徑。

        回傳：
        - `None`：此函式只負責批次刪除。
        """


class MinioObjectStorageReader(ObjectStorageReader):
    """從 MinIO/S3 API 讀取文件內容。"""

    def __init__(self, settings: WorkerSettings) -> None:
        """初始化 MinIO client。

        參數：
        - `settings`：包含 MinIO endpoint、bucket 與憑證設定的 worker 設定。

        回傳：
        - `None`：此建構子只負責初始化儲存 client。
        """

        endpoint = settings.minio_endpoint.removeprefix("http://").removeprefix("https://")
        self._bucket = settings.minio_bucket
        self._client = Minio(
            endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    def get_object(self, *, object_key: str) -> bytes:
        """讀取既有物件。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

        try:
            response = self._client.get_object(self._bucket, object_key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except S3Error as exc:
            raise StorageError("無法讀取物件儲存。") from exc

    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """寫入指定物件。

        參數：
        - `object_key`：物件儲存中的鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：物件 MIME 類型。

        回傳：
        - `None`：此函式只負責寫入物件。
        """

        try:
            self._client.put_object(
                self._bucket,
                object_key,
                data=BytesIO(payload),
                length=len(payload),
                content_type=content_type,
            )
        except S3Error as exc:
            raise StorageError("無法寫入物件儲存。") from exc

    def delete_prefix(self, *, prefix: str) -> None:
        """刪除指定前綴下的所有 MinIO 物件。

        參數：
        - `prefix`：物件儲存中的前綴路徑。

        回傳：
        - `None`：此函式只負責批次刪除。
        """

        try:
            objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
            for obj in objects:
                self._client.remove_object(self._bucket, obj.object_name)
        except S3Error as exc:
            raise StorageError("無法刪除物件儲存內容。") from exc


class FilesystemObjectStorageReader(ObjectStorageReader):
    """從本機檔案系統讀取文件內容。"""

    def __init__(self, settings: WorkerSettings) -> None:
        """初始化檔案系統儲存根目錄。

        參數：
        - `settings`：包含本機儲存路徑的 worker 設定。

        回傳：
        - `None`：此建構子只負責初始化儲存根目錄。
        """

        self._base_path = Path(settings.local_storage_path)

    def get_object(self, *, object_key: str) -> bytes:
        """讀取指定物件內容。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

        try:
            return (self._base_path / object_key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("無法讀取物件儲存。") from exc

    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """將位元組內容寫入本機檔案系統。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：物件 MIME 類型；filesystem backend 僅保留介面一致性。

        回傳：
        - `None`：此函式只負責寫入檔案。
        """

        del content_type
        target_path = self._base_path / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)

    def delete_prefix(self, *, prefix: str) -> None:
        """刪除指定前綴下的所有本機內容。

        參數：
        - `prefix`：檔案系統儲存中的相對前綴路徑。

        回傳：
        - `None`：此函式只負責刪除路徑。
        """

        target_path = self._base_path / prefix
        if target_path.is_dir():
            shutil.rmtree(target_path)
        elif target_path.exists():
            target_path.unlink()


def build_object_storage_reader(settings: WorkerSettings) -> ObjectStorageReader:
    """依設定建立 worker 使用的物件讀取器。

    參數：
    - `settings`：包含 storage backend 與儲存設定的 worker 設定。

    回傳：
    - `ObjectStorageReader`：符合目前執行模式的物件讀取器。
    """

    if settings.storage_backend == "filesystem":
        return FilesystemObjectStorageReader(settings=settings)
    return MinioObjectStorageReader(settings=settings)
