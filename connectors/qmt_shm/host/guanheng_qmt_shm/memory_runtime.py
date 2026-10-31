"""终端外冻结Python3.6.8依赖；生成的私有加载器只消费内存源码。

Adapted from the owner-authorized frozen broker_host/memory_runtime.py.
Original private source notices and CPython source/license identities are retained.
No old-platform package is imported or executed.

Only this generator reads source files. The emitted private importer consumes
literal source in a strategy-private module table. Real builtin modules use
the interpreter cache; existing shared module entries remain unchanged.
Business modules are included verbatim; capability bridges belong here.
"""
import ast
import hashlib
from pathlib import Path


# Pure CPython sources audited by the closed-import cold regression. Optional
# native accelerators are deliberately absent and use their pure-Python paths.
STDLIB = frozenset(('__future__', '_bootlocale', '_collections_abc', '_compat_pickle',
    '_dummy_thread', '_pydecimal', '_strptime', '_threading_local', '_weakrefset',
    'abc', 'base64', 'inspect', 'bisect', 'calendar', 'codecs', 'collections', 'collections.abc',
    'contextlib', 'copy', 'copyreg', 'datetime', 'decimal', 'encodings', 'encodings.aliases', 'enum', 'functools',
    'genericpath', 'hashlib', 'heapq', 'hmac', 'io', 'json', 'json.decoder', 'json.encoder',
    'json.scanner', 'keyword', 'linecache', 'locale',
    'ntpath', 'numbers', 'operator', 'os', 'queue', 'random', 're', 'reprlib',
    'sre_compile', 'sre_constants', 'sre_parse', 'stat', 'string', 'struct',
    'textwrap', 'threading', 'token', 'tokenize', 'traceback', 'types', 'uuid',
    'warnings', 'weakref'))
# _warnings owns process-global filters; CPython warnings uses its private fallback.
BUILTINS = frozenset(('sys', 'builtins', '_thread', 'time', 'mmap', 'math', 'binascii',
    'nt', '_datetime', '_collections', 'itertools', '_functools', '_operator',
    '_weakref', '_heapq', '_bisect', '_sre', '_json', '_random', '_codecs', '_locale',
    '_string', '_io', 'atexit', 'gc', 'errno', '_imp', '_stat',
    '_struct', '_sha256', '_sha1', '_sha512', '_md5', '_blake2', '_sha3', 'array'))
HOST_ONLY = frozenset(('guanheng_qmt_shm_agent.pipe', 'guanheng_qmt_shm_agent.shm',
    'guanheng_qmt_shm_agent.windows_security', 'guanheng_qmt_shm_agent.builtin_shm_native'))


BRIDGES = {
    # 保持原生datetime的精确类型身份；本仓协议日期由固定字段解析器拥有。
    # 原生strptime的隐式全局模块导入不属于受限入口的运行依赖。
    'datetime': '''from _datetime import *
''',
    # UUID4 and pure stdlib need OS entropy, PID and in-memory environment.
    # No filesystem/process/network operations are exposed by this facade.
    'os': '''from nt import urandom, getpid, environ
name = 'nt'
linesep = '\\r\\n'
import ntpath as path
''',
}


# CPython's C pattern.sub imports canonical "re" for string replacements.
# Calling the original PSF template compiler directly and passing its callable
# to C preserves replacement semantics without publishing a shared module alias.
REGEX_BRIDGE = '''
_memory_original_compile = _compile
class _MemoryPattern:
    def __init__(self, native): self._native = native
    def __getattr__(self, name): return getattr(self._native, name)
    def _replacement(self, value):
        if callable(value): return value
        expanded = _subx(self._native, value)
        return expanded if callable(expanded) else lambda match: expanded
    def sub(self, repl, string, count=0): return self._native.sub(self._replacement(repl), string, count)
    def subn(self, repl, string, count=0): return self._native.subn(self._replacement(repl), string, count)
def _compile(pattern, flags):
    if isinstance(pattern, _MemoryPattern):
        if flags: raise ValueError('cannot process flags argument with a compiled pattern')
        return pattern
    return _MemoryPattern(_memory_original_compile(pattern, flags))
'''


