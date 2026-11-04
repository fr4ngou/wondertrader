# -*- coding: utf-8 -*-
"""原策略线程证券资料；固定SDK只读入口、不可变名册及同一原请求截止。"""
import base64
import hashlib
import hmac
import math
import re
import threading
import time
from datetime import date, datetime, timezone
from uuid import uuid4
from .errors import GatewayError
from .protocol import ProtocolError, canonical, decode

UNIVERSE = 'market.security_universe'
DETAILS = 'market.security_details'
OPERATIONS = (DETAILS, UNIVERSE)
POLICY = 'qmt.security-reference-read.v1'
PROFILE_VERSION = 'qmt.read-profile.v9'
# 本适配层已结束的固定资料失败；仅这两个只读操作可沿原结果确认，不授重派未知请求。
CONFIRMED_ERRORS = ('security_catalog_expired', 'security_catalog_cursor_invalid',
                    'security_catalog_capacity', 'result_too_large')
MARKETS = ('SH', 'SZ', 'BJ')
TYPES = ('stock', 'etf', 'index')
RAW_FIELDS = ('ExchangeID', 'InstrumentID', 'InstrumentName', 'OpenDate', 'ExpireDate',
              'IsTrading', 'FloatVolumn', 'TotalVolumn')


def need(value):
    if not value:
        raise ProtocolError('security reference contract')


def text(value, maximum):
    need(type(value) is str and 0 < len(value.encode('utf-8')) <= maximum
         and all(ord(c) >= 32 and ord(c) != 127 for c in value))
    return value


def symbol(value):
    need(type(value) is str and re.match(r'^[0-9]{6}\.(SH|SZ|BJ)$', value) is not None and len(value) == 9)
    return value[-2:]


def digest(value):
    need(type(value) is str and re.match(r'^[0-9a-f]{64}$', value) is not None and len(value) == 64)
    return value


def limits(value, maximum):
    need(type(value) is dict and set(value) == {
        'schema',  # 显式额度合同版本；两个操作声明同一份额度及分类映射。
        'max_page_size',  # 每页证券数，1至256；不表示整组应采数量。
        'max_detail_symbols',  # 一次详情证券数，1至64；共用原30秒截止。
        'max_catalog_symbols',  # 一份冻结名册去重上限，最多20000只。
        'max_catalogs',  # 本Source代同时保留的名册份数，最多2份。
        'catalog_lifetime_seconds',  # 完成捕获后的单调有效秒数，900秒。
        'max_cache_bytes',  # 所有保留名册原件编码总字节，最多8MiB。
        'max_data_bytes',  # 本次成功data编码字节，最多300KiB且预留原reply封装。
        'source_groups',  # 受管分类声明：实际QMT目录/板块到市场和类型的映射。
    })
    need(value['schema'] == 'qmt.security-reference-limits.v1')
    for key, low, high in (('max_page_size', 1, 256), ('max_detail_symbols', 1, 64),
            ('max_catalog_symbols', 1, 20000), ('max_catalogs', 1, 2),
            ('catalog_lifetime_seconds', 900, 900), ('max_cache_bytes', 4096, 8*1024*1024),
            ('max_data_bytes', 4096, min(300*1024, maximum-4096))):
        need(type(value[key]) is int and low <= value[key] <= high)
    groups, seen = value['source_groups'], set()
    need(type(groups) is list and len(groups) <= 9)
    for group in groups:
        need(type(group) is dict and set(group) == {'market', 'security_type', 'sources'})
        need(type(group['market']) is str and group['market'] in MARKETS
             and type(group['security_type']) is str and group['security_type'] in TYPES)
        identity = (group['market'], group['security_type'])
        need(identity not in seen); seen.add(identity)
        need(type(group['sources']) is list and len(group['sources']) <= 8)
        sources = set()
        for source in group['sources']:
            need(type(source) is dict and set(source) == {'node', 'name'})
            need(type(source['node']) is str and len(source['node'].encode('utf-8')) <= 128)
            if source['node']:
                text(source['node'],128)
            text(source['name'], 128)
            key = (source['node'], source['name']); need(key not in sources); sources.add(key)
    return decode(canonical(value))


