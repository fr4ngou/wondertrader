"""Original 19 public ABI/lifecycle assertions; explicit installed library input."""
import argparse,ctypes,json,threading,hashlib,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--library',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();library=args.library.resolve(strict=True);output=args.output;output.parent.mkdir(parents=True,exist_ok=True);dll=ctypes.CDLL(str(library));create=dll.createTrader;create.argtypes=[];create.restype=ctypes.c_void_p
destroy=dll.deleteTrader;destroy.argtypes=[ctypes.POINTER(ctypes.c_void_p)];destroy.restype=None
view=dll.inspectReadOnlyTraderView;view.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)];view.restype=ctypes.c_int
wait=dll.waitReadOnlyTrader;wait.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32];wait.restype=ctypes.c_int
kernel_path=ctypes.WinDLL('kernel32',use_last_error=True);kernel_path.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint32];actual=ctypes.create_unicode_buffer(32768);assert kernel_path.GetModuleFileNameW(dll._handle,actual,len(actual));assert Path(actual.value).samefile(library);api=ctypes.c_void_p(create());assert api.value;checks=[]
def check(ok,name):assert ok,name;checks.append(name)
check(not hasattr(dll,'gh_qmt_http_test_closing_gate'),'production-no-test-export')
check(not hasattr(dll,'gh_nqh_test_notify_wait'),'production-no-own-wake-test-export')
check(wait(None,1,1)==-1,'wait-invalid-pointer')
check(wait(api,1,1)==-2,'wait-created-unavailable')
check(wait(api,0,1)==-1 and wait(api,8,1)==-1 and wait(api,1,120001)==-1,'wait-invalid-contract')
wrong_wait=[];t=threading.Thread(target=lambda:wrong_wait.append(wait(api,1,1)));t.start();t.join();check(wrong_wait==[-3],'wait-wrong-owner')
needed=ctypes.c_uint32(99);buffer=ctypes.create_string_buffer(b'UNCHANGED',100)
check(view(api,2,0,0,None,1,ctypes.byref(needed))==-1 and needed.value==0,'null-output-nonzero-capacity')
check(view(api,1,0,0,buffer,100,ctypes.byref(needed))==-1 and buffer.value==b'UNCHANGED' and needed.value==0,'version-error-no-output-write')
check(view(api,2,5,0,buffer,100,ctypes.byref(needed))==-1 and buffer.value==b'UNCHANGED','unknown-view-no-write')
check(view(api,2,0,0,None,0,None)==-1,'required-pointer-mandatory')
check(view(api,2,1,0,None,0,ctypes.byref(needed))==-2 and needed.value==0,'undelivered-row-unavailable')
check(view(ctypes.c_void_p(1),2,0,0,buffer,100,ctypes.byref(needed))==-1 and needed.value==0 and buffer.value==b'UNCHANGED','unregistered-address-invalid')
check(view(api,2,0,0,None,0,ctypes.byref(needed))==-8 and needed.value>0,'length-probe')
size=needed.value;full=ctypes.create_string_buffer(size)
check(view(api,2,0,0,full,size,ctypes.byref(needed))==0 and full.raw[-1:]==b'\x00','exact-capacity-nul')
original=full.raw;check(view(api,2,0,0,full,size,ctypes.byref(needed))==0 and full.raw==original,'two-step-view-no-state-advance')
state={}
def alien():
    n=ctypes.c_uint32(88);b=ctypes.create_string_buffer(b'UNCHANGED',100);state['status']=view(api,2,0,0,b,100,ctypes.byref(n));state['n']=n.value;state['b']=b.value;original=api.value;destroy(ctypes.byref(api));state['retained']=api.value==original
thread=threading.Thread(target=alien);thread.start();thread.join(3);check(not thread.is_alive() and state==dict(status=-3,n=0,b=b'UNCHANGED',retained=True),'wrong-owner-view-and-factory-retain')
stale=api.value;destroy(ctypes.byref(api));check(not api.value,'fresh-release-drain-join-delete')
check(view(stale,2,0,0,buffer,100,ctypes.byref(needed))==-1 and needed.value==0 and buffer.value==b'UNCHANGED','stale-pointer-invalid')
kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.FreeLibrary.argtypes=[ctypes.c_void_p];kernel.FreeLibrary.restype=ctypes.c_int;check(bool(kernel.FreeLibrary(dll._handle)),'actual-dll-unload')
output.write_text(json.dumps(dict(passed=len(checks),failed=0,checks=checks,loaded_path=actual.value,dll_sha256=hashlib.sha256(library.read_bytes()).hexdigest()),indent=2),encoding='utf-8');print(len(checks),'PASS')
