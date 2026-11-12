"""安装后的CTA进程装配；监督与Job生命周期复用ManagedLocalProcess。"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import time

from guanheng_market_client.runtime_status import read_status

from .managed_local_process import ManagedLocalProcess, _identity, _inspect, _json, _read, _require, _sha

from .strategy_profiles import (RETAINED_PACKAGES, SHARED_PACKAGES, SOURCE_HANDOFF_PACKAGES,
                                PACKAGE_DISTRIBUTIONS, shared_profiles, source_handoff)
_RETAINED_PYTHON_PACKAGES = RETAINED_PACKAGES
_PYTHON_PACKAGES = _RETAINED_PYTHON_PACKAGES


def _python_packages(native):
    """固定单/双profile依赖；旧调用保持原包集合。"""
    shared = shared_profiles(native)
    if source_handoff(native):
        return SOURCE_HANDOFF_PACKAGES
    return SHARED_PACKAGES if shared else RETAINED_PACKAGES


def _library_files(installation, *, clock=time.monotonic, deadline=float('inf')):
    """安装树运行期冻结；加载及每次启动均有限遍历并拒绝重解析目录。"""
    pending, libraries, visited = [installation / 'app'], set(), 0
    while pending:
        directory = pending.pop()
        _inspect(directory, directory=True)
        for path in directory.iterdir():
            visited += 1
            _require(visited <= 4096)
            if clock() >= deadline:
                raise TimeoutError('execution installation deadline')
            if path.is_dir():
                _inspect(path, directory=True)
                pending.append(path)
            else:
                _inspect(path)
                if path.suffix.lower() in ('.exe', '.dll'):
                    libraries.add(path.relative_to(installation).as_posix())
    return libraries


@dataclass(frozen=True)
class ExecutionProcessConfig:
    installation: Path  # 固定原生安装绝对目录；启动前核完整安装清单，进程存续期间保持冻结。
    configuration: Path  # 本代实际Native配置原件；库存准备后指向物化配置，供本代快照与恢复核验。
    configuration_sha256: str  # 上述配置完整原字节SHA256；与Native ready/关闭收据绑定，必填。
    control_root: Path  # 各控制代的私有父目录；由监督owner创建本代子目录并保留原件。
    startup_seconds: float  # 本代启动预算，单位秒；从Native start_ms转换，不含运行时长。
    stop_seconds: float  # 正常停止与回收预算，单位秒；从stop_ms转换，持续模式仍生效。
    artifacts: tuple[tuple[str, str], ...]  # 安装相对文件名与原字节SHA256的不可变集合，来自安装清单。
    recovery_mode: str | None = None  # 显式恢复模式；None表示未声明，不能替代原账准入证据。

    @property
    def pythonw(self):
        # 原监督器只使用此字段的父目录；本产品argv直接启动原生exe。
        return self.installation / 'app/GuanhengCtaHost.exe'

    @property
    def max_output_bytes(self):
        """每条管道最多保留256KiB；原监督器超额即停止并继续排空。"""
        return 256 * 1024

    @classmethod
    def load(cls, installation, configuration, control_root):
        installation, configuration, control_root = map(Path, (installation, configuration, control_root))
        _require(all(path.is_absolute() for path in (installation, configuration, control_root)))
        _inspect(installation, directory=True)
        _inspect(control_root, directory=True)
        manifest = _json(_read(installation / 'execution-install.json', 256 * 1024))
        _require(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'guanheng.execution-install.v1')
        files = manifest['files']
        _require(type(files) is dict and 1 <= len(files) <= 512 and 'app/GuanhengCtaHost.exe' in files)
        for name, digest in files.items():
            path = PurePosixPath(name)
            _require(type(name) is str and not path.is_absolute() and '..' not in path.parts
                     and ':' not in name and '\\' not in name and str(path) == name)
            _sha(digest)
        raw = _read(configuration, 256 * 1024)
        config = _json(raw)
        _require(config.get('schema_version') == 'guanheng.cta-execution.v1'
                 and Path(config['installation_root']) == installation / 'app')
        if 'strategy_extension_origin' in config:
            from .execution_recovery import strategy_extension_configuration
            strategy_extension_configuration(config)
            _require(config.get('recovery',{}).get('mode') in ('resume_clean','resume_reconciled'))
        if 'observation_refresh' in config:
            refresh=config['observation_refresh']
            _require(type(refresh) is dict and set(refresh)=={'interval_ms'}
                     and type(refresh['interval_ms']) is int and 1000<=refresh['interval_ms']<=60000)
        required_files = {'app/GuanhengCtaRuntime.dll', 'app/traders/TraderQMTStandard.dll', 'app/executers/WtExeFact.dll'}
        if 'role_replacement' in config:
            # 退役证券过滤器属于本代安装闭包；与原DLL一样由发行清单逐字节校验。
            name = config['environment']['filters']
            relative = PurePosixPath(name)
            _require(type(name) is str and name and not relative.is_absolute()
                     and '..' not in relative.parts and ':' not in name and '\\' not in name)
            required_files.add('app/' + name)
        for name in config['base_data'].values():
            required_files.add('app/' + name)
        for item in config['strategies']:
            required_files.add('app/' + item['module'])
        reader = config['data']['store']['module']
        _require(type(reader) is str and re.fullmatch(r'[A-Za-z0-9_-]+', reader))
        required_files.add('app/' + reader + '.dll')
        for item in config['parsers']:
            if item.get('active') is True:
                module = item['module']
                _require(type(module) is str and re.fullmatch(r'[A-Za-z0-9_-]+', module))
                required_files.add('app/parsers/' + module + '.dll')
        _require(required_files <= set(files))
        _require(_library_files(installation) <= set(files))
        budget = config['budget']
        _require(type(budget) is dict and set(budget) == {'start_ms', 'stop_ms', 'run_ms'})
        for name, maximum in (('start_ms', 60000), ('stop_ms', 60000)):
            _require(type(budget[name]) is int and 1000 <= budget[name] <= maximum)
        # 运行时长属于进程生命周期：0由用户明确选择持续运行，正常stop仍沿原预算。
        duration = budget['run_ms']
        _require(type(duration) is int and (duration == 0 or 1000 <= duration <= 86400000))
        recovery_mode = None
        if 'recovery' in config:
            selection = config['recovery']
            _require(type(selection) is dict and selection.get('mode') in ('record_clean', 'resume_clean', 'resume_reconciled')
                     and set(selection) == ({'mode', 'transition'} if selection['mode'] == 'resume_reconciled' else {'mode'}))
            recovery_mode = selection['mode']
        return cls(installation, configuration, hashlib.sha256(raw).hexdigest(), control_root,
                   budget['start_ms'] / 1000., budget['stop_ms'] / 1000., tuple(sorted(files.items())), recovery_mode)


class ManagedExecutionProcess(ManagedLocalProcess):
    _status_schema = 'guanheng.execution-process.v1'
    _stop_schema = 'guanheng.execution.stop.v1'
    _thread_name = 'managed-cta-execution'

    def status(self):
        """公开生命周期快照；原native入口没有Python业务结果定位。"""
        value = super().status()
        value['business_observation'] = None
        if value['ready'] and getattr(self, '_market_parser_count', 0):
            try:
                observation = read_status(self._directory / 'cta-observation.json', 4096)
            except (OSError, ValueError):
                observation = {}
            value['quote_input_state'] = _quote_input_state(observation, self._control_id,
                self.config.configuration_sha256, value['pid'], self._market_parser_count)
        return value

    def _validate_inputs(self, deadline):
        for name, expected in self.config.artifacts:
            self._verify_file(self.config.installation / name, expected, 256 * 1024 * 1024, deadline)
        self._verify_file(self.config.configuration, self.config.configuration_sha256, 256 * 1024, deadline)
        _require(_library_files(self.config.installation, clock=self._clock, deadline=deadline)
                 <= {name for name, unused in self.config.artifacts})
        _inspect(self.config.control_root, directory=True)
        self._directory.mkdir()

    def _command(self):
        # 保存本代真正交给Native的原配置，供正常/故障接续按ready中的SHA核对。
        # 库存准备器已在该位置生成物化配置时复用原件，禁止再写回部署模板。
        raw = _read(self.config.configuration, 256 * 1024)
        _require(hashlib.sha256(raw).hexdigest() == self.config.configuration_sha256)
        self._market_parser_count = sum(item.get('active') is True for item in _json(raw).get('parsers', ()))
        snapshot = self._directory / 'execution.json'
        if snapshot.exists():
            _require(_read(snapshot, 256 * 1024) == raw)
        else:
            with snapshot.open('xb') as stream:
                _require(stream.write(raw) == len(raw))
        return (str(self.config.pythonw), '--config', str(self.config.configuration),
                '--control', str(self._directory), '--control-id', self._control_id,
                '--config-sha256', self.config.configuration_sha256)

    def _receipt(self, name, deadline):
        closed = name == 'closed.json'
        path = self._directory / ('close-prepared.json' if closed else name)
        value = _json(_read(path, 4096, clock=self._clock, deadline=deadline))
        required = {'schema', 'control_id', 'config_sha256', 'pid', 'closed'}
        if closed:
            required |= {'ok', 'recovery_ready', 'error_code'}
        _require(set(value) == required and value['schema'] == ('guanheng.execution.close-prepared.v1' if closed
                 else 'guanheng.execution.ready.v1') and value['control_id'] == self._control_id
                 and value['config_sha256'] == self.config.configuration_sha256
                 and type(value['pid']) is int and value['pid'] > 0 and value['closed'] is closed)
        if closed:
            _require(value['ok'] is True and value['recovery_ready'] is (self.config.recovery_mode is not None)
                     and value['error_code'] is None)
        return value

    def _confirm_closed(self, deadline):
        """子进程退出及原监督者回收后发布证明；沿原停止截止，不触碰金融文件。"""
        def check():
            with self._condition:
                end = min(deadline, self._stop_deadline)
            self._check(end)
            return end
        def step(operation):
            result = operation(check())
            check()
            return result
        check()
        _require(self._exit_code == 0 and self._reaped and all(self._eof)
                 and not self._forced and self._host_handle is None)
        value = step(lambda end: self._receipt('closed.json', end))
        _require(value['pid'] == self._host_pid)
        value.update(schema='guanheng.execution.closed.v2', exit_code=0, resources_closed=True)
        marker_source = marker_target = None
        if self.config.recovery_mode is not None:
            raw = step(lambda end: _read(self.config.configuration, 256 * 1024, clock=self._clock, deadline=end))
            _require(hashlib.sha256(raw).hexdigest() == self.config.configuration_sha256)
            output = Path(_json(raw)['output_directory'])
            _require(output.is_absolute());step(lambda end: _inspect(output, directory=True))
            marker_source, marker_target = output / '.cta-clean.prepared.json', output / '.cta-clean.json'
            proof = _json(step(lambda end: _read(marker_source, 256 * 1024, clock=self._clock, deadline=end)))
            _require(proof['schema'] == 'guanheng.cta-clean.v2' and proof['closed'] is True
                     and proof['control_id'] == self._control_id and proof['pid'] == self._host_pid
                     and proof['closed_config_sha256'] == self.config.configuration_sha256
                     and proof['closed_receipt'] == str(self._directory / 'closed.json'))
            _require(not step(lambda end: marker_target.exists()))
        step(lambda end: _inspect(self._directory, directory=True))
        target, temporary = self._directory / 'closed.json', self._directory / 'closed.pending'
        _require(not step(lambda end: target.exists()))
        body = json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8')
        check()
        with temporary.open('xb') as stream:
            check()
            _require(step(lambda end: stream.write(body)) == len(body))
            step(lambda end: stream.flush())
            step(lambda end: os.fsync(stream.fileno()))
        check()
        step(lambda end: _inspect(temporary))
        def commit(source, destination):
            self._retry_sharing(lambda end: step(lambda active: os.rename(source, destination)), deadline)
            # I/O晚返回影响停止调用的及时性；已经成立的正常退出/回收事实保持真实。
            # 完整证明一旦可见即允许后续核查，避免读者已消费后再撤回。
            check()
        if marker_source is not None:
            commit(marker_source, marker_target)
        commit(temporary, target)

    def _run(self, startup_deadline):
        super()._run(startup_deadline)
        if not self._graceful or self._error is not None:
            return
        try:
            self._confirm_closed(self._stop_deadline)
        except BaseException:
            self._graceful = False
            self._failure('close_confirmation')


@dataclass(frozen=True)
class PythonExecutionProcessConfig:
    """固定入口使用当前安装解释器；native仍为原生配置的唯一owner。"""
    native: ExecutionProcessConfig  # 本代原生配置与安装绑定；Python装配继续沿同一Native owner。
    pythonw: Path  # 固定安装解释器入口绝对路径；实际CLI/无窗口入口随发行身份核验。
    python_files: tuple[tuple[str, str], ...]  # 解释器及受管源码绝对路径与SHA256；由本次安装清点生成。
    site_root: Path  # 上述受管Python包的唯一site-packages绝对目录；子进程隔离加载。
    packages: tuple[str, ...] = _RETAINED_PYTHON_PACKAGES  # 已绑定的策略与运行依赖包名集合，默认唯一保留策略。

    def __getattr__(self, name):
        return getattr(self.native, name)

    @classmethod
    def load(cls, installation, configuration, control_root):
        import importlib.metadata
        import sys
        native = ExecutionProcessConfig.load(installation, configuration, control_root)
        # 显式恢复仍由原生P21准入；R12数量决策只沿原用户KV及同源Python身份恢复。
        files = {Path(sys.executable).absolute(), Path(sys._base_executable).absolute()}
        base = Path(sys._base_executable).parent
        files.update(base / name for name in ('python3.dll', f'python{sys.version_info.major}{sys.version_info.minor}.dll'))
        files.add(Path(sys.prefix) / 'pyvenv.cfg')
        site = Path(__file__).absolute().parent.parent
        packages = _python_packages(_json(_read(native.configuration, 256 * 1024)))
        for package in packages:
            name = PACKAGE_DISTRIBUTIONS[package]
            distribution = importlib.metadata.distribution(name)
            _require(distribution.metadata['Name'].lower().replace('_', '-') == name)
            for item in distribution.files or ():
                relative = str(item).replace('\\', '/')
                if (relative.startswith(package + '/') and relative.endswith(('.py', '.json'))
                        or relative.endswith('.dist-info/METADATA')
                        or name == 'tzdata' and relative == 'tzdata/zoneinfo/Asia/Shanghai'):
                    files.add(Path(distribution.locate_file(item)).absolute())
            _require(Path(distribution.locate_file(package + '/__init__.py')).absolute() == site / package / '__init__.py')
        _require(Path(__file__).absolute() in files and 1 <= len(files) <= 512)
        identities, total = [], 0
        for path in sorted(files):
            raw = _python_bytes(path)
            total += len(raw)
            _require(total <= 64 * 1024 * 1024)
            identities.append((str(path), hashlib.sha256(raw).hexdigest()))
        _python_inventory(site, dict(identities), packages=packages)
        return cls(native, Path(sys.executable).absolute(), tuple(identities), site, packages)


def _quote_input_state(observation, control_id, configuration_sha256, pid, active_count):
    """由同一代CTA的SPI连接/关闭事实推导行情接入状态，保留进程ready语义。"""
    if (observation.get('schema') != 'guanheng.execution.cta-observation.v1'
            or observation.get('control_id') != control_id
            or observation.get('config_sha256') != configuration_sha256
            or observation.get('pid') != pid or observation.get('closed') is not False):
        return 'unknown'
    counts = tuple(observation.get(key) for key in ('parser_connects', 'parser_closes', 'parser_quotes'))
    if any(type(value) is not int or value < 0 for value in counts):
        return 'unknown'
    connects, closes, quotes = counts
    if connects - closes < active_count:
        return 'disconnected' if closes else 'waiting'
    return 'receiving' if quotes else 'waiting'


class ManagedPythonExecutionProcess(ManagedExecutionProcess):
    """同一原Job和收据；子进程只进入安装中的固定业务模块。"""
    def status(self):
        """交接本代既有投影的位置与原ready身份；读取和展示由独立消费者负责。"""
        value = super().status()
        if self.config is not None and value['pid'] is not None:
            value['business_observation'] = {
                'schema': 'guanheng.execution-observation-reference.v1',
                'control_id': self._control_id,
                'config_sha256': self.config.configuration_sha256,
                'pid': value['pid'],
                'path': str(self._directory / 'strategies.json'),
                'ready_path': str(self._directory / 'ready.json'),
            }
        return value

    def _validate_inputs(self, deadline):
        _require(type(self.config) is PythonExecutionProcessConfig)
        super()._validate_inputs(deadline)
        for name, expected in self.config.python_files:
            _require(hashlib.sha256(_python_bytes(Path(name), deadline=deadline)).hexdigest() == expected)
        _python_inventory(self.config.site_root, dict(self.config.python_files), packages=self.config.packages)
        raw = json.dumps({'schema': 'guanheng.cta-python-binding.v1',
                          'python': str(self.config.pythonw), 'site_root': str(self.config.site_root),
                          'files': self.config.python_files},
                         sort_keys=True, separators=(',', ':')).encode('ascii')
        _require(len(raw) <= 256 * 1024)
        with (self._directory / 'python-binding.json').open('xb') as stream:
            stream.write(raw)
        self._python_binding_sha = hashlib.sha256(raw).hexdigest()
        self._python_deadline = deadline

    def _command(self):
        # -S跳过.pth/sitecustomize；固定bootstrap只加入已绑定site，不执行安装启动脚本。
        bootstrap = "import runpy,sys;sys.path.append(sys.argv.pop(1));runpy.run_module('guanheng_wt_runtime.execution_configured',run_name='__main__')"
        return (str(self.config.pythonw), '-I', '-S', '-B', '-X', 'pycache_prefix=' + str(self._directory / 'python-cache'),
                '-c', bootstrap, str(self.config.site_root),
                *super()._command()[1:], '--installation', str(self.config.installation),
                '--deadline', str(self._python_deadline), '--python-binding-sha256', self._python_binding_sha)


def _python_inventory(site, identities, *, packages=_RETAINED_PYTHON_PACKAGES):
    """固定纯Python发行的完整源码集合；额外包目录不能遮蔽已绑定模块。"""
    seen, count = set(), 0
    _require(packages in (RETAINED_PACKAGES, SHARED_PACKAGES, SOURCE_HANDOFF_PACKAGES))
    for package in packages:
        # 每个owner同时绑定真实发行METADATA；子进程不能通过省略元数据缩小原集合。
        prefix = PACKAGE_DISTRIBUTIONS[package].replace('-', '_') + '-'
        metadata = [Path(name) for name in identities
                    if Path(name).parent.parent == site and Path(name).name == 'METADATA'
                    and Path(name).parent.name.startswith(prefix)
                    and Path(name).parent.name.endswith('.dist-info')]
        _require(len(metadata) == 1)
        pending = [site / package]
        while pending:
            directory = pending.pop();_inspect(directory, directory=True)
            for path in directory.iterdir():
                count += 1;_require(count <= 8192)
                if path.is_dir():
                    _inspect(path, directory=True)
                    if path.name != '__pycache__':pending.append(path)
                else:
                    _inspect(path)
                    _require(path.suffix.lower() != '.pyd')
                    if path.suffix in ('.py', '.json'):seen.add(str(path))
    expected = {name for name in identities if Path(name).suffix in ('.py', '.json')
                and any(Path(name).is_relative_to(site / package) for package in packages)}
    _require(seen == expected)


def _python_bytes(path, *, deadline=None):
    """安装源码允许空__init__.py；仍核原句柄、有限大小和读前后身份。"""
    import os
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('execution Python binding deadline')
    before = _inspect(path)
    _require(0 <= before.st_size <= 32 * 1024 * 1024)
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        _require(_identity(opened) == _identity(before))
        raw = stream.read(32 * 1024 * 1024 + 1)
        _require(len(raw) == opened.st_size and _identity(os.fstat(stream.fileno())) == _identity(opened))
    _require(_identity(_inspect(path)) == _identity(opened))
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('execution Python binding deadline')
    return raw


def write_installation_manifest(installation):
    """显式打包步骤：对实际安装文件登记摘要，不授予实盘运行资格。"""
    installation = Path(installation)
    _require(installation.is_absolute())
    _inspect(installation, directory=True)
    files = {}
    for path in sorted(installation.rglob('*')):
        if path.is_dir():
            _inspect(path, directory=True)
        elif path.name != 'execution-install.json':
            _inspect(path)
            _require(path.stat().st_size <= 256 * 1024 * 1024)
            files[path.relative_to(installation).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    _require('app/GuanhengCtaHost.exe' in files and 1 <= len(files) <= 512)
    value = {'schema': 'guanheng.execution-install.v1', 'files': files}
    with (installation / 'execution-install.json').open('xb') as stream:
        stream.write(json.dumps(value, separators=(',', ':'), sort_keys=True).encode())



def create_process(descriptor_path, expected_sha256):
    """由绑定部署构造原执行owner；不启动进程、不写账户或控制状态。

    返回start(绝对monotonic截止)/status/request_close/close(秒)协议。
    读取、身份和安装错误沿原ValueError/OSError传播，运行故障由owner记录。
    """
    path = Path(descriptor_path)
    _require(path.is_absolute())
    raw = _read(path, 65536)
    _require(hashlib.sha256(raw).hexdigest() == _sha(expected_sha256))
    value = _json(raw)
    required = {
        'schema', 'installation', 'configuration', 'configuration_sha256',
        'control_root', 'python_strategies'}
    _require(type(value) is dict and required <= set(value) <= required | {'initial_inventory'}
        and value['schema'] == 'guanheng.execution-deployment.v1'
        and type(value['python_strategies']) is bool)
    for key in ('installation', 'configuration', 'control_root'):
        _require(type(value[key]) is str and 1 <= len(value[key]) <= 1024
                 and chr(0) not in value[key] and Path(value[key]).is_absolute()
                 and '..' not in Path(value[key]).parts)
    config_type = PythonExecutionProcessConfig if value['python_strategies'] else ExecutionProcessConfig
    process_type = ManagedPythonExecutionProcess if value['python_strategies'] else ManagedExecutionProcess
    config = config_type.load(value['installation'], value['configuration'], value['control_root'])
    _require(config.configuration_sha256 == _sha(value['configuration_sha256']))
    if 'initial_inventory' in value:
        from .initial_inventory_execution import InitialInventoryStartupConfig, InitialInventoryExecutionProcess
        _require(value['python_strategies'])
        return InitialInventoryExecutionProcess(config, InitialInventoryStartupConfig.from_dict(value['initial_inventory']))
    return process_type(config)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='观衡受管CTA执行进程')
    parser.add_argument('--installation', type=Path, required=True)
    parser.add_argument('--make-manifest', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--control-root', type=Path)
    parser.add_argument('--seconds', type=float, default=60.)
    parser.add_argument('--python-strategies', action='store_true', help='固定configured业务Python入口')
    args = parser.parse_args()
    if args.make_manifest:
        write_installation_manifest(args.installation)
        return
    _require(args.config is not None and args.control_root is not None and 0 < args.seconds <= 86400)
    config_type = PythonExecutionProcessConfig if args.python_strategies else ExecutionProcessConfig
    process_type = ManagedPythonExecutionProcess if args.python_strategies else ManagedExecutionProcess
    config = config_type.load(args.installation, args.config, args.control_root)
    process = process_type(config)
    ready = False
    try:
        ready = process.start(time.monotonic() + config.startup_seconds)
        _require(ready)
        until = time.monotonic() + args.seconds
        while time.monotonic() < until and process.status()['ready']:
            time.sleep(min(.1, max(0., until-time.monotonic())))
    finally:
        closed = process.close(config.stop_seconds)
    result = process.status()
    print(json.dumps(result, ensure_ascii=False))
    if not ready or not closed or result['forced']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
