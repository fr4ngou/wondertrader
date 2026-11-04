"""数据侧将已完成QAB原件导入WT日线；不连接来源、不计算前复权或指标。"""
import base64
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import time

from .qmt_minute_import import import_dataset
from .native_history import _parse_source_receipt
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.daily_contract import REFERENCE_PREFIX,source_daily_symbol


def prepare_analysis_capture(capture,output,helper_sha256,*,deadline,
        max_input_bytes=268435456,max_total_bars=2000000,existing_stores=(),resume=False):
    """独占工作根保存转换输入和谱系，返回冻结准备收据；不调用原生写入或来源。

    capture为数据侧已完成且消费确认的原批次目录，deadline为单调绝对秒。
    max_input_bytes包含清单及全部slot，max_total_bars跨两种价格口径计数。
    existing_stores显式传入同一捕获已完成的原QMI根及固定收据SHA，逐根复用。
    收据按原Reader规则完整准入一次，确认捕获、价格口径及原Helper身份；
    原数据文件仍在实际Reader读取时逐文件核验，不重复转换或扫描已完成口径。
    resume显式续接同捕获的未成功根，复核已转换输入及原生文件，仅写未完成证券。
    新作业使用新根；未完成工作保留供核查，后继仅写缺少口径。
    调用方先确认上代作业关闭，保持原成功根不可修改；发布者拥有读取指针。
    转换成功独立保存，后继直接消费准备收据，不重复扫描原捕获或转换CSV。
    编码沿同一外部作业截止；准备后的原生调用及进程收尾归外层Job。
    """
    def check():
        if time.monotonic()>=deadline:raise TimeoutError('analysis import deadline expired')
    def read(path,maximum):
        check();before=path.stat()
        if before.st_size>maximum:raise ValueError('analysis import input capacity')
        with path.open('rb')as stream:body=stream.read(before.st_size+1)
        after=path.stat()
        if (len(body)>maximum or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)):
            raise ValueError('analysis import input changed')
        check();return body
    digest=lambda body:hashlib.sha256(body).hexdigest()
    if type(max_input_bytes)is not int or not 1<=max_input_bytes<=1073741824:
        raise ValueError('analysis import byte budget invalid')
    if type(max_total_bars)is not int or not 1<=max_total_bars<=10000000:
        raise ValueError('analysis import row budget invalid')
    capture=Path(capture).resolve(strict=True);output=Path(output).absolute()
    body=read(capture/'manifest.json',min(16777216,max_input_bytes));manifest=strict_json(body)
    capture_sha=digest(body)
    if (manifest.get('schema')!='guanheng.observation-qas-batch-capture.v1'
            or manifest.get('source_kind')not in ('actual-qmt','sdk-synthetic')
            or type(manifest.get('batches'))is not list or not 1<=len(manifest['batches'])<=20000):
        raise ValueError('analysis import capture invalid')
    total_bytes=len(body);seen=set()
    for batch in manifest['batches']:
        path=(capture/batch['slot']).resolve(strict=True)
        if not path.is_relative_to(capture)or path in seen:raise ValueError('analysis import slot path invalid')
        seen.add(path);total_bytes+=path.stat().st_size
        if total_bytes>max_input_bytes:raise ValueError('analysis import input capacity')
    # 认证、原ID、结果、消费与投影继续复用数据接入模块的唯一准入。
    from guanheng_qmt_shm.analysis_batch_source import read_capture
    verified=read_capture(capture);check()
    if verified!=manifest or digest(read(capture/'manifest.json',16777216))!=capture_sha:
        raise ValueError('analysis import capture changed')
    request=manifest['request'];symbols=request['symbols']
    if type(symbols)is not list or not 1<=len(symbols)<=10000 or len(set(symbols))!=len(symbols):
        raise ValueError('analysis import securities invalid')
    for symbol in symbols:source_daily_symbol(symbol)
    def profile_for(adjustment):
        return dict(provider='Qmt',instance_id='qmt-batch-source:'+capture_sha[:32],
            session_id=request['capture_id'],generation=1,dataset_version='qmt.batch-native-day.v1',
            source_license='unknown',input_kind='qmt_export'if manifest['source_kind']=='actual-qmt'else'synthetic',
            timezone='Asia/Shanghai',minute_boundary='unknown',adjustment=adjustment,
            factor_version=''if adjustment=='none'else REFERENCE_PREFIX+capture_sha,
            value_semantics='source',price_unit='unknown',volume_unit='unknown',amount_unit='unknown')
    if type(existing_stores)not in (tuple,list)or len(existing_stores)>2:
        raise ValueError('analysis import existing store list invalid')
    reused={};rows=0
    for descriptor in existing_stores:
        if type(descriptor)is not dict or set(descriptor)!={'store_root','import_receipt_sha256'}:
            raise ValueError('analysis import existing store descriptor invalid')
        root=Path(descriptor['store_root']).resolve(strict=True)
        raw=read(root/'qmt-import.json',16777216)
        if digest(raw)!=descriptor['import_receipt_sha256']:
            raise ValueError('analysis import existing receipt differs')
        profile,_,daily,entries=_parse_source_receipt(raw)
        adjustment=profile['adjustment'];receipt=strict_json(raw)
        observed={s for s in symbols if manifest['securities'][s][adjustment]['status']=='observed'}
        if (not daily or adjustment in reused or receipt['schema_version']!=4
                or profile!=profile_for(adjustment)or receipt['helper_sha256']!=helper_sha256
                or set(entries)!=observed or any(e['count']>request['max_rows']for e in entries.values())):
            raise ValueError('analysis import existing store belongs to another input')
        rows+=sum(e['count']for e in entries.values())
        reused[adjustment]=dict(store_root=str(root),import_receipt_sha256=digest(raw))
    if rows>max_total_bars:raise ValueError('analysis import row capacity')
    if type(resume)is not bool:raise ValueError('analysis import resume flag invalid')
    if output.exists():
        if not resume or (output/'RESULT.json').exists():
            raise FileExistsError('analysis import output is not an incomplete work root')
        previous=strict_json(read(output/'PROGRESS.json',16777216))
        if previous['capture_sha256']!=capture_sha or previous['source_kind']!=manifest['source_kind']:
            raise ValueError('analysis import previous input differs')
    else:
        if resume:raise FileNotFoundError('analysis import previous work root missing')
        output.mkdir(parents=False,exist_ok=False)
    def save_input(path,body):
        if path.exists():
            if not resume or read(path,max_input_bytes)!=body:
                raise ValueError('analysis import previous converted input differs')
        else:path.write_bytes(body)
    sources={};projections={a:{}for a in ('none','front_ratio')if a not in reused}
    for adjustment in projections:
        path=output/('input-'+adjustment);path.mkdir(exist_ok=resume);sources[adjustment]=path
    progress=output/'PROGRESS.json';lineage=[]
    def publish_progress(state):
        payload=dict(state=state,rows=rows,source_kind=manifest['source_kind'],input_bytes=total_bytes,
            capture_sha256=capture_sha,reused_price_bases=sorted(reused),
            completed_securities={k:len(v)for k,v in projections.items()})
        temporary=progress.with_suffix('.next');temporary.write_text(json.dumps(payload),'utf8');temporary.replace(progress)
    publish_progress('converting')
    for batch in manifest['batches']:
        check();adjustment=batch['adjustment']
        if adjustment not in ('none','front_ratio'):raise ValueError('analysis import price basis invalid')
        lineage.append(dict(batch_id=batch['batch_id'],adjustment=adjustment,slot=str(capture/batch['slot']),
            sha256=batch['sha256'],request_id=batch['request_id'],request_body_sha256=batch['request_body_sha256'],
            result_body_sha256=batch['result_body_sha256'],binding=batch['binding'],received_at=batch['received_at']))
        if adjustment in reused:continue
        slot_body=read(capture/batch['slot'],max_input_bytes)
        if digest(slot_body)!=batch['sha256']:raise ValueError('analysis import slot changed')
        slot=strict_json(slot_body);native_body=base64.b64decode(slot['result']['result_body_b64'],validate=True)
        if digest(native_body)!=batch['result_body_sha256']:raise ValueError('analysis import result changed')
        native=strict_json(native_body)['data']['securities']
        for symbol in batch['symbols']:
            check()
            if symbol not in manifest['securities']or symbol in projections[adjustment]:
                raise ValueError('analysis import repeated projection')
            item=native[symbol];projection=manifest['securities'][symbol][adjustment]
            if projection['batch_id']!=batch['batch_id']or projection['status']!=item['status']:
                raise ValueError('analysis import projection differs')
            values=item['data']
            if item['status']!='observed' or not values:
                if values:raise ValueError('analysis import unavailable values')
                projections[adjustment][symbol]=dict(status=item['status'],rows=0)
                continue
            if type(values)is not dict or len(values)>request['max_rows']:
                raise ValueError('analysis import row count invalid')
            stream=io.StringIO(newline='');writer=csv.writer(stream)
            writer.writerow(['timestamp','open','high','low','close','volume','amount'])
            for day,bar in sorted(values.items()):
                check();rows+=1
                if rows>max_total_bars:raise ValueError('analysis import row capacity')
                if type(day)is not str or len(day)!=8 or datetime.strptime(day,'%Y%m%d').strftime('%Y%m%d')!=day:
                    raise ValueError('analysis import source date invalid')
                if not request['start_date']<=day<=request['end_date']:raise ValueError('analysis import source date outside window')
                if set(bar)!={'open','high','low','close','volume','amount'}:raise ValueError('analysis import bar fields invalid')
                writer.writerow([day[:4]+'-'+day[4:6]+'-'+day[6:]+'T00:00:00+08:00',
                    *[bar[k]for k in ('open','high','low','close','volume','amount')]])
            csv_body=stream.getvalue().encode('utf8');path=sources[adjustment]/(symbol+'.csv');save_input(path,csv_body)
            projections[adjustment][symbol]=dict(status='observed',rows=len(values),path=path.name,sha256=digest(csv_body))
        publish_progress('converting')
    if any(set(values)!=set(symbols)for values in projections.values()):
        raise ValueError('analysis import incomplete projection set')
    native_inputs=[]
    for adjustment,items in projections.items():
        check();securities=[dict(symbol=s,chunks=[dict(path=v['path'],sha256=v['sha256'])])for s,v in items.items()if v['rows']]
        if not securities:raise ValueError('analysis import has no observed securities')
        profile=profile_for(adjustment)
        path=sources[adjustment]/'manifest.json'
        manifest_body=json.dumps(dict(schema_version=4,period='1d',profile=profile,securities=securities)).encode('utf8')
        save_input(path,manifest_body)
        native_inputs.append(dict(
            adjustment=adjustment,  # 本清单保存的来源价格口径，原价与前复权分别写入。
            manifest=str(path.relative_to(output)),  # 准备根内的原QMI清单相对路径。
            manifest_sha256=digest(manifest_body),  # 已转换CSV身份集合；QMI消费时逐块核对。
            store='store-'+adjustment))  # 本准备根内独占原生输出位置。
    original=dict(capture=str(capture),capture_sha256=capture_sha,source_kind=manifest['source_kind'],
        request=request,batches=lineage,source_received_at=max((b['received_at']for b in lineage),key=datetime.fromisoformat),
        price_reference='supplier front_ratio captured in original response; independent factors not requested')
    (output/'PROVENANCE.json').write_text(json.dumps(original,indent=2),'utf8')
    preparation=dict(
        schema='guanheng.qmt-analysis-conversion.v1',  # 转换完成和原生入库分别登记的固定合同。
        provenance_sha256=digest((output/'PROVENANCE.json').read_bytes()),  # 原捕获/请求/批次谱系的固定身份。
        helper_sha256=helper_sha256,  # 后继原生写入必须使用的原Helper身份。
        rows=rows,  # 原价及前复权全部实际行数，含已复用成功库。
        securities=len(symbols),  # 原请求定日股票池数量，独立于单口径可读证券数。
        existing_stores=list(reused.values()),  # 已完成口径及固定收据SHA，后继保持只读。
        native_inputs=native_inputs)  # 尚需原生入库的完整QMI输入集合。
    check();target=output/'CONVERSION.json';raw=json.dumps(preparation,indent=2).encode('utf8')
    save_input(target,raw);publish_progress('prepared')
    return dict(path=str(target),sha256=digest(raw))


