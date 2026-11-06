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


def start_document(path: Path, *, full: bool, current: bool) -> str:
    """默认输出导航与最近三条状态；完整历史由显式入口按需读取。"""
    text = path.read_text(encoding="utf-8-sig")
    if full:
        return text
    paragraphs = re.split(r"\n\s*\n", text.strip())
    selected = "\n\n".join(paragraphs[:4]) if current else text
    # 输出预算约束开发入口的上下文，原文和完整读取入口保持可用。
    preview = selected[:6000]
    if preview.strip() != text.strip():
        preview += "\n\n[摘要输出；详细正文按路径读取，或执行 scripts/project.py start --full。]"
    return preview


def check_document_snapshot(text: str, *, label: str, max_characters: int) -> list[str]:
    """核对当前快照的字符预算与日期流水；历史正文沿普通文档检查。"""
    errors = []
    if len(text) > max_characters:
        errors.append(f"{label}: snapshot exceeds character budget ({len(text)} > {max_characters})")
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    if re.search(r"(?m)^[ \t]*(?:[-*][ \t]+)?\d{4}-\d{2}-\d{2}", prose):
        errors.append(f"{label}: dated timeline in current snapshot; update the topic and link event evidence")
    return errors


def check(root: Path, *, include_skills: bool = True) -> list[str]:
    root = root.resolve()
    errors = []
    config = json.loads((root / "config/project.json").read_text(encoding="utf-8"))
    # Upstream reference documents can have intentionally sparse-checkout assets.
    # Check the project-maintained document scope declared in the configuration.
    patterns = config["documentation_paths"]
    docs = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})
    paths = [root / "AGENTS.md", root / config["documentation_entry"]] + docs
    # 配置字段：键为仓库内快照路径，值为含换行的最大 Unicode 字符数。
    snapshot_limits = config.get("document_snapshot_limits", {})
    if not isinstance(snapshot_limits, dict):
        raise ValueError("document_snapshot_limits must be an object")
    snapshot_budgets = {}
    for relative, budget in snapshot_limits.items():
        if not isinstance(relative, str) or type(budget) is not int or budget <= 0:
            raise ValueError("snapshot limits require relative paths and positive integer budgets")
        target = (root / relative).resolve()
        if not target.is_relative_to(root) or Path(relative).is_absolute():
            raise ValueError(f"snapshot path escapes project: {relative}")
        if target not in {p.resolve() for p in paths}:
            raise ValueError(f"snapshot is outside declared documentation scope: {relative}")
        snapshot_budgets[target] = budget
    graph = {}
    for path in dict.fromkeys(paths):
        if not path.is_file():
            errors.append(f"missing document: {path.relative_to(root)}")
            continue
        graph[path] = []
        try:
            text = path.read_text(encoding="utf-8-sig")
            if path.resolve() in snapshot_budgets:
                errors.extend(check_document_snapshot(
                    text, label=str(path.relative_to(root)),
                    max_characters=snapshot_budgets[path.resolve()],
                ))
            text = re.sub(r"```.*?```", "", text, flags=re.S)
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
    start = commands.add_parser("start")
    start.add_argument("--full", action="store_true", help="显式读取完整导航及当前工作历史")
    commands.add_parser("check")
    skills = commands.add_parser("skills").add_subparsers(dest="action", required=True)
    skills.add_parser("migrate")
    skills.add_parser("record").add_argument("--sources", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "start":
            for relative in ("docs/README.md", "docs/roadmap/NOW.md"):
                text = start_document(root / relative, full=args.full, current=relative.endswith("NOW.md"))
                print(f"\n[{relative}]\n{text}")
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
