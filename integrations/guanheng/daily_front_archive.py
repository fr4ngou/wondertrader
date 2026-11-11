"""供应商前复权独立落盘；新参考必须完整覆盖旧已知日期才替换该证券。"""
from pathlib import Path
import time

from .daily_data_update import _save,_load
from .source_archive_identity import DAILY_ARCHIVE_MANIFEST_BYTES
from .analysis_price_capture import load_price_capture,price_batches,capture_metadata,original_price_quality
from .daily_archive_merge import read_price_history
from .daily_archive_prepare import prepare_daily_archive,price_rows_identity
from .market_generation import read_fixed
from .source_archive_identity import archive_entry_identity


def prepare_front_archive(inputs,market,previous_archives,output,helper,*,deadline,
                          maximum_history_rows,cancelled,strategy_capture=None,strategy_coverage=None,
                          unit_evidence_by_capture=None):
    """调用方持原租约并关闭market；本函数不触发HPR，原价完成独立于可选前复权。

    每证券采用同一当前供应商参考的完整实读日期，或完整保留其旧价格/参考。
    新捕获缺少旧日期时保留旧档并说明原因；不同参考的价格不按日期拼接。
    Native文件沿原Helper写读，价格键和factor_version供原Reader分别选择。
    unit_evidence_by_capture仅复用本次按capture SHA核过的来源资格；证券映射仍归唯一单位解析器。
    """
    root=Path(output);root.mkdir(exist_ok=False)
    prepared=_load(inputs);cache=prepared['cache'];manifest=load_price_capture(cache)
    metadata=capture_metadata(manifest,cache['sha256'],'front_ratio');values={};candidates={}
    qualified=(unit_evidence_by_capture or{}).get(cache['sha256'])
    def check():
        if cancelled():raise InterruptedError('front archive stopped')
        if time.monotonic()>=deadline:raise TimeoutError('front archive deadline')
    for _,items in price_batches(cache,manifest,adjustment='front_ratio',deadline=deadline,cancelled=cancelled):
        for qmt,item in items.items():
            source_metadata=(capture_metadata(manifest,cache['sha256'],'front_ratio',symbol=qmt,
                unit_evidence=qualified)if qualified is not None else metadata)
            code,exchange=qmt.split('.');symbol={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[exchange]+'.'+code
            values[symbol]=item
            candidates[symbol]=[(item,source_metadata,'ordinary')]
    if strategy_capture is not None:
        if type(strategy_coverage)is not dict:raise ValueError('front strategy coverage required')
        hot=load_price_capture(strategy_capture);hot_metadata=capture_metadata(hot,strategy_capture['sha256'],'front_ratio')
        hot_qualified=(unit_evidence_by_capture or{}).get(strategy_capture['sha256'])
        for _,items in price_batches(strategy_capture,hot,adjustment='front_ratio',deadline=deadline,cancelled=cancelled):
            for qmt,item in items.items():
                source_metadata=(capture_metadata(hot,strategy_capture['sha256'],'front_ratio',symbol=qmt,
                    unit_evidence=hot_qualified)if hot_qualified is not None else hot_metadata)
                code,exchange=qmt.split('.');symbol={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[exchange]+'.'+code
                quality=strategy_coverage.get(symbol,{}).get('front_ratio',{})
                if quality.get('missing_dates')!=[]or quality.get('actual_rows',0)<1:continue
                values[symbol]=item;candidates.setdefault(symbol,[]).insert(0,(item,source_metadata,'strategy_history'))
    retained_symbols=set();retained_files={}
    for archive in previous_archives:
        for entry in _load(archive,DAILY_ARCHIVE_MANIFEST_BYTES)['entries']:
            if entry['provenance'][0]['metadata']['adjustment']!='front_ratio':continue
            retained_symbols.add(entry['symbol'])
            original_root=Path(archive['path']).parent.resolve(strict=True)
            path=(original_root/entry['path']).resolve(strict=True)
            if not path.is_relative_to(original_root):raise ValueError('front prior archive path escaped')
            retained_files.setdefault(entry['symbol'],dict(path=str(path),sha256=entry['sha256'],rows=entry['rows'],
                identity=archive_entry_identity(archive,entry)))
    rows={};provenance={};states={};reusable_files={}
    for symbol in sorted(set(values)|retained_symbols):
        check();item=values.get(symbol);current={};origin='retained'
        old=read_price_history(market,symbol,'front_ratio',deadline=deadline,
            maximum_history_rows=maximum_history_rows,cancelled=cancelled)
        original=retained_files.get(symbol)
        resolver=getattr(market,'static_archive_identity',None)
        if (original is not None and original['rows']==len(old)and callable(resolver)
                and resolver(symbol,'front_ratio')==original['identity']):
            check();read_fixed(Path(original['path']),maximum=268435456,identity=original['sha256'])
            reusable_files[symbol]=dict(path=original['path'],sha256=original['sha256'],
                rows_sha256=price_rows_identity([row for _,(row,_)in sorted(old.items())]))
            # 仅作筛选：old已沿原Native Reader实际核读；写入owner仍逐完整WTSBar核同后才链接原DSB。
        for option,source_metadata,source_origin in candidates.get(symbol,[]):
            proposed={int(day):(dict(date=int(day),**bar),source_metadata)for day,bar in option['data'].items()
                if original_price_quality(bar)=='qualified'}
            if proposed and set(old)<=set(proposed):current=proposed;item=option;origin=source_origin;break
            if not current:current=proposed
        complete=bool(current)and origin!='retained'
        selected=current if complete else old
        states[symbol]=dict(
            source_state=item['status']if item is not None else'not_in_current_capture',  # 原SDK状态，未出现旧证券另列。
            captured_rows=len(current),  # 当前参考下实际合格行数，原零量不改变。
            retained_rows=len(old)if not complete else 0,  # 旧参考整体保留行数，不混入新锚定价格。
            reason='current_reference_complete'if complete else'current_reference_incomplete'if old else'front_unavailable')
        if strategy_capture is not None:
            states[symbol]['selected_capture']=origin  # 显式窗口启用时说明整证券参考来源，不按日期拼接。
        if not selected:continue
        rows[symbol]=[];parts=[]
        for _,(row,original)in sorted(selected.items()):
            if not parts or parts[-1]['metadata']!=original:
                parts.append(dict(offset=len(rows[symbol]),count=0,metadata=original))
            parts[-1]['count']+=1;rows[symbol].append(row)
        provenance[symbol]=parts
    archive=None
    if rows:
        archive=prepare_daily_archive(rows,metadata,root/'data',helper['path'],helper['sha256'],deadline=deadline,
            provenance=provenance,maximum_history_rows=maximum_history_rows,cancelled=cancelled,
            reusable_files=reusable_files)
    result=dict(
        schema='guanheng.daily-front-archive.v1',  # 可选前复权阶段事实，与原价覆盖分别表达。
        archive=archive,  # 完整已知前复权目录，无可用数据时为空。
        securities=states,  # 每证券当前/旧参考选择及未更新原因。
        capture=cache)  # 原QAB两口径同捕获身份，未推导独立因子。
    _save(root/'RESULT.json',result);return result
