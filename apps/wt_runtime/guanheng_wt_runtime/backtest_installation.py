"""部署阶段生成原NSH安装绑定；运行期只消费其明确摘要。"""
import math
import re
import time

from .strategy_host import (HostError, InstallationBinding, INSTALL_SCHEMA,
    RETAINED_REPORT_SCHEMA, PER_DATE_REPORT_SCHEMA, ORIGINAL_REPORT_SCHEMA, _BASES, _bytes, _check, _digest, _encode, _path,
    _tree, _write, verify_install)


def write_binding(output, *, python, native_root, abi_probe, basefiles, seconds=60.0, replay_catalog=None, report_schema=None):
    """同步校验安装后独占写入新manifest，返回原InstallationBinding。

    调用方提供受管绝对路径及五种基础资料。seconds为包含全部读取与校验的总秒数；
    复用运行期验证器，拒绝隐式启动钩子、安装漂移或不匹配原生库。失败抛HostError
    或文件异常，已有输出保持；本入口不创建目录、启动Python/原生或执行策略。
    replay_catalog显式选择逐日族并绑定原A目录/manifest；省略保持最终批次族。
    """
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not .1 <= seconds <= 120:
        raise HostError('安装绑定期限需要0.1至120秒')
    deadline = time.monotonic()+seconds
    output, python, native_root, abi_probe = map(_path, (output, python, native_root, abi_probe))
    if (not output.parent.is_dir() or output.exists() or type(basefiles) is not dict
            or set(basefiles) != set(_BASES)):
        raise HostError('需要新安装绑定路径及完整五种基础资料')
    venv = python.parent.parent
    site = venv / 'Lib/site-packages'
    config = venv / 'pyvenv.cfg'
    text = _bytes(config, 16384, deadline).decode('utf-8')
    home = re.search(r'(?im)^home\s*=\s*(.+?)\s*$', text)
    if home is None:
        raise HostError('Python环境缺少明确home')
    runtime = _path(home.group(1))

    def artifact(path):
        path = _path(path)
        return dict(path=str(path), sha256=_digest(_bytes(path, 64*1024*1024, deadline)))

    def inventory(root):
        files, _ = _tree(root, 512*1024*1024, 8192, deadline)
        return {path.relative_to(root).as_posix(): artifact(path)['sha256'] for path in files}

    if report_schema is not None and (report_schema != ORIGINAL_REPORT_SCHEMA or replay_catalog is not None):
        raise HostError('显式报告族需要独立原版WT且不能同时选择逐日目录')
    value = dict(schema=INSTALL_SCHEMA, report_schema=report_schema or RETAINED_REPORT_SCHEMA,
        python=artifact(python), python_config=artifact(config),
        python_runtime=[artifact(path) for path in (runtime/'python.exe', *sorted(runtime.glob('python3*.dll')))],
        site_root=str(site), site_files=inventory(site), native_root=str(native_root),
        native_files=inventory(native_root), library=artifact(native_root/'WtBtPorter.dll'),
        abi_probe=artifact(abi_probe), basefiles={name: artifact(basefiles[name]) for name in _BASES})
    if replay_catalog is not None:
        if type(replay_catalog) is not dict or set(replay_catalog) != {'path', 'manifest_sha256'}:
            raise HostError('逐日目录绑定字段失配')
        value.update(report_schema=PER_DATE_REPORT_SCHEMA,
            replay_catalog=dict(path=str(_path(replay_catalog['path'])),
                                manifest_sha256=replay_catalog['manifest_sha256']))
    raw = _encode(value)
    digest = _digest(raw)
    verify_install(raw, digest, deadline)
    _check(deadline)
    _write(output, raw)
    # 写入可能跨D；文件作为实际制品保留，调用结果继续按原期限确认。
    _check(deadline)
    return InstallationBinding(output, digest)
