"""Project navigation and local integrity checks (Python 3.10+, standard library)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

from project_support.skills import check_skills, migrate, record

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]\n]*\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")


def check(root: Path, *, include_skills: bool = True) -> list[str]:
    root = root.resolve()
    errors = []
    config = json.loads((root / "config/project.json").read_text(encoding="utf-8"))
    # Upstream reference documents can have intentionally sparse-checkout assets.
    # Check the project-maintained document scope declared in the configuration.
    patterns = config["documentation_paths"]
    docs = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})
    paths = [root / "AGENTS.md", root / config["documentation_entry"]] + docs
    graph = {}
    for path in dict.fromkeys(paths):
        if not path.is_file():
            errors.append(f"missing document: {path.relative_to(root)}")
            continue
        graph[path] = []
        try:
            text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8-sig"), flags=re.S)
            for match in LINK.finditer(text):
                raw = match.group(1).strip("<>")
                parts = urlsplit(raw)
                if parts.scheme in {"http", "https", "mailto"} or raw.startswith("#"):
                    continue
                relative = unquote(parts.path)
                if not relative:
                    continue
                if parts.scheme or raw.startswith(("/", "\\")) or "\\" in relative:
                    errors.append(f"{path.relative_to(root)}: non-portable link {raw}")
                    continue
                target = (path.parent / relative).resolve()
                if not target.is_relative_to(root):
                    errors.append(f"{path.relative_to(root)}: link escapes project {raw}")
                elif not target.exists():
                    errors.append(f"{path.relative_to(root)}: missing target {raw}")
                else:
                    graph[path].append(target / "README.md" if target.is_dir() else target)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    pending, seen = [root / "AGENTS.md", root / config["documentation_entry"]], set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        pending.extend(graph.get(path, []))
    errors.extend(f"unindexed document: {p.relative_to(root)}" for p in docs if p not in seen)
    if include_skills:
        errors.extend(check_skills(root))
    return errors


def main(root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("start")
    commands.add_parser("check")
    skills = commands.add_parser("skills").add_subparsers(dest="action", required=True)
    skills.add_parser("migrate")
    skills.add_parser("record").add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "start":
            for relative in ("docs/README.md", "docs/roadmap/NOW.md"):
                print(f"\n[{relative}]\n{(root / relative).read_text(encoding='utf-8-sig')}")
            return 0
        if args.command == "skills":
            result = migrate(root) if args.action == "migrate" else record(root, args.sources)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        errors = check(root)
        print("FAILED\n" + "\n".join(errors) if errors else "PASS: local document navigation and skill manifest integrity")
        print("Scope excludes application build, runtime, UI acceptance and publishing.")
        return int(bool(errors))
    except (OSError, ValueError, TypeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
