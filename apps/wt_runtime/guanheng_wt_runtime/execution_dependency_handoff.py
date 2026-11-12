"""原策略扩展的固定依赖续接；只读证明，真实安装/Source准入仍归原owner。"""
from copy import deepcopy
from pathlib import Path,PurePosixPath
import hashlib,json,re,time
from .managed_local_process import _read,_json,_require,_sha,_path

FIELDS={
    'schema',  # 固定依赖材料版本；不接受通用JSON修改指令。
    'origin_configuration_sha256',  # OLS-6原execution.json的原字节摘要。
    'previous_installation',  # 原execution-install.json的file/sha256，绑定原root及完整清单。
    'current_installation',  # 本代execution-install.json的file/sha256，实际DLL仍由原安装owner核验。
    'reader_additions',  # 恰两条ETF映射；原八条顺序/值保持。
    'contract_addition',  # 唯一SZSE159352完整Native行；原合约所有旧行保留。
    'contract_reference',  # 已准入证券资料catalog的file/sha256；ETF身份/名称/上市日期来自该原件。
    'source_extension',  # 原Source版本/采用证明及限定运输；未变化时为None，不猜Source成功。
}
ADDITIONS=[
    dict(std_code='SSE.ETF.589680',  # 原WT三段证券身份，保留原版589680代码。
         symbol='589680.SH'),  # Source两段证券身份；不推断价格/量单位。
    dict(std_code='SZSE.ETF.159352',  # 原WT三段ETF身份，独立新增读取映射。
         symbol='159352.SZ'),  # Source两段证券身份，须有固定ETF资料依据。
]
GENERIC_SCHEMA = 'guanheng.strategy-dependency-handoff.v2'
GENERIC_FIELDS = (FIELDS - {'contract_addition'}) | {'contract_additions'}
TRANSPORT=(
    'base_url',  # 当前已绑定Source的HTTP定位；实际认证由原Source握手验证。
    'binding_sha256',  # 当前完整交易绑定的Source规范摘要；原binding_id保持。
    'instance_id',  # 当前Source运输代身份，不替代Journal或命令身份。
    'key_id_env',  # 认证key环境变量名；本模块不读取或输出秘密值。
    'hmac_secret_env',  # HMAC环境变量名；仅归一化比较副本。
)
SOURCE_FIELDS={
    'previous_version',  # 原owner实际连续前版完整canonical记录的file/SHA。
    'current_version',  # 原owner实际已采用版本原件，parent/SHA保持真实。
    'adoption_receipt',  # 原Source采用回执，版本/计划/完整版本SHA逐项绑定。
    'transport',  # 本代恰五项冻结运输值；其余Trader业务字段继续严格相等。
    'plan',  # 原prepare完整canonical计划；路径及自身语义ID不可改写。
    'origin_deployment',  # 实际原pair部署原件的file/SHA；原Source owner仅派生无秘密身份。
    'origin_identity',  # Source owner对上述原件的无秘密投影，限定原Journal路径及绑定。
}

def _canonical(value):
    # Source采用原protocol的UTF8规范编码，与Native业务配置的ASCII身份分别解释。
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def _digest(value):return hashlib.sha256(_canonical(value)).hexdigest()

def _source_origin(proof,binding_sha256,pinned,pinned_raw):
    """原Source无秘密投影绑定真实部署；副本plan不能冒充原Journal采用。"""
    identity,unused=pinned(proof['origin_identity'],65536)
    deployment=pinned_raw(proof['origin_deployment'],16*1024*1024)
    plan,unused=pinned(proof['plan'],1024*1024)
    # 只在显式Source续接分支复用原owner；投影必须可由已核原部署正文重新派生。
    from guanheng_qmt_shm import reference_deployment_identity
    _require(reference_deployment_identity(deployment)==identity)
    _require(_digest({k:v for k,v in plan.items()if k!='plan_sha256'})==_sha(plan['plan_sha256'])
        and set(identity)=={'schema','deployment_sha256','journal_path','trade_binding_sha256'}
        and identity['schema']=='qmt.trade-deployment-origin.v1'
        and identity['deployment_sha256']==hashlib.sha256(deployment).hexdigest()
        and identity['trade_binding_sha256']==binding_sha256
        and _path(plan['journal_path'])==_path(identity['journal_path'])
        and plan['schema_version']=='qmt.trade-binding-extension-plan.v1')
    return plan

