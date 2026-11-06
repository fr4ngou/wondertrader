"""原版独立CLI；只在显式新路径保存输入与报告。"""

import argparse
import json
from pathlib import Path
import sqlite3

from .reference import MAX_BYTES, canonical, export_database, run_reference


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="固定上游共振原版离线核对")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="只读冻结原SQLite业务字段")
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--codes", help="逗号分隔原六位代码；默认原组合九证券")
    export.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run", help="运行固定stable信号与原组合")
    run.add_argument("--source", type=Path, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("输出路径已存在，请指定新文件")
        if args.command == "export":
            options = {"codes": tuple(args.codes.split(","))} if args.codes else {}
            value = export_database(args.database, **options)
        else:
            if args.input.stat().st_size > MAX_BYTES:
                raise ValueError("输入超过32MiB")
            value = run_reference(args.source, json.loads(args.input.read_text(encoding="utf-8")), args.timeout_seconds)
        # 独占创建，避免覆盖并行任务或原始数据；失败文件不作为完成报告。
        content = canonical(value)
        with args.output.open("xb") as stream:
            stream.write(content)
        print(json.dumps({"status": "complete", "output": str(args.output), "schema": value["schema"]}, ensure_ascii=False))
    except sqlite3.Error:
        print(json.dumps({"status": "failed", "error": "原SQLite结构或读取失败"}, ensure_ascii=False))
        return 1
    except (OSError, ValueError, TimeoutError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