LOADER = '''import sys as _memory_sys
import _thread as _memory_thread
_memory_import = __import__
_memory_module_type = type(_memory_sys)
_memory_modules = {}
_memory_lock = _memory_thread.RLock()
_memory_original_builtins = dict(vars(_memory_import('builtins')))
_memory_forbidden_attempts = 0
def _memory_forbidden(*args, **kwargs):
    global _memory_forbidden_attempts
    _memory_forbidden_attempts += 1
    raise RuntimeError('file/process/network capability is unavailable in the memory Agent')
class _MemoryNoFile:
    def __new__(cls, *args, **kwargs): return _memory_forbidden()
def _memory_load(name):
    with _memory_lock:
        if name in _memory_modules:
            return _memory_modules[name]
        if name == 'os.path':
            return _memory_load('os').path
        if name in _memory_builtin_names:
            module = _memory_import(name)
            if module.__loader__ is not _memory_sys.__loader__:
                raise ImportError('memory Agent requires a real interpreter builtin: ' + name)
            if name in ('builtins', 'nt', '_io'):
                facade = _memory_module_type(name)
                if name == 'nt':
                    for key in ('urandom', 'getpid'):
                        setattr(facade, key, getattr(module, key))
                    facade.environ = dict(module.environ)
                else:
                    facade.__dict__.update(vars(module))
                    for key in ('open', 'open_code', 'FileIO', '_WindowsConsoleIO'):
                        if hasattr(facade, key):
                            setattr(facade, key, _MemoryNoFile if key in ('FileIO', '_WindowsConsoleIO') else _memory_forbidden)
                    if name == 'builtins': facade.__import__ = _memory_dispatch
                module = facade
            _memory_modules[name] = module
            return module
        if name not in _memory_sources:
            raise ImportError('module is outside the frozen memory Agent: ' + name)
        source, package = _memory_sources[name]
        expected = _memory_source_hashes.get(name)
        if _memory_import('_sha256').sha256(source.encode('utf-8')).hexdigest() != expected:
            raise ImportError('memory Agent source identity differs: ' + name)
        # Initialize the parent package first, matching Python import semantics.
        # RLock and the private cache preserve ordinary package re-exports.
        parent = name.rpartition('.')[0]
        if parent and parent not in _memory_modules:
            _memory_load(parent)
            if name in _memory_modules:
                return _memory_modules[name]
        module = _memory_module_type(name)
        module.__package__ = name if package else name.rpartition('.')[0]
        module.__file__ = '<qmt-memory/' + name + '>'
        if package: module.__path__ = []
        builtins = dict(_memory_original_builtins)
        builtins.update(__import__=_memory_dispatch, open=_memory_forbidden)
        module.__dict__['__builtins__'] = builtins
        _memory_modules[name] = module
        try:
            exec(compile(source, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            del _memory_modules[name]
            raise
        parent, _, child = name.rpartition('.')
        if parent:
            setattr(_memory_load(parent), child, module)
        return module
def _memory_dispatch(name, globals=None, locals=None, fromlist=(), level=0):
    if level:
        package = (globals or {}).get('__package__', '')
        pieces = package.split('.')
        if not package or level > len(pieces): raise ImportError('invalid memory relative import')
        name = '.'.join(pieces[:len(pieces)-level+1]) + ('.' + name if name else '')
    module = _memory_load(name)
    if fromlist:
        for item in fromlist:
            child = name + '.' + item
            if item != '*' and not hasattr(module, item) and child in _memory_sources:
                _memory_load(child)
        return module
    return _memory_load(name.split('.')[0])
'''


