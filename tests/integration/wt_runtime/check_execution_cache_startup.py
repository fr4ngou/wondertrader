"""运行真实 CTA 入口，验证旧缓存先于柜台与恢复准入被拒绝。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    exe, root = args.exe.resolve(strict=True), args.output.resolve()
    root.mkdir()
    template_cache = root / "old-generation"
    template_cache.mkdir()
    template_sentinel = template_cache / "owner.lock"
    template_sentinel.write_bytes(b"old generation")
    for name, expected in (
        ("old-directory", "market_cache"),
        ("old-file", "market_cache"),
        ("unused", "configuration"),
    ):
        control = root / name
        control.mkdir()
        cache = control / "daily-cache"
        if name == "old-directory":
            cache.mkdir()
        elif name == "old-file":
            cache.write_bytes(b"existing file")
        cfg = {
            "schema_version": "guanheng.cta-execution.v1",
            "data": {"store": {"module": "GuanhengRealtimeReader",
                               "daily": {"publication": {"cache_root": str(template_cache)}}}},
            "recovery": {"mode": "resume_reconciled"},
        }
        raw = json.dumps(cfg).encode()
        config = control / "execution.json"
        config.write_bytes(raw)
        run = subprocess.run([str(exe), "--config", str(config), "--control", str(control),
                              "--control-id", str(uuid4()), "--config-sha256", hashlib.sha256(raw).hexdigest()],
                             cwd=exe.parent, capture_output=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW)
        assert run.returncode != 0
        failure = json.loads((control / "failure.json").read_bytes())
        assert failure["stage"] == expected, (name, failure["stage"])
        assert not any((control / file).exists() for file in ("ready.json", "reconciled.json", "lifecycle-started.json"))
        assert config.read_bytes() == raw
    assert template_sentinel.read_bytes() == b"old generation"
    assert (root / "old-directory" / "daily-cache").is_dir()
    assert (root / "old-file" / "daily-cache").read_bytes() == b"existing file"
    assert not (root / "unused" / "daily-cache").exists()
    print("CTA cache startup regression passed")


if __name__ == "__main__":
    main()
