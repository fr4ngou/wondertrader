"""真实on_tick/cta_targets红绿：原WT旧理论证券可继续存在，桥只投影声明reads。"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import native


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before',type=Path,required=True)
    parser.add_argument('--after',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    env,_=native.environment(args.output)
    compiler=shutil.which('cl.exe',path=env['PATH'])
    assert compiler
    deadline=time.monotonic()+90
    results={}
    for label,root in (('before',args.before),('after',args.after)):
        bridge=root/'src/GuanhengRealtime/ManagedStrategyBridge.cpp'
        context=root/'src/GuanhengRealtime/ContextAccess.h'
        body=bridge.read_text(encoding='utf-8')
        on_tick=body[body.index('    void on_tick('):body.index('    void on_session_begin(')].replace('override','')
        body=context.read_text(encoding='utf-8')
        targets=body[body.index('inline std::map<std::string,double> cta_targets('):body.index('inline GhRtFacts cta_facts(')]
        helpers=body[body.index('struct CtaAccessError'):body.index('inline GhRtBar cta_bar(')]
        common=(ROOT/'src/GuanhengRealtime/RealtimeBridge.h').read_text(encoding='utf-8')
        constants=re.search(r'enum GhRtResult\s*\{.*?\};',common,re.S).group()
        quote=re.search(r'typedef struct GhMsQuote\s*\{.*?\} GhMsQuote;',
                        (ROOT/'src/GuanhengRealtime/ManagedStrategyBridge.h').read_text(encoding='utf-8'),re.S).group()
        code=r'''#include <string>
#include <cstring>
#include <cmath>
#include <map>
#include <set>
#include <mutex>
#include <atomic>
#include <functional>
#include <vector>
#include <limits>
#include <iostream>
#include <cstdint>
#define GH_RT_CODE_BYTES 64
#define GH_RT_MAX_READS 16
@@CONSTANTS@@
@@QUOTE@@
namespace wtp {
struct ICtaStraCtx {
    std::vector<std::pair<std::string,double>> values;
    void enum_position(std::function<void(const char*,double)> callback,bool){
        for(auto& row:values)callback(row.first.c_str(),row.second);
    }
};
struct WTSTickData {
    struct Tick {double price=1.403;uint32_t action_date=20261105,action_time=150250000;} raw;
    const Tick& getTickStruct(){return raw;}
};
}
using namespace wtp;
@@HELPERS@@
@@TARGETS@@
struct Owner {std::atomic<int32_t> failure{0};void fail(int32_t value){failure.store(value);}};
Owner& owner(){static Owner value;return value;}
struct Binding {
    std::set<std::string> reads; // 不可变的声明读取集合。
    std::mutex quote_mutex; // 沿原已应用tick缓存的锁。
    std::map<std::string,GhMsQuote> quotes; // 固定预分配缓存，未声明tick不创建条目。
};
struct Strategy {
    Binding& binding;
@@TICK@@
};
int main(){
    Binding binding;binding.reads.insert("SSE.ETF.588030");binding.quotes.emplace("SSE.ETF.588030",GhMsQuote{});
    Strategy strategy{binding};WTSTickData tick;
    strategy.on_tick(nullptr,"SSE.ETF.589680",&tick);
    const bool outside_tick_safe=owner().failure.load()==0&&binding.quotes.size()==1;
    owner().failure.store(0);strategy.on_tick(nullptr,"SSE.ETF.588030",&tick);
    const bool declared_tick_updated=owner().failure.load()==0&&binding.quotes.begin()->second.price_cny==1.403;
    tick.raw.price=0;strategy.on_tick(nullptr,"SSE.ETF.588030",&tick);
    const bool declared_tick_invalid_rejected=owner().failure.load()==GH_RT_NATIVE;
    ICtaStraCtx ctx;ctx.values={{"SSE.ETF.589680",188600},{"SSE.ETF.588030",100}};
    bool outside_target_safe=false;
    try{auto projected=cta_targets(ctx,binding.reads);outside_target_safe=projected.size()==1&&projected.at("SSE.ETF.588030")==100;}catch(...){}
    ctx.values={{"SSE.ETF.588030",std::numeric_limits<double>::quiet_NaN()}};
    bool declared_target_invalid_rejected=false;
    try{cta_targets(ctx,binding.reads);}catch(...){declared_target_invalid_rejected=true;}
    std::cout<<"{\"outside_tick_safe\":"<<outside_tick_safe<<",\"declared_tick_updated\":"<<declared_tick_updated
        <<",\"declared_tick_invalid_rejected\":"<<declared_tick_invalid_rejected<<",\"outside_target_safe\":"<<outside_target_safe
        <<",\"declared_target_invalid_rejected\":"<<declared_target_invalid_rejected<<"}\n";
}
'''
        for marker,value in (('CONSTANTS',constants),('QUOTE',quote),('HELPERS',helpers),('TARGETS',targets),('TICK',on_tick)):
            code=code.replace('@@'+marker+'@@',value)
        source=args.output/(label+'.cpp');source.write_text(code,encoding='utf-8')
        exe=args.output/(label+'.exe')
        native.run([compiler,'/nologo','/std:c++17','/EHsc','/W4','/O2','/MD','/utf-8',
                    '/Fo'+str(args.output/(label+'.obj')),'/Fe'+str(exe),str(source),
                    '/link','/machine:x64','/INCREMENTAL:NO'],cwd=args.output,env=env,
                   log=args.output/(label+'-build.log'),timeout=max(.1,deadline-time.monotonic()),private_console=True)
        log=args.output/(label+'-run.log')
        native.run([exe],cwd=args.output,env=env,log=log,timeout=max(.1,deadline-time.monotonic()),private_console=True)
        value=json.loads(log.read_text(encoding='utf-8'))
        assert value==dict(outside_tick_safe=int(label=='after'),outside_target_safe=int(label=='after'),
                           declared_tick_updated=1,declared_tick_invalid_rejected=1,declared_target_invalid_rejected=1)
        results[label]=dict(bridge_sha256=sha256(bridge.read_bytes()).hexdigest(),
                            context_sha256=sha256(context.read_bytes()).hexdigest(),**value)
    results['passed']=True
    (args.output/'RESULT.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results))


if __name__=='__main__':main()
