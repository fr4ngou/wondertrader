"""SDK 清单采集失败及重复输出时必须保留原文件。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import qmt_sdk_manifest


class SdkManifestTests(unittest.TestCase):
    def test_other_python_version_is_rejected(self):
        with patch.object(qmt_sdk_manifest.sys, 'version_info', (3, 12, 0)):
            with self.assertRaisesRegex(ValueError, '3.6.8'):
                qmt_sdk_manifest.collect()

    def test_manifest_is_json_and_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'sdk.json'
            value = dict(schema_version='qmt.memory-sdk.v1', python_version=[3, 6, 8])
            with patch.object(qmt_sdk_manifest, 'collect', return_value=value):
                self.assertEqual(qmt_sdk_manifest.main(['--output', str(target)]), 0)
                self.assertEqual(json.loads(target.read_bytes()), value)
                original = target.read_bytes()
                with self.assertRaises(FileExistsError):
                    qmt_sdk_manifest.main(['--output', str(target)])
                self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
