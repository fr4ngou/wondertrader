"""Independent authenticated read-only QMT Host; internal private artifact."""
from importlib import import_module

__version__ = "0.1.0a22+mdphttp.3.tes.1.uc.1.sdkreturn.1"

# 公开API在实际使用时才加载：共享内存/私有文件等标准库工具独立运行，
# HTTP应用的FastAPI/Uvicorn依赖只由使用HTTP入口的进程承担。
_EXPORTS = {
    "build_runtime": ".bootstrap", "create_app": ".app",
    "create_server": ".server", "run_server": ".server",
    "HostReadRuntime": ".runtime", "HostRequest": ".runtime", "HostResponse": ".runtime",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
