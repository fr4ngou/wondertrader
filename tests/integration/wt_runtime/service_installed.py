"""普通安装候选的 WT 服务启停主链；使用协议替身且不连接 QMT/账户。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from guanheng_market_client.runtime_status import read_status


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")), encoding="ascii")
    return path


def invoke(executable, config, action):
    result = subprocess.run(
        [str(executable), action, "--service-config", str(config)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
        text=True,
        encoding="utf-8",
    )
    assert not result.stderr
    value = json.loads(result.stdout)
    assert value["schema"] == "guanheng.wt-service-result.v1" and value["action"] == action
    return result.returncode, value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir()
    controls = args.work / "controls"
    generations = args.work / "generations"
    public = args.work / "public"
    temporary = args.work / "temporary"
    for path in (controls, generations, public, temporary):
        path.mkdir()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    service_cli = Path(sys.executable).with_name("guanheng-wt-service.exe")
    fixture_entry = args.source_root / "tests/integration/wt_runtime/collector_fixture.py"
    fixture_config = write(args.work / "collector.json", {"schema": "wt.fixture-collector.v1"})
    descriptor = write(
        args.work / "collector-deployment.json",
        {
            "schema": "qmt.quote-collector-process.v1",
            "pythonw": str(pythonw),
            "pythonw_sha256": sha(pythonw),
            "entry": str(fixture_entry),
            "entry_sha256": sha(fixture_entry),
            "configuration": str(fixture_config),
            "configuration_sha256": sha(fixture_config),
            "control_root": str(controls),
            "startup_seconds": 10,
            "stop_seconds": 5,
            "max_output_bytes": 65536,
        },
    )
    instance_id = str(uuid4())
    runtime = write(
        args.work / "runtime.json",
        {
            "schema": "guanheng.wt-runtime.v1",
            "instance_id": instance_id,
            "startup_seconds": 15,
            "stop_seconds": 10,
            "components": {
                "collection": {
                    "kind": "quote_collection",
                    "descriptor": str(descriptor),
                    "sha256": sha(descriptor),
                }
            },
        },
    )
    environment = write(
        args.work / "environment.json",
        {"TEMP": str(temporary), "TMP": str(temporary), "WT_SERVICE_INSTALLED_TEST": "private"},
    )
    current = public / "CURRENT.json"
    service = write(
        args.work / "service.json",
        {
            "schema": "guanheng.wt-service.v1",
            "pythonw": str(pythonw),
            "pythonw_sha256": sha(pythonw),
            "bootstrap_configuration": str(runtime),
            "bootstrap_configuration_sha256": sha(runtime),
            "control_root": str(controls),
            "generation_root": str(generations),
            "current_file": str(current),
            "environment_file": str(environment),
            "environment_sha256": sha(environment),
        },
    )
    results = []
    try:
        for action in ("start", "start", "status", "stop", "stop", "start", "status", "stop"):
            code, value = invoke(service_cli, service, action)
            results.append({"exit_code": code, "value": value})
            write(args.work / "ACTION-RESULTS.json", {"schema": "wt.service-actions.v1", "results": results})
            assert code == 0
        first, duplicate, first_status, first_stop, duplicate_stop, second, second_status, second_stop = [
            item["value"] for item in results
        ]
        assert first["state"] == duplicate["state"] == first_status["state"] == "ready"
        assert first["changed"] and not duplicate["changed"] and not first_status["changed"]
        assert first_stop["state"] == duplicate_stop["state"] == second_stop["state"] == "stopped"
        assert first_stop["changed"] and not duplicate_stop["changed"] and second_stop["changed"]
        assert second["state"] == second_status["state"] == "ready" and second["changed"]
        assert first["current"]["wt_control_id"] != second["current"]["wt_control_id"]
        assert first["current"]["wt_instance_id"] == second["current"]["wt_instance_id"] == instance_id
        assert set(read_status(current)) == {
            "schema", "wt_status_file", "wt_control_id", "wt_instance_id", "wt_configuration_sha256"
        }
        for item in (first_stop, second_stop):
            control = Path(item["current"]["wt_status_file"]).parent
            closed = read_status(control / "closed.json")
            final = read_status(control / "status.json")
            assert closed["components_closed"] and final["state"] == "closed"
            assert final["components"]["collection"]["state"] == "closed"
    finally:
        if current.exists():
            invoke(service_cli, service, "stop")
    receipt = {
        "schema": "wt.service-installed-result.v1",
        "passed": True,
        "instance_id": instance_id,
        "actions": [item["value"]["action"] for item in results],
        "control_ids": [results[0]["value"]["current"]["wt_control_id"], results[5]["value"]["current"]["wt_control_id"]],
        "same_instance": True,
        "idempotent_start": not results[1]["value"]["changed"],
        "idempotent_stop": not results[4]["value"]["changed"],
        "current_fields": sorted(read_status(current)),
        "qmt_calls": 0,
        "account_calls": 0,
        "orders": 0,
        "cancels": 0,
    }
    write(args.work / "RESULT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
