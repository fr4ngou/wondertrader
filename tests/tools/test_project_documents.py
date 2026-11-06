"""验证当前快照阻止历史流水累积，同时保留普通历史资料的追溯能力。"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from project import check  # noqa: E402


class DocumentSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "config").mkdir()
        (self.root / "docs").mkdir()
        (self.root / "AGENTS.md").write_text("[Docs](docs/README.md)\n", encoding="utf-8")
        (self.root / "docs/README.md").write_text("[Current](CURRENT.md)\n", encoding="utf-8")
        (self.root / "docs/CURRENT.md").write_text(
            "# Current\n\nVerified: 2026-11-07\n\n## State\n\nOwner status needs current evidence.\n",
            encoding="utf-8",
        )
        self.config = {
            "documentation_paths": ["docs/**/*.md"],
            "documentation_entry": "docs/README.md",
            "document_snapshot_limits": {"docs/CURRENT.md": 6000},
        }

    def run_check(self):
        (self.root / "config/project.json").write_text(json.dumps(self.config), encoding="utf-8")
        return check(self.root, include_skills=False)

    def test_current_topic_snapshot_passes(self):
        self.assertEqual(self.run_check(), [])

    def test_original_dated_append_is_rejected_below_size_limit(self):
        # 原失效方式：每个任务向当前入口追加一段带日期的阶段流水。
        with (self.root / "docs/CURRENT.md").open("a", encoding="utf-8") as stream:
            stream.write("\n2026-11-04 previous ready observation\n")
        self.assertTrue(any("dated timeline" in error for error in self.run_check()))

    def test_dated_bullet_append_is_rejected(self):
        with (self.root / "docs/CURRENT.md").open("a", encoding="utf-8") as stream:
            stream.write("\n- 2026-11-04 previous task outcome\n")
        self.assertTrue(any("dated timeline" in error for error in self.run_check()))

    def test_snapshot_growth_is_rejected(self):
        (self.root / "docs/CURRENT.md").write_text("Current: " + "x" * 6000, encoding="utf-8")
        self.assertTrue(any("exceeds character budget" in error for error in self.run_check()))

    def test_long_dated_archive_remains_valid(self):
        # 历史资料应可完整保留；体积与流水检查只约束配置的当前入口。
        (self.root / "docs/history.md").write_text(
            "2026-11-04 previous observation\n" + "x" * 7000, encoding="utf-8",
        )
        with (self.root / "docs/CURRENT.md").open("a", encoding="utf-8") as stream:
            stream.write("\n[History](history.md)\n")
        self.assertEqual(self.run_check(), [])

    def test_existing_projects_without_snapshot_configuration_keep_behavior(self):
        self.config.pop("document_snapshot_limits")
        (self.root / "docs/CURRENT.md").write_text("2026-11-04 " + "x" * 7000, encoding="utf-8")
        self.assertEqual(self.run_check(), [])

    def test_snapshot_budget_requires_positive_integer(self):
        for invalid in [True, 0, -1, "6000"]:
            with self.subTest(budget=invalid):
                self.config["document_snapshot_limits"] = {"docs/CURRENT.md": invalid}
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    self.run_check()

    def test_snapshot_path_cannot_escape_project(self):
        self.config["document_snapshot_limits"] = {"../outside.md": 6000}
        with self.assertRaisesRegex(ValueError, "escapes project"):
            self.run_check()

    def test_snapshot_must_be_in_declared_document_scope(self):
        self.config["document_snapshot_limits"] = {"not-declared.md": 6000}
        with self.assertRaisesRegex(ValueError, "outside declared documentation scope"):
            self.run_check()


if __name__ == "__main__":
    unittest.main()
