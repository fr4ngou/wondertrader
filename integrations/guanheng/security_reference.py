"""WT数据侧证券资料/日历读取和原件准备；资料与价格生命周期分别保留。"""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

from ..guanheng_market_client import strict_json
from ..guanheng_market_client.market_snapshot import _day, _clock, _hash
from ..guanheng_market_client.security import validate_security_identity
from .market_generation import read_fixed, encode


def trade_day_state(state):
    """原合格日事实的交易状态解释；缺成交量与真实零量分开，不生成价格。"""
    if state is None or state['qualification']!='qualified':return 'unresolved'
    if state['tradestatus']=='0':
        if not state['volume']:return 'source_halted_quantity_unknown'
        if Decimal(state['volume'])==0:return 'source_halted_no_trade'
        return 'source_trade_state_inconsistent'
    if state['tradestatus']=='1'and state['close_reference']and Decimal(state['close_reference'])>0:
        return 'source_active'
    return 'unresolved'


def _descriptor(value, maximum):
    if (type(value) is not dict or set(value) != {'path', 'sha256'}
            or type(value['path']) is not str or not Path(value['path']).is_absolute()):
        raise ValueError('security reference descriptor invalid')
    return strict_json(read_fixed(value['path'], maximum=maximum, identity=_hash(value['sha256'])))


def _calendar(value):
    if (type(value) is not dict or value.get('kind') != 'official-exchange-calendar/v1'
            or type(value.get('id')) is not str or not 1 <= len(value['id']) <= 128):
        raise ValueError('security calendar invalid')
    first, last = _day(value['coverage_start']), _day(value['coverage_end'])
    if first > last:
        raise ValueError('security calendar range invalid')
    days = value['closed_dates']
    if type(days) is not list or len(days) > 10000 or days != sorted(set(days)):
        raise ValueError('security calendar closed dates invalid')
    for day in days:
        _day(day)
    if value.get('verified_through') is not None:
        _day(value['verified_through'])
    if not isinstance(value.get('evidence'), list) or not value['evidence']:
        raise ValueError('security calendar evidence missing')
    return value


def _source_reference_lineage(value, securities):
    """动态资料的Source名册/分组/原槽谱系；只校声明，不在查询热路径重读原槽。"""
    if type(value)is not dict or set(value)!={'catalog_id','captured_at','source_as_of','groups','evidence'}:
        raise ValueError('dynamic security reference lineage invalid')
    _hash(value['catalog_id']);_clock(value['captured_at'])
    if value['source_as_of']is not None:_clock(value['source_as_of'])
    groups=value['groups']
    if type(groups)is not list or not 1<=len(groups)<=9:
        raise ValueError('dynamic security reference groups invalid')
    markets={'SH':'SSE','SZ':'SZSE','BJ':'BSE'};seen=set()
    for group in groups:
        if type(group)is not dict or set(group)!={'market','security_type','state','expected_count','observed_count','source_groups','reason_code'}:
            raise ValueError('dynamic security reference group fields invalid')
        key=(group['market'],group['security_type'])
        if (key in seen or key[0]not in markets or key[1]not in ('stock','etf','index')
                or group['state']not in ('complete','partial','unavailable','unsupported')
                or type(group['observed_count'])is not int or group['observed_count']<0):
            raise ValueError('dynamic security reference group invalid')
        seen.add(key)
        if group['state']=='complete':
            actual=sum(row['market']==markets[key[0]]and row['security_type']==key[1]for row in securities.values())
            if (type(group['expected_count'])is not int or group['expected_count']!=actual
                    or group['observed_count']!=actual or group['reason_code']is not None):
                raise ValueError('dynamic security reference complete count differs')
        elif group['expected_count']is not None or type(group['reason_code'])is not str or not group['reason_code']:
            raise ValueError('dynamic security reference unknown count fabricated')
        if type(group['source_groups'])is not list or any(type(v)is not str or not 1<=len(v)<=128 for v in group['source_groups']):
            raise ValueError('dynamic security reference group evidence invalid')
    evidence=value['evidence']
    if type(evidence)is not list or not 1<=len(evidence)<=512:
        raise ValueError('dynamic security reference evidence capacity invalid')
    for item in evidence:
        if type(item)is not dict or set(item)!={'path','sha256'}or type(item['path'])is not str or not Path(item['path']).is_absolute():
            raise ValueError('dynamic security reference evidence invalid')
        _hash(item['sha256'])