def freeze_sources(agent_root, stdlib_root, roots=('guanheng_qmt_shm_agent.restricted',), *, reader=None):
    """Resolve only explicit pure sources, preserving exact Agent source text.

    Both roots are external trusted deployment paths. Unknown/dynamic imports
    remain denied; selected host-only transport implementations are excluded.
    Returned hashes qualify source identity, never live SDK or account access.
    """
    agent_root, stdlib_root = Path(agent_root), Path(stdlib_root)
    if reader is None:
        agent_root, stdlib_root = agent_root.resolve(strict=True), stdlib_root.resolve(strict=True)
    read = _bounded_bytes if reader is None else reader
    sources, pending = {}, list(roots)
    required_agent = set(roots)
    while pending:
        name = pending.pop()
        if name in sources or name in BUILTINS or name in HOST_ONLY:
            continue
        if not name.startswith('guanheng_qmt_shm_agent') and name not in STDLIB:
            continue
        if name == 'encodings':
            # Locale needs only aliases and normalization. Extract the original
            # function verbatim; importing encodings/__init__ would register a
            # new process-global codec searcher for unrelated QMT strategies.
            original = read(stdlib_root/'encodings/__init__.py', 2097152).decode('utf-8-sig')
            function = next(n for n in ast.parse(original).body if isinstance(n, ast.FunctionDef)
                            and n.name == 'normalize_encoding')
            text, package = 'from . import aliases\n'+ast.get_source_segment(original, function)+'\n', True
        elif name == 'inspect':
            # 账户只读转换只用getattr_static。保留CPython原函数及其完整私有辅助，
            # 避免为静态属性检查引入磁盘源码/动态DLL加载器。
            original = read(stdlib_root/'inspect.py', 2097152).decode('utf-8-sig')
            tree = ast.parse(original)
            wanted = {'_static_getmro', '_check_instance', '_check_class',
                      '_is_type', '_shadowed_dict', 'getattr_static'}
            functions = [node for node in tree.body
                         if isinstance(node, ast.FunctionDef) and node.name in wanted]
            if {node.name for node in functions} != wanted:
                raise ValueError('qualified CPython static attribute helpers are incomplete')
            text = 'import types\n_sentinel = object()\n' + '\n\n'.join(
                ast.get_source_segment(original, node) for node in functions) + '\n'
            package = False
        elif name in BRIDGES:
            text, package = BRIDGES[name], False
        else:
            root = agent_root.parent if name.startswith('guanheng_qmt_shm_agent') else stdlib_root
            path = root.joinpath(*name.split('.'))
            package = path.is_dir()
            path = path / '__init__.py' if package else path.with_suffix('.py')
            if not path.is_file():
                if name in required_agent:
                    raise ValueError('required Agent source is missing: ' + name)
                continue  # An import-from attribute is not necessarily a module.
            text = read(path, 2097152).decode('utf-8-sig')
        if name == 'threading':
            # 私有模块借用加载它的宿主线程；退出哨兵由平台原Thread拥有。
            # 复用CPython的外部线程记录，私有新建Thread仍保留原生join逻辑。
            tree = ast.parse(text)
            def binds_main(target):
                if isinstance(target, ast.Name):
                    return target.id == '_main_thread'
                if isinstance(target, (ast.Tuple, ast.List)):
                    return any(binds_main(item) for item in target.elts)
                if isinstance(target, ast.Starred):
                    return binds_main(target.value)
                return False
            mains = [node for node in tree.body
                     if ((isinstance(node, ast.Assign)
                          and any(binds_main(target) for target in node.targets))
                         or (isinstance(node, (ast.AnnAssign, ast.AugAssign))
                             and binds_main(node.target)))]
            if (len(mains) != 1 or not isinstance(mains[0], ast.Assign)
                    or len(mains[0].targets) != 1
                    or not isinstance(mains[0].targets[0], ast.Name)
                    or not isinstance(mains[0].value, ast.Call)
                    or not isinstance(mains[0].value.func, ast.Name)
                    or mains[0].value.func.id != '_MainThread'
                    or mains[0].value.args or mains[0].value.keywords):
                raise ValueError('qualified CPython borrowed-thread initialization differs')
            original_main = ast.get_source_segment(text, mains[0])
            if text.count(original_main) != 1:
                raise ValueError('qualified CPython borrowed-thread source is ambiguous')
            text = text.replace(original_main, '_main_thread = _DummyThread()', 1)
        if name == 're':
            text += REGEX_BRIDGE
        if len(sources) >= 192 or sum(len(v[0].encode('utf-8')) for v in sources.values()) + len(text.encode('utf-8')) > 4194304:
            raise ValueError('memory source closure exceeds its explicit budget')
        sources[name] = (text, package)
        parent = name.rpartition('.')[0]
        if parent:
            pending.append(parent)
        package_name = name if package else parent
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                pending.extend(alias.name for alias in node.names)
                required_agent.update(alias.name for alias in node.names
                                      if alias.name.startswith('guanheng_qmt_shm_agent'))
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    pieces = package_name.split('.')
                    prefix = '.'.join(pieces[:len(pieces)-node.level+1]) + ('.' + prefix if prefix else '')
                if prefix:
                    pending.append(prefix)
                    if prefix.startswith('guanheng_qmt_shm_agent'):
                        required_agent.add(prefix)
                pending.extend(prefix + '.' + alias.name for alias in node.names if alias.name != '*')
    hashes = {name: hashlib.sha256(text.encode()).hexdigest() for name, (text, _) in sources.items()}
    return sources, hashes


