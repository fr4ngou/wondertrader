"""同一服务owner组合SHM当前报价与既有WT历史；两者来源元数据各自保留。"""
from __future__ import annotations
from .market_service import NativeMarket
from .source_market import create_native_source_market
from ..guanheng_market_client import API_VERSION, validate_request, validate_response, MarketUnavailable


class ShmQuotesMarket:
    """原服务线程拥有两个后端；关闭反向释放，任一关闭失败继续收回另一资源。"""
    def __init__(self, config, *, max_response_bytes=8*1024*1024):
        self._quotes=self._history=None
        try:
            if type(config)is not dict or set(config)!={'mode','quotes','history'} or config['mode']!='source-shm-quotes':
                raise ValueError('SHM quotes composition differs')
            quotes=config['quotes']
            if type(quotes)is not dict or set(quotes)!={'library','sha256','configuration'}:
                raise ValueError('SHM quotes deployment differs')
            history=config['history']
            if type(history)is not dict or history.get('mode')not in ('source-store','source-stores','source-catalog','source-collected'):
                raise ValueError('history source differs')
            self._history=create_native_source_market(history,max_response_bytes=max_response_bytes)
            self._quotes=NativeMarket(quotes['library'],quotes['sha256'],quotes['configuration'],max_response_bytes=max_response_bytes)
        except BaseException:
            self.close();raise

    def call(self, request):
        request=validate_request(request)
        if self._quotes is None or self._history is None:raise MarketUnavailable('market owner closed')
        if request['action']=='quotes.query':return self._quotes.call(request)
        if request['action']!='capabilities':return self._history.call(request)
        history=self._history.call(request);quotes=self._quotes.call(request)
        if history['status']['code']!='Ok':return history
        # 行情暂缺保留历史能力，source仅描述当前报价，历史结果仍携带自身元数据。
        available=quotes['status']['code']=='Ok'
        data=dict(history['data'])
        data['snapshot']=quotes['data']['snapshot'] if available else dict(supported=False,qualification='Unavailable',reason='共享内存报价尚未就绪')
        if available:data['source']=quotes['data']['source']
        return validate_response(dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=data),request)

    def close(self):
        first=None
        for name in ('_quotes','_history'):
            owner=getattr(self,name,None)
            if owner is not None:
                try:owner.close()
                except BaseException as error:first=first or error
                else:setattr(self,name,None)
        if first is not None:raise first
