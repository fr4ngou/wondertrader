"""固定外部依赖的来源和内容身份，缺失时给出 unavailable，不复制上游代码。"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import IntegrationUnavailable


REGISTRY = Path(__file__).with_name("upstream-contracts.json")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


class ExternalQmt:
    """只读导入明确提供的 QMT 源根；进程只能绑定一个业务包版本。

    registry 的切片身份和 SHA 都必须匹配。传入路径由部署 owner 决定，包不存在、
    文件修订或进程已加载其它来源时失败关闭。该验证不授生产资格。
    """

    def __init__(self, root: Path, registry: Path = REGISTRY):
        self.root = Path(root).resolve()
        try:
            self.registry = json.loads(Path(registry).read_text(encoding="utf-8"))
            if self.registry["schema_version"] != 1:
                raise ValueError("依赖登记版本不合格")
        except (OSError, ValueError, KeyError) as exc:
            raise IntegrationUnavailable("外部依赖登记不可用：" + str(exc)) from exc

    def verify(self, section: str):
        try:
            spec = self.registry[section]
            for relative, expected in spec["source_sha256"].items():
                path = self.root / relative
                if digest(path) != expected:
                    raise ValueError("源文件版本变化：" + relative)
        except (OSError, ValueError, KeyError) as exc:
            raise IntegrationUnavailable("QMT 依赖不匹配：" + str(exc), section) from exc
        return spec

    def strategy(self):
        spec = self.verify("business_core")
        source = self.root / "src"
        # Python 的全局包缓存不能同时混入另一个工作树的 DTO 和策略核心。
        for name, module in tuple(sys.modules.items()):
            if name == "qmt_platform" or name.startswith("qmt_platform."):
                file = getattr(module, "__file__", None)
                if file and not Path(file).resolve().is_relative_to(source):
                    raise IntegrationUnavailable("进程已经绑定其他 QMT 来源，请使用独立受管运行时")
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
        try:
            ZoneInfo("Asia/Shanghai")
            prefix = "qmt_platform.services.strategy.strategies.resonance_regime_v1."
            modules = {name: importlib.import_module(prefix + name)
                       for name in ("models", "features", "signals", "strategy")}
            modules["contracts"] = importlib.import_module("qmt_platform.common.contracts")
        except (ImportError, OSError, ZoneInfoNotFoundError) as exc:
            raise IntegrationUnavailable("QMT 纯策略或 DTO 依赖缺失：" + str(exc)) from exc
        for name, module in modules.items():
            if not Path(module.__file__).resolve().is_relative_to(source):
                raise IntegrationUnavailable("QMT 模块来源发生冲突：" + name)
        if modules["strategy"].STRATEGY_VERSION != spec["strategy_version"]:
            raise IntegrationUnavailable("QMT 纯策略声明版本与依赖登记不符")
        return modules

    def broker_types(self):
        spec = self.verify("broker_dependency")
        path = self.root / spec["types_path"]
        # DTO 模块仅依赖标准库，独立模块名避免改变业务核心 qmt_platform 的包绑定。
        name = "_guanheng_broker_" + spec["source_sha256"][spec["types_path"]]
        if name not in sys.modules:
            module_spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(module_spec)
            sys.modules[name] = module
            try:
                module_spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(name, None)
                raise
        return sys.modules[name]

    def retained(self):
        """导入既有业务纯函数/DTO；存储实例与副作用仍由外部 owner 显式注入。"""
        modules = self.strategy()
        self.verify("retained_services")
        names = {
            "risk": "services.portfolio.risk",
            "approvals": "services.portfolio.multi_strategy_approval",
            "commands": "services.bridge.multi_strategy_command",
            "command_store": "services.bridge.store",
            "security": "common.security",
            "analysis": "services.market_data.analysis_window",
            "bar_ingestion": "services.bridge.bar_ingestion",
        }
        try:
            for key, suffix in names.items():
                module = importlib.import_module("qmt_platform." + suffix)
                if not Path(module.__file__).resolve().is_relative_to(self.root / "src"):
                    raise IntegrationUnavailable("既有业务模块来源冲突：" + key)
                modules[key] = module
        except (ImportError, OSError) as exc:
            raise IntegrationUnavailable("既有业务依赖不可用：" + str(exc), "retained_services") from exc
        modules["broker_types"] = self.broker_types()
        return modules

    def console_consumer(self):
        """只读加载原 Console 入口供隔离契约验收；不启动其 lifespan 或上游连接。"""
        self.strategy()
        self.verify("retained_consumers")
        try:
            return importlib.import_module("qmt_platform.services.console.app")
        except (ImportError, OSError) as exc:
            raise IntegrationUnavailable("原 Console 接口依赖缺失：" + str(exc), "console") from exc
