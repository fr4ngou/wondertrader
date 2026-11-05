"""提取真实Guard/parse，对原完整RuntimeInput做节点预算红绿；无产品/QMT进程。"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
import native


def node_count(value):
    """沿原SAX规则计容器/标量；键名不另计节点。"""
    return 1 + (sum(map(node_count, value.values())) if isinstance(value,dict)
                else sum(map(node_count,value)) if isinstance(value,list) else 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--include',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    env,_ = native.environment(args.output)
    compiler = shutil.which('cl.exe',path=env['PATH'])
    assert compiler
    deadline = time.monotonic()+90
    result = {}
    for label,source in (('before',args.before),('after',args.after)):
        text = source.read_text(encoding='utf-8')
        helpers = text[text.index('struct Guard:'):text.index('const rj::Value& member(')]
        invocation = 'parse(body,body.size());' if 'Guard guard(maximum_nodes)' in helpers else 'parse(body);'
        fixture = '''#include <rapidjson/document.h>
#include <rapidjson/reader.h>
#include <rapidjson/memorystream.h>
#include <vector>
#include <set>
#include <string>
#include <cstdint>
#include <cmath>
#include <stdexcept>
#include <fstream>
#include <iostream>
#include <iterator>
namespace rj=rapidjson;
void need(bool value){if(!value)throw std::runtime_error("invalid");}
''' + helpers + '''
int main(int argc,char** argv){
    if(argc!=2)return 2;
    std::ifstream file(argv[1],std::ios::binary);
    std::string body((std::istreambuf_iterator<char>(file)),std::istreambuf_iterator<char>());
    bool ordinary=false,full=false,small=false;
    try{parse("{\\"ok\\":true}");small=true;}catch(...){}
    try{parse(body);ordinary=true;}catch(...){}
    try{@@INVOKE@@full=true;}catch(...){}
    std::cout<<"{\\"small\\":"<<small<<",\\"ordinary\\":"<<ordinary<<",\\"full\\":"<<full<<"}\\n";
}
'''.replace('@@INVOKE@@',invocation)
        path = args.output/(label+'.cpp')
        path.write_text(fixture,encoding='utf-8')
        exe = args.output/(label+'.exe')
        native.run([compiler,'/nologo','/std:c++17','/EHsc','/W4','/O2','/MD','/utf-8',
                    '/I'+str(args.include),'/Fo'+str(args.output/(label+'.obj')),
                    '/Fe'+str(exe),str(path),'/link','/machine:x64','/INCREMENTAL:NO'],
                   cwd=args.output,env=env,log=args.output/(label+'-build.log'),
                   timeout=max(.1,deadline-time.monotonic()),private_console=True)
        log = args.output/(label+'-run.log')
        native.run([exe,args.input],cwd=args.output,env=env,log=log,
                   timeout=max(.1,deadline-time.monotonic()),private_console=True)
        value = json.loads(log.read_text(encoding='utf-8'))
        assert value == dict(small=1,ordinary=0,full=int(label=='after'))
        result[label] = dict(source_sha256=sha256(source.read_bytes()).hexdigest(),**value)
    # 输入原件为已关闭本代的固定材料；只做只读计数，不写金融文件。
    raw = args.input.read_bytes()
    result['input'] = dict(path=str(args.input),bytes=len(raw),sha256=sha256(raw).hexdigest(),
                           scalar_container_nodes=node_count(json.loads(raw)))
    result['passed'] = True
    (args.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
