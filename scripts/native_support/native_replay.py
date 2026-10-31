"""将固定原回放实现纳入 core 后继；旧行情 SDK 和原数据目录保持。

输入是已验 core wheel 与两个显式源码身份。输出是标准纯 Python wheel；
旧代码逐字复制，新增公开重导出。算法只由原 qmt_native_replay 维护。
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile


BASE_VERSION = "0.1.0a1"
VERSION = "0.1.0a2"
NAME = "guanheng_native_analysis_core"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(baseline, baseline_sha256, replay, replay_sha256, client, client_sha256, output):
    """核输入、独占创建后继 wheel；失败保留原件，不覆盖既有输出。"""
    paths = [Path(p).resolve(strict=True) for p in (baseline, replay, client)]
    expected = [baseline_sha256, replay_sha256, client_sha256]
    if [sha(p) for p in paths] != expected:
        raise ValueError("native_replay_build_input_changed")
    before = dict(zip(map(str, paths), expected))
    base_info = NAME + "-" + BASE_VERSION + ".dist-info/"
    new_info = NAME + "-" + VERSION + ".dist-info/"
    payload, old_code = {}, {}
    with zipfile.ZipFile(paths[0]) as archive:
        infos = archive.infolist()
        if len(infos) > 4096 or len({v.filename for v in infos}) != len(infos):
            raise ValueError("native_replay_wheel_members")
        total = 0
        for item in infos:
            name = PurePosixPath(item.filename)
            total += item.file_size
            if (item.is_dir() or name.is_absolute() or ".." in name.parts
                    or "\\" in item.filename or item.file_size > 64 * 1024 * 1024
                    or total > 256 * 1024 * 1024):
                raise ValueError("native_replay_wheel_member")
            raw = archive.read(item)
            if item.filename == base_info + "RECORD":
                continue
            relative = item.filename
            if relative.startswith(base_info):
                relative = new_info + relative[len(base_info):]
            else:
                old_code[relative] = hashlib.sha256(raw).hexdigest()
            payload[relative] = raw
    metadata = payload[new_info + "METADATA"]
    if metadata.count(b"Version: " + BASE_VERSION.encode() + b"\n") != 1:
        raise ValueError("native_replay_baseline_version")
    payload[new_info + "METADATA"] = metadata.replace(
        b"Version: " + BASE_VERSION.encode() + b"\n", b"Version: " + VERSION.encode() + b"\n", 1
    ).rstrip() + b"\nRequires-Dist: guanheng-market-client==0.15.0\n"
    additions = {
        "integrations/guanheng/qmt_native_replay.py": paths[1].read_bytes(),
        "guanheng_market_client/qmt_native_replay.py": paths[2].read_bytes(),
    }
    if set(additions) & set(payload):
        raise ValueError("native_replay_existing_member")
    payload.update(additions)
    origins = dict(schema="guanheng.native-replay-core-origins.v1", baseline=before[str(paths[0])],
                   original_files=old_code, additions={name: dict(
                       source=str(paths[i + 1]), sha256=expected[i + 1])
                       for i, name in enumerate(additions)})
    payload["integrations/REPLAY-ORIGINS.json"] = json.dumps(
        origins, sort_keys=True, separators=(",", ":")).encode("utf8")
    records = io.StringIO(newline="")
    writer = csv.writer(records, lineterminator="\n")
    for name, raw in sorted(payload.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode()
        writer.writerow((name, "sha256=" + digest, len(raw)))
    record_path = new_info + "RECORD"
    writer.writerow((record_path, "", ""))
    payload[record_path] = records.getvalue().encode("utf8")
    output = Path(output).absolute()
    if not output.parent.is_dir() or output.exists():
        raise ValueError("native_replay_new_output_required")
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    if any(sha(p) != h for p, h in before.items()):
        raise ValueError("native_replay_input_changed_after_build")
    return dict(schema="guanheng.native-replay-core-build.v1", version=VERSION,
                wheel=str(output), sha256=sha(output), members=len(payload),
                original_code_files=old_code, new_code_files=list(additions), inputs=before)
