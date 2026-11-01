"""把已发布证券身份与核验名称表组装为观衡只读证券目录。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from pypinyin import Style, lazy_pinyin

SCHEMA = "guanheng.security-catalog.v1"
TYPE = {"1": "stock", "2": "index", "5": "etf"}


def compact_pinyin(name: str, style: Style) -> str:
    parts = lazy_pinyin(name, style=style, errors=lambda value: [point.lower() for point in value if point.isascii()])
    value = "".join(parts).replace("ü", "v").replace("u:", "v").lower()
    return "".join(point for point in value if point.isascii() and point.isalnum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--names", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    identity_raw = arguments.identity.read_bytes()
    names_raw = arguments.names.read_bytes()
    identity = json.loads(identity_raw)
    names_document = json.loads(names_raw)
    fields = identity.get("fields")
    if fields != ["code", "code_name", "ipoDate", "outDate", "type", "status"]:
        raise ValueError("identity fields")
    names = {}
    for row in names_document.get("rows", []):
        if not isinstance(row, dict) or set(row) != {"code", "exchange", "name", "security_type"}:
            raise ValueError("name row")
        symbol = f"{row['code']}.{row['exchange']}"
        if symbol in names and names[symbol] != row:
            raise ValueError("duplicate name identity")
        names[symbol] = row
    securities = []
    missing = []
    for row in identity.get("rows", []):
        if not isinstance(row, list) or len(row) != 6 or row[4] not in TYPE or row[5] != "1":
            continue
        prefix, code = row[0].split(".", 1)
        exchange = {"sh": "SH", "sz": "SZ"}.get(prefix)
        if exchange is None or not re.fullmatch(r"[0-9]{6}", code):
            continue
        symbol = f"{code}.{exchange}"
        named = names.get(symbol)
        expected = TYPE[row[4]]
        if named is None or named["security_type"] != expected:
            missing.append((symbol, expected))
            continue
        name = named["name"].strip()
        if not name or "�" in name:
            raise ValueError("invalid name")
        full = compact_pinyin(name, Style.NORMAL)
        initials = compact_pinyin(name, Style.FIRST_LETTER)
        if not re.fullmatch(r"[a-z0-9]+", full) or not re.fullmatch(r"[a-z0-9]+", initials):
            raise ValueError(f"pinyin {symbol}")
        securities.append({"symbol": symbol, "code": code, "exchange": exchange, "name": name,
                           "security_type": expected, "pinyin_initials": initials, "pinyin_full": full})
    securities.sort(key=lambda item: item["symbol"])
    payload = json.dumps(securities, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    result = {"schema_version": SCHEMA, "catalog_id": hashlib.sha256(payload).hexdigest(),
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
              "source": {"identity_sha256": hashlib.sha256(identity_raw).hexdigest(),
                         "names_sha256": hashlib.sha256(names_raw).hexdigest(),
                         "names_retrieved_at": names_document.get("retrieved_at"),
                         "included": len(securities), "missing": len(missing)},
              "securities": securities}
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"output": str(arguments.output), "catalog_id": result["catalog_id"],
                      "included": len(securities), "missing": len(missing),
                      "sample_missing": missing[:20]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
