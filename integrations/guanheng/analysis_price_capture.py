"""原QAB捕获的唯一价格投影读取；不连接行情、不准备缓存、不改原slot。"""
import base64
import hashlib
import math
from pathlib import Path
import time

from ..guanheng_market_client import strict_json
from ..guanheng_market_client.daily_contract import REFERENCE_PREFIX
from .market_generation import read_fixed


def original_price_quality(bar):
    """完整原价行的Native准入；原零量/零金额保留，零价及OHLC矛盾分别报告。"""
    if set(bar)!={'open','high','low','close','volume','amount'}:
        return 'source_fields_missing'
    if any(type(v)not in(int,float)or not math.isfinite(v)for v in bar.values()):
        return 'source_nonfinite_fields'
    if min(bar[k]for k in ('open','high','low','close'))<=0:
        return 'source_nonpositive_price'
    if min(bar['volume'],bar['amount'])<0:
        return 'source_negative_quantity'
    if (bar['low']>min(bar['open'],bar['close'])or bar['high']<max(bar['open'],bar['close'])
            or bar['low']>bar['high']):return 'source_inconsistent_ohlc'
    return 'qualified'


def capture_profile(manifest, capture_sha256, adjustment):
    """原导入profile保持字段、值与顺序；原价与供应商前复权分别标识。"""
    if adjustment not in ('none','front_ratio'):
        raise ValueError('analysis capture adjustment invalid')
    request=manifest['request']
    return dict(
        provider='Qmt',  # 原QAB提供者，不推造其他供应商来源。
        instance_id='qmt-batch-source:'+capture_sha256[:32],  # 捕获内容身份，区别WT进程实例。
        session_id=request['capture_id'],  # 原持久捕获UUID。
        generation=1,  # 原不可变捕获内容的一代，不借用终端运行代际。
        dataset_version='qmt.batch-native-day.v1',  # 原QAB日线数据集合同。
        source_license='unknown',  # 本通道未独立提供授权资格。
        input_kind='qmt_export'if manifest['source_kind']=='actual-qmt'else'synthetic',  # 真源与替身保持区分。
        timezone='Asia/Shanghai',  # 原交易日期标签时区，非接收时刻。
        minute_boundary='unknown',  # 日线不提升分钟边界资格。
        adjustment=adjustment,  # none原价与front_ratio来源分析价。
        factor_version=''if adjustment=='none'else REFERENCE_PREFIX+capture_sha256,  # 原来源参考，不声称独立因子。
        value_semantics='source',  # 原数值保持，未做数量/金额换算。
        price_unit='unknown',  # 无本批独立价格单位证明。
        volume_unit='unknown',  # 缺量不填0，原真实0仍由原件保存。
        amount_unit='unknown')  # 缺金额不填0，原真实0仍由原件保存。


def capture_metadata(manifest, capture_sha256, adjustment):
    """把同一原profile映射到公开来源元数据；内容SHA绑定整份已验证捕获。"""
    profile=capture_profile(manifest,capture_sha256,adjustment)
    value={key:profile[key]for key in ('dataset_version','source_license','adjustment','factor_version',
        'timezone','value_semantics','price_unit','volume_unit','amount_unit','minute_boundary')}
    value.update(
        source={key:profile[key]for key in ('provider','instance_id','session_id','generation')},  # 原捕获身份。
        qualification='DevelopmentVerified',  # 数据链资格，不授完整市场或历史可知。
        period='1d',  # 来源日线周期。
        timestamp_semantics='source_date',  # 每条标签表示交易日期。
        content_id=capture_sha256)  # 原manifest及逐slot摘要集合身份。
    return value


def load_price_capture(descriptor):
    """一次准入原manifest/原slot；调用方按原证据读取后续价格投影。"""
    from guanheng_qmt_shm.analysis_batch_source import read_capture
    if type(descriptor)is not dict or set(descriptor)!={'directory','sha256'}:
        raise ValueError('analysis capture descriptor invalid')
    root=Path(descriptor['directory']).absolute()
    raw=read_fixed(root/'manifest.json',maximum=16777216,identity=descriptor['sha256'])
    manifest=read_capture(root)
    if manifest!=strict_json(raw):raise ValueError('analysis capture changed during admission')
    return manifest


def read_price_batch(directory,batch,manifest,*,read=None):
    """同一manifest内单个批次的固定SHA/价格字段准入；允许调用方提供原有界读函数。"""
    root=Path(directory).absolute();slot=root/batch['slot']
    if not slot.resolve().is_relative_to(root.resolve()):raise ValueError('analysis capture slot escaped')
    raw=(read(slot,16777216)if read is not None else read_fixed(slot,maximum=16777216))
    if hashlib.sha256(raw).hexdigest()!=batch['sha256']:raise ValueError('analysis capture slot differs')
    record=strict_json(raw);body=base64.b64decode(record['result']['result_body_b64'],validate=True)
    if (hashlib.sha256(body).hexdigest()!=batch['result_body_sha256']
            or record['result']['result_body_sha256']!=batch['result_body_sha256']):
        raise ValueError('analysis capture result differs')
    data=strict_json(body)['data']
    if data['adjustment']!=batch['adjustment']or set(data['securities'])!=set(batch['symbols']):
        raise ValueError('analysis capture batch selection differs')
    for item in data['securities'].values():
        if item['status']not in ('observed','empty','missing','invalid','requires_partition'):
            raise ValueError('analysis capture source state invalid')
        for day,bar in item['data'].items():
            if not manifest['request']['start_date']<=day<=manifest['request']['end_date']:
                raise ValueError('analysis capture date outside request')
            if set(bar)!={'open','high','low','close','volume','amount'}or any(
                    type(v)not in(int,float)or not math.isfinite(v)or v<0 for v in bar.values()):
                raise ValueError('analysis capture original numeric fields invalid')
    return data['securities']


def price_batches(descriptor, manifest, *, adjustment='none', deadline, cancelled=lambda:False):
    """流式返回每原批次的证券/原值；只物化一份已绑定结果，不聚合全市场副本。

    descriptor须先由load_price_capture准入；每次读取仍核原slot SHA。原始0保持，
    缺项/非有限值明确失败，不为Native构造价格或量额。取消和总D沿数据owner。
    """
    if adjustment not in ('none','front_ratio')or not callable(cancelled):
        raise ValueError('analysis capture selection invalid')
    if type(deadline)not in(int,float)or not math.isfinite(deadline):
        raise ValueError('analysis capture finite deadline required')
    root=Path(descriptor['directory']).absolute()
    for batch in manifest['batches']:
        if batch['adjustment']!=adjustment:continue
        if cancelled():raise InterruptedError('analysis capture stopped')
        if time.monotonic()>=deadline:raise TimeoutError('analysis capture deadline')
        yield batch,read_price_batch(root,batch,manifest)
