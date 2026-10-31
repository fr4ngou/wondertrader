"""Host-only bounded source pairing, shared by offline audit and launch."""
import hashlib
from pathlib import Path


def source_manifest(package, *, reader=None, check_deadline=None):
    """Hash at most 1000 Python files <=2 MiB; optional guard preserves one caller D."""
    if check_deadline is not None and not callable(check_deadline):
        raise ValueError("source verification requires a callable deadline guard")
    check = (lambda: None) if check_deadline is None else check_deadline
    package = Path(package)
    if not package.is_absolute():
        raise ValueError("explicit source package is required")
    check()
    initialized = (package / "__init__.py").is_file()
    check()
    if not initialized:
        raise ValueError("explicit source package is required")
    values = {}
    root = package.resolve()
    check()
    paths = iter(package.rglob("*.py"))
    while True:
        check()
        try:
            path = next(paths)
        except StopIteration:
            check()
            break
        check()
        if len(values) >= 1000:
            raise ValueError("source package exceeds its 1000 source-file budget")
        resolved = path.resolve()
        check()
        if not resolved.is_relative_to(root):
            raise ValueError("source escapes its package or byte budget")
        if reader is None:
            size = path.stat().st_size
            check()
            if size > 2097152:
                raise ValueError("source escapes its package or byte budget")
            raw = path.read_bytes()
        else:
            raw = reader(path, 2097152)
        check()
        values[path.relative_to(package).as_posix()] = hashlib.sha256(raw).hexdigest()
    if not values:
        raise ValueError("source package exceeds its 1000 source-file budget")
    return dict(sorted(values.items()))
