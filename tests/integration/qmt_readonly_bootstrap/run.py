"""Isolated child-process oracle. Fixture data only; no endpoint or credentials."""
from pathlib import Path
import argparse, copy, hashlib, json, subprocess, time
ROOT=Path(__file__).resolve().parents[3]
from invocation import arguments,resolve,verify
IDENTITY=dict(source="synthetic-qmt",account="SYNTHETIC-NQB",environment="fixture",session="fixture-session",generation=1,trading_date=20261022)
def fixture():
    stock=dict(code="600000",exchange="SH",total=700,previous=500,today=200,available_previous=420,available_today=0,average_price=10.25,cost=7175,position_semantics="remaining_yesterday")
    etf=dict(code="510300",exchange="SH",total=37,previous=20,today=17,available_previous=15,available_today=12,average_price=3.25,cost=120.25,position_semantics="remaining_yesterday")
    order=dict(code="600000",exchange="SH",order_id="fixture-order-1",user_tag="otp.nqb.17",ownership=dict(kind="fixture_wt",adapter_id="nqb",order_id="fixture-order-1",local_id=17),side="buy",quantity=200,price=10.35,filled=70,remaining=130,inactive=0,state="partial",date=20261022,time=93507123)
    trade=dict(code="600000",exchange="SH",order_id="fixture-order-1",trade_id="fixture-trade-1",side="buy",quantity=70,price=10.31,amount=721.7,date=20261022,time=93508124)
    account=dict(currency="CNY",total_asset=100000,available=82000,previous_balance=99900,commission=12.34,frozen_cash=200)
    data=dict(positions=[stock,etf],orders=[order],trades=[trade],account=[account])
    return dict(identity=IDENTITY,responses={key:[dict(http_status=200,request_id="nqb-fixture:"+key,ok=True,complete=True,source=IDENTITY,observed_at="2026-10-22T01:36:00Z",data=rows)] for key,rows in data.items()})
def write(root,value,request_ms=300,round_ms=1500,enabled=True,max_rows=128,raw_text=None):
    root.mkdir(parents=True,exist_ok=False)
    objects={"fixture.json":value,"sessions.json":{"DAY":{"name":"synthetic-day","offset":0,"sections":[{"from":930,"to":1130},{"from":1300,"to":1500}]}},
    "commodities.json":{"SSE":{"STK":{"name":"synthetic-stock","session":"DAY","holiday":"CHINA","category":0,"pricetick":.01,"volscale":1,"covermode":0,"pricemode":0,"trademode":2},"ETF":{"name":"synthetic-T0-test","session":"DAY","holiday":"CHINA","category":0,"pricetick":.001,"volscale":1,"covermode":0,"pricemode":0,"trademode":1}}},
    "contracts.json":{"SSE":{"600000":{"name":"synthetic-stock","exchg":"SSE","product":"STK","opendate":20000101,"expiredate":20991231},"510300":{"name":"synthetic-T0-test","exchg":"SSE","product":"ETF","opendate":20000101,"expiredate":20991231}}},
    "config.json":dict(module="TraderQMTReadOnly",user="",password="",savedata=False,enabled=enabled,source="fixture",adapter_id="nqb",instance_id="nqb-fixture",fixture=str(root/"fixture.json"),request_ms=request_ms,round_ms=round_ms,max_rows=max_rows)}
    for name,obj in objects.items():(root/name).write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
    if raw_text is not None:(root/"fixture.json").write_text(raw_text,encoding="utf-8")
