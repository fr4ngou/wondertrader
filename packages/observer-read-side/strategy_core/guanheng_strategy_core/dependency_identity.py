"""已安装纯策略包的唯一版本声明准入；业务计算不读取安装环境。"""
from importlib import metadata, resources
import json
import re
import sys


def _exact_version_matches(candidate, pinned):
    """公开精确pin忽略合法local后缀；显式local pin仍要求原文本一致。

    public部分保持现有逐字身份，不在这里实现版本归一化或放宽范围/来源。
    """
    if (type(candidate) is not str or type(pinned) is not str
            or not candidate or not pinned or len(candidate) > 256 or len(pinned) > 256):
        return False
    public, separator, local = candidate.partition("+")
    if separator and re.fullmatch(r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*", local) is None:
        return False
    if "+" in pinned:
        return candidate == pinned
    return public == pinned


def _requirements(values):
    if type(values) is not list or not 1 <= len(values) <= 8:
        raise RuntimeError("策略精确依赖集合无效")
    result = {}
    pattern = r'''([A-Za-z0-9_-]+)==([A-Za-z0-9.]+(?:\+[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*)?)(?:\s*;\s*sys_platform\s*==\s*(['"])win32\3)?'''
    for requirement in values:
        if type(requirement) is not str or len(requirement) > 256:
            raise RuntimeError("策略依赖声明超过容量")
        match = re.fullmatch(pattern, requirement)
        if match is None:
            raise RuntimeError("纯策略依赖需要精确版本及已声明平台条件")
        name = match[1].lower().replace("_", "-")
        if name in result:
            raise RuntimeError("策略依赖声明重复")
        result[name] = (match[2], match[3] is not None)
    return result


def package_identity(module_name, distribution_name):
    """核包内来源声明、安装METADATA与实际依赖，返回独立的版本/依赖/声明。

    仅供包导入阶段调用；输入是包自身固定名称。运行前拒绝来源声明与安装元数据
    漂移，避免源码内重复版本常量在依赖升级后继续误报旧身份。
    """
    with resources.files(module_name).joinpath("source_manifest.json").open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise RuntimeError("策略来源声明超过容量")
    value = json.loads(raw)
    version = value.get("package_version")
    declared = value.get("dependencies")
    if (type(version) is not str or len(version) > 64 or type(declared) is not dict
            or not 1 <= len(declared) <= 8
            or any(type(name) is not str or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", name) is None
                   or type(pin) is not str or (len(pin) > 64 or re.fullmatch(r"[0-9][a-zA-Z0-9.]*(?:\+[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*)?", pin) is None)
                   for name, pin in declared.items())):
        raise RuntimeError("策略版本与依赖声明无效")
    requirements = _requirements(value.get("requires_dist"))
    if {name: item[0] for name, item in requirements.items()} != declared:
        raise RuntimeError("策略精确依赖与平台声明失配")
    try:
        installed = _requirements(metadata.requires(distribution_name))
        if (metadata.version(distribution_name) != version or installed != requirements
                or any(not _exact_version_matches(metadata.version(name), pin) for name, (pin, windows_only) in requirements.items()
                       if not windows_only or sys.platform == "win32")):
            raise RuntimeError("策略来源、安装与固定依赖身份失配")
    except metadata.PackageNotFoundError:
        raise RuntimeError("策略固定依赖尚未安装") from None
    return version, dict(declared), value
