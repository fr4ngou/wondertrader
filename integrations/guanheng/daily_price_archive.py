"""全类别新增原价与旧补充档按日期统一合并；所有原目录保持只读。"""
from pathlib import Path
import time

from .analysis_price_capture import load_price_capture,price_batches,capture_metadata,original_price_quality
from .daily_data_update import _load,_save,_descriptor
from .daily_archive_merge import merge_original_price_rows
from .daily_archive_prepare import price_rows_identity
from .market_generation import read_fixed
from .native_history import NativeHistory,source_file_metadata
from ..guanheng_market_client.daily_contract import source_daily_security
from ..guanheng_market_client.source_history import validate_source_metadata


def materialize_price_archive(inputs,market,previous_archives,output,helper,native_reader,*,deadline,
                              maximum_history_rows=10000,cancelled=lambda:False,additional_captures=()):
    """调用方持原发布租约并关闭market；本函数关闭其独有Native文件Reader。

    inputs绑定已完成价格回读。previous_archives按最新成功版本优先排列，旧原价
    补充文件只填尚无记录的日期；market为本轮新股票Native已组合的读取视图。
    合并后每证券保留完整旧档与逐段来源，避免旧整文件遮蔽新尾日。未变股票
    不进入此补充写入集合。源空值不转0，不在本阶段产生HPR/行情请求。
    """
    def check():
        if cancelled():raise InterruptedError('daily price archive stopped')
        if time.monotonic()>=deadline:raise TimeoutError('daily price archive deadline')
    check();prepared=_load(inputs)
    if prepared.get('schema')!='guanheng.daily-price-input-result.v1':
        raise ValueError('daily price archive input differs')
    cache=prepared['cache'];manifest=load_price_capture(cache)
    fallback=capture_metadata(manifest,cache['sha256'],'none')
    additions={};reusable_files={};reader=None
    try:
        for descriptor in previous_archives:
            check();document=_load(descriptor);root=Path(descriptor['path']).parent
            if document.get('schema')not in('guanheng.daily-native-archive.v1','guanheng.daily-native-archive.v2'):
                raise ValueError('daily price prior archive invalid')
            for entry in document['entries']:
                check();parts=entry['provenance']
                if parts[0]['metadata']['adjustment']!='none':continue
                if entry['rows']>maximum_history_rows:raise ValueError('daily price prior history exceeds capacity')
                path=(root/entry['path']).resolve(strict=True)
                if not path.is_relative_to(root.resolve()):raise ValueError('daily price prior path escaped')
                read_fixed(path,maximum=268435456,identity=entry['sha256'])
                if reader is None:reader=NativeHistory(native_reader['library'],native_reader['sha256'],
                    max_bars=maximum_history_rows,max_file_bytes=268435456)
                exchange,code=entry['symbol'].split('.')
                header=source_file_metadata(parts[0]['metadata'],entry['sha256'],entry['rows'],
                    decoding_version='wt-daily-native-archive.v1',quality=entry.get('price_range_quality'))
                history=reader.read_source_file(path,source_daily_security(exchange,code),header)
                read_fixed(path,maximum=268435456,identity=entry['sha256'])
                if len(history.bars)!=entry['rows']:raise ValueError('daily price prior history count differs')
                original_rows=[dict(date=int(bar.occurred_at.strftime('%Y%m%d')),
                    **{key:getattr(bar,key)for key in ('open','high','low','close','volume','amount')})for bar in history.bars]
                reusable_files.setdefault(entry['symbol'],dict(
                    path=str(path),  # 本轮原Reader已经完整核读的旧DSB绝对位置，旧根只读。
                    sha256=entry['sha256'],  # 已核旧文件字节身份，采用前再次完整核验。
                    rows_sha256=price_rows_identity(original_rows)))  # 仅为筛选；原Helper还会比对本次全部WTSBar字段。
                values=additions.setdefault(entry['symbol'],{});covered=0
                for part in parts:
                    validate_source_metadata(part['metadata'],period='1d')
                    if part['offset']!=covered or part['count']<1 or part['metadata']['adjustment']!='none':
                        raise ValueError('daily price prior provenance invalid')
                    for bar in history.bars[covered:covered+part['count']]:
                        row=dict(date=int(bar.occurred_at.strftime('%Y%m%d')),
                            **{k:getattr(bar,k)for k in ('open','high','low','close','volume','amount')})
                        values.setdefault(row['date'],(row,part['metadata']))
                    covered+=part['count']
                if covered!=entry['rows']:raise ValueError('daily price prior provenance count differs')
        for current_capture in (cache,*additional_captures):
            current_manifest=manifest if current_capture==cache else load_price_capture(current_capture)
            current_metadata=capture_metadata(current_manifest,current_capture['sha256'],'none')
            for _,items in price_batches(current_capture,current_manifest,deadline=deadline,cancelled=cancelled):
                for qmt,item in items.items():
                    code,exchange=qmt.split('.');symbol={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[exchange]+'.'+code
                    values=additions.setdefault(symbol,{})
                    for day,bar in sorted(item['data'].items()):
                        if original_price_quality(bar)!='qualified':continue  # 旧成功日及普通捕获优先，热窗口只填缺日。
                        values.setdefault(int(day),(dict(date=int(day),**bar),current_metadata))
        if prepared.get('supplemental_prices')is not None:
            from .official_index_prices import load_official_index_prices
            supplement=load_official_index_prices(prepared['supplemental_prices'])
            if not set(supplement['securities'])<=set(prepared['securities']):
                raise ValueError('official prices outside original price universe')
            for symbol,item in supplement['securities'].items():
                check();values=additions.setdefault(symbol,{})
                for day,bar in sorted(item['data'].items()):
                    metadata=item['metadata_by_provider'][item['provider_by_date'][day]]
                    values.setdefault(int(day),(dict(date=int(day),**bar),metadata))
        rows={};provenance={}
        for symbol,values in additions.items():
            check();rows[symbol]=[];provenance[symbol]=[]
            for _,(bar,metadata)in sorted(values.items()):
                if not provenance[symbol]or provenance[symbol][-1]['metadata']!=metadata:
                    provenance[symbol].append(dict(
                        offset=len(rows[symbol]),  # 此证券新DSB内的零基行起点。
                        count=0,  # 连续相同原来源的实际记录数。
                        metadata=metadata))  # 逐段原数值/单位/复权资格，历史来源保持。
                provenance[symbol][-1]['count']+=1;rows[symbol].append(bar)
        result=merge_original_price_rows(market,rows,fallback,output,helper['path'],helper['sha256'],
            deadline=deadline,addition_provenance=provenance,retain_unchanged=True,
            maximum_history_rows=maximum_history_rows,cancelled=cancelled,reusable_files=reusable_files)
        if result is None:
            # 合法空补充集也是已完成的不可变档案；不加载Helper、不制造任何价格条目。
            check();output=Path(output);output.mkdir(parents=False,exist_ok=False)
            _save(output/'archive.json',dict(schema='guanheng.daily-native-archive.v1',entries=[]))
            result=_descriptor(output/'archive.json')
        return result
    finally:
        if reader is not None:reader.close()