def arguments(operation, value, scope):
    need(type(value) is dict)
    if operation == UNIVERSE:
        need(set(value) == {'markets', 'security_types', 'limit', 'cursor'})
        for field, ordered in (('markets', MARKETS), ('security_types', TYPES)):
            items = value[field]
            need(type(items) is list and items and all(type(v) is str and v in ordered for v in items)
                 and items == [v for v in ordered if v in items])
        need(type(value['limit']) is int and 1 <= value['limit'] <= scope['max_page_size'])
        need(value['cursor'] is None or type(value['cursor']) is str and 0 < len(value['cursor'].encode('utf-8')) <= 512)
    else:
        need(operation == DETAILS and set(value) == {'catalog_id', 'symbols'})
        if value['catalog_id'] is not None:
            digest(value['catalog_id'])
        need(type(value['symbols']) is list and 1 <= len(value['symbols']) <= scope['max_detail_symbols'])
        for item in value['symbols']:
            symbol(item)
        need(len(set(value['symbols'])) == len(value['symbols']))
    return value


def _fail(code):
    raise GatewayError(code, '证券资料读取未取得本次完整资格')


class SecurityReferenceAdapter(object):
    """原策略线程唯一owner；SDK分配自身不可抢占，返回后沿原D再次核验。"""
    def __init__(self, context, scope, maximum, sector_list_query=None, clock=time.monotonic):
        self.context = context  # 原ContextInfo，仅原策略线程调用固定证券读取方法。
        self.scope = limits(scope, maximum)  # 已认证profile显式预算/板块映射；不按代码猜类型。
        self.sector_list_query = sector_list_query  # 固定内置全局get_sector_list(node)，缺失保留unsupported。
        self.clock, self.owner = clock, threading.get_ident()  # 同机单调截止及原构造线程身份。
        self.catalogs = {}  # catalog_id到不可变正文/到期/字节额度；最多两份，断代后旧游标失效。
        self.generation, self.sequence = uuid4().hex, 0  # 本代游标绑定随机身份与捕获序号，不是账户身份。

    def _check(self, deadline):
        if threading.get_ident() != self.owner:
            _fail('owner_required')
        if self.clock() >= deadline:
            _fail('execution_timeout')

    def _encode(self, value, maximum, deadline):
        self._check(deadline)
        raw = canonical(value)
        self._check(deadline)
        if len(raw) > maximum:
            _fail('result_too_large')
        return raw

    def _purge(self):
        for key in list(self.catalogs):
            if self.clock() >= self.catalogs[key]['expires']:
                del self.catalogs[key]

    def _catalog(self, key):
        self._purge()
        if key not in self.catalogs:
            _fail('security_catalog_expired')
        return self.catalogs[key]['body']

    @staticmethod
    def _utc():
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _capture(self, request, deadline):
        groups, members, directories = [], {}, {}
        declared = {(g['market'], g['security_type']): g['sources'] for g in self.scope['source_groups']}
        get_members = getattr(self.context, 'get_stock_list_in_sector', None)
        for market in request['markets']:
            for kind in request['security_types']:
                self._check(deadline)
                sources = declared.get((market, kind), [])
                seen, used, failures, successful = set(), [], [], 0
                if not sources or not callable(get_members) or not callable(self.sector_list_query):
                    failures.append('source_capability_unavailable')
                for source in sources if not failures else []:
                    self._check(deadline)
                    try:
                        node = source['node']
                        if node not in directories:
                            listed = self.sector_list_query(node)
                            self._check(deadline)
                            need(type(listed) in (list, tuple) and len(listed) == 2
                                 and type(listed[0]) in (list, tuple) and len(listed[0]) <= 4096)
                            directories[node] = set(text(v, 128) for v in listed[0])
                        if source['name'] not in directories[node]:
                            failures.append('source_group_unavailable'); continue
                        used.append(source['name'])
                        rows = get_members(source['name'])
                        self._check(deadline)
                        need(type(rows) in (list, tuple) and len(rows) <= self.scope['max_catalog_symbols']*9)
                    except GatewayError:
                        raise
                    except Exception:
                        failures.append('source_call_failed'); continue
                    successful += 1
                    for item in rows:
                        self._check(deadline)
                        try:
                            actual_market = symbol(item)
                        except ProtocolError:
                            failures.append('source_invalid_value'); continue
                        if actual_market != market:
                            continue
                        seen.add(item)
                        if item not in members:
                            if len(members) >= self.scope['max_catalog_symbols']:
                                _fail('security_catalog_capacity')
                            members[item] = {
                                'types': set(),  # 实际板块声明取得的类型集合，冲突保留unknown。
                                'sources': set(),  # 该证券实际出现的QMT板块名，捕获期间由本owner去重。
                            }
                        members[item]['types'].add(kind); members[item]['sources'].add(source['name'])
                state = ('complete' if not failures else 'partial' if successful else
                         'unsupported' if failures[0] == 'source_capability_unavailable' else 'unavailable')
                # 分组事实：market/type是原范围；state是SDK资格；expected_count仅完整组赋值。
                # observed_count覆盖冻结全组，source_groups保留实际板块，reason_code固定且无异常正文。
                groups.append({
                    'market': market,  # 原请求市场，按实际符号后缀验证成员。
                    'security_type': kind,  # 原请求分类，只采用实际QMT板块映射。
                    'state': state,  # 本组完整/部分/不可用/不支持的取得资格。
                    'expected_count': len(seen) if state == 'complete' else None,  # 完整组应覆盖数；未知为null。
                    'observed_count': len(seen),  # 本份全组实际去重数，包含真实空组0。
                    'source_groups': sorted(set(used)),  # 实际核存在并调用的板块名，失败也保留来源。
                    'reason_code': failures[0] if failures else None,  # 固定分类；完整组为null，无异常正文。
                })
        conflicts = {item for item, value in members.items() if len(value['types']) != 1}
        for group in groups:
            if any(symbol(s) == group['market'] and group['security_type'] in members[s]['types'] for s in conflicts):
                group.update(state='partial', expected_count=None, reason_code='classification_conflict')
        items = [{
            'symbol': s,  # 原六位代码及已验证市场后缀，跨组只保留一次。
            'market': symbol(s),  # 从原符号后缀验证市场，不用代码前缀推断。
            'security_type': next(iter(v['types'])) if len(v['types']) == 1 else 'unknown',  # 板块分类冲突保持未知。
            'source_groups': sorted(v['sources']),  # 实际命中板块，支持消费者核对分类来源。
        } for s, v in sorted(members.items())]
        complete = all(g['state'] == 'complete' for g in groups)
        return {
            'schema': 'qmt.security-universe.v1',  # 固定名册data版本。
            'captured_at': self._utc(),  # Source完成本份捕获的UTC时刻，所有页保持同值。
            'source_as_of': None,  # SDK未提供独立资料时点，保留未知。
            'markets': list(request['markets']),  # 回显固定市场scope，不跨页变更。
            'security_types': list(request['security_types']),  # 回显固定类型scope。
            'state': 'complete' if complete else 'partial',  # 所有组取得资格，不代表分页已结束。
            'total_count': len(items) if complete else None,  # 全部组完整才声明总数；未知保持null。
            'groups': groups,  # 不可变分组事实；每页重复整份说明。
            'items': items,  # 本owner冻结全部证券；对外页只投影有限切片。
        }

    def _cursor(self, catalog, offset, scope):
        payload = canonical({
            'catalog': catalog,  # 本代冻结原件的SHA身份；不从新捕获替换旧游标。
            'offset': offset,  # 下一页在已冻结有序证券中的位置。
            'scope': scope,  # 原市场/类型/页大小的SHA；代际密钥另绑定本Source。
        })
        body = base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')
        tag = hmac.new(self.generation.encode('ascii'), body.encode('ascii'), hashlib.sha256).hexdigest()
        return body + '.' + tag

    def _universe(self, request, deadline):
        scope = hashlib.sha256(canonical({k: request[k] for k in ('markets', 'security_types', 'limit')})).hexdigest()
        cursor = request['cursor']
        if cursor is None:
            body = self._capture(request, deadline)
            self.sequence += 1
            raw = self._encode(dict(body=body, generation=self.generation, sequence=self.sequence), self.scope['max_cache_bytes'], deadline)
            catalog = hashlib.sha256(raw).hexdigest()
            self._purge()
            while self.catalogs and (len(self.catalogs) >= self.scope['max_catalogs'] or
                    sum(v['bytes'] for v in self.catalogs.values()) + len(raw) > self.scope['max_cache_bytes']):
                oldest = min(self.catalogs, key=lambda k: self.catalogs[k]['sequence'])
                del self.catalogs[oldest]
            self.catalogs[catalog] = {
                'body': body,  # 本owner独占的冻结名册，外部成功页返回独立投影。
                'bytes': len(raw),  # 原件编码字节，计入跨名册总缓存上限。
                'sequence': self.sequence,  # 本代捕获序号，满额时先回收最早名册。
                'expires': self.clock()+self.scope['catalog_lifetime_seconds'],  # 单调秒截止，回收后旧ID显式过期。
            }
            offset = 0
        else:
            try:
                encoded, tag = cursor.rsplit('.', 1)
                expected = hmac.new(self.generation.encode('ascii'), encoded.encode('ascii'), hashlib.sha256).hexdigest()
                need(hmac.compare_digest(tag, expected))
                decoded = decode(base64.urlsafe_b64decode((encoded+'='*((-len(encoded)) % 4)).encode('ascii')))
                need(type(decoded) is dict and set(decoded) == {'catalog', 'offset', 'scope'} and decoded['scope'] == scope)
                catalog, offset = digest(decoded['catalog']), decoded['offset']
                need(type(offset) is int and offset > 0)
            except Exception:
                _fail('security_catalog_cursor_invalid')
            body = self._catalog(catalog)
            need(body['markets'] == request['markets'] and body['security_types'] == request['security_types'] and offset < len(body['items']))
        end = min(offset+request['limit'], len(body['items']))
        result = dict(body,
            catalog_id=catalog,  # 同次原件身份，所有页一致；含本代身份及捕获序号。
            items=body['items'][offset:end],  # 当前有限页；其余组/时刻均来自原件。
            next_cursor=self._cursor(catalog, end, scope) if end < len(body['items']) else None,  # 原件结束才为null。
        )
        # 返回独立投影，调用方修改当前页不会改写冻结名册或后续页。
        return decode(self._encode(result, self.scope['max_data_bytes'], deadline))

    @staticmethod
    def _day(value):
        if type(value) is int:
            value = str(value)
        if type(value) is not str:
            return None
        if re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', value) and len(value) == 10:
            normalized = value[:4]+value[5:7]+value[8:]
        else:
            normalized = value
        if len(normalized) != 8 or re.match(r'^[0-9]{8}$', normalized) is None:
            return None
        try:
            return date(int(normalized[:4]), int(normalized[4:6]), int(normalized[6:8])).isoformat()
        except ValueError:
            return None

    def _detail(self, security, deadline):
        self._check(deadline)
        reasons, raw = {}, {}
        getter = getattr(self.context, 'get_instrumentdetail', None)
        try:
            source = getter(security) if callable(getter) else None
        except Exception:
            source = None
        self._check(deadline)
        available = type(source) is dict and bool(source)
        if available:
            for key in RAW_FIELDS:
                if key not in source:
                    continue
                value = source[key]
                if value is None:
                    reasons[key] = 'source_missing'
                if type(value) is float and not math.isfinite(value):
                    value = None; reasons[key] = 'source_nonfinite'
                elif type(value) not in (str, int, float, bool, type(None)):
                    value = None; reasons[key] = 'source_invalid_value'
                raw[key] = value
        market = symbol(security)
        if available and (raw.get('ExchangeID') not in (None, market) or raw.get('InstrumentID') not in (None, security[:6])):
            available = False
            reasons['identity'] = 'source_market_conflict'
        name = raw.get('InstrumentName') if available else None
        if type(name) is not str or not name.strip():
            name = None
        listed = self._day(raw.get('OpenDate')) if available else None
        expires = self._day(raw.get('ExpireDate')) if available else None
        trading = 'active' if available and raw.get('IsTrading') is True else 'unknown'
        # IsTrading=False只证明当前不可交易，缺少独立停牌定义时保留unknown，不推造停牌事实。
        for key, value, original in (('name', name, 'InstrumentName'), ('listed_on', listed, 'OpenDate'),
                                    ('expires_on', expires, 'ExpireDate')):
            if value is None:
                reasons[key] = ('source_market_conflict' if reasons.get('identity') else 'source_unavailable' if not available else
                                'source_missing' if raw.get(original) is None else 'source_invalid_value')
        if trading == 'unknown':
            reasons['trading_status'] = 'source_unavailable' if not available else 'source_missing' if 'IsTrading' not in raw else 'source_status_ambiguous'
        # 单证券：身份回显、实际可用性、映射资料与观察时刻；缺字段原因和原白名单分开保存。
        # name/日期缺失为null；trading_status缺证为unknown；raw_fields中的真实0保持原数值。
        result = {
            'symbol': security,  # 原请求符号，缺项也保留价格池身份。
            'market': market,  # 已验证的原后缀市场，不采用冲突SDK字段。
            'status': 'observed' if available else 'unavailable',  # 整项取得资格；字段缺失单独说明。
            'name': name,  # SDK原名；空串/缺失/无效为null，原值在raw_fields。
            'listed_on': listed,  # SDK明确且有效的上市日期YYYY-MM-DD，未知/哨兵为null。
            'expires_on': expires,  # SDK明确且有效的到期日期，未知/哨兵为null。
            'trading_status': trading,  # 只有明确事实才映射，IsTrading=False不足以推造halted。
            'observed_at': self._utc(),  # 本证券取得/缺失观察完成的UTC时刻。
            'field_reasons': reasons,  # 未准入字段的固定原因；无供应商异常正文。
            'raw_fields': raw,  # SDK公开字段白名单，真实0不换算，非有限数null并注明原因。
        }
        self._encode(result, 4096, deadline)
        return result

    def execute(self, operation, request, deadline):
        """原线程、单调秒绝对D内读SDK；固定失败码交还原reply，目录不跨代恢复。"""
        self._check(deadline)
        arguments(operation, request, self.scope)
        if operation == UNIVERSE:
            return self._universe(request, deadline)
        catalog = request['catalog_id']
        if catalog is not None:
            known = {v['symbol'] for v in self._catalog(catalog)['items']}
            if any(v not in known for v in request['symbols']):
                _fail('invalid_arguments')
        items = [self._detail(v, deadline) for v in request['symbols']]
        result = {
            'schema': 'qmt.security-details.v1',  # 固定详情data版本。
            'catalog_id': catalog,  # 原请求名册身份或null，仅约束证券范围。
            'captured_at': self._utc(),  # 本批详情观察完成的UTC时刻，不宣称各证券同一瞬间。
            'source_as_of': None,  # SDK没有独立资料有效时点。
            'items': items,  # 原请求每只恰好一项，unavailable项仍保留。
        }
        self._encode(result, self.scope['max_data_bytes'], deadline)
        return result