def _reference_catalog(value):
    """验证单份v1/v2当前资料；完整Source组只按这份当前名册计算。"""
    if (type(value)is not dict or set(value)!={'schema','securities','provenance'}
            or value['schema']not in('guanheng.security-reference.v1','guanheng.security-reference.v2')
            or type(value['securities'])is not dict or not 1<=len(value['securities'])<=20000):
        raise ValueError('security reference catalog invalid')
    _identities(value['securities'])
    original=value['provenance']
    if value['schema']=='guanheng.security-reference.v1':
        if type(original)is not dict or set(original)!={'catalog_sha256','details_sha256','indices_sha256'}:
            raise ValueError('security reference lineage invalid')
        _hash(original['catalog_sha256'])
        if original['details_sha256']is not None:_hash(original['details_sha256'])
        if original['indices_sha256']is not None:_hash(original['indices_sha256'])
    else:_source_reference_lineage(original,value['securities'])
    return value


def _identities(rows):
    if type(rows)is not dict or not 1<=len(rows)<=20000:
        raise ValueError('security reference identity capacity invalid')
    for symbol,row in rows.items():
        validate_security_identity(row)
        if row['symbol']!=symbol:raise ValueError('security reference key differs')


class SecurityReference:
    """单个SnapshotSourceMarket拥有本对象；最多20000项/16MiB原JSON，关闭释放。"""
    def __init__(self, reference=None, calendar=None):
        self._rows = {}  # WT证券身份到不可变资料，最多20000项，随本市场版本关闭。
        self._dynamic_symbols=set()  # 当前v2成员拥有名称/日期；保留成员继续沿其历史资料及原basic规则。
        self._retained_symbols=set()  # 组合资料中的历史保留成员；只允许时间更近的完整basic替换资料字段。
        self.current_reference=reference  # v1/v2叶原件描述符；组合资料写入时展平，避免当前引用递归增长。
        self.reference_sha256 = None  # 固定资料原件SHA，未配置时None，区别于价格缺失。
        self._calendar = None  # 原官方日历对象；缺项时不推断任何交易日。
        self._calendar_sha256 = None  # 日历原件字节SHA，供缺口复核。
        self._closed_days = set()  # 同日历年度休市日期集合；仅用于已覆盖区间。
        self._closed = False  # 关闭后拒绝读；内存由本实例close归还。
        if reference is not None:
            value = _descriptor(reference, 16777216)
            if type(value)is dict and value.get('schema')=='guanheng.security-reference.v3':
                if set(value)!={'schema','securities','provenance'}:
                    raise ValueError('retained security reference fields invalid')
                _identities(value['securities']);original=value['provenance']
                if type(original)is not dict or set(original)!={'current_reference','retained_sources'}:
                    raise ValueError('retained security reference lineage invalid')
                sources=original['retained_sources']
                if type(sources)is not list or not 1<=len(sources)<=370:
                    raise ValueError('retained security reference sources invalid')
                for item in sources:
                    if (type(item)is not dict or set(item)!={'path','sha256'}
                            or type(item['path'])is not str or not Path(item['path']).is_absolute()):
                        raise ValueError('retained security reference source invalid')
                    _hash(item['sha256'])  # 热读取只核声明；原件已由写入owner固定，不追读历史链。
                self.current_reference=original['current_reference']
                current=_reference_catalog(_descriptor(self.current_reference,16777216))
                if any(value['securities'].get(symbol)!=row for symbol,row in current['securities'].items()):
                    raise ValueError('retained security reference current identity changed')
                self._retained_symbols=set(value['securities'])-set(current['securities'])
            else:
                current=_reference_catalog(value)
            self._rows = value['securities']
            if current['schema']=='guanheng.security-reference.v2':self._dynamic_symbols=set(current['securities'])
            self.reference_sha256 = reference['sha256']
        if calendar is not None:
            self._calendar = _calendar(_descriptor(calendar, 1048576))
            self._calendar_sha256 = calendar['sha256']
            self._closed_days = set(self._calendar['closed_dates'])

    def security(self, snapshot, symbol):
        """股票池拥有stock身份；同版本QMT非空资料优先，其他资料沿原目录。"""
        if self._closed:
            raise ValueError('security reference closed')
        result = deepcopy(self._rows.get(symbol))
        if result is None:
            result = dict(
                symbol=symbol,  # 请求的规范WT证券身份。
                name=None,  # 资料缺项，不影响独立原生日线读取。
                market=symbol.split('.')[0],  # 来自规范证券身份的明确市场。
                security_type='unknown',  # 目录和股票池均无资格时保留未知。
                listed_on=None,  # 未取得原上市日期，不能按价格首日反推。
                expires_on=None,  # 未取得到期事实，不能按价格尾日推断退市。
                observed_at=None)  # 资料来源时刻未知，区别于本查询发生时刻。
        if symbol in snapshot['basics']:
            result['security_type'] = 'stock'
            basic = snapshot['basics'][symbol]
            newer=(result['observed_at']is None or basic is not None and basic['observed_at']is not None
                   and datetime.fromisoformat(basic['observed_at'].replace('Z','+00:00'))
                   >=datetime.fromisoformat(result['observed_at'].replace('Z','+00:00')))
            if (basic is not None and symbol not in self._dynamic_symbols
                    and (symbol not in self._retained_symbols or newer)):
                for key in ('name', 'market', 'listed_on', 'expires_on', 'observed_at'):
                    result[key] = basic[key]
        return validate_security_identity(result)

    def assess(self, query, security, available_dates, facts):
        """仅合格同日事实确认missing；上市前/停牌/未知保留各自分类。"""
        if self._closed:
            raise ValueError('security reference closed')
        result = dict(
            **{'from': query['from'], 'to': query['to']},  # 本次评估闭区间YYYYMMDD，最多366自然日。
            calendar_id=None,  # 缺日历时None，不把普通工作日当已核交易日。
            calendar_sha256=None,  # 原官方日历SHA，配置缺项时None。
            calendar_covered=False,  # 整个请求窗口是否在声明覆盖区间内。
            calendar_verified_through=None,  # 原交叉核验截止日，区别于年度休市安排覆盖日。
            missing_dates=[],  # 确认原来源有交易状态，WT未读到该日价格的日期。
            before_listing_dates=[],  # 原上市日期之前的计划交易日；不作为数据缺失。
            after_expiry_dates=[],  # 原到期日期之后的计划交易日；不推断退市性质。
            no_trade_dates=[],  # 合格同日事实确认停牌且成交股数为0的日期。
            unresolved_dates=[])  # 无法确认是否应有行情的计划交易日，保留未知原因。
        calendar = self._calendar
        if calendar is None:
            return result
        first = datetime.strptime(str(query['from']), '%Y%m%d').date()
        last = datetime.strptime(str(query['to']), '%Y%m%d').date()
        result.update(calendar_id=calendar['id'], calendar_sha256=self._calendar_sha256,
                      calendar_covered=calendar['coverage_start'] <= first.isoformat() <= last.isoformat() <= calendar['coverage_end'],
                      calendar_verified_through=calendar.get('verified_through'))
        present = set(available_dates)
        current = first
        while current <= last:
            iso = current.isoformat()
            label = current.year * 10000 + current.month * 100 + current.day
            current += timedelta(days=1)
            if (label in present or not calendar['coverage_start'] <= iso <= calendar['coverage_end']
                    or date.fromisoformat(iso).weekday() >= 5 or iso in self._closed_days):
                continue
            if security['listed_on'] is not None and iso < security['listed_on']:
                kind = 'before_listing_dates'
            elif security['expires_on'] is not None and iso > security['expires_on']:
                kind = 'after_expiry_dates'
            else:
                state = facts.security_state(iso, query['symbol']) if facts is not None else None
                status=trade_day_state(state)
                if status == 'source_halted_no_trade':
                    kind = 'no_trade_dates'
                elif status == 'source_active':
                    kind = 'missing_dates'
                else:
                    kind = 'unresolved_dates'
            result[kind].append(label)
        return result

    def close(self):
        self._rows.clear()
        self._dynamic_symbols.clear()
        self._retained_symbols.clear()
        self._calendar = None
        self._closed_days.clear()
        self._closed = True


