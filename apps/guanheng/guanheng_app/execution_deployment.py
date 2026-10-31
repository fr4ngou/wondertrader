"""App显式执行部署只绑定来源身份；原生配置及进程规则归原B模块。"""
from __future__ import annotations

from hashlib import sha256

from .execution_process import ExecutionProcessConfig, PythonExecutionProcessConfig
from .managed_local_process import _inspect, _json, _path, _read, _require, _sha


_FIELDS = {"schema", "installation", "installation_manifest_sha256", "configuration", "configuration_sha256", "control_root"}
_SCHEMAS = {"guanheng.execution-app.v1": _FIELDS, "guanheng.execution-app.v2": _FIELDS | {"runtime"}}
_ERROR = "invalid execution App deployment"


class ExecutionDeploymentConfig:
    """有界加载门面；构造/加载均不创建owner、线程、Job或执行状态。"""

    @staticmethod
    def from_path(path, expected_sha256=None) -> ExecutionProcessConfig | PythonExecutionProcessConfig | None:
        """绑定父文档及B实际消费的配置/清单前后摘要，错误统一去敏ValueError。"""
        try:
            if path is None or path == "":
                _require(expected_sha256 is None or expected_sha256 == "")
                return None
            expected = _sha(expected_sha256)
            parent = _path(path)
            raw = _read(parent, 16 * 1024)
            _require(sha256(raw).hexdigest() == expected)
            value = _json(raw)
            _require(value.get("schema") in _SCHEMAS and set(value) == _SCHEMAS[value["schema"]])
            runtime = value.get("runtime", "native")
            _require(runtime in ("native", "configured-python"))
            config_type = PythonExecutionProcessConfig if runtime == "configured-python" else ExecutionProcessConfig
            installation = _path(value["installation"])
            configuration = _path(value["configuration"])
            control_root = _path(value["control_root"], e_drive=True)
            _inspect(control_root, directory=True)
            manifest_sha = _sha(value["installation_manifest_sha256"])
            configuration_sha = _sha(value["configuration_sha256"])
            manifest_path = installation / "execution-install.json"
            manifest_raw = _read(manifest_path, 256 * 1024)
            configuration_raw = _read(configuration, 256 * 1024)
            _require(sha256(manifest_raw).hexdigest() == manifest_sha
                     and sha256(configuration_raw).hexdigest() == configuration_sha)
            manifest = _json(manifest_raw)
            loaded = config_type.load(installation, configuration, control_root)
            _require(type(loaded) is config_type and loaded.installation == installation
                     and loaded.configuration == configuration and loaded.control_root == control_root
                     and loaded.configuration_sha256 == configuration_sha
                     and loaded.artifacts == tuple(sorted(manifest["files"].items())))
            _require(_read(parent, 16 * 1024) == raw
                     and _read(manifest_path, 256 * 1024) == manifest_raw
                     and _read(configuration, 256 * 1024) == configuration_raw)
            return loaded
        except Exception:
            raise ValueError(_ERROR) from None
