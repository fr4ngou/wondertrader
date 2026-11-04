"""WT已落盘行情快照及证券资料合同；原件归数据侧，消费者只读。"""
from datetime import date,datetime,timezone
import hashlib,json,re
from . import MarketProtocolError,_object,_text,_number,_list


def _day(value):
    if type(value)is not str or date.fromisoformat(value).isoformat()!=value:
        raise MarketProtocolError('market snapshot date invalid')
    return value


def _hash(value):
    if type(value)is not str or re.fullmatch('[0-9a-f]{64}',value)is None:
        raise MarketProtocolError('market snapshot identity invalid')
    return value


def _clock(value):
    if type(value)is not str:raise MarketProtocolError('market snapshot source clock invalid')
    parsed=datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset()is None or parsed>datetime.now(timezone.utc):
        raise MarketProtocolError('market snapshot source clock invalid')


def snapshot_identity(value):
    """绑定整个数据目录和定日证券池；字段顺序不影响身份。"""
    body={k:v for k,v in value.items()if k!='snapshot_id'}
    return hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()


def validate_snapshot_request(value):
    """date为需要的已闭合观察日YYYY-MM-DD；来源缺日保持Unavailable。"""
    _object(value,('date',));_day(value['date']);return value


def validate_market_snapshot(value):
    """members为定日WT股票池；basics为各自observed_at可见资料，空项保持None。

    source_received_at是本批日线原件收齐时刻；observation_date是交易日期，
    二者分别保存。price_bases列已落盘口径。provenance中的摘要绑定原件及base配置。
    """
    _object(value,('schema','snapshot_id','observation_date','members','source_kind','source_received_at',
        'price_bases','price_reference','basics','provenance'))
    if value['schema']!='guanheng.market-source-snapshot.v1':raise MarketProtocolError('market snapshot schema invalid')
    _hash(value['snapshot_id']);_day(value['observation_date']);_clock(value['source_received_at'])
    if value['source_kind']not in ('actual-qmt','sdk-synthetic')or value['price_bases']!=['none','front_ratio']:
        raise MarketProtocolError('market snapshot source or price basis invalid')
    reference=_object(value['price_reference'],('kind','capture_sha256','requested_from','requested_to',
        'reference_date','independent_factors'))
    if (reference['kind']!='supplier_current_front_ratio'or reference['reference_date']is not None
            or reference['independent_factors']is not None):
        raise MarketProtocolError('market snapshot price reference invalid')
    from .source_history import _date
    first,last=reference['requested_from'],reference['requested_to']
    if (type(first)is not str or type(last)is not str or len(first)!=8 or len(last)!=8
            or _date(int(first))>_date(int(last))):
        raise MarketProtocolError('market snapshot price reference range invalid')
    _hash(reference['capture_sha256'])
    members=_list(value['members'],10000)
    if (not members or any(type(s)is not str or re.fullmatch(r'(SSE|SZSE|BSE)\.[0-9]{6}',s)is None for s in members)
            or members!=sorted(set(members))):
        raise MarketProtocolError('market snapshot membership invalid')
    basics=value['basics']
    if type(basics)is not dict or set(basics)!=set(members):raise MarketProtocolError('market snapshot basic coverage invalid')
    for symbol,row in basics.items():
        if row is None:continue
        _object(row,('name','market','security_type','listed_on','expires_on','float_volume','total_volume','volume_unit','observed_at'))
        _text(row['name'],limit=128)
        if row['market']!=symbol.split('.')[0]or row['security_type']!='stock':
            raise MarketProtocolError('market snapshot basic classification differs')
        for key in ('listed_on','expires_on'):
            if row[key]is not None:_day(row[key])
        for key in ('float_volume','total_volume'):
            if row[key]is not None:_number(row[key])
        if row['volume_unit']not in ('share','unknown'):raise MarketProtocolError('market snapshot basic volume unit invalid')
        _clock(row['observed_at'])
    required=('capture_sha256','source_binding_sha256','universe_sha256','basics_sha256','base_configuration_sha256')
    provenance=_object(value['provenance'],required+('daily_facts_sha256','security_reference_sha256','calendar_sha256'),required)
    for identity in provenance.values():_hash(identity)
    if reference['capture_sha256']!=provenance['capture_sha256']:
        raise MarketProtocolError('market snapshot price reference differs')
    if snapshot_identity(value)!=value['snapshot_id']:raise MarketProtocolError('market snapshot content differs')
    return value