def prepare_retained_reference(current,securities,sources,output):
    """将历史价格身份随同一快照发布；当前分组分母和资料优先级保持原叶事实。"""
    reader=SecurityReference(current)
    try:
        leaf=reader.current_reference
        current_rows=_reference_catalog(_descriptor(leaf,16777216))['securities']
        rows=deepcopy(securities);rows.update(current_rows)
    finally:reader.close()
    _identities(rows)
    if rows==current_rows:return leaf
    value=dict(
        schema='guanheng.security-reference.v3',  # 同一数据owner的当前/保留身份组合合同。
        securities=rows,  # 完整价格身份并集；当前Source缺项保持当前None。
        provenance=dict(
            current_reference=leaf,  # 独立v1/v2原件，当前完整组在此核算，不含历史保留数。
            retained_sources=sources))  # 原资料/历史价格池/股票池描述符，保留身份归属和原时点。
    from .daily_data_update import _save,_descriptor as descriptor
    path=Path(output).absolute();_save(path,value);result=descriptor(path)
    check=SecurityReference(result)
    check.close()
    return result


def prepare_security_reference(catalog, output, *, details=None, indices=None):
    """复用已发布v1身份目录/原QMT只读资料；新根写一次，完全不发起报价请求。"""
    source = _descriptor(catalog, 16777216)
    if (type(source) is not dict or source.get('schema_version') != 'guanheng.security-catalog.v1'
            or type(source.get('securities')) is not list or not 1 <= len(source['securities']) <= 20000
            or hashlib.sha256(encode(source['securities'])).hexdigest() != source.get('catalog_id')):
        raise ValueError('original security catalog differs')
    clock = source['source']['names_retrieved_at']
    _clock(clock)
    rows = {}
    markets = {'SH': 'SSE', 'SZ': 'SZSE', 'BJ': 'BSE'}
    for item in source['securities']:
        if item['symbol'] != item['code'] + '.' + item['exchange'] or item['exchange'] not in markets:
            raise ValueError('original security catalog identity differs')
        symbol = markets[item['exchange']] + '.' + item['code']
        if symbol in rows:
            raise ValueError('original security catalog key repeated')
        rows[symbol] = validate_security_identity(dict(
            symbol=symbol,  # 原身份目录证券代码，映射到WT规范市场。
            name=item['name'],  # 原已发布名称，保持原文字及别名。
            market=markets[item['exchange']],  # 原明确交易所身份。
            security_type=item['security_type'],  # 原目录stock/etf/index分类，按代码猜测不参与。
            listed_on=None,  # 原目录没有上市日期，暂保持未知。
            expires_on=None,  # 原目录没有到期日期，暂保持未知。
            observed_at=clock))  # 原名称获取时刻，保留来源日期。
    if indices is not None:
        original = _descriptor(indices, 16777216)
        if (original.get('schema') != 'guanheng.fifty-index-coverage.v1'
                or type(original.get('indices')) is not list or len(original['indices']) != 50):
            raise ValueError('original index identity catalog differs')
        seen = set()
        for item in original['indices']:
            code, market = item['symbol'].split('.')
            symbol = markets[market] + '.' + code
            if symbol in seen or symbol in rows and rows[symbol]['security_type'] != 'index':
                raise ValueError('original index classification differs')
            seen.add(symbol)
            if symbol not in rows:
                rows[symbol] = validate_security_identity(dict(
                    symbol=symbol,  # 原50指数的规范身份。
                    name=item['name'],  # 原已验收指数登记名称。
                    market=markets[market],  # 原指数条目的明确交易所。
                    security_type='index',  # 原indices登记身份，不从代码范围猜测。
                    listed_on=None,  # 指数首条行情日期不代表成立或上市日期。
                    expires_on=None,  # 原登记没有到期事实。
                    observed_at=None))  # 原名称登记没有采集时刻，不以文件mtime充当来源事实。
    if details is not None:
        original = _descriptor(details, 16777216)
        if original.get('schema') != 'guanheng.vendor-basic-probe.v1' or original.get('state') != 'completed':
            raise ValueError('original basic details incomplete')
        for item in original['calls']:
            if item['method'] != 'get_instrumentdetail' or not item['value']:
                continue
            code, market = item['argument'].split('.')
            symbol = markets[market] + '.' + code
            if symbol not in rows:
                continue  # 新股票/BSE身份仍由固定股票池拥有，单份details不推测证券类型。
            value = item['value']
            if (value['InstrumentID'], value['ExchangeID']) != (code, market):
                raise ValueError('original basic details identity differs')
            row = rows[symbol]
            row['name'] = value['InstrumentName']
            row['listed_on'] = datetime.strptime(str(value['OpenDate']), '%Y%m%d').date().isoformat() if value['OpenDate'] else None
            row['expires_on'] = datetime.strptime(str(value['ExpireDate']), '%Y%m%d').date().isoformat() if value['ExpireDate'] else None
            row['observed_at'] = datetime.fromtimestamp(item['received_wall_ms'] / 1000, timezone.utc).isoformat()
            validate_security_identity(row)
    value = dict(
        schema='guanheng.security-reference.v1',  # 数据侧冻结资料合同，与行情原件分别保存。
        securities=rows,  # 规范WT身份到资料，随固定snapshot一起发布。
        provenance=dict(
            catalog_sha256=catalog['sha256'],  # 原已发布身份/名称目录完整字节摘要。
            details_sha256=details['sha256'] if details is not None else None,  # 原QMT资料捕获摘要，缺项为None。
            indices_sha256=indices['sha256'] if indices is not None else None))  # 原50指数身份登记摘要，缺项为None。
    output = Path(output).absolute()
    output.mkdir(parents=False, exist_ok=False)
    path = output / 'reference.json'
    path.write_bytes(encode(value))
    descriptor = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    store = SecurityReference(descriptor)
    store.close()
    return descriptor
