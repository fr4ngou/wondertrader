"""真实形状的长SHA回执名：临时文件保持同目录，目的身份和原子提交保持。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from guanheng_qmt_shm.read_retention_client import _save


class ReceiptPathTests(unittest.TestCase):
    def test_long_sha_destination_can_publish_and_replace_same_receipt(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            parent=root/('x'*(158-len(str(root))-1))
            target=parent/('a'*64+'.json')
            self.assertLess(len(str(target)),260)
            self.assertGreater(len(str(target))+37,260)
            _save(target,dict(request_id='original',consumed=False))
            _save(target,dict(request_id='original',consumed=True))
            self.assertEqual(json.loads(target.read_bytes()),dict(request_id='original',consumed=True))
            self.assertEqual(list(parent.iterdir()),[target])

    def test_failed_replace_keeps_original_and_complete_short_temporary_receipt(self):
        with tempfile.TemporaryDirectory()as directory:
            target=Path(directory)/('b'*64+'.json');_save(target,dict(request_id='original',consumed=False))
            candidates=[]
            def fail(candidate,destination):
                self.assertEqual(candidate.parent,destination.parent)
                self.assertLessEqual(len(candidate.name),37)
                candidates.append(candidate);raise OSError('synthetic replacement interruption')
            with patch('guanheng_qmt_shm.read_retention_client._replace_receipt',side_effect=fail):
                with self.assertRaises(OSError):_save(target,dict(request_id='original',consumed=True))
            self.assertFalse(json.loads(target.read_bytes())['consumed'])
            self.assertTrue(json.loads(candidates[0].read_bytes())['consumed'])


if __name__=='__main__':unittest.main()
