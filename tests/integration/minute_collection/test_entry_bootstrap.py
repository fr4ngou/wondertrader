"""用实际完整运行解释器、隔离入口及干净进程检查release装配，不启动服务。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class EntryBootstrapTests(unittest.TestCase):
    def run_entry(self, relative):
        script = '''
from pathlib import Path
import runpy,sys,threading
entry=Path(sys.argv[1]);before=threading.active_count()
namespace=runpy.run_path(str(entry),run_name='isolated_entry_admission')
import integrations.guanheng.quote_collection as collection
assert Path(collection.__file__).resolve().is_relative_to(entry.parents[2].resolve())
assert threading.active_count()==before
print('actual release entry loaded without services')
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(ROOT/relative)],
                cwd=directory, capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_collector_direct_entry_resolves_its_release_package(self):
        self.run_entry('integrations/guanheng/quote_collection_service.py')

    def test_history_direct_entry_uses_complete_runtime_and_release(self):
        self.run_entry('integrations/guanheng/source_market_service.py')