class ReferenceOperation(object):
    def __init__(self, owner, operation):
        self.owner = owner  # 本代共享的名册缓存owner，两个操作不各建一份缓存。
        self.operation = operation  # 显式固定操作标识，原请求权限由认证profile准入。

    def execute(self, arguments, deadline):
        return self.owner.execute(self.operation, arguments, deadline)


# 响应边界只准入固定状态/原因；不让供应商异常原文成为业务字段。
GROUP_REASONS = ('source_capability_unavailable', 'source_group_unavailable',
                 'source_call_failed', 'source_invalid_value', 'classification_conflict')
FIELD_REASONS = ('source_missing', 'source_unavailable', 'source_invalid_value',
                 'source_market_conflict', 'source_nonfinite', 'source_status_ambiguous')


def _timestamp(value):
    text(value, 40)
    need(re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z$', value) is not None)
    try:
        datetime(int(value[:4]),int(value[5:7]),int(value[8:10]),int(value[11:13]),int(value[14:16]),int(value[17:19]))
    except ValueError:
        need(False)


def _sources(value):
    need(type(value) is list and len(value) <= 24)
    for name in value:
        text(name, 128)
    need(value == sorted(set(value)))


def validate_result(request, result):
    """Host与Source共用成功data校验；原失败reply仍沿原身份/字节保存。"""
    need(type(result) is dict)
    if result.get('ok') is not True:
        return
    data, operation, args = result.get('data'), request['operation_id'], request['arguments']
    need(type(data) is dict and data.get('source_as_of') is None)
    need(len(canonical(data)) <= 300*1024)
    _timestamp(data.get('captured_at'))
    if operation == UNIVERSE:
        need(set(data) == {'schema','catalog_id','captured_at','source_as_of','markets','security_types','state','total_count','groups','items','next_cursor'})
        need(data['schema'] == 'qmt.security-universe.v1' and data['markets'] == args['markets'] and data['security_types'] == args['security_types'])
        digest(data['catalog_id'])
        need(data['state'] in ('complete','partial') and type(data['groups']) is list
             and len(data['groups']) == len(args['markets'])*len(args['security_types']))
        expected = [(m,t) for m in args['markets'] for t in args['security_types']]
        for group, pair in zip(data['groups'], expected):
            need(type(group) is dict and set(group) == {'market','security_type','state','expected_count','observed_count','source_groups','reason_code'})
            need((group['market'],group['security_type']) == pair and group['state'] in ('complete','partial','unavailable','unsupported'))
            need(type(group['observed_count']) is int and 0 <= group['observed_count'] <= 20000)
            _sources(group['source_groups'])
            if group['state'] == 'complete':
                need(type(group['expected_count']) is int and group['expected_count'] == group['observed_count'] and group['reason_code'] is None)
            else:
                need(group['expected_count'] is None and group['reason_code'] in GROUP_REASONS)
        need(type(data['items']) is list and len(data['items']) <= args['limit'])
        seen = set()
        for item in data['items']:
            need(type(item) is dict and set(item) == {'symbol','market','security_type','source_groups'} and item['market'] == symbol(item['symbol'])
                 and item['market'] in args['markets'] and item['security_type'] in args['security_types']+['unknown'])
            _sources(item['source_groups'])
            need(item['source_groups'] and item['symbol'] not in seen); seen.add(item['symbol'])
        need([v['symbol'] for v in data['items']] == sorted(seen))
        complete = all(g['state'] == 'complete' for g in data['groups'])
        need((data['state'] == 'complete') == complete)
        if complete:
            need(type(data['total_count']) is int and len(data['items']) <= data['total_count'] <= 20000
                 and sum(g['observed_count'] for g in data['groups']) == data['total_count'])
        else:
            need(data['total_count'] is None)
        need(data['next_cursor'] is None or type(data['next_cursor']) is str and 0 < len(data['next_cursor'].encode('utf-8')) <= 512)
    else:
        need(operation == DETAILS and set(data) == {'schema','catalog_id','captured_at','source_as_of','items'})
        need(data['schema'] == 'qmt.security-details.v1' and data['catalog_id'] == args['catalog_id'] and type(data['items']) is list)
        if data['catalog_id'] is not None:
            digest(data['catalog_id'])
        need(len(data['items']) == len(args['symbols']))
        seen = set()
        for item in data['items']:
            need(type(item) is dict and set(item) == {'symbol','market','status','name','listed_on','expires_on','trading_status','observed_at','field_reasons','raw_fields'})
            need(item['symbol'] not in seen and item['symbol'] in args['symbols']); seen.add(item['symbol'])
            need(item['market'] == symbol(item['symbol']) and item['status'] in ('observed','unavailable')
                 and item['trading_status'] in ('active','halted','unknown') and type(item['field_reasons']) is dict
                 and type(item['raw_fields']) is dict and set(item['raw_fields']) <= set(RAW_FIELDS))
            _timestamp(item['observed_at'])
            need(item['name'] is None or type(item['name']) is str and bool(item['name'].strip()))
            for key in ('listed_on','expires_on'):
                value = item[key]
                need(value is None or type(value) is str and len(value) == 10 and SecurityReferenceAdapter._day(value) == value)
            for key, reason in item['field_reasons'].items():
                need(key in RAW_FIELDS+('name','listed_on','expires_on','trading_status','identity') and reason in FIELD_REASONS)
            for value in item['raw_fields'].values():
                need(type(value) in (str,int,float,bool,type(None)) and (type(value) is not float or math.isfinite(value)))
            for key in ('name','listed_on','expires_on'):
                if item[key] is None:
                    need(key in item['field_reasons'])
            if item['trading_status'] == 'unknown':
                need('trading_status' in item['field_reasons'])
            if item['status'] == 'unavailable':
                need(item['name'] is None and item['listed_on'] is None and item['expires_on'] is None and item['trading_status'] == 'unknown')
            need(len(canonical(item)) <= 4096)
