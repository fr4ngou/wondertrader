"""离线安装WT数据角色到全新目录；不启动数据采集、服务或修改外部历史。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tools'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain(path):
    path = Path(path).absolute()
    if any(p.is_symlink() or (p.exists() and getattr(p.lstat(), 'st_file_attributes', 0) & 0x400)
            for p in (path, *path.parents)):
        raise ValueError('daily installation linked path rejected')
    return path


def install(artifact, manifest_sha256, destination, python, *, seconds):
    """使用调用方固定的清单与基础解释器；全部子命令复用原隐藏Job和同一总D。"""
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 10 <= seconds <= 3600:
        raise ValueError('daily installation finite deadline required')
    artifact, destination, python = plain(artifact), plain(destination), plain(python)
    manifest_path = artifact / 'ARTIFACT.json'
    if sha(manifest_path) != manifest_sha256:
        raise ValueError('daily artifact identity differs')
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('schema') != 'guanheng.daily-data-artifact.v1' or len(manifest['files']) > 1024:
        raise ValueError('daily artifact schema or capacity invalid')
    for member, identity in manifest['files'].items():
        name = PurePosixPath(member)
        if name.is_absolute() or name.as_posix() != member or '..' in name.parts or ':' in member or '\\' in member:
            raise ValueError('daily artifact relative member invalid')
        if sha(plain(artifact / member)) != identity:
            raise ValueError('daily artifact member changed')
    actual = {p.relative_to(artifact).as_posix() for p in artifact.rglob('*') if p.is_file()}
    if actual != set(manifest['files']) | {'ARTIFACT.json'}:
        raise ValueError('daily artifact has undeclared files')
    if sha(python) != manifest['runtime']['python_sha256']:
        raise ValueError('daily installation base interpreter differs')
    base_record = artifact / manifest['runtime']['base_files']
    if sha(base_record) != manifest['runtime']['base_files_sha256']:
        raise ValueError('daily fixed runtime declaration differs')
    for member, identity in json.loads(base_record.read_bytes()).items():
        if sha(plain(python.parent / member)) != identity:
            raise ValueError('daily fixed runtime source file changed')
    if destination.exists() or destination.is_relative_to(artifact) or artifact.is_relative_to(destination):
        raise ValueError('daily installation fresh separate destination required')
    destination.mkdir(parents=False, exist_ok=False)
    deadline = time.monotonic() + seconds
    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise TimeoutError('daily installation deadline')
        return value
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(('PIP_', 'PYTHON'))}
    environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8',
        PIP_NO_INDEX='1', PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_CONFIG_FILE=os.devnull)
    import native
    logs = destination / 'logs'
    logs.mkdir()
    native.run([python, '-I', '-B', '-m', 'venv', '--copies', destination / 'venv'],
        cwd=destination, env=environment, timeout=remaining(), log=logs / 'venv.log', private_console=True)
    executable = destination / 'venv/Scripts/python.exe'
    native.run([executable, '-I', '-B', '-m', 'pip', 'install', '--no-index', '--no-compile', '--require-hashes',
        '--find-links', artifact / 'wheels', '-r', artifact / 'requirements.lock'],
        cwd=destination, env=environment, timeout=remaining(), log=logs / 'install.log', private_console=True)
    native.run([executable, '-I', '-B', '-m', 'pip', 'check'], cwd=destination, env=environment,
        timeout=remaining(), log=logs / 'pip-check.log', private_console=True)
    shutil.copytree(artifact / 'native', destination / 'native')
    query = ('import json,sys,importlib.metadata as m;'
             'print(json.dumps(dict(version=sys.version,base_prefix=sys.base_prefix,executable=sys.executable,'
             'distributions=sorted((d.metadata["Name"],d.version)for d in m.distributions()))))')
    raw, _ = native.run([executable, '-I', '-B', '-c', query], cwd=destination, env=environment,
        timeout=remaining(), log=logs / 'identity.log', private_console=True)
    runtime = json.loads(raw)
    if not runtime['version'].startswith(manifest['runtime']['version']):
        raise ValueError('daily installed interpreter version differs')
    # 以wheel的RECORD与永久ORIGINS逐一校验原模块，正常安装产生的元数据另由pip check核。
    site = destination / 'venv/Lib/site-packages'
    origins = json.loads((site / 'guanheng_daily_data/ORIGINS.json').read_bytes())
    for member, row in origins.items():
        if sha(plain(site / member)) != row['sha256']:
            raise ValueError('daily installed source bytes differ')
    if sha(manifest_path) != manifest_sha256:
        raise ValueError('daily artifact changed during installation')
    # 在全部子命令结束后核同目标字节，复制期间的来源改变也不能取得安装成功资格。
    installed_native = {p.relative_to(destination / 'native').as_posix(): sha(plain(p))
                        for p in (destination / 'native').rglob('*') if p.is_file()}
    expected_native = {name.removeprefix('native/'): identity
                       for name, identity in manifest['files'].items() if name.startswith('native/')}
    if installed_native != expected_native:
        raise ValueError('daily installed native bytes differ')
    remaining()
    receipt = dict(
        schema='guanheng.daily-data-installation.v1',  # 独立程序安装事实，未启动任何行情/交易服务。
        version=manifest['version'],  # 来源发行版本，不替代CURRENT数据版本。
        artifact_sha256=manifest_sha256,  # 外部固定的原离线制品清单SHA。
        python=str(executable),  # 安装后独立解释器绝对路径。
        python_sha256=sha(executable),  # venv launcher实际字节身份，区别基础解释器。
        pythonw=str(executable.with_name('pythonw.exe')),  # WT受管隐藏进程入口。
        pythonw_sha256=sha(executable.with_name('pythonw.exe')),  # 隐藏launcher字节身份，由WT父部署固定。
        base_python=dict(path=str(python), sha256=sha(python)),  # 原固定基础解释器及身份。
        runtime=runtime,  # 实际解释器版本/基础目录及完整已安装发行集合。
        source_members=len(origins),  # 逐字节核同的永久共享源码成员数。
        source_market_entry=str(site / 'integrations/guanheng/source_market_service.py'),  # 原SMP托管入口，可显式组合数据生产。
        source_market_entry_sha256=sha(site / 'integrations/guanheng/source_market_service.py'),  # 与父SMP部署记录核同的原入口字节。
        daily_data_entry=str(site / 'integrations/guanheng/daily_data_service.py'),  # 独立数据入口，任务数据由外部配置拥有。
        daily_data_entry_sha256=sha(site / 'integrations/guanheng/daily_data_service.py'),  # 独立数据命令固定身份。
        native=installed_native,  # 已逐件核同制品清单的Reader/Helper/Storage发行字节。
        source_calls=0,  # 安装阶段没有来源调用，不取得市场覆盖资格。
        services_started=0)  # 安装阶段不启动WT、QMT或观衡进程。
    (destination / 'INSTALLATION.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--seconds', type=float, default=600)
    args = parser.parse_args()
    result = install(args.artifact, args.manifest_sha256, args.destination, args.python, seconds=args.seconds)
    print(json.dumps(dict(passed=True,python=result['python'],source_members=result['source_members'])))


if __name__ == '__main__':
    main()
