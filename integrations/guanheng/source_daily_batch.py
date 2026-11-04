"""在原服务线程与原Reader上顺序执行已准入批次；不触发SDK、补齐或新读取池。"""
import time
from contextlib import nullcontext
from ..guanheng_market_client import API_VERSION, MarketProtocolError, encode_json, validate_response
from ..guanheng_market_client.daily_batch import daily_batch_requests,validate_daily_batch_request


def call_daily_batch(native,request,*,deadline,max_response_bytes):
    """所有单项共用本次HTTP绝对截止与响应额度；超限丢弃整个未发布批次。"""
    # 当前版本包装器在批次入口换代一次；旧固定Reader沿用原生命周期。
    scope=getattr(native,'read_scope',nullcontext)
    with scope():
        return _call_daily_batch(native,request,deadline=deadline,max_response_bytes=max_response_bytes)


def _call_daily_batch(native,request,*,deadline,max_response_bytes):
    query=validate_daily_batch_request(request['request'])
    results=[];used=256;available=0
    for symbol,single in daily_batch_requests(query):
        if time.monotonic()>=deadline:
            return dict(api_version=API_VERSION,status=dict(code='Timeout',reason='daily batch deadline expired'),data={})
        original=dict(api_version=API_VERSION,action='history.source-daily-query',request=single)
        reply=validate_response(native.call(original),original)
        row=dict(
            symbol=symbol,  # 本项原请求WT证券身份，顺序保持。
            status=reply['status'],  # 原读取状态和原因，缺资料保持Unavailable。
            data=reply['data'])  # 原日线、单位和谱系；失败项为空对象。
        used+=len(encode_json(row))+1
        if used>max_response_bytes:
            raise MarketProtocolError('daily batch response exceeds its byte budget')
        results.append(row);available+=reply['status']['code']=='Ok'
    if time.monotonic()>=deadline:
        return dict(api_version=API_VERSION,status=dict(code='Timeout',reason='daily batch deadline expired'),data={})
    return dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=dict(
        results=results,  # 完整准入批次逐项结果；无静默截断。
        available_count=available))  # 成功读取项数，不表示全市场完整性。
