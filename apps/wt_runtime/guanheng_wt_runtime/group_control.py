"""同一操作入口组合独立WT服务；各原ServiceController继续拥有运行及恢复。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
import hashlib
import json
from pathlib import Path
import time
from typing import get_type_hints

from guanheng_wt_runtime.managed_local_process import _path, _read, _require, _sha
from guanheng_wt_runtime.service_control import ServiceConfig, ServiceController, _ServiceLease, _publish
from guanheng_wt_runtime.runtime import RuntimeConfig


def _service_snapshot(raw):
    """由同一已核SHA字节构造原配置，避免再次读取已被替换的service.json。"""
    value = json.loads(raw)
    names = {field.name for field in fields(ServiceConfig)}
    _require(type(value) is dict and set(value) == names | {'schema'}
             and value['schema'] == 'guanheng.wt-service.v1')
    types = get_type_hints(ServiceConfig)
    _require(all(types[name] in (Path, str) for name in names))
    service = ServiceConfig(**{name: _path(value[name], e_drive=True) if types[name] is Path
                              else _sha(value[name]) for name in names})
    service.validate()
    return service


@dataclass(frozen=True)
class GroupMember:
    name: str  # 操作结果中的角色名称，来自组配置；不承载账户或凭证。
    service: ServiceConfig  # 原服务的完整已验证配置，运行及金融事实继续由原控制器持有。


@dataclass(frozen=True)
class GroupConfig:
    members: tuple[GroupMember, ...]  # 已声明依赖顺序；先启动依赖，逆序正常停止。
    status_file: Path  # 本组公开结果绝对路径；原子替换，锁文件归同一组操作租约。

    @classmethod
    def from_path(cls, filename):
        value = json.loads(_read(_path(str(filename), e_drive=True), 65536))
        _require(type(value) is dict and set(value) == {'schema', 'services', 'status_file'}
                 and value['schema'] == 'guanheng.wt-service-group.v1')
        status_file = _path(value['status_file'], e_drive=True)
        _require(status_file.parent.is_dir() and type(value['services']) is list and value['services'])
        members, names, currents = [], set(), set()
        for row in value['services']:
            _require(type(row) is dict and set(row) == {'name', 'configuration', 'sha256'})
            name = row['name']
            _require(type(name) is str and name and len(name) <= 64 and not any(ord(c) < 32 for c in name)
                     and name not in names)
            path = _path(row['configuration'], e_drive=True)
            raw = _read(path, 65536)
            _require(hashlib.sha256(raw).hexdigest() == _sha(row['sha256']))
            service = _service_snapshot(raw)
            _require(service.current_file not in currents and service.current_file != status_file)
            names.add(name)
            currents.add(service.current_file)
            members.append(GroupMember(name, service))
        return cls(tuple(members), status_file)


class GroupController:
    """只串行调用已有服务接口；失败保留原代与已运行角色，交原恢复流程续核。"""

    def __init__(self, config):
        self.config = config  # 本次固定组配置；操作过程中不改成员及依赖顺序。

    def _run(self, action):
        results = []
        order = self.config.members if action != 'stop' else tuple(reversed(self.config.members))
        for member in order:
            try:
                controller = ServiceController(member.service)
                budget = RuntimeConfig.from_path(str(member.service.bootstrap_configuration),
                    member.service.bootstrap_configuration_sha256).startup_seconds
                deadline = time.monotonic() + budget + 10  # 同原服务启动总截止；轮询不重新start或延长截止。
                code, value = getattr(controller, action)()
                changed = value.get('changed', False)
                # 原子发布的短暂共享冲突可返回starting；续读同一当前代，不重复创建进程。
                while action == 'start' and code == 0 and value.get('state') == 'starting' and time.monotonic() < deadline:
                    time.sleep(.05)
                    code, observed = controller.status()
                    value = dict(observed, action='start', changed=changed)
            except Exception:
                code, value = 2, dict(state='control_error', ready=False, changed=False,
                                      error_code='control_error')
            results.append(dict(name=member.name, result=value, exit_code=code))
            expected = value.get('state') == 'ready' if action == 'start' else value.get('state') in ('stopped', 'absent')
            if action != 'status' and (code != 0 or not expected):
                break  # 未确认停止时保留依赖；启动失败时保持已运行成员，不自动反复启动。
        complete = len(results) == len(order)
        if action == 'stop':
            success = complete and all(row['exit_code'] == 0 and row['result']['state'] in ('stopped', 'absent') for row in results)
            state = 'stopped' if success else 'stop_incomplete'
        else:
            success = complete and all(row['exit_code'] == 0 and row['result'].get('state') == 'ready' for row in results)
            state = 'ready' if success else 'not_ready'
        return (0 if success else 2), dict(schema='guanheng.wt-service-group-result.v1', action=action,
            state=state, ready=success and action != 'stop', services=results,
            unprocessed=[member.name for member in order[len(results):]])

    def run(self, action):
        if action == 'status':
            return self._run(action)  # 查询不写控制文件或触发服务恢复。
        with _ServiceLease(self.config.status_file):
            code, result = self._run(action)
            _publish(self.config.status_file, result)
            return code, result


def main(argv=None):
    parser = argparse.ArgumentParser(description='WT统一启停及状态')
    parser.add_argument('action', choices=('start', 'stop', 'status'))
    parser.add_argument('--group-config', required=True)
    args = parser.parse_args(argv)
    try:
        code, result = GroupController(GroupConfig.from_path(args.group_config)).run(args.action)
    except Exception:
        code, result = 2, dict(schema='guanheng.wt-service-group-result.v1', action=args.action,
            state='control_error', ready=False, services=[], unprocessed=[], error_code='control_error')
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
