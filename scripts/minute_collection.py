"""分钟模块离线准备、整包核验与显式Source采用；运行进程仍由原WT owner管理。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / 'integrations', ROOT / 'connectors/qmt_shm/agent', ROOT / 'connectors/qmt_shm/host'):
    sys.path.insert(0, str(entry))

import argparse
import hashlib
import json
import os
from uuid import uuid4

from integrations.guanheng.collection_installation import descriptor, stage_program, verify_program
from integrations.guanheng.collection_deployment import load, prepare_configuration
from integrations.guanheng.market_generation import read_fixed
from integrations.guanheng.source_history_transport import require
from guanheng_market_client import MarketClient
from guanheng_qmt_shm.private_files import write_private_new


def verify_deployment(selected, *, adopted=False):
    """核全程序、私有配置及完整Source字节；不启动服务、不读取账户或调用SDK。"""
    plan = load(selected)
    require(plan['schema'] == 'qmt.minute-collection-deployment.v1')
    program = verify_program(plan['program'])
    for selected_file in plan['files'].values():
        read_fixed(selected_file['path'], maximum=16777216, identity=selected_file['sha256'])
    for original in plan['originals'].values():
        read_fixed(original['path'], maximum=16777216, identity=original['sha256'])
    load(plan['hpr_pair_manifest'])
    source = plan['source']
    read_fixed(source['source_after']['path'], maximum=2097152, identity=source['source_after']['sha256'])
    expected = source['source_after']['sha256'] if adopted else source['source_before']['sha256']
    read_fixed(source['source_before']['path'], maximum=2097152, identity=expected)
    # 从配置还原真实链路，保证组件引用的是同一份worker/producer/只读source。
    worker, producer = load(plan['files']['worker']), load(plan['files']['producer'])
    recovered = load(plan['files']['source'])
    require(worker['maintenance'] == plan['files']['maintenance']
            and load(worker['maintenance'])['producer'] == plan['files']['producer']
            and recovered['producer'] == plan['files']['producer']
            and recovered['base'] == producer['base'])
    native = load(plan['files']['native'])
    require(native['writer']['path'] == producer['base']['minute_native']['storage_root'])
    require(len(producer['base']['collection']['symbols']) == plan['quote_count'])
    return dict(schema='qmt.minute-collection-verification.v1', passed=True,
        deployment_sha256=selected['sha256'], program_files=len(program['files']),
        quote_count=plan['quote_count'], source_adopted=adopted, resources_started=False)


def adopt_source(selected):
    """仅供Root维护批次显式调用；原Source正常停止后按before CAS原子采用完整新正文。

    此命令只更换指定GH正文；SDK启停、WT角色切换、公开日线版本采用继续归原owner。
    已采用相同after返回成功；其他字节冲突保持原文件并抛错。回退使用单独显式命令。
    """
    plan = load(selected); source = plan['source']
    target = Path(source['source_before']['path'])
    actual = descriptor(target)['sha256']
    if actual == source['source_after']['sha256']:
        return dict(adopted=True, already_adopted=True, source_sha256=actual)
    verify_deployment(selected)
    raw = read_fixed(source['source_after']['path'], maximum=2097152, identity=source['source_after']['sha256'])
    # 维护者已停止原GH行后才调用；复核before后同目录替换，不修改其他策略文件。
    require(descriptor(target)['sha256'] == source['source_before']['sha256'])
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.tmp')
    write_private_new(temporary, raw)
    try:
        require(descriptor(target)['sha256'] == source['source_before']['sha256'])
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()  # 只删除本次已关闭的精确临时文件，原Source和备份保持。
    require(descriptor(target)['sha256'] == source['source_after']['sha256'])
    return dict(adopted=True, already_adopted=False, source_sha256=source['source_after']['sha256'])


def rollback_source(selected):
    """Root停止新GH正文后沿after CAS恢复已固定的完整旧正文；其他文件保持原样。"""
    plan = load(selected); source = plan['source']
    target = Path(source['source_before']['path'])
    actual = descriptor(target)['sha256']
    if actual == source['source_before']['sha256']:
        return dict(rolled_back=True, already_original=True, source_sha256=actual)
    require(actual == source['source_after']['sha256'])
    backup = Path(source['source_after']['path']).parent / 'source.before.py'
    raw = read_fixed(backup, maximum=2097152, identity=source['source_before']['sha256'])
    temporary = target.with_name(target.name + '.' + uuid4().hex + '.tmp')
    write_private_new(temporary, raw)
    try:
        require(descriptor(target)['sha256'] == source['source_after']['sha256'])
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return dict(rolled_back=True, already_original=False, source_sha256=descriptor(target)['sha256'])


def accept_minutes(selected, day, *, endpoint=None, credential_file=None, token_env=None):
    """Root切换后的只读业务验收；股票/ETF/双市场指数及实际策略八ETF均须有该日原值。

    本命令只查询原公开服务；结果逐项记录实际条数和尾时刻，不据样本授全市场完整性。
    凭据由私有环境文件读取，输出只含证券、状态、条数和时间，不含令牌或原价格正文。
    """
    from datetime import date
    require(date.fromisoformat(day).isoformat() == day)
    plan = load(selected)
    maintenance = load(plan['files']['maintenance'])
    service = load(plan['files']['service'])
    envfile = credential_file or plan['files']['environment']['path']
    environment = json.loads(read_fixed(envfile, maximum=1048576))
    key = token_env or service['token_env']
    client = MarketClient(endpoint or ('http://' + service['listen']['host'] + ':' + str(service['listen']['port'])),
        environment[key], timeout=30)
    symbols = list(dict.fromkeys(maintenance['priority_symbols'] + ['SSE.600000', 'SZSE.000001', 'SSE.000001', 'SZSE.399001']))
    label = int(day.replace('-', ''))
    observations = []
    for symbol in symbols:
        exchange, code = symbol.split('.')
        response = client.source_history_query(dict(exchange=exchange, code=code,
            **{'from': label * 10000 + 931, 'to': label * 10000 + 1500}, limit=30))
        bars = response['data'].get('bars', [])
        observations.append(dict(symbol=symbol, status=response['status']['code'], rows=len(bars),
            first=None if not bars else bars[0]['minute'], last=None if not bars else bars[-1]['minute']))
    return dict(schema='qmt.minute-collection-entry-acceptance.v1',
        passed=all(row['status'] == 'Ok' and row['rows'] > 0 and row['last'] // 10000 == label for row in observations),
        date=day, samples=observations, market_complete_coverage=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    stage = commands.add_parser('stage-program')
    stage.add_argument('--mainline', type=Path, required=True)
    stage.add_argument('--native-build', type=Path, required=True)
    stage.add_argument('--collection-component', type=Path, required=True)
    stage.add_argument('--output', type=Path, required=True)
    prepare = commands.add_parser('prepare-config')
    prepare.add_argument('--request', type=Path, required=True)
    prepare.add_argument('--request-sha256', required=True)
    for name in ('verify', 'adopt-source', 'rollback-source'):
        command = commands.add_parser(name)
        command.add_argument('--deployment', type=Path, required=True)
        command.add_argument('--deployment-sha256', required=True)
        if name == 'verify':
            command.add_argument('--adopted', action='store_true')
    run = commands.add_parser('run-role')
    run.add_argument('--deployment', type=Path, required=True)
    run.add_argument('--deployment-sha256', required=True)
    run.add_argument('--pythonw', required=True)
    run.add_argument('--pythonw-sha256', required=True)
    run.add_argument('--owner-root', type=Path, required=True)
    stop = commands.add_parser('stop-role')
    stop.add_argument('--owner-root', type=Path, required=True)
    accept = commands.add_parser('accept-minutes')
    accept.add_argument('--deployment', type=Path, required=True)
    accept.add_argument('--deployment-sha256', required=True)
    accept.add_argument('--day', required=True)
    accept.add_argument('--endpoint')
    accept.add_argument('--credential-file')
    accept.add_argument('--token-env')
    args = parser.parse_args()
    if args.command == 'stage-program':
        result = stage_program(args.mainline, ROOT, descriptor(args.native_build), args.collection_component, args.output)
    elif args.command == 'prepare-config':
        result = prepare_configuration(load(dict(path=str(args.request), sha256=args.request_sha256)))
    elif args.command == 'run-role':
        from integrations.guanheng.collection_role import run_role
        selected = dict(path=str(args.deployment), sha256=args.deployment_sha256)
        verify_deployment(selected, adopted=True)
        result = run_role(selected, args.pythonw, args.pythonw_sha256, args.owner_root)
    elif args.command == 'stop-role':
        from integrations.guanheng.collection_role import stop_role
        result = stop_role(args.owner_root)
    elif args.command == 'accept-minutes':
        result = accept_minutes(dict(path=str(args.deployment), sha256=args.deployment_sha256), args.day,
            endpoint=args.endpoint, credential_file=args.credential_file, token_env=args.token_env)
    else:
        selected = dict(path=str(args.deployment), sha256=args.deployment_sha256)
        if args.command == 'verify':
            result = verify_deployment(selected, adopted=args.adopted)
        else:
            result = adopt_source(selected) if args.command == 'adopt-source' else rollback_source(selected)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    if isinstance(result, dict) and result.get('passed') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # 原值、SDK正文及部署秘密不进入诊断输出，只报告阶段异常类型。
        print(json.dumps(dict(status='failed', exception_type=type(error).__name__)), file=sys.stderr)
        raise SystemExit(2)
