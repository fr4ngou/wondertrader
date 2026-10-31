"""Pinned Uvicorn lifecycle with one Host-owned shutdown window.

The upstream connection/task limiter includes the current connection and uses
>=. N+1 permits N connections; the app enforces exactly N processing requests.
Idle keepalive occupies that upstream connection count until its finite timeout.
These limits do not bound TCP backlog, pre-header sockets or total process RSS.
"""
import time
import uvicorn
from .app import create_app


class HostServer(uvicorn.Server):
    def __init__(self, runtime, *, http_keys):
        self.runtime=runtime
        super().__init__(uvicorn.Config(create_app(runtime,http_keys=http_keys),
            host=runtime.listen_host,port=runtime.listen_port,workers=1,
            log_config=None,log_level='critical',access_log=False,
            limit_concurrency=runtime.max_http_inflight+1,
            timeout_keep_alive=runtime.budget.io_seconds,
            timeout_graceful_shutdown=runtime.budget.io_seconds+1))

    def request_close(self):
        deadline=self.runtime.begin_shutdown()
        self.runtime.request_close()
        self.should_exit=True
        return deadline

    def handle_exit(self, sig, frame):
        # 信号只发布与控制线程共享的首次关闭截止，不获取Python锁；
        # shutdown()随后唤醒I/O并排空HTTP，所有阶段沿用这份剩余预算。
        self.runtime.begin_shutdown()
        super().handle_exit(sig,frame)

    async def shutdown(self, sockets=None):
        deadline=self.request_close()
        # Uvicorn 0.51 sleeps 0.1s before wait_for; reserve another 0.1s for
        # lifespan/Journal cleanup, all inside the same original deadline.
        self.config.timeout_graceful_shutdown=max(0,deadline-time.monotonic()-0.2)
        await super().shutdown(sockets)

    def close(self):
        deadline=self.request_close()
        self.runtime.close(deadline)
        if (getattr(self,'lifespan',None) is not None
                and (self.lifespan.startup_failed or self.lifespan.shutdown_failed)):
            raise RuntimeError('Host lifespan did not complete')


def create_server(runtime, *, http_keys):
    return HostServer(runtime,http_keys=http_keys)


def run_server(runtime, *, http_keys):
    server=create_server(runtime,http_keys=http_keys)
    try:
        server.run()
        if not server.started:
            raise RuntimeError('Host HTTP did not start')
    finally:
        server.close()