def complete_analysis_import(preparation,expected_sha256,helper,helper_sha256,*,deadline,
        max_input_bytes=268435456,max_total_bars=2000000):
    """消费冻结转换收据并写原WT库；原生中断按原QMI逐证券续接，成功口径直接复用。

    本阶段不读QAB slot、不重做转换。expected_sha256由准备阶段或原作业记录提供。
    调用方保证原作业已关闭和输出根独占；原Helper/CSV/已有DSB验证与最终收据沿同一QMI。
    """
    def read(path,maximum=16777216):
        if time.monotonic()>=deadline:raise TimeoutError('analysis native import deadline expired')
        before=path.stat()
        if before.st_size>maximum:raise ValueError('analysis native input capacity')
        with path.open('rb')as stream:raw=stream.read(before.st_size+1)
        after=path.stat()
        if len(raw)>maximum or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ValueError('analysis native input changed')
        if time.monotonic()>=deadline:raise TimeoutError('analysis native import deadline expired')
        return raw
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    preparation=Path(preparation).resolve(strict=True);output=preparation.parent
    raw=read(preparation)
    if sha(raw)!=expected_sha256:raise ValueError('analysis conversion receipt differs')
    plan=strict_json(raw)
    if (set(plan)!={'schema','provenance_sha256','helper_sha256','rows','securities','existing_stores','native_inputs'}
            or plan['schema']!='guanheng.qmt-analysis-conversion.v1'or plan['helper_sha256']!=helper_sha256
            or type(plan['rows'])is not int or not 1<=plan['rows']<=max_total_bars
            or type(plan['securities'])is not int or not 1<=plan['securities']<=10000
            or type(plan['existing_stores'])is not list or type(plan['native_inputs'])is not list
            or len(plan['existing_stores'])+len(plan['native_inputs'])!=2):
        raise ValueError('analysis conversion receipt invalid')
    raw=read(output/'PROVENANCE.json')
    if sha(raw)!=plan['provenance_sha256']:raise ValueError('analysis conversion provenance differs')
    original=strict_json(raw);capture_sha=original['capture_sha256'];request=original['request']
    if sha(read(Path(original['capture'])/'manifest.json'))!=capture_sha:
        raise ValueError('analysis conversion source capture differs')
    stores={};total_rows=0
    def completed(root,expected=None,document=None):
        nonlocal total_rows
        raw=read(root/'qmt-import.json')
        if expected is not None and sha(raw)!=expected:raise ValueError('analysis completed receipt differs')
        value=strict_json(raw);profile,_,daily,entries=_parse_source_receipt(raw);basis=profile['adjustment']
        if (not daily or value['schema_version']!=4 or value['helper_sha256']!=helper_sha256
                or basis not in ('none','front_ratio')or basis in stores
                or profile['instance_id']!='qmt-batch-source:'+capture_sha[:32]
                or profile['session_id']!=request['capture_id']
                or profile['factor_version']!=(''if basis=='none'else REFERENCE_PREFIX+capture_sha)):
            raise ValueError('analysis completed source profile differs')
        if document is not None:
            body,parsed=document
            if (value['manifest_sha256']!=sha(body)or profile!=parsed['profile']
                    or {s:e['chunks']for s,e in entries.items()}!={s['symbol']:s['chunks']for s in parsed['securities']}):
                raise ValueError('analysis completed converted input differs')
        total_rows+=sum(e['count']for e in entries.values())
        stores[basis]=dict(store_root=str(root),import_receipt_sha256=sha(raw))
    for item in plan['existing_stores']:
        if type(item)is not dict or set(item)!={'store_root','import_receipt_sha256'}:
            raise ValueError('analysis existing store descriptor invalid')
        completed(Path(item['store_root']).resolve(strict=True),item['import_receipt_sha256'])
    for item in plan['native_inputs']:
        if type(item)is not dict or set(item)!={'adjustment','manifest','manifest_sha256','store'}:
            raise ValueError('analysis native input descriptor invalid')
        basis=item['adjustment']
        if basis not in ('none','front_ratio')or basis in stores:
            raise ValueError('analysis native input price basis invalid')
        paths=[]
        for name in ('manifest','store'):
            path=Path(item[name])
            if path.is_absolute()or '..'in path.parts:raise ValueError('analysis native input path invalid')
            path=(output/path).resolve()
            if not path.is_relative_to(output):raise ValueError('analysis native input path escaped')
            paths.append(path)
        manifest,root=paths;body=read(manifest)
        if sha(body)!=item['manifest_sha256']:raise ValueError('analysis native manifest differs')
        document=strict_json(body)
        if document['profile']['adjustment']!=basis:raise ValueError('analysis native manifest basis differs')
        if not (root/'qmt-import.json').exists():
            import_dataset(manifest,root,helper,helper_sha256,max_bars=request['max_rows'],
                max_input_bytes=max_input_bytes,max_total_bars=max_total_bars,
                resume_manifest_sha256=item['manifest_sha256']if root.exists()else None)
        completed(root,document=(body,document))
    if set(stores)!={'none','front_ratio'}or total_rows!=plan['rows']:
        raise ValueError('analysis native completed coverage differs')
    result=dict(schema='guanheng.qmt-analysis-native-import.v1',state='completed',capture_sha256=capture_sha,
        observation_date=request['end_date'],source_kind=original['source_kind'],rows=total_rows,securities=plan['securities'],
        stores=[stores[basis]for basis in ('none','front_ratio')],source_received_at=original['source_received_at'],
        SDK_calls=0,financial_commands=0)
    read(preparation)
    body=json.dumps(result,indent=2).encode('utf8');target=output/'RESULT.json'
    if target.exists()and strict_json(target.read_bytes())!=result:raise ValueError('analysis completed result already differs')
    if not target.exists():
        pending=target.with_suffix('.next');pending.write_bytes(body);pending.replace(target)
    progress=output/'PROGRESS.json'
    value=strict_json(progress.read_bytes())if progress.exists()else{}
    value.update(state='completed',rows=total_rows,capture_sha256=capture_sha,
        preparation_sha256=expected_sha256)
    pending=progress.with_suffix('.next');pending.write_text(json.dumps(value),'utf8');pending.replace(progress)
    return result


def import_analysis_capture(capture,output,helper,helper_sha256,*,deadline,
        max_input_bytes=268435456,max_total_bars=2000000,existing_stores=(),resume=False):
    """完整主入口：先持久保存转换阶段，再沿冻结准备收据执行原生导入。

    resume在调用方确认原Job关闭后使用；已有CONVERSION时直接续接原生阶段。
    源调用、金融命令、当前服务指针均不属于此接口。
    """
    path=Path(output)/'CONVERSION.json'
    if resume and path.exists():
        descriptor=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        original=strict_json((path.parent/'PROVENANCE.json').read_bytes())
        if Path(capture).resolve(strict=True)!=Path(original['capture']).resolve(strict=True):
            raise ValueError('analysis previous capture path differs')
    else:
        descriptor=prepare_analysis_capture(capture,output,helper_sha256,deadline=deadline,
            max_input_bytes=max_input_bytes,max_total_bars=max_total_bars,existing_stores=existing_stores,resume=resume)
    return complete_analysis_import(descriptor['path'],descriptor['sha256'],helper,helper_sha256,deadline=deadline,
        max_input_bytes=max_input_bytes,max_total_bars=max_total_bars)