def render_runtime(agent_root, stdlib_root, builtin_names, *, roots=('guanheng_qmt_shm_agent.restricted',), reader=None):
    """Emit a strategy-private in-memory loader, with no platform side effects."""
    sources, hashes = freeze_sources(agent_root, stdlib_root, roots, reader=reader)
    available = frozenset(builtin_names) & BUILTINS
    if not {'sys', 'builtins', '_thread', 'mmap', '_datetime', '_sha256', 'nt'} <= available:
        raise ValueError('SDK builtin capability set cannot contain the full memory Agent')
    # QMT rewrites editor text using GBK before Run. ASCII literal escapes keep
    # every original source code point intact through that platform save.
    target_check = ('# -*- coding: utf-8 -*-\nimport sys as _memory_target_sys\n'
        + 'if _memory_target_sys.version_info[:3] != (3, 6, 8):\n'
        + '    raise RuntimeError(\"memory entry requires its qualified CPython 3.6.8\")\n'
        + 'if tuple(sorted(_memory_target_sys.builtin_module_names)) != ' + repr(tuple(sorted(builtin_names))) + ':\n'
        + '    raise RuntimeError(\"memory entry builtin capability identity differs\")\n')
    return (target_check + '_memory_sources = ' + ascii(sources)
        + '\n_memory_source_hashes = ' + ascii(hashes)
        + '\n_memory_builtin_names = ' + repr(tuple(sorted(available))) + '\n' + LOADER), hashes


CPYTHON_LICENSE_SHA256 = 'b9a6d9320b8f2693e8d41e496ce56caadacaddcca9be2a64a61749278f425cf2'
SDK_FIELDS = frozenset(('schema_version', 'python_version', 'python_executable',
    'python_sha256', 'python_dll_sha256', 'builtin_names', 'stdlib_root'))


def _bounded_bytes(path, maximum):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError('memory-runtime input exceeds its byte budget')
    return raw


def prepare_runtime(agent_root, sdk_metadata, license_bytes):
    """冻结原只读入口的完整依赖闭包及离线来源身份。"""
    return _prepare_runtime(agent_root, sdk_metadata, license_bytes,
        ('guanheng_qmt_shm_agent.restricted',))


def prepare_read_service_runtime(agent_root, sdk_metadata, license_bytes):
    """显式常驻只读闭包；原单代/交易入口的roots保持各自身份。"""
    return _prepare_runtime(agent_root, sdk_metadata, license_bytes,
        ('guanheng_qmt_shm_agent.reconnecting_read',))


def prepare_trade_runtime(agent_root, sdk_metadata, license_bytes):
    """冻结交易入口完整闭包；运行期仍只从已核内存源码加载。"""
    return _prepare_runtime(agent_root, sdk_metadata, license_bytes,
        ('guanheng_qmt_shm_agent.trading_agent',))


