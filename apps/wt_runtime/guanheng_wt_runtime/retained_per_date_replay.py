"""消费A逐日原生窗口；原Porter、财务、周期和数量推进复用原回放owner。"""
from dataclasses import fields
from datetime import date
import hashlib
import json
import re
from types import MappingProxyType

from guanheng_strategy_core.contracts import canonical_bytes
from guanheng_strategy_v1 import RetainedHistoricalModel, RetainedInput

from .retained_replay import RetainedBacktestSession
from .strategy_replay_facts import SessionError, _digest

REPORT_SCHEMA = 'guanheng.retained-per-date-replay-report.v1'
INPUT_SCHEMA = 'guanheng.retained-per-date-replay-input.v1'
REPORT_SCOPE = 'per-date-front-ratio-reconstruction; historical-15:00-assumed; availability/revisions-unknown; RT/broker/production-unqualified'
_WIRE = {'schema','analysis_ready','analysis','history','current_view','units','selection','replay_identity','qualification'}


def _require(value, reason):
    if not value:
        raise SessionError(reason)


def normalize_source_binding(value):
    """复制原逐日纯值身份；父宿主与session共用日期/SHA准入。"""
    _require(type(value) is dict and set(value) == {'schema', 'manifest_sha256', 'windows'}
        and value['schema'] == 'guanheng.retained-per-date-source.v1', '逐日来源绑定字段失配')
    manifest, windows = value['manifest_sha256'], value['windows']
    _require(type(manifest) is str and re.fullmatch('[0-9a-f]{64}', manifest)
        and type(windows) is dict and 1 <= len(windows) <= 4096, '逐日来源身份或容量无效')
    previous = ''
    for day, digest in windows.items():
        _require(type(day) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', day)
            and previous < day and type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest),
            '逐日日期顺序或窗口身份无效')
        try:
            date.fromisoformat(day)
        except ValueError:
            raise SessionError('逐日日期无效') from None
        previous = day
    return dict(schema=value['schema'], manifest_sha256=manifest, windows=dict(windows))


class RetainedPerDateBacktestSession(RetainedBacktestSession):
    """market_source是调用者以A公开API打开的只读对象；本类不动态导入代码。

    source_binding固定全部日期/窗口SHA和manifest；每轮沿原D再核本轮窗口。
    委托、持仓、资金、周期及用户状态继续由父类的原生上下文拥有。
    """
    def __init__(self, inputs, *, market_source, source_binding, **kwargs):
        source_binding = normalize_source_binding(source_binding)
        manifest=source_binding['manifest_sha256'];windows=source_binding['windows']
        self._market_source=market_source
        self._manifest_sha=manifest;self._window_shas=MappingProxyType(dict(windows))
        _require(getattr(market_source,'manifest_sha256',None)==manifest
            and tuple(windows)==tuple(market_source.dates), '逐日来源和日期顺序失配')
        super().__init__(inputs, **kwargs)
        days=tuple(self._clock(day,1500).date().isoformat() for day in self._days)
        _require(days==tuple(self._window_shas), '逐日来源须覆盖本次完整原价日期')
        last=self._read_window(days[-1],lambda:None)
        _require(self._inputs.volume_unit==last['units']['volume'], '逐日来源成交量单位与原生bar声明失配')
        final=self._decode_window(last, self._inputs.request)
        _require((final.history,final.analysis,final.current_view)==
            (self._inputs.request.history,self._inputs.request.analysis,self._inputs.request.current_view),
            '初始完整输入与目录末窗失配')
        self._input_id=_digest((self._input_id,source_binding))

    def _read_window(self, day, check):
        check();wire=self._market_source.window(day);check()
        _require(type(wire) is dict and set(wire)==_WIRE and wire['analysis_ready'] is True
            and wire['schema']=='guanheng.qmt-native-analysis-window.v1'
            and wire['units']=={'price':'CNY','volume':'lot','amount':'unknown'}, '逐日窗口协议或单位失配')
        _require(type(wire['history']) is dict and type(wire['history'].get('observations')) is list
            and 1<=len(wire['history']['observations'])<=32768
            and type(wire['analysis']) is dict and type(wire['analysis'].get('bars')) is list
            and len(wire['analysis']['bars'])==len(wire['history']['observations']), '逐日窗口行数超出完整前缀容量')
        raw=json.dumps(wire,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')
        _require(0<len(raw)<=32*1024*1024 and hashlib.sha256(raw).hexdigest()==self._window_shas[day],
            '逐日窗口内容摘要漂移')
        value=json.loads(raw);identity=value['replay_identity'];check()
        _require(value['analysis']['basis_date']==day and identity['manifest_sha256']==self._manifest_sha,
            '逐日窗口基准或目录身份失配')
        return value

    @staticmethod
    def _decode_window(wire, request):
        small={field.name:getattr(request,field.name) for field in fields(RetainedInput)
               if field.name not in ('history','analysis','current_view')}
        value=json.loads(canonical_bytes(small,max_bytes=65536))
        value.update({key:wire[key] for key in ('history','analysis','current_view')})
        return RetainedInput.from_dict(value)

    def _market_request(self, cutoff, cycles, exits, check):
        request,unused,unused_publication=super()._market_request(cutoff,cycles,exits,check)
        native_prefix=request.history.observations
        day=cutoff.date().isoformat();wire=self._read_window(day,check)
        request=self._decode_window(wire,request);check()
        _require(request.history.observations[-1].trade_date==cutoff.date()
            and all(row.trade_date<=cutoff.date() for row in request.history.observations), '逐日原价含未来或缺末日')
        # 原Porter的撮合序列来自末窗raw；逐日分析须对应同一组原生原值。
        values=('symbol','trade_date','open','high','low','close','volume','amount')
        _require(len(request.history.observations)==len(native_prefix)
            and all(tuple(getattr(row,k) for k in values)==tuple(getattr(original,k) for k in values)
                    for row,original in zip(request.history.observations,native_prefix)), '逐日计算与原生撮合raw前缀失配')
        # 既有历史模型逐次绑定本窗口；实际实收时间保持，15:00属于显式回测假设。
        model=RetainedHistoricalModel(request.current_view.dataset_sha256,request.history.factor_revision,
            request.analysis.basis_date,request.current_view.received_at)
        publication=dict(manifest_sha256=self._manifest_sha,window_sha256=self._window_shas[day],
            basis_date=day,factor_revision=request.history.factor_revision,
            known_at=request.analysis.known_at.isoformat(),received_at=request.current_view.received_at.isoformat(),
            native_output_sha256=wire['replay_identity']['native_output_sha256'])
        return request,model,publication

    def _report_market(self):
        return dict(schema=REPORT_SCHEMA,scope=REPORT_SCOPE,historical_model=None,
            per_date_source=dict(schema='guanheng.retained-per-date-source.v1',manifest_sha256=self._manifest_sha,
                                 windows=dict(self._window_shas)))
