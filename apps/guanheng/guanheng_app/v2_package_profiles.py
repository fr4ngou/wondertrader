"""V2发行身份组来自同一包内静态定义；SPA消费相同JSON，运行只采用current组。"""
from importlib.resources import files
from functools import cache
from copy import deepcopy
import json


@cache
def _definition():
    return json.loads(files(__package__).joinpath("v2_package_profiles.json").read_bytes())


def profiles():
    """读取安装包固定资源，不探测配置/旧源码目录；每次返回独立值。"""
    return deepcopy(_definition())


def dependencies(profile):
    return {"guanheng-strategy-signals": profile["signal_version"],
            "guanheng-strategy-variants": profile["variants_version"], "tzdata": profile["tzdata_version"]}


def match_profile(pipeline_dependencies, trace):
    """逐组核完整版本/摘要；不同有效组的字段组合不组成第三种资格。"""
    for profile in profiles()["profiles"]:
        if (pipeline_dependencies == dependencies(profile)
                and trace.get("core_version") == profile["core_version"]
                and trace.get("core_wheel_sha256") == profile["core_wheel_sha256"]):
            return profile
    return None


def current_packages():
    value = profiles()
    current = next(profile for profile in value["profiles"] if profile["profile_id"] == value["current_profile"])
    return {**dependencies(current), "guanheng-strategy-core": current["core_version"],
            "guanheng-strategy-v2": current["v2_version"], "guanheng-strategy-native": "0.1.0a1"}