def _prepare_runtime(agent_root, sdk_metadata, license_bytes, roots, *, reader=None):
    """从受管外部SDK取源码并冻结身份；本函数不启动进程或读取QMT状态。

    SDK元数据由构建/维护阶段在实际目标解释器独立采集，包含完整内建模块列表。
    此处核磁盘二进制、依赖源码及许可；生成入口在运行时再次核版本和内建列表。
    元数据与源码核验授离线物料身份，真实券商模块许可另行实测。
    """
    # 显式严格入口的正文与来源身份消费同一份首读快照；旧调用保持原读取合同。
    snapshots = {}
    def read(path, maximum):
        if reader is None:
            return _bounded_bytes(path, maximum)
        path = Path(path)
        if path not in snapshots:
            snapshots[path] = reader(path, maximum)
        return snapshots[path]
    if (type(sdk_metadata) is not dict or set(sdk_metadata) != SDK_FIELDS
            or sdk_metadata['schema_version'] != 'qmt.memory-sdk.v1'
            or sdk_metadata['python_version'] != [3, 6, 8]
            or any(type(x) is not int for x in sdk_metadata['python_version'])):
        raise ValueError('qualified SDK metadata differs')
    names = sdk_metadata['builtin_names']
    if (type(names) is not list or not 1 <= len(names) <= 256
            or any(type(name) is not str or not name.isidentifier() for name in names)
            or len(set(names)) != len(names)):
        raise ValueError('qualified SDK builtin identities differ')
    executable = Path(sdk_metadata['python_executable'])
    stdlib = Path(sdk_metadata['stdlib_root'])
    if (not executable.is_absolute() or not stdlib.is_absolute()
            or executable.name.lower() != 'pythonw.exe'
            or stdlib.resolve(strict=True) != (executable.parent/'Lib').resolve(strict=True)):
        raise ValueError('qualified SDK source origin differs')
    for path, field in ((executable, 'python_sha256'),
                        (executable.parent/'python36.dll', 'python_dll_sha256')):
        expected = sdk_metadata[field]
        if (type(expected) is not str or len(expected) != 64
                or any(ch not in '0123456789abcdef' for ch in expected)
                or hashlib.sha256(read(path, 67108864)).hexdigest() != expected):
            raise ValueError('qualified SDK binary changed')
    if type(license_bytes) is not bytes or hashlib.sha256(license_bytes).hexdigest() != CPYTHON_LICENSE_SHA256:
        raise ValueError('qualified CPython license differs')
    source, hashes = render_runtime(agent_root, stdlib, names, roots=roots,
        **({'reader': read} if reader is not None else {}))
    generator_sha = hashlib.sha256(read(__file__, 2097152)).hexdigest()
    raw_sources = {}
    for name in sorted(hashes):
        if name in BRIDGES:
            raw_sources[name] = {'kind': 'capability-bridge', 'generator_sha256': generator_sha}
            continue
        base = Path(agent_root).parent if name.startswith('guanheng_qmt_shm_agent') else stdlib
        path = base.joinpath(*name.split('.'))
        path = path/'__init__.py' if path.is_dir() else path.with_suffix('.py')
        raw = read(path, 2097152)
        raw_sources[name] = {'kind': 'python-source', 'path': str(path if reader is not None else path.resolve(strict=True)),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    identity = {'schema_version': 'qmt.memory-runtime.v1',
        'sdk': dict(sdk_metadata), 'roots': list(roots),
        'generator_sha256': generator_sha, 'source_files': raw_sources,
        'sources': hashes, 'sources_sha256': hashlib.sha256(
            repr(tuple(sorted(hashes.items()))).encode('ascii')).hexdigest(),
        'runtime_sha256': hashlib.sha256(source.encode('ascii')).hexdigest(),
        'stdlib_license': {'file': 'CPYTHON-LICENSE.txt', 'sha256': CPYTHON_LICENSE_SHA256}}
    return source, identity
