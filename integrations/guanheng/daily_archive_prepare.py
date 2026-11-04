"""将明确来源的日线缺口写为既有WT静态DSB归档；不覆盖已导入商店。"""
from datetime import datetime
import hashlib,json,math,re,time
from pathlib import Path
from .qmt_minute_import import _Native
from .native_history import WTSBar
from ..guanheng_market_client.source_history import validate_source_metadata


def prepare_daily_archive(securities,metadata,output,helper,helper_sha256,*,deadline,provenance=None):
    """写入独占新目录，原Helper写读一致后发布旧daily-native-archive合同。

    securities是最多10000个symbol到有序日线记录的字典；metadata为对应来源
    的source/单位/原价资格，content_id绑定调用方保留的来源原件。仅接收已知
    原数值，不把缺成交股数或金额转成零；调用方在定日事实另列这些状态。
    """
    if type(securities)is not dict or not 1<=len(securities)<=10000:raise ValueError('daily archive securities invalid')
    validate_source_metadata(metadata,period='1d')
    if metadata['adjustment']!='none':raise ValueError('daily archive requires explicit original price')
    if provenance is not None and (type(provenance)is not dict or set(provenance)!=set(securities)):
        raise ValueError('daily archive provenance securities differ')
    output=Path(output);output.mkdir(parents=False,exist_ok=False);entries=[];total=0
    native=_Native(helper,helper_sha256)
    try:
        for symbol,rows in sorted(securities.items()):
            if time.monotonic()>=deadline:raise TimeoutError('daily archive deadline expired')
            if re.fullmatch(r'(SSE|SZSE)\.[0-9]{6}',symbol)is None or not 1<=len(rows)<=2000:raise ValueError('daily archive security or rows invalid')
            bars=[];last=0
            for row in rows:
                if set(row)!={'date','open','high','low','close','volume','amount'}:raise ValueError('daily archive row fields invalid')
                day=row['date'];datetime.strptime(str(day),'%Y%m%d')
                if type(day)is not int or day<=last:raise ValueError('daily archive dates not ordered')
                last=day
                values=[row[k]for k in ('open','high','low','close','volume','amount')]
                if any(type(v)not in(int,float)or not math.isfinite(v)for v in values)or min(values[:4])<=0 or min(values[4:])<0:
                    raise ValueError('daily archive numeric input invalid')
                if row['low']>min(row['open'],row['close'])or row['high']<max(row['open'],row['close'])or row['low']>row['high']:
                    raise ValueError('daily archive OHLC invalid')
                bar=WTSBar();bar.date=day;bar.time=0
                for key in ('open','high','low','close'):setattr(bar,key,row[key])
                bar.vol=row['volume'];bar.money=row['amount'];bars.append(bar)
            total+=len(bars)
            if total>1000000:raise ValueError('daily archive row budget exceeded')
            parts=[dict(offset=0,count=len(bars),metadata=metadata)]if provenance is None else provenance[symbol]
            covered=0
            for part in parts:
                if (type(part)is not dict or set(part)!={'offset','count','metadata'}or part['offset']!=covered
                        or type(part['count'])is not int or part['count']<1):raise ValueError('daily archive provenance invalid')
                validate_source_metadata(part['metadata'],period='1d')
                if part['metadata']['adjustment']!='none':raise ValueError('daily archive provenance price basis differs')
                covered+=part['count']
            if covered!=len(bars):raise ValueError('daily archive provenance rows differ')
            name=symbol+'.dsb';path=output/name;native.write_verify(path,bars,period='1d')
            entries.append(dict(symbol=symbol,  # WT证券身份；仅本次真实缺数集。
                path=name,  # 新目录内相对DSB路径。
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),  # 原Helper真实回读后的DSB身份。
                rows=len(bars),  # 实际已存条数；缺值日期未被补零。
                first=rows[0]['date'],last=rows[-1]['date'],  # 原件实际首尾日。
                provenance=parts))  # 每段行绑定其原供应商事实与单位，旧历史保持。
    finally:native.close()
    encode=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    path=output/'archive.json';body=encode(dict(schema='guanheng.daily-native-archive.v1',entries=entries));path.write_bytes(body)
    return dict(path=str(path.absolute()),sha256=hashlib.sha256(body).hexdigest())