def dependency_shape(value):
    if type(value) is not dict:
        return False
    schema = value.get('schema')
    return (schema == 'guanheng.strategy-dependency-handoff.v1' and set(value) == FIELDS
            or schema == GENERIC_SCHEMA and set(value) == GENERIC_FIELDS)


def retired_target_symbols(marker, origin):
    """退役只作用于已退出前代活动集合的旧策略代码。"""
    if 'retired_targets' not in marker:
        return ()
    retirement = marker['retired_targets']
    _require(type(retirement) is dict and set(retirement) == {'strategy_id', 'symbols'}
             and len(origin['strategies']) == 1 and retirement['strategy_id'] == origin['strategies'][0]['id'])
    symbols = retirement['symbols']
    _require(type(symbols) is list and symbols
             and all(type(code) is str and re.fullmatch(r'(SSE|SZSE)\.ETF\.[0-9]{6}', code) for code in symbols)
             and len(set(symbols)) == len(symbols)
             and not set(symbols) & {row['std_code'] for row in origin['data']['store']['symbols']})
    return tuple(symbols)


def without_retired_filters(raw, symbols):
    """只移除明确退役证券的原 ignore 行。"""
    filters = _json(raw)
    by_code = filters['code_filters']
    _require(type(by_code) is dict)
    for code in symbols:
        _require(by_code.get(code) == {'action': 'ignore'})
        del by_code[code]
    return filters


