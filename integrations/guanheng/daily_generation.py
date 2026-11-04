"""冻结QAB转换→独立WT日线版本；相同CSV复用原DSB，仅变化证券调用原Helper。"""
from pathlib import Path
import hashlib,json,os,time,uuid
from ..guanheng_market_client import strict_json
from ..guanheng_market_client.source_history import validate_source_metadata
from .native_history import _parse_source_receipt
from .qmt_minute_import import _Native,_manifest,_rows,_chunk_path
from .price_quality import PriceRangeQuality
from .native_history import NativeHistory, source_file_metadata
from ..guanheng_market_client.daily_contract import source_daily_security


def materialize_generation(preparation,previous_stores,output,helper,helper_sha256,*,deadline,resume=False,previous_archives=(),native_reader=None):
    """prepared(path/sha256)绑定原转换；旧根只读，output为新独占版本或同身份续接。

    previous_stores是原成功QMI根/收据SHA，previous_archives是本实现的v2目录。
    CSV完整SHA、口径、单位和原Helper一致才复用DSB；每份旧DSB仍核完整SHA。
    新/复用证券完成后原子写单项收据；未知中断文件保留改名，再写本次新文件。
    全部完成才写archive与RESULT；同一准备身份续接，既有已完成版本直接核回执。
    native_reader为原文件Reader的library/sha256；有旧档时必须声明，用于确认历史日期。
    当前缓存遗漏旧日期时拒绝发布，保留旧版本；完全未出现的旧键沿原DSB/来源复制保留。
    """
    def check():
        if time.monotonic()>=deadline:raise TimeoutError('daily generation deadline expired')
    sha=lambda body:hashlib.sha256(body).hexdigest()
    encode=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    def read(path,identity=None,maximum=16777216):
        check();path=Path(path);before=path.stat()
        if before.st_size>maximum:raise ValueError('daily generation file budget exceeded')
        with path.open('rb')as stream:body=stream.read(before.st_size+1)
        after=path.stat()
        if (len(body)>maximum or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns)
                or identity is not None and sha(body)!=identity):raise ValueError('daily generation input changed')
        check();return body
    def save(path,value):
        pending=path.with_suffix(path.suffix+'.next');pending.write_bytes(encode(value));pending.replace(path)
    source=Path(preparation['path']).resolve(strict=True);plan=strict_json(read(source,preparation['sha256']))
    if plan['schema']!='guanheng.qmt-analysis-conversion.v1'or plan['helper_sha256']!=helper_sha256 or plan['existing_stores']:
        raise ValueError('daily generation conversion contract differs')
    provenance=strict_json(read(source.parent/'PROVENANCE.json',plan['provenance_sha256']))
    if sha(read(Path(provenance['capture'])/'manifest.json'))!=provenance['capture_sha256']:raise ValueError('daily generation original capture changed')
    if (previous_stores or previous_archives) and (type(native_reader)is not dict or set(native_reader)!={'library','sha256'}):
        raise ValueError('daily generation previous history requires original reader')
    output=Path(output).absolute();intent=dict(schema='guanheng.daily-generation-intent.v1',preparation=preparation,previous_stores=list(previous_stores),previous_archives=list(previous_archives),helper_sha256=helper_sha256,native_reader=native_reader)
    if output.exists():
        if not resume or strict_json(read(output/'INTENT.json'))!=intent:raise ValueError('daily generation owner or intent differs')
    else:output.mkdir(parents=False);save(output/'INTENT.json',intent)
    if (output/'PROVENANCE.json').exists():read(output/'PROVENANCE.json',plan['provenance_sha256'])
    else:(output/'PROVENANCE.json').write_bytes(read(source.parent/'PROVENANCE.json',plan['provenance_sha256']))
    if (output/'RESULT.json').exists():
        result=strict_json(read(output/'RESULT.json'));read(result['archive']['path'],result['archive']['sha256']);return result
    previous={};comparable=('adjustment','timezone','minute_boundary','value_semantics','price_unit','volume_unit','amount_unit')
    for store in previous_stores:
        root=Path(store['store_root']).resolve(strict=True);body=read(root/'qmt-import.json',store['import_receipt_sha256']);receipt=strict_json(body)
        profile,_,daily,entries=_parse_source_receipt(body)
        if not daily or receipt['schema_version']!=4 or receipt['helper_sha256']!=helper_sha256:raise ValueError('daily generation previous native layout differs')
        for symbol,entry in entries.items():
            if len(entry['chunks'])!=1:continue
            code,market=symbol.split('.');security={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code;key=(security,profile['adjustment'])
            if key in previous:raise ValueError('daily generation previous price source repeated')
            previous[key]=dict(path=root/entry['path'],sha256=entry['sha256'],source_rows_sha256=entry['chunks'][0]['sha256'],profile=profile,rows=entry['count'],store=store,entry=None)
    for descriptor in previous_archives:
        path=Path(descriptor['path']).resolve(strict=True);archive=strict_json(read(path,descriptor['sha256']))
        if archive['schema']!='guanheng.daily-native-archive.v2'or archive['helper_sha256']!=helper_sha256:raise ValueError('daily generation previous archive differs')
        for entry in archive['entries']:
            metadata=entry['provenance'][0]['metadata'];key=(entry['symbol'],metadata['adjustment'])
            if key in previous:raise ValueError('daily generation previous price source repeated')
            previous[key]=dict(path=path.parent/entry['path'],sha256=entry['sha256'],source_rows_sha256=entry['source_rows_sha256'],profile=metadata,rows=entry['rows'],store=None,entry=entry)
    def source_metadata(profile,content):
        if 'source'in profile:return dict(profile)
        value={k:profile[k]for k in ('dataset_version','source_license','adjustment','factor_version','timezone','value_semantics','price_unit','volume_unit','amount_unit','minute_boundary')}
        value.update(source={k:profile[k]for k in ('provider','instance_id','session_id','generation')},qualification='DevelopmentVerified',period='1d',timestamp_semantics='source_date',content_id=content)
        return value
    reader=None
    def old_history(key,old):
        nonlocal reader
        check();read(old['path'],old['sha256'])
        if reader is None:reader=NativeHistory(native_reader['library'],native_reader['sha256'],max_bars=2000,max_file_bytes=268435456)
        security,basis=key;exchange,code=security.split('.')
        if old['store']is not None:
            history=reader.read_source_store(old['store']['store_root'],exchange,code,expected_import_sha256=old['store']['import_receipt_sha256'])
        else:
            entry=old['entry'];header=source_file_metadata(old['profile'],old['sha256'],old['rows'],
                decoding_version='wt-daily-native-archive.v1',quality=entry.get('price_range_quality'))
            history=reader.read_source_file(old['path'],source_daily_security(exchange,code),header)
        if len(history.bars)!=old['rows']:raise ValueError('daily generation previous history count differs')
        check();return history
    entries=[];reused=written=rows_total=retained=0;keys=set();native=_Native(helper,helper_sha256)
    try:
        for item in plan['native_inputs']:
            check();manifest=(source.parent/item['manifest']).resolve(strict=True)
            if not manifest.is_relative_to(source.parent):raise ValueError('daily generation manifest escaped')
            document=_manifest(read(manifest,item['manifest_sha256']),manifest.parent);profile=document['profile'];basis=profile['adjustment']
            for security in document['securities']:
                check()
                if len(security['chunks'])!=1:raise ValueError('daily generation requires complete per-security CSV')
                chunk=security['chunks'][0];body=read(_chunk_path(manifest.parent,chunk['path']),chunk['sha256'],8388608)
                bars,first,last=_rows(body,profile,None,2000,period='1d')
                if not bars:raise ValueError('daily generation empty observed security')
                code,market=security['symbol'].split('.');symbol={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[market]+'.'+code;key=(symbol,basis)
                if key in keys:raise ValueError('daily generation price key repeated')
                keys.add(key);rows_total+=len(bars)
                if rows_total>2000000:raise ValueError('daily generation total row budget exceeded')
                quality=PriceRangeQuality()
                for bar in bars:
                    day=bar.date;quality.observe(f'{day//10000:04d}-{day//100%100:02d}-{day%100:02d}T00:00:00+08:00',bar.open,bar.high,bar.low,bar.close)
                metadata=source_metadata(profile,chunk['sha256'])
                validate_source_metadata(metadata,period='1d')
                relative=basis+'/'+symbol+'.dsb';path=output/relative;path.parent.mkdir(exist_ok=True);receipt=path.with_suffix('.json')
                if receipt.exists():
                    entry=strict_json(read(receipt));read(path,entry['sha256'])
                    if (entry['source_rows_sha256']!=chunk['sha256']or entry['rows']!=len(bars)
                            or entry['provenance']!=[dict(offset=0,count=len(bars),metadata=metadata)]or entry['price_range_quality']!=quality.result()):
                        raise ValueError('daily generation completed security differs')
                    entries.append(entry);reused+=entry.get('sha256')==previous.get(key,{}).get('sha256');written+=entry.get('sha256')!=previous.get(key,{}).get('sha256');continue
                if path.exists():path.rename(path.with_suffix('.interrupted-'+uuid.uuid4().hex))
                old=previous.get(key)
                can_reuse=(old is not None and old['source_rows_sha256']==chunk['sha256']and old['rows']==len(bars)
                    and all(old['profile'][k]==profile[k]for k in comparable))
                if old is not None and not can_reuse:
                    dates={bar.date for bar in bars}
                    prior=old_history(key,old)
                    if any(int(bar.occurred_at.strftime('%Y%m%d'))not in dates for bar in prior.bars):
                        raise ValueError('daily generation source cache lost archived dates')
                if can_reuse:
                    old_body=read(old['path'],old['sha256']);reused+=1
                    if old['path'].drive.upper()==path.drive.upper():os.link(old['path'],path)
                    else:path.write_bytes(old_body)
                    identity=old['sha256']
                else:
                    pending=path.with_suffix('.importing')
                    if pending.exists():pending.rename(pending.with_suffix('.interrupted-'+uuid.uuid4().hex))
                    native.write_verify(pending,bars,period='1d');pending.replace(path);identity=sha(read(path));written+=1
                entry=dict(symbol=symbol,path=relative,sha256=identity,rows=len(bars),first=bars[0].date,last=bars[-1].date,
                    provenance=[dict(offset=0,count=len(bars),metadata=metadata)],source_rows_sha256=chunk['sha256'],price_range_quality=quality.result())
                save(receipt,entry);entries.append(entry)
                save(output/'PROGRESS.json',dict(state='materializing',completed=len(entries),reused=reused,written=written,rows=rows_total))
        if rows_total!=plan['rows']:raise ValueError('daily generation row total differs')
        for key,old in sorted(previous.items()):
            if key in keys:continue
            check();history=old_history(key,old);relative=key[1]+'/'+key[0]+'.dsb';path=output/relative;path.parent.mkdir(exist_ok=True)
            old_body=read(old['path'],old['sha256'])
            if path.exists():read(path,old['sha256'])
            elif old['path'].drive.upper()==path.drive.upper():os.link(old['path'],path)
            else:path.write_bytes(old_body)
            if old['entry']is not None:entry=dict(old['entry'],path=relative)
            else:
                quality=PriceRangeQuality()
                for bar in history.bars:quality.observe(bar.occurred_at.isoformat(),bar.open,bar.high,bar.low,bar.close)
                entry=dict(symbol=key[0],path=relative,sha256=old['sha256'],rows=old['rows'],
                    first=int(history.bars[0].occurred_at.strftime('%Y%m%d')),last=int(history.bars[-1].occurred_at.strftime('%Y%m%d')),
                    provenance=[dict(offset=0,count=old['rows'],metadata=source_metadata(old['profile'],old['source_rows_sha256']))],
                    source_rows_sha256=old['source_rows_sha256'],price_range_quality=quality.result())
            receipt=path.with_suffix('.json')
            if receipt.exists()and strict_json(read(receipt))!=entry:
                raise ValueError('daily generation retained receipt differs')
            save(receipt,entry);entries.append(entry);retained+=1;reused+=1;rows_total+=old['rows']
            if rows_total>2000000:raise ValueError('daily generation retained history capacity')
    finally:
        native.close()
        if reader is not None:reader.close()
    archive=output/'archive.json';save(archive,dict(schema='guanheng.daily-native-archive.v2',entries=entries,helper_sha256=helper_sha256))
    result=dict(schema='guanheng.qmt-analysis-native-import.v2',state='completed',capture_sha256=provenance['capture_sha256'],
        observation_date=provenance['request']['end_date'],source_kind=provenance['source_kind'],source_received_at=provenance['source_received_at'],
        securities=plan['securities'],rows=rows_total,stores=[],archive=dict(path=str(archive),sha256=sha(read(archive))),
        reused_securities=reused,written_securities=written,
        retained_price_files=retained,  # 当前输入未出现、沿旧DSB及完整原来源保留的价格键数量。
        input_rows=plan['rows'],  # 本次实际捕获行数；rows另包含退出/缺项证券的已保留历史。
        helper_sha256=helper_sha256,original_roots_modified=False,SDK_calls=0)
    save(output/'RESULT.json',result);save(output/'PROGRESS.json',dict(state='completed',completed=len(entries),reused=reused,written=written,rows=rows_total))
    return result
