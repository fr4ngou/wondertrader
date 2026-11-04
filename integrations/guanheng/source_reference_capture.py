"""受管Source名册/详情消费接缝；原retained客户端和生命周期由数据owner提供。"""
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
import time

from .daily_data_update import _save
from ..guanheng_market_client.security import validate_security_identity

UNIVERSE = 'market.security_universe'
DETAILS = 'market.security_details'
MARKETS = {'SH': 'SSE', 'SZ': 'SZSE', 'BJ': 'BSE'}
KINDS = ('stock', 'etf', 'index')
RAW_FIELDS = {'ExchangeID','InstrumentID','InstrumentName','OpenDate','ExpireDate','IsTrading','FloatVolumn','TotalVolumn'}


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('reference source fields differ')


def _clock(value):
    if type(value) is not str:
        raise ValueError('reference source clock missing')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError('reference source clock must be UTC')


def _symbol(value):
    if type(value) is not str or re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)', value) is None:
        raise ValueError('reference source symbol invalid')
    code, market = value.split('.')
    return MARKETS[market]+'.'+code, market


def _hash(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('reference catalog identity invalid')


def _date(value):
    if value is not None and (type(value) is not str or date.fromisoformat(value).isoformat() != value):
        raise ValueError('reference source date invalid')


def capture_reference(source, scope, directory, *, deadline, cancelled=lambda:False,
                      maximum_records=20000, maximum_pages=128):
    """同步消费有限分页及64只详情；缺少新能力时保持明确等待，不取本地终端文件。

    source为原SecurityReferenceSource消费接缝，调用方关闭其transport；同目录恢复沿原slot。
    scope含markets/security_types/limit，不含游标；价格池与指标池由上层分别保存。
    此处仅形成资料事实，不授价格覆盖、历史可知、股本单位或全部字段完整资格。
    """
    _fields(scope, 'markets security_types limit')
    for key, allowed in [('markets', tuple(MARKETS)), ('security_types', KINDS)]:
        values = scope[key]
        if (type(values) is not list or not values or any(type(v)is not str for v in values)
                or values != [v for v in allowed if v in values]):
            raise ValueError('reference source scope invalid')
    if (type(scope['limit']) is not int or not 1 <= scope['limit'] <= 256
            or type(maximum_records) is not int or not 1 <= maximum_records <= 20000
            or type(maximum_pages) is not int or not 1 <= maximum_pages <= 128):
        raise ValueError('reference source capacity invalid')
    if type(deadline) not in (int,float) or not math.isfinite(deadline) or not callable(cancelled):
        raise ValueError('reference source deadline invalid')

    def check():
        if cancelled():
            raise InterruptedError('reference capture stopped')
        if time.monotonic() >= deadline:
            raise TimeoutError('reference capture deadline')

    def original(path, value):
        if path.exists():
            if json.loads(path.read_bytes()) != value:
                raise ValueError('reference capture original identity differs')
        else:
            _save(path, value)

    check()
    root = Path(directory).absolute()
    root.mkdir(parents=False,exist_ok=True)
    original(root/'REQUEST.json',dict(
        scope=scope,  # 固定市场/类型/分页额度，恢复沿原请求范围。
        maximum_records=maximum_records,  # 整份捕获的去重证券上限。
        maximum_pages=maximum_pages))  # 同一名册的最大分页次数。
    from guanheng_qmt_shm.read_retention_client import RetainedReadPending,RetainedReadBindingChanged
    capability=source.capabilities(deadline=deadline);metadata=capability['metadata']
    missing = [name for name in (UNIVERSE,DETAILS) if name not in metadata['profile']['operation_profiles']]
    if capability['state']!='ready':
        state = dict(
            state='waiting_reference_capability',  # Source尚未提供本合同；已有日线继续服务。
            missing_operations=missing,  # 仅固定操作名称，不包含凭据或异常正文。
            membership_complete=False,  # 尚未取得完整名册，不以旧资料目录替代。
            expected_count=None)  # 未知应覆盖数保持null。
        _save(root/'STATE.json',state)
        return state
    binding_path=root/'BINDING.json'
    if binding_path.exists():
        pinned=json.loads(binding_path.read_bytes())
    else:
        original(binding_path,metadata);pinned=metadata
    binding=pinned['binding']
    evidence = []

    def call(operation, arguments, name):
        check()
        slot = root/name
        if not slot.exists():
            current=source.capabilities(deadline=deadline)
            if current['state']!='ready':raise RetainedReadPending('reference_capability_waiting')
            if current['metadata']['binding']!=binding:
                raise RetainedReadBindingChanged('reference_capture_binding_changed')
        method=source.universe if operation==UNIVERSE else source.details
        while True:
            check()
            try:
                observed=method(arguments,slot,deadline=deadline,expected_binding=binding)
            except RetainedReadPending as failure:
                if str(failure)!='read_retention_capacity_rejected':raise
                # 原SDK已确认尚未受理，仍以同槽/UUID等待正常容量释放；通信未知交回owner。
                check();time.sleep(min(.25,max(0,deadline-time.monotonic())))
                continue
            break
        if observed['state']!='observed':raise RetainedReadPending('reference_result_waiting')
        returned=observed['result']
        if returned['binding']!=binding:raise RetainedReadBindingChanged('reference_result_binding_changed')
        check()
        body = slot.read_bytes()
        if len(body) > 2*1024*1024:
            raise ValueError('reference source slot capacity')
        evidence.append(dict(path=str(slot),sha256=hashlib.sha256(body).hexdigest()))
        return returned['reply']['data']

    cursor = None
    cursors = set()
    header = None
    members = {}
    for page_number in range(maximum_pages):
        page = call(UNIVERSE,dict(scope,cursor=cursor),'universe-%03d.json'%page_number)
        _fields(page,'schema catalog_id captured_at source_as_of markets security_types state total_count groups items next_cursor')
        if page['schema'] != 'qmt.security-universe.v1' or page['state'] not in ('complete','partial'):
            raise ValueError('reference universe schema invalid')
        _hash(page['catalog_id']);_clock(page['captured_at'])
        if page['source_as_of'] is not None:_clock(page['source_as_of'])
        if page['markets'] != scope['markets'] or page['security_types'] != scope['security_types']:
            raise ValueError('reference universe scope changed')
        selected = {key:page[key] for key in page if key not in ('items','next_cursor')}
        if header is None:header = selected
        elif selected != header:raise ValueError('reference universe changed across pages')
        if type(page['items']) is not list or len(page['items']) > scope['limit']:
            raise ValueError('reference universe page capacity')
        for item in page['items']:
            _fields(item,'symbol market security_type source_groups')
            _, market = _symbol(item['symbol'])
            if (market != item['market'] or market not in scope['markets']
                    or item['security_type'] not in set(scope['security_types'])|{'unknown'}
                    or type(item['source_groups']) is not list or len(item['source_groups'])>64
                    or any(type(name) is not str or not name or len(name)>128 for name in item['source_groups'])
                    or item['symbol'] in members):
                raise ValueError('reference universe member invalid or repeated')
            members[item['symbol']] = item
            if len(members) > maximum_records:raise ValueError('reference universe total capacity')
        cursor = page['next_cursor']
        if cursor is None:break
        if type(cursor) is not str or not 1 <= len(cursor.encode('utf8')) <= 512 or cursor in cursors or not page['items']:
            raise ValueError('reference universe cursor invalid')
        cursors.add(cursor)
    else:
        raise ValueError('reference universe pagination incomplete')
    expected_groups = {(m,k) for m in scope['markets'] for k in scope['security_types']}
    groups = {}
    if type(header['groups']) is not list or len(header['groups']) != len(expected_groups):
        raise ValueError('reference universe group shape invalid')
    for group in header['groups']:
        _fields(group,'market security_type state expected_count observed_count source_groups reason_code')
        key = (group['market'],group['security_type'])
        if key not in expected_groups or key in groups or group['state'] not in ('complete','partial','unavailable','unsupported'):
            raise ValueError('reference universe group invalid')
        if type(group['observed_count']) is not int or group['observed_count'] < 0:
            raise ValueError('reference universe observed count invalid')
        if (type(group['source_groups']) is not list or len(group['source_groups'])>64
                or any(type(v)is not str or not 1<=len(v)<=128 for v in group['source_groups'])):
            raise ValueError('reference universe group evidence invalid')
        if group['state'] == 'complete':
            if type(group['expected_count']) is not int or group['expected_count'] != group['observed_count'] or group['reason_code'] is not None:
                raise ValueError('reference universe complete group count differs')
            actual = sum((v['market'],v['security_type']) == key for v in members.values())
            if actual != group['expected_count']:raise ValueError('reference universe complete member count differs')
        elif (group['expected_count'] is not None or type(group['reason_code']) is not str
              or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',group['reason_code']) is None):
            raise ValueError('reference universe unknown group fabricated')
        groups[key] = group
    if set(groups) != expected_groups:raise ValueError('reference universe group missing')
    complete = all(g['state']=='complete' for g in groups.values()) and all(v['security_type']!='unknown' for v in members.values())
    if header['state'] != ('complete' if complete else 'partial'):
        raise ValueError('reference universe completeness differs')
    if (complete and (type(header['total_count']) is not int or header['total_count'] != len(members))
            or not complete and header['total_count'] is not None):
        raise ValueError('reference universe total count fabricated')
    securities = {}
    unavailable = 0
    symbols = sorted(members)
    for start in range(0,len(symbols),64):
        selected = symbols[start:start+64]
        data = call(DETAILS,dict(catalog_id=header['catalog_id'],symbols=selected),'details-%03d.json'%(start//64))
        _fields(data,'schema catalog_id captured_at source_as_of items')
        if data['schema'] != 'qmt.security-details.v1' or data['catalog_id'] != header['catalog_id']:
            raise ValueError('reference details identity differs')
        _clock(data['captured_at'])
        if data['source_as_of'] is not None:_clock(data['source_as_of'])
        if type(data['items']) is not list or len(data['items']) != len(selected):raise ValueError('reference details count differs')
        seen = set()
        for item in data['items']:
            _fields(item,'symbol market status name listed_on expires_on trading_status observed_at field_reasons raw_fields')
            symbol,market = _symbol(item['symbol'])
            if item['symbol'] not in selected or item['symbol'] in seen or item['market'] != market:
                raise ValueError('reference details symbol differs')
            seen.add(item['symbol'])
            if item['status'] not in ('observed','unavailable') or item['trading_status'] not in ('active','halted','unknown'):
                raise ValueError('reference details status invalid')
            _clock(item['observed_at']);_date(item['listed_on']);_date(item['expires_on'])
            if type(item['field_reasons']) is not dict or type(item['raw_fields']) is not dict or not set(item['raw_fields'])<=RAW_FIELDS:
                raise ValueError('reference details raw fields invalid')
            if any(type(k)is not str or type(v)is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,63}',v)is None
                   for k,v in item['field_reasons'].items()):
                raise ValueError('reference details field reason invalid')
            if any(type(v)not in (type(None),bool,int,float,str) for v in item['raw_fields'].values()):
                raise ValueError('reference details original scalar invalid')
            if len(json.dumps(item,allow_nan=False).encode('utf8'))>4096:raise ValueError('reference details row capacity')
            if item['status']=='unavailable':
                unavailable += 1
                if any(item[k]is not None for k in ('name','listed_on','expires_on')) or item['trading_status']!='unknown':
                    raise ValueError('reference unavailable details fabricated')
            securities[symbol] = validate_security_identity(dict(
                symbol=symbol,  # WT规范身份，来自已验证的Source符号后缀。
                name=item['name'],  # 原名或None，详情缺项不删除证券。
                market=MARKETS[market],  # 明确市场映射，不按名称或代码前缀猜测。
                security_type=members[item['symbol']]['security_type'],  # 原Source分类及unknown。
                listed_on=item['listed_on'],  # 当前可见上市事实，未知保留None。
                expires_on=item['expires_on'],  # 当前可见到期事实，哨兵值不转换。
                observed_at=item['observed_at']))  # 原资料观察时刻，不冒充历史可知。
    reference = dict(
        schema='guanheng.security-reference.v2',  # 动态Source分页谱系；v1静态三原件合同继续独立读取。
        securities=securities,  # 全部已取得名册证券，保留缺详情与unknown分类。
        provenance=dict(
            catalog_id=header['catalog_id'],  # 原Source名册身份，与价格版本区分。
            captured_at=header['captured_at'],  # 名册实际捕获时刻，不回填市场日期。
            source_as_of=header['source_as_of'],  # SDK独立资料时点；未知保持None。
            groups=header['groups'],  # 原逐组完整性和原因，不推导未知分母。
            evidence=evidence))  # 原逐槽路径/SHA，凭据不进入派生资料。
    encoded = json.dumps(reference,ensure_ascii=False,allow_nan=False).encode('utf8')
    if len(encoded)>16*1024*1024:raise ValueError('reference normalized catalogue capacity')
    descriptor = None
    if securities:
        _save(root/'REFERENCE.json',reference)
        descriptor = dict(path=str(root/'REFERENCE.json'),sha256=hashlib.sha256((root/'REFERENCE.json').read_bytes()).hexdigest())
    state = dict(
        state='captured',  # 原分页和详情观察完成，不声称价格或全部字段完整。
        membership_complete=complete,  # 仅分组和名册去重计数完整性。
        observed_count=len(members),  # 实际取得的证券数，非推算市场总数。
        expected_count=header['total_count'],  # 未知完整分母保持None。
        details_unavailable=unavailable,  # 详情不可用数量，证券仍在价格池。
        groups=header['groups'],  # 逐类原完整性、应覆盖数和原因。
        reference=descriptor)  # 非空派生资料固定身份；空名册不替换已有可用资料。
    _save(root/'STATE.json',state)
    return state
