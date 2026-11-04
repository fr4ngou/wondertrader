"""供应商前复权独立落盘；新参考必须完整覆盖旧已知日期才替换该证券。"""
from pathlib import Path
import time

from .daily_data_update import _save,_load
from .analysis_price_capture import load_price_capture,price_batches,capture_metadata,original_price_quality
from .daily_archive_merge import read_price_history
from .daily_archive_prepare import prepare_daily_archive


def prepare_front_archive(inputs,market,previous_archives,output,helper,*,deadline,
                          maximum_history_rows,cancelled):
    """调用方持原租约并关闭market；本函数不触发HPR，原价完成独立于可选前复权。

    每证券采用同一当前供应商参考的完整实读日期，或完整保留其旧价格/参考。
    新捕获缺少旧日期时保留旧档并说明原因；不同参考的价格不按日期拼接。
    Native文件沿原Helper写读，价格键和factor_version供原Reader分别选择。
    """
    root=Path(output);root.mkdir(exist_ok=False)
    prepared=_load(inputs);cache=prepared['cache'];manifest=load_price_capture(cache)
    metadata=capture_metadata(manifest,cache['sha256'],'front_ratio');values={}
    def check():
        if cancelled():raise InterruptedError('front archive stopped')
        if time.monotonic()>=deadline:raise TimeoutError('front archive deadline')
    for _,items in price_batches(cache,manifest,adjustment='front_ratio',deadline=deadline,cancelled=cancelled):
        for qmt,item in items.items():
            code,exchange=qmt.split('.');symbol={'SH':'SSE','SZ':'SZSE','BJ':'BSE'}[exchange]+'.'+code
            values[symbol]=item
    retained_symbols=set()
    for archive in previous_archives:
        for entry in _load(archive)['entries']:
            if entry['provenance'][0]['metadata']['adjustment']=='front_ratio':retained_symbols.add(entry['symbol'])
    rows={};provenance={};states={}
    for symbol in sorted(set(values)|retained_symbols):
        check();item=values.get(symbol);current={}
        if item is not None:
            current={int(day):(dict(date=int(day),**bar),metadata)for day,bar in item['data'].items()
                     if original_price_quality(bar)=='qualified'}
        old=read_price_history(market,symbol,'front_ratio',deadline=deadline,
            maximum_history_rows=maximum_history_rows,cancelled=cancelled)
        complete=bool(current)and set(old)<=set(current)
        selected=current if complete else old
        states[symbol]=dict(
            source_state=item['status']if item is not None else'not_in_current_capture',  # 原SDK状态，未出现旧证券另列。
            captured_rows=len(current),  # 当前参考下实际合格行数，原零量不改变。
            retained_rows=len(old)if not complete else 0,  # 旧参考整体保留行数，不混入新锚定价格。
            reason='current_reference_complete'if complete else'current_reference_incomplete'if old else'front_unavailable')
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
            provenance=provenance,maximum_history_rows=maximum_history_rows,cancelled=cancelled)
    result=dict(
        schema='guanheng.daily-front-archive.v1',  # 可选前复权阶段事实，与原价覆盖分别表达。
        archive=archive,  # 完整已知前复权目录，无可用数据时为空。
        securities=states,  # 每证券当前/旧参考选择及未更新原因。
        capture=cache)  # 原QAB两口径同捕获身份，未推导独立因子。
    _save(root/'RESULT.json',result);return result
