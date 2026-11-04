"""原CLI普通异常丢失原因的离线回归；全程无Host/Scan/SHM实例。"""
import errno
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'apps/wt_runtime'))
from guanheng_wt_runtime import __main__ as cli


class OfflineRuntime:
    def __init__(self):
        self.closed=False
        self.close_calls=[]
    def start(self,deadline):return True
    def status(self):
        return dict(schema='guanheng.wt-runtime-status.v1',state='closed' if self.closed else 'ready',
            error_code=None,ready=not self.closed,components={})
    def wait_close_request(self,timeout):return self.closed
    def check(self):self.closed=True;return True
    def request_close(self):self.closed=True
    def close(self,timeout):self.close_calls.append(timeout);self.closed=True;return True


class FailureDiagnostics(unittest.TestCase):
    def test_real_windows_replace_denied_preserves_health_and_normal_close(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4());runtime=OfflineRuntime();captured=[]
            original=cli.replace_status
            def deny_once(candidate,target):
                if target.exists() and not captured:
                    # Python普通读句柄不授删除共享，直接触发原ReplaceFileW失败；释放后原finally可收尾。
                    with target.open('rb'):
                        try:original(candidate,target)
                        except OSError as error:captured.append(error);raise
                    self.fail('Windows replacement should be denied by this read handle')
                return original(candidate,target)
            configuration=SimpleNamespace(instance_id=str(uuid4()),startup_seconds=1,stop_seconds=1)
            with patch.object(cli,'Runtime',return_value=runtime),patch.object(cli,'replace_status',side_effect=deny_once):
                result=cli.run(configuration,'a'*64,directory,str(uuid4()))
            self.assertEqual(result,0)
            self.assertEqual(runtime.close_calls,[1])
            closed=json.loads((directory/'closed.json').read_bytes())
            self.assertEqual(set(closed),{'schema','control_id','instance_id','pid',
                'configuration_sha256','components_closed','error_code','status'})
            self.assertIsNone(closed['error_code'])
            self.assertTrue(closed['components_closed'])
            self.assertEqual(json.loads((directory/'status.json').read_bytes())['state'],'closed')
            pending=list(directory.glob('.status.json.*'))
            self.assertEqual(pending,[])
            self.assertEqual(captured[0].winerror,32)
            self.assertFalse((directory/'failure.json').exists())
            self.assertFalse((directory/'diagnostic.json').exists())

    def _run(self, runtime, directory, *, publish=None):
        configuration=SimpleNamespace(instance_id=str(uuid4()),startup_seconds=1,stop_seconds=1)
        with patch.object(cli,'Runtime',return_value=runtime):
            if publish is None:return cli.run(configuration,'a'*64,directory,str(uuid4()))
            with patch.object(cli,'_publish',side_effect=publish):
                return cli.run(configuration,'a'*64,directory,str(uuid4()))

    def test_normal_run_has_original_receipt_and_no_diagnostic(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4());runtime=OfflineRuntime()
            self.assertEqual(self._run(runtime,directory),0)
            self.assertEqual(runtime.close_calls,[1])
            self.assertTrue((directory/'closed.json').exists())
            self.assertFalse((directory/'failure.json').exists())
            self.assertFalse((directory/'diagnostic.json').exists())
            self.assertEqual({p.name for p in directory.iterdir()},{'status.json','ready.json','closed.json'})

    def test_status_snapshot_exception_is_distinct_from_file_publication(self):
        class SnapshotFail(OfflineRuntime):
            def __init__(self):super().__init__();self.snapshots=0
            def status(self):
                self.snapshots+=1
                if self.snapshots==2:raise OSError(errno.EIO,'private snapshot detail')
                return super().status()
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4())
            self.assertEqual(self._run(SnapshotFail(),directory),2)
            value=json.loads((directory/'diagnostic.json').read_bytes())
            self.assertEqual(value['failure']['phase'],'loop_status_snapshot')
            self.assertEqual(list(directory.glob('.status.json.*')),[])

    def test_custom_exception_name_message_cause_and_path_never_enter_diagnostic(self):
        secret='SECRET_ACCOUNT_AND_TOKEN'
        class Failing(OfflineRuntime):
            def check(self):
                custom=type(secret,(Exception,),{})
                raise custom(secret) from ValueError(secret)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4());runtime=Failing()
            self.assertEqual(self._run(runtime,directory),2)
            raw=(directory/'diagnostic.json').read_text()
            self.assertNotIn(secret,raw)
            self.assertNotIn(str(directory),raw)
            event=json.loads(raw)['failure']
            self.assertEqual(event,dict(phase='component_check',exception_type='Exception',errno=None,winerror=None))

    def test_diagnostic_write_failure_keeps_original_failure_and_close(self):
        class Failing(OfflineRuntime):
            def check(self):raise ValueError('private error')
        original=cli._publish;attempts=[]
        def publish(directory,name,value,**kwargs):
            attempts.append(name)
            if name=='diagnostic.json':raise OSError(errno.EACCES,'private path')
            return original(directory,name,value,**kwargs)
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4());runtime=Failing()
            self.assertEqual(self._run(runtime,directory,publish=publish),2)
            self.assertEqual(runtime.close_calls,[1])
            self.assertTrue(json.loads((directory/'failure.json').read_bytes())['components_closed'])
            self.assertEqual(attempts.count('diagnostic.json'),1)
            self.assertEqual(attempts[-2:],['failure.json','diagnostic.json'])

    def test_cleanup_failure_propagates_original_and_preserves_first_failure(self):
        class Failing(OfflineRuntime):
            def check(self):raise ValueError('private trigger')
            def close(self,timeout):raise OSError(errno.EIO,'private close path')
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4())
            # 原close抛异常会跳过原信号恢复；替身避免测试自身改变进程的真实信号处理器。
            with patch.object(cli.signal,'signal',return_value=None):
                with self.assertRaises(OSError) as raised:self._run(Failing(),directory)
            self.assertEqual(raised.exception.errno,errno.EIO)
            value=json.loads((directory/'diagnostic.json').read_bytes())
            self.assertEqual(value['failure']['phase'],'component_check')
            self.assertEqual(value['cleanup_failure']['phase'],'runtime_close')
            self.assertEqual(value['cleanup_failure']['errno'],errno.EIO)
            self.assertFalse((directory/'closed.json').exists())

    def test_component_failure_result_is_not_changed_into_an_exception(self):
        class Failing(OfflineRuntime):
            def check(self):return False
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as root:
            directory=Path(root)/str(uuid4());runtime=Failing()
            self.assertEqual(self._run(runtime,directory),2)
            self.assertEqual(json.loads((directory/'failure.json').read_bytes())['error_code'],'component_runtime')
            self.assertFalse((directory/'diagnostic.json').exists())


if __name__=='__main__':unittest.main()
