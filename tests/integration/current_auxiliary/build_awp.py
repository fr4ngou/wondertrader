"""Freeze and build only AWP; other three installed packages stay exact."""
import hashlib,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
r=Path(__file__).resolve().parents[3];q=Path(sys.argv[1]).resolve();w=q/'build';w.mkdir();stage=w/'source';stage.mkdir()
src=r/'apps/analysis_window_producer';files={}
for p in src.rglob('*'):
 if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
  relative=p.relative_to(src);t=stage/relative;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(p.read_bytes());files[str(p.relative_to(r))]=hashlib.sha256(p.read_bytes()).hexdigest()
(q/'SOURCE.json').write_text(json.dumps(files,indent=2),encoding='utf8')
py=Path('E:/workspace/wondertrader-qa/current-auxiliary-module-20261106-001/venv/Scripts/python.exe')
backend=Path('E:/workspace/wondertrader-qa/current-auxiliary-module-20261106-001/flit_core-3.12.0-py3-none-any.whl');out=w/'wheels';out.mkdir()
subprocess.run([str(py),'-I','-B','-c','import sys;sys.path.insert(0,sys.argv[1]);from flit_core.buildapi import build_wheel;build_wheel(sys.argv[2])',str(backend),str(out)],cwd=stage,check=True,env=dict(os.environ,SOURCE_DATE_EPOCH='315532800'))
wheel=next(out.glob('*.whl'));digest=hashlib.sha256(wheel.read_bytes()).hexdigest();lock=w/'INSTALL.lock';lock.write_text('guanheng-analysis-window-producer==0.1.0a13+auxiliary.4.current.2 --hash=sha256:'+digest+'\n')
uv='C:/Users/frangou/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe/uv.exe'
subprocess.run([uv,'pip','install','--python',str(py),'--offline','--no-index','--no-deps','--require-hashes','--find-links',str(out),'-r',str(lock)],check=True)
subprocess.run([uv,'pip','check','--python',str(py)],check=True)
assert all(hashlib.sha256((r/n).read_bytes()).hexdigest()==h for n,h in files.items())
(q/'BUILD.json').write_text(json.dumps(dict(wheel=str(wheel),sha256=digest,source_cas=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest(),dependencies=['guanheng-native-analysis-core==0.1.0a3+currentaux.1','guanheng-wt-runtime==0.1.0a15+currentaux.1','guanheng-strategy-v1==0.1.0a13'],other_packages_rebuilt=0,passed=True),indent=2))
print(digest)
