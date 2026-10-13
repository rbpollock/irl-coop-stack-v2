"""供本機操作與容器驗證使用的 worker 健康檢查腳本。"""

from worker.tasks.health import ping


def main() -> int:
    """同步執行本機 ping task，並回傳程序結束碼。"""

    result = ping.apply().get()
    if result != "pong":
        return 1
    print("worker 健康檢查通過")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
