"""安装后的本机只读应用入口。"""

import argparse

import uvicorn

from .app import create_app
from .settings import ConsoleSettings

# 只读HTTP入口使用标准套接字传输；进程和管道继续由独立WT拥有。
HTTP_LOOP = "asyncio:SelectorEventLoop"


def main():
    parser = argparse.ArgumentParser(description="观衡独立业务应用")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "::1"])
    parser.add_argument("--port", type=int, default=18120)
    parser.add_argument("--static-directory")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口须为1至65535")
    try:
        settings = ConsoleSettings.from_environment()
        application = create_app(settings=settings, static_directory=args.static_directory)
    except ValueError:
        parser.error("观衡读取配置无效；运行配置请迁至独立WT入口，观衡仅配置读取连接")
    uvicorn.run(application, host=args.host, port=args.port, access_log=False,
                loop=HTTP_LOOP)
    # App在默认配置下也拥有读取线程；关闭总结果覆盖全部owner，新能力无需另列退出条件。
    if not getattr(application.state, "shutdown_complete", False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
