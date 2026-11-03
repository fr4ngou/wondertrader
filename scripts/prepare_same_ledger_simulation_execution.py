"""离线准备原账1.1.2模拟执行权限候选；不启动owner、连接QMT或消费原金融状态。"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import secrets
import socket
from uuid import uuid4

from guanheng_qmt_shm.account_read_composition import account_read_material
from guanheng_qmt_shm.bound import MAX_METADATA_BYTES
from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from guanheng_qmt_shm.trade_event_records import _STREAM_BYTES, validate_trade_event_storage
from guanheng_qmt_shm.trade_pair import create_product_pair, verify_product_pair
from guanheng_qmt_shm.trade_bootstrap import trade_agent_settings, validate_trade_launch
from guanheng_qmt_shm_agent.protocol import canonical
from guanheng_qmt_shm_agent.trading_configuration import validate_trade_configuration
import guanheng_qmt_shm_agent
from guanheng_wt_runtime.execution_recovery import compatible_business_configuration
import time


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', required=True, type=Path, help='当前只读WRI准备收据；读取配置引用，不消费运行状态')
    parser.add_argument('--pair', required=True, type=Path, help='当前已验证Host配对目录；私有凭据仅在内存读取')
    parser.add_argument('--output', required=True, type=Path, help='全新E盘私有候选目录；禁止覆盖原目录')
    parser.add_argument('--account-sha256', required=True, help='用户确认的模拟账户完整标识SHA256，不接受账户明文参数')
    parser.add_argument('--symbols', required=True, nargs=8, help='由策略owner给出的固定8证券；须与原输入集合完全相同')
    parser.add_argument('--max-commands', type=int, default=2048, help='同Journal通信记录容量1..2048；不是资金或止损限额')
    parser.add_argument('--predecessor-control', required=True, type=Path)
    parser.add_argument('--successor-pythonw', required=True, type=Path)
    args = parser.parse_args()
    if not (args.output.is_absolute() and args.output.drive.upper() == 'E:' and not args.output.exists()):
        raise ValueError('simulation candidate input or identity differs')
    if not (1 <= args.max_commands <= 2048):
        raise ValueError('simulation candidate input or identity differs')
    previous = read(args.prepared)
    if not (sha(previous['configuration']) == previous['configuration_sha256']):
        raise ValueError('simulation candidate input or identity differs')
    runtime = read(previous['configuration'])
    if not (sha(runtime['components']['execution']['descriptor']) == runtime['components']['execution']['sha256']):
        raise ValueError('simulation candidate input or identity differs')
    execution = read(runtime['components']['execution']['descriptor'])
    if not (sha(execution['configuration']) == execution['configuration_sha256']):
        raise ValueError('simulation candidate input or identity differs')
    template = read(execution['configuration'])
    # 当前WRI负责实际前代身份；外部路径只用于逐项核对该同一引用。
    status = read(previous['status_file'])
    if not (status['configuration_sha256'] == previous['configuration_sha256']
            and status['control_id'] == previous['control_id']
            and status['instance_id'] == runtime['instance_id']):
        raise ValueError('predecessor runtime identity differs')
    reference = status['components']['execution']['business_observation']
    if not (reference['schema'] == 'guanheng.execution-observation-reference.v1'
            and Path(reference['path']).parent.resolve() == args.predecessor_control.resolve()
            and Path(reference['ready_path']).resolve() == (args.predecessor_control/'ready.json').resolve()
            and reference['control_id'] == args.predecessor_control.name):
        raise ValueError('predecessor execution reference differs')
    native = read(args.predecessor_control/'execution.json')
    origin = copy.deepcopy(native)
    origin_ready = read(args.predecessor_control/'ready.json')
    if not (origin_ready['schema'] == 'guanheng.execution.ready.v1'
            and all(origin_ready[key] == reference[key] for key in ('control_id','config_sha256','pid'))
            and origin_ready['config_sha256'] == sha(args.predecessor_control/'execution.json')
            and native['output_directory'] == template['output_directory']
            and compatible_business_configuration(native,template,deadline=time.monotonic()+10)):
        raise ValueError('predecessor configuration differs')
    inventory_input = Path(execution['initial_inventory']['state_root'])/'native-input.json'
    if not (Path(native['takeover']['input_file']).resolve() == inventory_input.resolve()
            and native['takeover']['input_sha256'] == sha(inventory_input)):
        raise ValueError('predecessor inventory identity differs')
    if not args.successor_pythonw.is_absolute() or not args.successor_pythonw.is_file():
        raise ValueError('successor role interpreter required')
    manifest = read(args.pair/'manifest.json')
    verified = verify_product_pair(args.pair, installed_agent=Path(guanheng_qmt_shm_agent.__file__).parent)
    if not (verified['paired'] is True and verified['qualified_in_qmt'] is False):
        raise ValueError('simulation candidate input or identity differs')
    current_host = read(runtime['components']['trade_host']['descriptor'])
    if not (sha(runtime['components']['trade_host']['descriptor']) == runtime['components']['trade_host']['sha256']):
        raise ValueError('simulation candidate input or identity differs')
    if not (Path(current_host['pair_directory']) == args.pair and sha(args.pair/'manifest.json') == current_host['pair_manifest_sha256']):
        raise ValueError('simulation candidate input or identity differs')
    pair = read(args.pair/'deployment.json')
    host = copy.deepcopy(pair['host'])
    if not (host['writes_enabled'] is False and native['trader']['writes_enabled'] is False):
        raise ValueError('simulation candidate input or identity differs')
    binding = host['trade_binding']
    if not (hashlib.sha256(binding['account_id'].encode()).hexdigest() == args.account_sha256):
        raise ValueError('simulation candidate input or identity differs')
    if not (native['trader']['expected_account'] == binding['account_id']):
        raise ValueError('simulation candidate input or identity differs')
    # 证券集合沿已固定的原策略，而价格/数量步长沿同一Native已验合约。
    strategy = native['strategies'][0]['parameters']['python_strategy']
    inputs = read(strategy['input_file'])
    symbols = sorted(c['symbol'] for c in inputs['request']['cycles'])
    if not (len(symbols) == 8 and len(set(symbols)) == 8):
        raise ValueError('simulation candidate input or identity differs')
    if not (set(symbols) == set(args.symbols) and len(set(args.symbols)) == 8):
        raise ValueError('simulation candidate input or identity differs')
    commodities = read(Path(native['installation_root'])/native['base_data']['commodities'])
    rules = {}
    for symbol in symbols:
        group = commodities['SSE' if symbol.endswith('.SH') else 'SZSE']['ETF']
        if not (group['minlots'] == group['lotstick'] == 100 and group['pricetick'] == .001):
            raise ValueError('simulation candidate input or identity differs')
        rules[symbol] = dict(price_tick='0.001', buy_min=100, buy_step=100, sell_min=100, sell_step=100)
    output = create_private_directory(args.output)
    for name in ('native-controls', 'trade-host-controls', 'wt-controls'):
        create_private_directory(output/name)
    write = lambda path, value: write_private_new(path, canonical(value))
    write_private_new(output/'policy.json', Path(host['operation_policies_path']).read_bytes())
    host.update(operation_policies_path=str(output/'policy.json'), journal_path=str(output/'communication.sqlite'),
                writes_enabled=True, ipc_secret_env='GH_AUTO_CANDIDATE_IPC', http_secret_env='GH_AUTO_CANDIDATE_HTTP')
    binding.update(binding_id='auto-sim-'+uuid4().hex, symbol_rules=rules, max_commands=args.max_commands)
    host['route'].update(route_id='auto-sim-'+uuid4().hex, route_epoch=host['route']['route_epoch']+1)
    host['transport']['name'] = 'qmt-broker-auto-sim-'+uuid4().hex
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        host['listen_port'] = probe.getsockname()[1]
    limits = host['trade_profile']['limits']
    limits.update(max_commands=args.max_commands, max_events=2*args.max_commands,
                  max_total_event_bytes=2*args.max_commands*limits['max_event_bytes'])
    host['trade_profile']['binding_sha256'] = hashlib.sha256(canonical(binding)).hexdigest()
    host['max_trade_bytes'] = args.max_commands*(limits['max_command_bytes']+limits['max_call_result_bytes']+MAX_METADATA_BYTES)+MAX_METADATA_BYTES
    storage = host['event_storage']
    storage.update(max_events=limits['max_events'],
                   max_bytes=storage['max_streams']*_STREAM_BYTES+limits['max_events']*(limits['max_event_bytes']+512))
    credentials = dict(ipc_secret=secrets.token_bytes(32), http_keys={host['http_key_id']:secrets.token_hex(32)})
    # 新Source/Host同一配置生成；原account_read组合及其权限逐字段保持。
    admitted_host, policies, unused = validate_trade_launch(host, credentials=credentials)
    admitted = validate_trade_configuration(trade_agent_settings(admitted_host, policies, credentials['ipc_secret']))
    unused, unused, identity, unused = validate_trade_event_storage(admitted.profile, binding, storage,
                                                                  max_result_bytes=host['max_result_bytes'])
    storage['max_bytes'] += len(identity)
    generated = output/'pair'
    actual = create_product_pair(host, credentials=credentials, output=generated,
        sdk_metadata=manifest['memory_runtime']['sdk'], stdlib_license=(args.pair/'CPYTHON-LICENSE.txt').read_bytes(),
        reconnect_seconds=pair['reconnect_seconds'], installed_agent=Path(guanheng_qmt_shm_agent.__file__).parent,
        source_runtime=pair.get('source_runtime'),
        account_read=account_read_material(pair['account_read'], decode_secrets=True))
    if not (verify_product_pair(generated, installed_agent=Path(guanheng_qmt_shm_agent.__file__).parent) == actual):
        raise ValueError('simulation candidate input or identity differs')
    environment = read(previous['environment'])
    environment.update({host['ipc_secret_env']:credentials['ipc_secret'].hex(),
                        host['http_secret_env']:credentials['http_keys'][host['http_key_id']],
                        'GH_AUTO_CANDIDATE_KEY_ID':host['http_key_id']})
    write(output/'environment.json', environment)
    descriptor = read(runtime['components']['trade_host']['descriptor'])
    descriptor.update(pair_directory=str(generated), pair_manifest_sha256=sha(generated/'manifest.json'),
                      control_root=str(output/'trade-host-controls'))
    write(output/'trade-host.json', descriptor)
    native['trader'].update(writes_enabled=True, base_url='http://127.0.0.1:'+str(host['listen_port']),
        binding_id=binding['binding_id'], binding_sha256=host['trade_profile']['binding_sha256'],
        instance_id=str(uuid4()), key_id_env='GH_AUTO_CANDIDATE_KEY_ID', hmac_secret_env=host['http_secret_env'])
    # 原账连续：固定实际前代，保留全部金融/行情/库存配置；仅改变七项权限/连接。
    native['execution_permission_origin'] = dict(
        schema='guanheng.execution-permission-origin.v1',  # 权限兼容来源协议，不授金融动作。
        file=str(args.predecessor_control/'execution.json'),  # 实际前代配置绝对路径。
        sha256=sha(args.predecessor_control/'execution.json'))  # 前代原字节摘要。
    native['recovery'] = dict(mode='resume_reconciled',transition=dict(
        file=str(output/'transition-after-normal-close.json'),sha256='0'*64))
    if not compatible_business_configuration(native,origin,deadline=time.monotonic()+10):
        raise ValueError('same-ledger business configuration differs')
    write(output/'execution-same-ledger.json',native)
    execution.update(configuration=str(output/'execution-same-ledger.json'),
        configuration_sha256=sha(output/'execution-same-ledger.json'),control_root=str(output/'native-controls'))
    capital=execution['initial_inventory']['capital']
    write(output/'execution-deployment.json',execution)
    runtime['components']['trade_host'].update(descriptor=str(output/'trade-host.json'),sha256=sha(output/'trade-host.json'))
    runtime['components']['execution'].update(descriptor=str(output/'execution-deployment.json'),sha256=sha(output/'execution-deployment.json'))
    write(output/'runtime-same-ledger.json',runtime)
    control=str(uuid4())
    prepared=dict(
        schema='guanheng.same-ledger-simulation-prepared.v1',  # 原账模拟权限候选收据版本。
        configuration=str(output/'runtime-same-ledger.json'),  # 尚待实际关闭后绑定transition的候选配置。
        configuration_sha256=sha(output/'runtime-same-ledger.json'),  # 候选配置原字节摘要。
        instance_id=runtime['instance_id'],  # 保持原实例独占身份。
        control_id=control,  # 预留后继控制身份，当前未运行。
        environment=str(output/'environment.json'),  # 新候选的受控凭据材料路径。
        pythonw=str(args.successor_pythonw),  # 实际后继角色解释器入口。
        source=str(generated/'strategy.py'),  # 离线新Source正文，当前尚未装入终端。
        source_sha256=sha(generated/'strategy.py'),  # 候选Source原字节摘要。
        control_directory=str(output/'wt-controls'/control),  # 新控制目录，当前未创建。
        status_file=str(output/'wt-controls'/control/'status.json'),  # 后继状态位置。
        financial_state=native['output_directory'],  # 原金融账根，保持原事实。
        initial_inventory=execution['initial_inventory']['state_root'],  # 原库存及资本基准根。
        capital_cny=capital['total_cny'],  # 原资本声明，保持原金额。
        writes_enabled=True,  # 候选请求执行，仍须原各层授权。
        started=False,  # 准备器只写候选材料。
        live_adoption_authorized=False,  # 当前离线交付不授现场切换。
        new_baseline_required=False,  # 使用原账准入，保留原基准。
        transition_after_normal_close_required=True)  # 实际正常关闭后由后继解释器生成。
    write(output/'PREPARED.json', prepared)
    summary=dict(
        schema='guanheng.same-ledger-simulation-candidate.v1',  # 原账离线候选摘要版本。
        account_suffix=binding['account_id'][-4:],  # 账户脱敏尾号。
        account_sha256=args.account_sha256,  # 绑定用户已确认的模拟账户完整标识摘要。
        account_nature='user-confirmed-no-real-funds',  # 用户确认的无真实资金模拟柜台。
        symbols=symbols,  # 原策略固定八证券。
        pair=str(generated),  # 离线通信配对材料路径，包含受控凭据。
        pair_manifest_sha256=sha(generated/'manifest.json'),  # 固定配对清单摘要。
        Source_sha256=sha(generated/'strategy.py'),  # 离线候选Source摘要。
        runtime_configuration=prepared['configuration'],  # 原账候选WRI配置路径。
        runtime_configuration_sha256=prepared['configuration_sha256'],  # WRI配置摘要。
        original_financial_root=native['output_directory'],  # 原金融状态根。
        original_inventory_root=execution['initial_inventory']['state_root'],  # 原基准库存根。
        original_capital_cny=capital['total_cny'],  # 原100万元声明。
        same_business_configuration_verified=True,  # 权限/运输归一化后全配置精确相同。
        current_financial_state_reused=True,  # 采用时沿原账核查，不产生新基准。
        new_baseline_required=False,  # 原基准连续。
        original_runtime_untouched=True,  # 本准备器只读原环境。
        owners_started=False,  # 没有启动owner。
        SDK_calls=0,  # 没有SDK调用。
        live_adoption_authorized=False,  # 现场权限/发布另按原授权核查。
        native_upgrade_required=True,  # 采用前固定已审权限归一化Native制品。
        transition_after_normal_close_required=True)  # 尚未消费当前生命周期。
    write(output/'SUMMARY.json',summary)
    print(json.dumps(dict(prepared=True,same_ledger=True,new_baseline=False,owners_started=False,SDK_calls=0)))


if __name__ == '__main__':
    main()
