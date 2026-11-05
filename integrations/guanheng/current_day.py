"""WT原Writer当日快照的有界投影与查询；归档及策略闭合日线仍归原owner。"""
from copy import deepcopy
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone, timedelta
import hashlib
import math
from pathlib import Path
import re
import threading
import time
from uuid import UUID, uuid4

from ..guanheng_market_client import API_VERSION, encode_json, strict_json, validate_request, validate_response
from ..guanheng_market_client.source_history import validate_source_daily_data, validate_source_metadata
from .daily_overlay import _metadata, _select
from .market_generation import read_fixed


SHANGHAI = timezone(timedelta(hours=8))  # 原tick自然日/时刻采用上海时区。
MAXIMUM = 8 * 1024 * 1024  # 全市场单份快照上限；只替换一份，不积累历史副本。


def _need(value):
    if not value:
        raise ValueError('WT current day projection invalid')


def _source_time(row):
    """HHMMSSmmm严格还原原tick时刻，不使用服务读取时间替换。"""
    day = datetime.strptime(str(row['action_date']), '%Y%m%d')
    clock = row['action_time']
    _need(type(clock) is int and 0 <= clock <= 235959999)
    return day.replace(hour=clock//10000000, minute=clock//100000 % 100,
        second=clock//1000 % 100, microsecond=clock % 1000 * 1000, tzinfo=SHANGHAI)


def _validate_row(row):
    fields = {'symbol','trading_date','action_date','action_time','open','high','low','close','volume','amount'}
    _need(type(row) is dict and set(row) == fields)
    _need(type(row['symbol']) is str and re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',row['symbol']))
    _need(type(row['trading_date']) is int)
    datetime.strptime(str(row['trading_date']), '%Y%m%d')
    stamp = _source_time(row)
    _need(row['trading_date'] == row['action_date'])  # 本部署沪深北现货日线，交易日沿原自然日。
    for key in ('open','high','low','close','volume','amount'):
        _need(type(row[key]) in (int,float) and math.isfinite(row[key]) and row[key] >= 0)
    _need(0 < row['low'] <= min(row['open'],row['close']) <= max(row['open'],row['close']) <= row['high'])
    return stamp


def publish_current_day(root, rows, *, control_id, configuration_sha256, observed_at):
    """采集管理线程发布原Writer值拷贝；失败保留旧文件并删除本次临时文件。

    每份记录保留原交易日/时刻；整份observed_at只说明读取时间。旧日缓存保持旧日，
    无行情的证券保持缺失。此文件属于WT数据根，由原单Writer租约协调生命周期。
    """
    _need(str(UUID(control_id)) == control_id)
    _need(re.fullmatch(r'[0-9a-f]{64}',configuration_sha256))
    _need(type(rows) is list and len(rows) <= 10000)
    _need(type(observed_at) in (int,float) and math.isfinite(observed_at))
    for row in rows:
        _validate_row(row)
    _need(len({r['symbol'] for r in rows}) == len(rows))
    value = dict(
        schema='guanheng.wt-current-day.v1',  # 原Writer当前值投影，不代表日线归档。
        control_id=control_id,  # 本次采集实例UUID，不是策略身份。
        configuration_sha256=configuration_sha256,  # 已准入采集配置的原字节SHA。
        observed_at=datetime.fromtimestamp(observed_at,timezone.utc).isoformat(),  # 快照读取时刻。
        rows=rows)  # 实际已缓存证券；每行价量额沿原profile，单位由查询部署声明。
    raw=encode_json(value)
    _need(0 < len(raw) <= MAXIMUM)
    from guanheng_qmt_shm.private_files import write_private_new
    from .collection_status import replace_status
    target=Path(root)/'current-day.json'
    temporary=target.with_name('current-day-'+str(uuid4())+'.tmp')
    try:
        write_private_new(temporary,raw,maximum_bytes=MAXIMUM)
        replace_status(temporary,target)
    finally:
        temporary.unlink(missing_ok=True)


def publish_current_day_observation(collection,root,directory,*,control_id,configuration_sha256):
    """采集旁路独立失败边界：当前值与其诊断均失败时原采集仍继续。

    Writer真实健康错误仍由管理循环原check_health接管；此接缝只报告本次投影结果。
    两种文件各自原子替换且清理本次临时文件，不把投影错误升级成Writer关闭。
    """
    error=None
    try:
        publish_current_day(root,collection.current_days(),control_id=control_id,
            configuration_sha256=configuration_sha256,observed_at=time.time())
    except (OSError,ValueError,RuntimeError,AttributeError) as exception:
        error=type(exception).__name__
    try:
        from .collection_projection import publish_projection
        publish_projection(directory,'current-day-status.json',dict(
            schema='guanheng.wt-current-day-status.v1',  # 当前值旁路状态，不描述Writer健康。
            control_id=control_id,  # 本次采集实例身份。
            observed_wall_time=time.time(),  # 此次投影尝试时刻。
            error_kind=error),True)  # None表示当前值发布成功，失败为固定异常类别。
    except (OSError,ValueError,RuntimeError) as exception:
        return type(exception).__name__  # 诊断文件不可写仍属于旁路，本轮无新状态可发布。
    return error


class CurrentDayMarket:
    """原服务线程组合固定历史和原Writer快照；只有显式current视图采用盘中值。

    config.base沿原读取服务；current_day.path为单Writer原子替换文件，profile的许可与
    价量额单位来自实际采集声明。默认/归档查询透传，策略不会隐式读到未收盘日线。
    """
    def __init__(self,config,*,max_response_bytes):
        _need(type(config) is dict and set(config) == {'mode','base','current_day'})
        _need(config['mode'] == 'source-current-day')
        profile=config['current_day']
        _need(type(profile) is dict and set(profile) == {'path','source_license','price_unit','volume_unit','amount_unit'})
        _need(type(profile['path']) is str and Path(profile['path']).is_absolute())
        self._path=Path(profile['path'])  # 原Writer拥有的动态文件，读取方不固定某次文件SHA。
        self._profile=deepcopy(profile)  # 当前采集的原单位/许可；未知继续unknown。
        self._owner=threading.get_ident()  # 与base原生Reader相同的唯一服务线程。
        self._maximum=max_response_bytes  # 沿原服务单次响应预算。
        self._base=None  # 构造失败仍由本对象关闭已建立的base。
        self._closed=False  # close后拒绝读取原生句柄。
        self._depth=0  # 一个HTTP批次内固定同一归档代及同一Writer快照。
        self._snapshot_loaded=False  # 区分尚未读取与本次已确认快照缺失。
        self._snapshot_bytes=None  # 本请求域最多一份8MiB正文，退出域立即释放。
        from .source_market import create_native_source_market
        try:
            # 提前校验部署单位，避免请求后才发现profile无法表达。
            validate_source_metadata(_metadata(dict(provider='Qmt',instance_id='wt-writer',session_id='configuration',generation=1),
                '0'*64,'wt-current-day.v1',profile),period='1d')
            self._base=create_native_source_market(config['base'],max_response_bytes=max_response_bytes)
        except BaseException:
            self.close()
            raise

    @contextmanager
    def read_scope(self):
        """复用base的原版本域；Writer投影在本批次首次需要时读取一次。"""
        _need(threading.get_ident() == self._owner and not self._closed)
        scope=getattr(self._base,'read_scope',nullcontext)
        with scope():
            self._depth+=1
            try:
                yield
            finally:
                self._depth-=1
                if not self._depth:
                    self._snapshot_loaded=False
                    self._snapshot_bytes=None

    def call(self,request):
        with self.read_scope():
            return self._call(request)

    def _call(self,request):
        request=validate_request(strict_json(encode_json(request)))
        if request['action'] != 'history.source-daily-query' or request['request'].get('view') != 'current':
            return self._base.call(request)
        query=request['request']
        archived=deepcopy(request)
        archived['request'].pop('view')
        response=self._base.call(archived)
        if response['status']['code'] not in ('Ok','Unavailable'):
            return response
        data=(validate_source_daily_data(response['data'],archived['request'])
              if response['status']['code']=='Ok' else None)
        # 前复权参考有独立因子时点；原Writer只提供原价，不混入分析价历史。
        if query.get('adjustment','none') != 'none':
            return response
        try:
            return self._combine(request,data,response)
        except (OSError,ValueError,KeyError,TypeError):
            # 当前快照缺失/损坏只影响形成中行；已成功读取的历史继续沿其原日期展示。
            return response

    def _combine(self,request,data,response):
        query=request['request']
        today=int(datetime.now(SHANGHAI).strftime('%Y%m%d'))
        if query['to'] < today or data is not None and any(r['date'] >= today for r in data['bars']):
            return response  # 历史区间或已归档当日无需打开全市场当前值快照。
        if not self._snapshot_loaded:
            try:
                self._snapshot_bytes=read_fixed(self._path,maximum=MAXIMUM)
            except FileNotFoundError:
                self._snapshot_bytes=None
            self._snapshot_loaded=True
        raw=self._snapshot_bytes
        if raw is None:
            return response
        snapshot=strict_json(raw)
        _need(type(snapshot) is dict and set(snapshot) == {'schema','control_id','configuration_sha256','observed_at','rows'})
        _need(snapshot['schema'] == 'guanheng.wt-current-day.v1')
        _need(str(UUID(snapshot['control_id'])) == snapshot['control_id'])
        _need(re.fullmatch(r'[0-9a-f]{64}',snapshot['configuration_sha256']))
        observed=datetime.fromisoformat(snapshot['observed_at'])
        _need(observed.utcoffset() is not None and observed <= datetime.now(timezone.utc))
        _need(type(snapshot['rows']) is list and len(snapshot['rows']) <= 10000)
        _need(all(type(row) is dict for row in snapshot['rows']))
        symbol=query['exchange']+'.'+query['code']
        found=[r for r in snapshot['rows'] if r.get('symbol') == symbol]
        _need(len(found) <= 1)
        if not found:
            return response
        row=found[0]
        source_at=_validate_row(row)
        _need(source_at <= observed)
        day=row['trading_date']
        # 原归档同日值优先；旧缓存仍保留旧日期，禁止在新日冒充今日K线。
        if day != today or not query['from'] <= day <= query['to'] or data is not None and any(r['date'] >= day for r in data['bars']):
            return response
        metadata=_metadata(dict(provider='Qmt',instance_id='wt-writer',session_id=snapshot['control_id'],generation=1),
            hashlib.sha256(raw).hexdigest(),'wt-current-day.v1',self._profile)
        if data is None:
            data=dict(bars=[],metadata=metadata)
        rows={}
        for part in data.get('provenance',[dict(offset=0,count=len(data['bars']),metadata=data['metadata'])]):
            for old in data['bars'][part['offset']:part['offset']+part['count']]:
                rows[old['date']]=(old,part['metadata'])
        rows[day]=(dict(symbol=symbol,date=day,
            **{k:row[k] for k in ('open','high','low','close','volume','amount')}),metadata)
        selected=_select(rows,query,data['metadata'])
        selected['current_day']=dict(
            date=day,  # 未收盘行对应的原交易日，必须在返回bars中。
            source_at=source_at.isoformat(),  # 原tick发生时间，上海时区。
            observed_at=snapshot['observed_at'],  # WT读取Writer快照的时间。
            closed=False)  # 本入口只观察当前值，闭合资格由原归档提供。
        result=dict(api_version=API_VERSION,status=dict(code='Ok',reason=''),data=selected)
        _need(len(encode_json(result)) <= self._maximum)
        return validate_response(result,request)

    def close(self):
        if self._closed:
            return
        _need(threading.get_ident() == self._owner)
        if self._base is not None:
            self._base.close()
        self._closed=True
