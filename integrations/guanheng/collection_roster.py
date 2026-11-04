"""从唯一资料原件准备原QST双端集合与WT基础资料候选；不启动订阅或Writer。"""
from copy import deepcopy
import hashlib
from pathlib import Path

from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.quote_stream_contract import symbols_digest, validate_profile
from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from .security_reference import _descriptor, _reference_catalog
from .source_history_transport import require


def prepare_roster(reference, connection, contracts, commodities, output):
    """保留原订阅并补入当前支持市场的已知成员，逐项列未接入市场与原集合保留项。

    输出为全新E盘目录中的QST连接、contracts/commodities和同一份差异证明。
    调用者把连接及基础资料同时固定进原Source/Host/Reader候选，Root统一正式切换。
    """
    value = _reference_catalog(_descriptor(reference, 16777216))
    require(value['schema'] == 'guanheng.security-reference.v2' and 'secret' not in connection)
    rows = value['securities']
    suffix = {'SSE': '.SH', 'SZSE': '.SZ'}
    products = {'stock': 'STK', 'etf': 'ETF', 'index': 'IDX'}
    known = {symbol for symbol, row in rows.items()
             if row['market'] in suffix and row['security_type'] in products}
    requested = {symbol.split('.')[1] + suffix[rows[symbol]['market']] for symbol in known}
    previous = set(connection['symbols'])
    combined = sorted(previous | requested)
    selected = deepcopy(connection)
    selected['symbols'] = combined
    selected['profile']['symbols_sha256'] = symbols_digest(combined)
    validate_profile(selected['profile'], combined)
    native, classes = deepcopy(contracts), deepcopy(commodities)
    for symbol in sorted(known):
        row = rows[symbol]; market, code = symbol.split('.')
        product = products[row['security_type']]
        existing = native.setdefault(market, {}).get(code)
        if existing is not None:
            require(existing['product'] == product)
            continue
        if product not in classes.setdefault(market, {}):
            require(product == 'IDX' and 'STK' in classes[market])
            # 指数沿同一WT股票时段；Reader/Writer不作下单或量额单位推导。
            classes[market]['IDX'] = dict(deepcopy(classes[market]['STK']), name='index')
        native[market][code] = dict(name=row['name'] or symbol, exchg=market, product=product,
            opendate=19900101 if row['listed_on'] is None else int(row['listed_on'].replace('-', '')),
            expiredate=20991231 if row['expires_on'] is None else int(row['expires_on'].replace('-', '')))
    registered = {code + suffix[market] for market, entries in native.items()
                  for code in entries if market in suffix}
    require(registered == set(combined))
    root = Path(output)
    require(root.is_absolute() and root.resolve().drive.upper() == 'E:' and not root.exists())
    create_private_directory(root)
    descriptors = {}
    for name, body in (('connection', selected), ('contracts', native), ('commodities', classes)):
        raw = canonical(body); path = root / (name + '.json')
        write_private_new(path, raw)
        descriptors[name] = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())
    report = dict(
        schema='qmt.collection-roster-candidate.v1', reference=reference,  # 唯一固定原件，不捕获Source。
        reference_catalog_id=value['provenance']['catalog_id'],  # 同次Source名册身份。
        previous_count=len(previous), current_known_supported_count=len(requested),
        candidate_count=len(combined), added=sorted(requested - previous),
        retained_outside_current_reference=sorted(previous - requested),  # 保留旧集合项，保持现有运行输入。
        unsupported_symbols=sorted(set(rows) - known),  # 原资料已知、此原QST/Reader尚未接入的市场。
        files=descriptors, subscriptions_changed=False, native_started=False)
    write_private_new(root / 'ROSTER.json', canonical(report))
    return report
