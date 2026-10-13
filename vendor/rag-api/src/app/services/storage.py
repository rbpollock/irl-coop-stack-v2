"""API 使用的物件儲存抽象。"""

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
import shutil

from minio import Minio
from minio.error import S3Error

from app.core.settings import AppSettings


class StorageError(RuntimeError):
    """代表物件儲存操作失敗。"""


class ObjectStorage(ABC):
    """提供文件原始檔讀寫的最小介面。"""

    @abstractmethod
    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """寫入物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：要記錄的 MIME 類型。

        回傳：
        - `None`：此抽象方法只描述寫入行為。
        """

    @abstractmethod
    def get_object(self, *, object_key: str) -> bytes:
        """讀取物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

    @abstractmethod
    def delete_object(self, *, object_key: str) -> None:
        """刪除既有物件內容。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `None`：此抽象方法只描述刪除行為。
        """

    @abstractmethod
    def delete_prefix(self, *, prefix: str) -> None:
        """刪除指定前綴下的所有物件。

        參數：
        - `prefix`：物件儲存中的前綴路徑。

        回傳：
        - `None`：此抽象方法只描述批次刪除行為。
        """


class MinioObjectStorage(ObjectStorage):
    """以 MinIO/S3 API 儲存原始檔。"""

    def __init__(self, settings: AppSettings) -> None:
        """初始化 MinIO client。

        參數：
        - `settings`：包含 MinIO endpoint、bucket 與憑證設定的應用程式設定。

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

    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """若 bucket 不存在則先建立，再寫入物件。

        參數：
        - `object_key`：物件儲存中的鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：要記錄的 MIME 類型。

        回傳：
        - `None`：此方法只負責寫入物件。
        """

        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
            self._client.put_object(
                self._bucket,
                object_key,
                BytesIO(payload),
                length=len(payload),
                content_type=content_type,
            )
        except S3Error as exc:
            raise StorageError("無法寫入物件儲存。") from exc

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

    def delete_object(self, *, object_key: str) -> None:
        """刪除既有 MinIO 物件。

        參數：
        - `object_key`：物件儲存中的鍵值。

        回傳：
        - `None`：此方法只負責刪除物件。
        """

        try:
            self._client.remove_object(self._bucket, object_key)
        except S3Error as exc:
            raise StorageError("無法刪除物件儲存內容。") from exc

    def delete_prefix(self, *, prefix: str) -> None:
        """刪除指定前綴下的所有 MinIO 物件。

        參數：
        - `prefix`：物件儲存中的前綴路徑。

        回傳：
        - `None`：此方法只負責批次刪除物件。
        """

        try:
            objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
            for obj in objects:
                self._client.remove_object(self._bucket, obj.object_name)
        except S3Error as exc:
            raise StorageError("無法刪除物件儲存內容。") from exc


class FilesystemObjectStorage(ObjectStorage):
    """測試與本機驗證使用的檔案系統儲存。"""

    def __init__(self, settings: AppSettings) -> None:
        """初始化本機儲存根目錄。

        參數：
        - `settings`：包含本機儲存路徑設定的應用程式設定。

        回傳：
        - `None`：此建構子只負責初始化儲存根目錄。
        """

        self._base_path = Path(settings.local_storage_path)

    def put_object(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        """將物件寫入本機檔案系統。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。
        - `payload`：要寫入的原始位元組內容。
        - `content_type`：保留的 MIME 類型；檔案系統儲存不會使用。

        回傳：
        - `None`：此方法只負責寫入檔案。
        """

        del content_type
        destination = self._base_path / object_key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    def get_object(self, *, object_key: str) -> bytes:
        """從本機檔案系統讀取物件。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。

        回傳：
        - `bytes`：讀取出的原始位元組內容。
        """

        source = self._base_path / object_key
        try:
            return source.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("無法讀取物件儲存。") from exc

    def delete_object(self, *, object_key: str) -> None:
        """從本機檔案系統刪除既有物件。

        參數：
        - `object_key`：檔案系統儲存中的相對鍵值。

        回傳：
        - `None`：此方法只負責刪除檔案。
        """

        target = self._base_path / object_key
        if target.exists():
            target.unlink()

    def delete_prefix(self, *, prefix: str) -> None:
        """從本機檔案系統刪除指定前綴下的所有內容。

        參數：
        - `prefix`：檔案系統儲存中的相對前綴路徑。

        回傳：
        - `None`：此方法只負責刪除路徑。
        """

        target = self._base_path / prefix
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def build_object_storage(settings: AppSettings) -> ObjectStorage:
    """依設定建立物件儲存實例。

    參數：
    - `settings`：包含 storage backend 與儲存設定的應用程式設定。

    回傳：
    - `ObjectStorage`：符合目前執行模式的物件儲存實作。
    """

    if settings.storage_backend == "filesystem":
        return FilesystemObjectStorage(settings=settings)
    return MinioObjectStorage(settings=settings)
