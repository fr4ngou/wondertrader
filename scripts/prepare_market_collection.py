"""离线装配原Writer日线、指数订阅与动态Reader；不启动Source或运行实例。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')


def load(path,expected=None):
    raw=Path(path).read_bytes()
    if expected and hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('input SHA256 changed')
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def prepare(worker_path,worker_sha,daily_path,daily_sha,registry_path,output):
    """输出新E盘候选；外部输入及storage_root只读，完整原历史与配对身份保留。"""
    output=Path(output).resolve()
    if output.drive.upper()!='E:' or output.exists():raise ValueError('output requires a new E drive directory')
    worker,worker_identity=load(worker_path,worker_sha)
    daily,daily_identity=load(daily_path,daily_sha)
    registry,registry_identity=load(registry_path)
    if registry.get('schema')!='guanheng.collection-indices.v1' or len(registry['instruments'])!=50:raise ValueError('index registry')
    symbols=[item['symbol'] for item in registry['instruments']]
    if len(set(symbols))!=50 or any(re.fullmatch(r'\d{6}\.(SH|SZ)',value) is None for value in symbols):raise ValueError('index identity')
    connection,connection_identity=load(worker['connection']['path'],worker['connection']['sha256'])
    native,native_identity=load(worker['native']['configuration'],worker['native']['configuration_sha256'])
    if 'secret' in connection:raise ValueError('connection must omit private secret')
    if native['qmt_source']['volume_multiplier']!=1 or native['qmt_source']['amount_multiplier']!=1:
        raise ValueError('index raw values require existing unnormalized multipliers')
    if daily['mode']!='source-daily-overlay' or daily['response_shape']!='segments' or daily['archive'] is None:
        raise ValueError('requires original segmented daily index archive')
    stock_tail=daily['base']['snapshots']
    if not stock_tail:raise ValueError('existing stock daily tail required')
    original_native_path=worker['native']['configuration']
    old_symbols=list(connection['symbols']);old_contracts,_=load(native['basefiles']['contract'])
    commodities,_=load(native['basefiles']['commodity']);contracts=deepcopy(old_contracts)
    original_commodities=deepcopy(commodities)
    for exchange in ('SSE','SZSE'):
        if 'IDX' in commodities[exchange]:raise ValueError('existing index commodity requires explicit reconciliation')
        reference=commodities[exchange]['STK']
        commodities[exchange]['IDX']=dict(reference,name='公开指数',category=90,pricetick=.01,pricemode=9,trademode=9)
    added=[]
    for item in registry['instruments']:
        code,suffix=item['symbol'].split('.');exchange='SSE' if suffix=='SH' else 'SZSE'
        if code in contracts[exchange] or item['symbol'] in old_symbols:raise ValueError('index collides with original registration')
        contracts[exchange][code]=dict(exchg=exchange,name=item['name'],product='IDX');added.append(exchange+'.'+code)
    connection['symbols']=sorted(set(old_symbols)|set(symbols))
    if len(connection['symbols'])>connection['profile']['max_symbols']:raise ValueError('original QST capacity exceeded')
    connection['profile']['symbols_sha256']=hashlib.sha256(encoded(connection['symbols'])).hexdigest()
    # 只改变订阅集合摘要；原route、运输、profile版本、批量和队列预算保持。
    if len(connection['symbols'])!=len(old_symbols)+50:raise ValueError('subscription delta')
    output.mkdir(parents=True);private=output/'private';private.mkdir();baseinfo=private/'baseinfo';baseinfo.mkdir()
    records=[]
    def write(path,value):
        raw=encoded(value);path.write_bytes(raw);identity=hashlib.sha256(raw).hexdigest()
        # 文件收据：path是候选绝对位置；sha256绑定原字节；bytes是字节长度。
        records.append(dict(path=str(path),sha256=identity,bytes=len(raw)))
        return identity
    for name,value in native['basefiles'].items():
        if name in ('contract','commodity'):continue
        source=Path(value);target=baseinfo/source.name;raw=source.read_bytes();target.write_bytes(raw)
        native['basefiles'][name]=str(target)
        records.append(dict(path=str(target),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    commodity_path=baseinfo/'commodities.json';contract_path=baseinfo/'contracts.json'
    write(commodity_path,commodities);write(contract_path,contracts)
    native['basefiles'].update(commodity=str(commodity_path),contract=str(contract_path));native['writer']['disableday']=False
    connection_path=private/'connection.json';connection_sha=write(connection_path,connection)
    native_path=private/'datakit.json';native_sha=write(native_path,native)
    worker['connection'].update(path=str(connection_path),sha256=connection_sha)
    worker['native'].update(configuration=str(native_path),configuration_sha256=native_sha)
    worker_target=private/'worker.json';worker_target_sha=write(worker_target,worker)
    # 原股票/ETF base与其派生日线形状逐字节等价；仅外层50指数启用动态尾部。
    index_tail=deepcopy(stock_tail);scratch=output/'reader-scratch';scratch.mkdir()
    index_tail.update(symbols=sorted(added),scratch_root=str(scratch))
    index_tail.update(source_license='QMT cumulative snapshot raw values archived by original WT Writer; index price/quantity units unqualified',
        price_unit='unknown',volume_unit='unknown',amount_unit='unknown')
    daily['snapshots']=index_tail
    daily_target=private/'source-dynamic.json';daily_target_sha=write(daily_target,daily)
    for exchange,items in old_contracts.items():
        assert all(contracts[exchange][code]==row for code,row in items.items())
        assert all(commodities[exchange][key]==row for key,row in original_commodities[exchange].items())
    # 所有path/sha256引用均为绝对文件位置及其原字节身份；正文不含凭据值。
    result=dict(
        schema='guanheng.continuous-market-prepared.v1', # 离线装配收据版本。
        status='prepared-not-applied', # 只证明候选生成，现场尚未采用。
        original_worker=dict(path=str(worker_path),sha256=worker_identity), # 原采集入口。
        original_native=dict(path=str(Path(original_native_path)),sha256=native_identity), # 原DataKit配置。
        original_connection_sha256=connection_identity, # 原QST连接正文身份。
        original_daily=dict(path=str(daily_path),sha256=daily_identity), # 原统一历史配置。
        registry=dict(path=str(registry_path),sha256=registry_identity), # 新增50指数唯一名录。
        worker=dict(path=str(worker_target),sha256=worker_target_sha), # 新采集入口。
        daily=dict(path=str(daily_target),sha256=daily_target_sha), # 新日线动态读取配置。
        added_indices=sorted(added), # 新增WT标准证券代码集合。
        original_symbols=len(old_symbols), # 原QST订阅证券数量。
        symbols=len(connection['symbols']), # 新QST订阅总数，含原集合。
        storage_root=native['writer']['path'], # 原Writer数据根，仅配置引用。
        native_directory=worker['native']['directory'], # 复用固定原生制品目录。
        session_library_sha256=worker['native']['session_library_sha256'], # 实际加载Session制品身份。
        files=records, # 本次输出文件及其字节收据。
        old_contract_values_preserved=True, # 原证券基础资料逐字段保持。
        old_commodity_values_preserved=True, # 原股票/ETF品种参数保持。
        source2_required='merge new QST symbols/profile into current complete GH after original unknown requests are resolved', # 完整源端正文仍由Source2合并。
        live_changed=False, # 本入口不操作运行实例及数据根。
        framework_changed=False) # 本入口不修改WT框架。
    (output/'PREPARED.json').write_bytes(encoded(result));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path,required=True);parser.add_argument('--worker-sha256',required=True)
    parser.add_argument('--daily-source',type=Path,required=True);parser.add_argument('--daily-source-sha256',required=True)
    parser.add_argument('--indices',type=Path,default=Path(__file__).resolve().parents[1]/'config/market-collection-indices.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();value=prepare(args.worker,args.worker_sha256,args.daily_source,args.daily_source_sha256,args.indices,args.output)
    print(json.dumps(dict(status=value['status'],symbols=value['symbols'],indices=len(value['added_indices']),output=str(args.output))))


if __name__=='__main__':main()