def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path);p.add_argument('--minimal',action='store_true');p.add_argument('--only',nargs='+');arguments(p);args=p.parse_args()
    probe,library,cwd,build,binary_identity=resolve(args,root=ROOT)
    cases=[]
    def case(name,edit=None,mode="normal",expect="ready",**kwargs):
        value=copy.deepcopy(fixture())
        if edit:edit(value)
        cases.append((name,value,mode,expect,kwargs))
    case("happy")
    case("empty",lambda f:[f["responses"][k][0].update(data=[]) for k in ("positions","orders","trades")])
    case("stop-before",mode="stop-before",expect="stopped")
    if not args.minimal:
        case("new-instance")
        for stage in ("positions","orders","trades","account"):
            case("source-failure-"+stage,lambda f,s=stage:f["responses"][s][0].update(ok=False),expect="failed")
            case("incomplete-"+stage,lambda f,s=stage:f["responses"][s][0].update(complete=False),expect="failed")
            case("wrong-request-"+stage,lambda f,s=stage:f["responses"][s][0].update(request_id="another-request"),expect="failed")
        for mode in ("stop-position","stop-order","stop-trade","stop-ready"):
            case(mode,mode=mode,expect="stopped")
        case("stop-pending",lambda f:f.update(delay_ms=500),mode="stop-pending",expect="stopped")
        case("late-result",lambda f:f.update(delay_ms=5),mode="late-result",expect="stopped")
        case("release-ready",mode="release-ready",expect="stopped")
        case("null-data",lambda f:f["responses"]["orders"][0].update(data=None),expect="failed")
        case("http-failure",lambda f:f["responses"]["orders"][0].update(http_status=500),expect="failed")
        case("row-budget",expect="failed",max_rows=1)
        case("long-identity",lambda f:f["responses"]["orders"][0]["data"][0].update(order_id="x"*64),expect="failed")
        case("fractional-order",lambda f:f["responses"]["orders"][0]["data"][0].update(quantity=200.25),expect="failed")
        case("order-conservation",lambda f:f["responses"]["orders"][0]["data"][0].update(remaining=129),expect="failed")
        case("duplicate-order",lambda f:f["responses"]["orders"][0]["data"].append(copy.deepcopy(f["responses"]["orders"][0]["data"][0])))
        case("conflicting-order",lambda f:f["responses"]["orders"][0]["data"].append(dict(f["responses"]["orders"][0]["data"][0],remaining=0,filled=200,state="filled")),expect="failed")
        case("duplicate-position",lambda f:f["responses"]["positions"][0]["data"].append(copy.deepcopy(f["responses"]["positions"][0]["data"][0])),expect="failed")
        case("json-malformed",expect="init-failed",raw_text="{")
        case("json-duplicate-key",expect="init-failed",raw_text='{"identity":1,"identity":2}')
        case("response-byte-budget",expect="init-failed",raw_text=" "*(1024*1024+1))
        case("202-exhausted",lambda f:f["responses"].update(orders=[dict(http_status=202,request_id="nqb-fixture:orders")]*16),expect="failed")
        case("throw-ready",mode="throw-ready",expect="failed-ready")
        case("202-same-request",lambda f:f["responses"]["orders"].insert(0,dict(http_status=202,request_id="nqb-fixture:orders")))
        case("202-no-result",lambda f:f["responses"].update(orders=[dict(http_status=202,request_id="nqb-fixture:orders")]),expect="failed")
        case("timeout",lambda f:f.update(delay_ms=500),expect="failed",request_ms=10,round_ms=100)
        case("callback-delayed",lambda f:f.update(delay_ms=5))
        case("missing-price",lambda f:f["responses"]["orders"][0]["data"][0].pop("price"),expect="failed")
        case("missing-trade-id",lambda f:f["responses"]["trades"][0]["data"][0].pop("trade_id"),expect="failed")
        case("missing-previous",lambda f:f["responses"]["positions"][0]["data"][0].pop("previous"),expect="failed")
        case("negative",lambda f:f["responses"]["positions"][0]["data"][0].update(total=-1),expect="failed")
        case("fractional",lambda f:f["responses"]["positions"][0]["data"][0].update(total=700.5),expect="failed")
        case("unknown-contract",lambda f:f["responses"]["positions"][0]["data"][0].update(code="999999"),expect="failed")
        case("invalid-t1-available",lambda f:f["responses"]["positions"][0]["data"][0].update(available_today=1),expect="failed")
        case("missing-source-proof",lambda f:f["responses"]["positions"][0]["data"][0].update(position_semantics="opening_yesterday"),expect="failed")
        case("bad-observation-time",lambda f:f["responses"]["orders"][0].update(observed_at="2026-02-30T25:90:00Z"),expect="failed")
        case("reordered-source",lambda f:f["responses"]["orders"][0].update(source=dict(reversed(list(IDENTITY.items())))))
        case("bad-date",lambda f:f["responses"]["orders"][0]["data"][0].update(date=20260230),expect="failed")
        case("bad-time",lambda f:f["responses"]["trades"][0]["data"][0].update(time=256000000),expect="failed")
        case("changed-session",lambda f:f["responses"]["trades"][0].update(source=dict(IDENTITY,session="new-session")),expect="failed")
        case("cross-day",lambda f:f["responses"]["trades"][0]["data"][0].update(date=20261023),expect="failed")
        case("missing-account",lambda f:f["responses"]["account"][0].update(data=[]),expect="failed")
        case("missing-cash",lambda f:f["responses"]["account"][0]["data"][0].pop("available"),expect="failed")
        case("account-presence",lambda f:[f["responses"]["account"][0]["data"][0].pop(k) for k in ("previous_balance","commission","frozen_cash")])
        case("duplicate-trade",lambda f:f["responses"]["trades"][0]["data"].append(copy.deepcopy(f["responses"]["trades"][0]["data"][0])))
        case("conflicting-trade",lambda f:f["responses"]["trades"][0]["data"].append(dict(f["responses"]["trades"][0]["data"][0],price=12)),expect="failed")
        case("external-order",lambda f:f["responses"]["orders"][0]["data"][0].pop("user_tag"))
        case("unknown-order-state",lambda f:f["responses"]["orders"][0]["data"][0].update(state="future-code"),expect="failed")
        for state in ("accepted","filled","canceled","rejected","canceling"):
            values=dict(accepted=(0,200,0),filled=(200,0,0),canceled=(70,0,130),rejected=(0,0,200),canceling=(70,130,0))[state]
            case("order-"+state,lambda f,s=state,v=values:f["responses"]["orders"][0]["data"][0].update(state=s,filled=v[0],remaining=v[1],inactive=v[2]))
        case("disabled",expect="init-failed",enabled=False)
    if args.only:
        if set(args.only)-{row[0] for row in cases}:raise ValueError('unknown fixture selection')
        cases=[row for row in cases if row[0] in args.only]
    runroot=build/('cases-'+str(time.time_ns()));runroot.mkdir();results=[]
    for name,value,mode,expect,kwargs in cases:
        path=runroot/name;write(path,value,**kwargs);start=time.monotonic()
        run=subprocess.run([str(probe),str(path),str(library),mode],cwd=cwd,capture_output=True,timeout=10)
        (path/'process.log').write_bytes(run.stdout+run.stderr)
        verify(binary_identity)
        output=json.loads((path/'result.json').read_text(encoding='utf-8')) if (path/'result.json').exists() else {}
        errors=[]
        def check(ok,label):
            if not ok:errors.append(label)
        check(run.returncode==0,'process-exit-'+str(run.returncode))
        if expect=='init-failed':check(not output.get('initialized'),'init-refused')
        else:
            for key,val in dict(joined=1,worker_live=0,queue=0,write_rejections=2,trade_pushes=0,order_pushes=0).items():check(output.get(key)==val,key)
            check(output.get('threads_after')==output.get('threads_before'),'threads-reclaimed')
            check(output.get('close_ms',10000)<500,'bounded-interruptible-close')
            if name=='late-result':check(output.get('preclose_results')==1 and output.get('discarded')>=1 and output.get('delivered')==0,'late-result-discarded')
            if name=='timeout':check(output.get('observed_ms',10000)<500 and '单项' in output.get('reason',''),'request-deadline')
            if expect=='ready':
                check(output.get('ready')==1 and output.get('delivered')==15 and output.get('error')==0,'ready-chain')
                check(output.get('reentrant')==-7,'pump-reentry-rejected')
                check(output.get('lost')==1,'ready-close-notified')
                if name=='empty':check(output.get('position')==0 and output.get('orders')==0,'empty-native')
                else:
                    check(output.get('position')==700 and output.get('available')==420,'native-stock')
                    check(output.get('etf_position')==37 and output.get('etf_available')==27,'native-etf')
                    check(output.get('balance')==100000 and output.get('dynbalance')==100000 and output.get('cash')==82000,'account-equity')
                if name=='happy':check(output.get('rows_2')==1 and output.get('observed_2')=='2026-10-22T01:36:00Z','preserved-observation');check(output.get('orders')==1 and output.get('undone')==130 and output.get('order_price')==10.35,'native-order')
                if name=='external-order':check(output.get('orders')==0 and output.get('undone')==0,'external-ownership')
                if name=='account-presence':check(output.get('account_presence')==3,'unknown-fields-presence')
                if name=='202-same-request':check(output.get('reads')==4 and output.get('polls')==1,'same-request-poll')
            elif expect.startswith('failed'):
                check(output.get('error',0)<0,'failure-classified')
                if expect=='failed':check(output.get('ready')==0,'failure-no-ready')
                else:check(output.get('lost')==1,'failed-ready-close-notified')
            elif expect=='stopped':check(output.get('ready')==(1 if mode in ('stop-ready','release-ready') else 0),'stop-stage')
        result=dict(case=name,passed=not errors,errors=errors,elapsed_ms=round((time.monotonic()-start)*1000),output=output);results.append(result);print(name,'PASS' if not errors else 'FAIL '+','.join(errors),flush=True)
    report=dict(binary_inputs=binary_identity,cwd=str(cwd),passed=sum(r['passed'] for r in results),failed=sum(not r['passed'] for r in results),skipped=0,transport="fixture",network_transport_present=False,results=results)
    (runroot/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');print('RESULT',runroot,report['passed'],report['failed']);return bool(report['failed'])
if __name__=='__main__':raise SystemExit(main())
