"""运行时长切换回归：库存业务身份沿已绑定原件，金融模型保持原约束。"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from guanheng_wt_runtime.execution_recovery import (
    compatible_business_configuration,
    market_origin_configuration,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


class ExecutionBusinessIdentityTests(unittest.TestCase):
    def fixture(self, root, duration):
        origin = {
            "budget": {"start_ms": 25000, "stop_ms": 10000, "run_ms": duration},
            "trader": {"account": "SYNTHETIC", "writes_enabled": False},
            "output_directory": str(root / "financial"),
            "takeover": {"input_file": str(root / "inventory.json"), "input_sha256": "1" * 64},
            "recovery": {"mode": "record_clean"},
            "strategies": [{"parameters": {"python_strategy": {"input_file": str(root / "input.json"), "input_sha256": "2" * 64}}}],
            "data": {"store": {"daily": {"root": str(root / "daily")}}},
        }
        raw = canonical(origin)
        path = root / "execution.json"
        path.write_bytes(raw)
        current = deepcopy(origin)
        current.pop("takeover")
        current["recovery"] = {"mode": "resume_reconciled"}
        current["market_input_origin"] = {
            "schema": "guanheng.market-input-origin.v1",
            "file": str(path),
            "sha256": sha256(raw).hexdigest(),
        }
        window = root / "window.json"
        current["strategies"][0]["parameters"]["python_strategy"]["market_window"] = {"path": str(window), "max_age_seconds": 3600}
        current["data"]["store"]["daily"]["publication"] = {
            "status_file": str(root / "status.json"), "publication_file": str(window), "cache_root": str(root / "cache")}
        current["data"]["store"]["daily"]["adjustment"] = "front_ratio"
        return current

    def test_inventory_origin_survives_duration_change_in_both_directions(self):
        # 原BASELINE对业务投影取哈希；切换预算时必须保持该哈希，且不改实际执行预算。
        for old, new in ((70000, 0), (0, 70000)):
            with self.subTest(old=old, new=new), tempfile.TemporaryDirectory() as directory:
                current = self.fixture(Path(directory), old)
                before = market_origin_configuration(current)
                current["budget"]["run_ms"] = new
                after = market_origin_configuration(current)
                self.assertEqual(sha256(canonical(before)).digest(), sha256(canonical(after)).digest())
                self.assertEqual(after["budget"]["run_ms"], old)
                self.assertEqual(current["budget"]["run_ms"], new)

    def test_financial_model_changes_are_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            current = self.fixture(Path(directory), 70000)
            for field in ("account", "output_directory"):
                with self.subTest(field=field):
                    changed = deepcopy(current)
                    changed["budget"]["run_ms"] = 0
                    if field == "account":
                        changed["trader"][field] = "OTHER-SYNTHETIC"
                    else:
                        changed[field] = str(Path(directory) / "other-financial")
                    with self.assertRaises(ValueError):
                        market_origin_configuration(changed)

    def test_materialized_configuration_changes_only_duration(self):
        old = {"budget": {"run_ms": 70000}, "trader": {"account": "SYNTHETIC"}}
        new = deepcopy(old)
        new["budget"]["run_ms"] = 0
        self.assertTrue(compatible_business_configuration(new, old))
        for invalid in (True, 999, -1, 86400001):
            with self.subTest(duration=invalid):
                new["budget"]["run_ms"] = invalid
                with self.assertRaises(ValueError):
                    compatible_business_configuration(new, old)


if __name__ == "__main__":
    unittest.main()
