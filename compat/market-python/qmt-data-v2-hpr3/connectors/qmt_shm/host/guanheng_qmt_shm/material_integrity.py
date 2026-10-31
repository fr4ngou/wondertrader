"""Host-only bounded source pairing, shared by offline audit and launch.

Only source bytes are read. This supplementary pairing never imports installed
code, touches financial databases or grants QMT/financial readiness.
"""
import hashlib
from pathlib import Path


def source_manifest(package, *, reader=None):
    """Hash at most 1000 Python files, each <=2 MiB, below one absolute package.

    Include all subpackages; ignore caches and non-source runtime data. Existing
    maintenance audit remains the owner of the complete installed artifact.
    """
    package = Path(package)
    if not package.is_absolute() or not (package / "__init__.py").is_file():
        raise ValueError("explicit source package is required")
    values, root = {}, package.resolve()
    for path in package.rglob("*.py"):
        if len(values) >= 1000:
            raise ValueError("source package exceeds its 1000 source-file budget")
        if not path.resolve().is_relative_to(root):
            raise ValueError("source escapes its package or byte budget")
        if reader is None:
            if path.stat().st_size > 2097152:
                raise ValueError("source escapes its package or byte budget")
            raw = path.read_bytes()
        else:
            raw = reader(path, 2097152)
        values[path.relative_to(package).as_posix()] = hashlib.sha256(raw).hexdigest()
    if not values:
        raise ValueError("source package exceeds its 1000 source-file budget")
    return dict(sorted(values.items()))