def normalize_dependencies(current,origin,reference,origin_sha256,*,execution_symbol=None,confirmation=False,
                           execution_securities=None,retired_targets=(),deadline):
    """调用方提供去新增ctx/标记后的副本；只回投已核依赖，不改实际配置。"""
    def pinned_raw(ref,maximum):
        _require(type(ref)is dict and set(ref)=={'file','sha256'})
        raw=_read(_path(ref['file']),maximum,deadline=deadline,clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest()==_sha(ref['sha256']))
        return raw
    def pinned(ref,maximum):
        raw=pinned_raw(ref,maximum);return _json(raw),raw
    value,unused=pinned(reference,1024*1024)
    _require(dependency_shape(value)
        and value['origin_configuration_sha256']==_sha(origin_sha256))
    generic = value['schema'] == GENERIC_SCHEMA
    _require(generic == (execution_securities is not None) and (generic or not retired_targets))
    old_rows = origin['data']['store']['symbols']
    catalog, unused = pinned(value['contract_reference'], 16 * 1024 * 1024)
    from .execution_security import etf_mapping_and_contract, required_etf_dependencies
    additions=ADDITIONS[1:] if confirmation else ADDITIONS
    if not generic and execution_symbol is not None:
        _require(not confirmation and type(execution_symbol)is str and re.fullmatch(r'SSE\.ETF\.[0-9]{6}',execution_symbol)
            and execution_symbol!='SSE.ETF.589680')
        execution_code=execution_symbol.rsplit('.',1)[1]
        additions=[dict(std_code=execution_symbol,symbol=execution_code+'.SH'),ADDITIONS[1]]
    current=deepcopy(current)
    def manifest(ref,native):
        root=_path(native['installation_root']);_require(_path(ref['file'])==root.parent/'execution-install.json')
        doc,unused=pinned(ref,256*1024)
        _require(set(doc)=={'schema','files'}and doc['schema']=='guanheng.execution-install.v1'
            and type(doc['files'])is dict and 1<=len(doc['files'])<=512)
        for name,h in doc['files'].items():
            p=PurePosixPath(name)
            _require(type(name)is str and not p.is_absolute() and '..'not in p.parts
                and ':'not in name and '\\'not in name and str(p)==name)
            _sha(h)
        return root,doc['files']
    previous_root,previous=manifest(value['previous_installation'],origin)
    root,files=manifest(value['current_installation'],current)
    _require(current['base_data']==origin['base_data'] and 'contracts'in current['base_data'])
    def installed(folder,entries,name):
        p=PurePosixPath(name)
        _require(type(name)is str and not p.is_absolute()and '..'not in p.parts and ':'not in name and '\\'not in name and str(p)==name)
        key='app/'+name;h=_sha(entries[key]);raw=_read(folder/name,16*1024*1024,deadline=deadline,clock=time.monotonic)
        _require(hashlib.sha256(raw).hexdigest()==h);return raw
    for kind,name in current['base_data'].items():
        before=installed(previous_root,previous,name);after=installed(root,files,name)
        if kind!='contracts':_require(before==after);continue
        old,new=_json(before),_json(after)
        if generic:
            additions, required = required_etf_dependencies(catalog, execution_securities, old_rows, old)
            _require(value['contract_additions'] == required)
            expected = deepcopy(old)
            for market, contracts in required.items():
                expected.setdefault(market, {}).update(contracts)
            _require(new == expected)
            continue
        row=value['contract_addition']
        _require('159352'not in old['SZSE'] and new['SZSE'].get('159352')==row)
        def validate_contract(exchange,code,row):
            mapping, expected = etf_mapping_and_contract(catalog, exchange+'.'+code)
            _require(mapping in additions and row == expected
                     and type(row['expiredate']) is int and type(row['opendate']) is int)
        validate_contract('SZSE','159352',row)
        new['SZSE'].pop('159352')
        if execution_symbol is not None:
            _require(execution_code in new['SSE'])
            if execution_code not in old['SSE']:
                validate_contract('SSE',execution_code,new['SSE'].pop(execution_code))
        _require(new==old)
    # 同名环境原件保持字节身份，只有显式退役的全局 ignore 可精确移除。
    _require(current['environment']==origin['environment'])
    for key in ('filters','fees'):
        if key in origin['environment']:
            name=origin['environment'][key];_require(type(name)is str)
            if key == 'filters' and retired_targets:
                _require(bool(name))
                _require(_json(installed(root,files,name)) == without_retired_filters(
                    installed(previous_root,previous,name), retired_targets))
            elif name:
                _require(installed(root,files,name)==installed(previous_root,previous,name))
    _require(not retired_targets or 'filters' in origin['environment'])
    rows=current['data']['store']['symbols'];added=value['reader_additions']
    _require(type(old_rows)is list and (generic or len(old_rows)==8) and added==additions and rows==old_rows+added
        and len({r['std_code']for r in rows})==len(rows) and len({r['symbol']for r in rows})==len(rows))
    current['data']['store']['symbols']=deepcopy(old_rows)
    proof=value['source_extension'];old=origin['trader'];new=current['trader']
    if proof is None:
        _require(all(new.get(k)==old.get(k)for k in TRANSPORT))
    else:
        _require(type(proof)is dict and set(proof)==SOURCE_FIELDS
            and type(proof['transport'])is dict and set(proof['transport'])==set(TRANSPORT)
            and all(k in old and k in new and proof['transport'][k]==new[k]for k in TRANSPORT))
        previous_version,old_raw=pinned(proof['previous_version'],1024*1024)
        version,raw=pinned(proof['current_version'],1024*1024);receipt,unused=pinned(proof['adoption_receipt'],65536)
        plan=_source_origin(proof,old['binding_sha256'],pinned,pinned_raw)
        _require(type(plan['expected_version'])is int and plan['expected_version']==previous_version['version']
            and plan['new_identity']==version['identity']and plan['new_profile']==version['profile']
            and plan['protected_facts']['facts_sha256']==version['protected_facts_sha256']
            and _sha(plan['plan_sha256'])==_sha(version['plan_sha256']))
        _require(previous_version['schema_version']==version['schema_version']=='qmt.trade-binding-extension.v1'
            and type(previous_version['version'])is int and type(version['version'])is int
            and previous_version['version']>=1 and version['version']==previous_version['version']+1
            and version['parent_sha256']==hashlib.sha256(old_raw).hexdigest()
            and set(receipt)=={'schema_version','version','identity_sha256','plan_sha256','adopted'}
            and receipt['schema_version']=='qmt.trade-binding-extension.v1'and receipt['adopted']is True
            and type(receipt['version'])is int and receipt['version']==version['version']
            and receipt['identity_sha256']==hashlib.sha256(raw).hexdigest()
            and _sha(receipt['plan_sha256'])==_sha(version['plan_sha256'])
            and _digest(previous_version['identity']['trade_binding'])==old['binding_sha256']
            and _digest(version['identity']['trade_binding'])==new['binding_sha256'])
        for key in TRANSPORT:new[key]=deepcopy(old[key])
    current['installation_root']=origin['installation_root']
    return current
