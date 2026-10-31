"""Explicit precompiled test inputs, shared by the fixture and HTTP test owners."""
from pathlib import Path
import hashlib
import json


def arguments(parser):
    parser.add_argument('--probe', type=Path)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--cwd', type=Path)
    parser.add_argument('--work', type=Path)


def resolve(args, *, root=None):
    build = args.build.resolve() if args.build else None
    explicit = args.probe is not None or args.library is not None
    if explicit and (args.probe is None or args.library is None or args.cwd is None or args.work is None):
        raise ValueError('explicit tests require --probe, --library, --cwd and --work')
    if not explicit and build is None:
        raise ValueError('provide explicit test inputs or legacy --build')
    probe = (args.probe if explicit else build / 'probe.exe').resolve(strict=True)
    library = (args.library if explicit else build / 'traders/TraderQMTReadOnly.dll').resolve(strict=True)
    cwd = (args.cwd if explicit else build).resolve(strict=True)
    # The original Adapter opens CWD/traders by module name. The direct ABI
    # library and that module must be the same file, including gated tests.
    if not (cwd / 'traders/TraderQMTReadOnly.dll').samefile(library):
        raise ValueError('Adapter CWD plugin differs from explicit library')
    outputs = (args.work if explicit else build).resolve()
    outputs.mkdir(parents=True, exist_ok=True)
    identity = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (probe, library)}
    if not explicit:
        manifest = json.loads((build / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('compile_exit') != 0:
            raise ValueError('legacy build did not compile')
        for relative, digest in manifest['artifacts'].items():
            if hashlib.sha256((build / relative).read_bytes()).hexdigest() != digest:
                raise ValueError('legacy artifact changed')
        if root is not None:
            for relative, digest in manifest['self_owned'].items():
                if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                    raise ValueError('legacy source changed')
    return probe, library, cwd, outputs, identity


def verify(identity):
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest for path, digest in identity.items()):
        raise ValueError('test binary changed during execution')
