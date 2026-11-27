"""Build and run the terminal-external market roles of a read-only QMT pair."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
import time
from uuid import uuid4


ROLES = ('history', 'analysis', 'batch', 'reference')
DIRECTORY = 'market-readonly'


class DeploymentError(RuntimeError):
    """可公开的本机部署错误，消息只含操作名称与固定说明。"""


def load_profile(value, account_port):
    """读取脱敏选择，具体证券和板块合同由原 Agent 准入。"""
    if (type(value) is not dict or set(value) != {
            'schema', 'ports', 'quote_symbols', 'history_prepare_symbols', 'security_source_groups'}
            or value['schema'] != 'qmt.readonly-market-onboarding.v1'):
        raise DeploymentError('expected a read-only market profile')
    ports = value['ports']
    if (type(ports) is not dict or set(ports) != set(ROLES)
            or any(type(port) is not int or not 1024 <= port <= 65535 for port in ports.values())
            or len({account_port, *ports.values()}) != len(ROLES) + 1):
        raise DeploymentError('market and account roles need distinct loopback ports')
    for label in ('quote_symbols', 'history_prepare_symbols'):
        symbols = value[label]
        if (type(symbols) is not list or not 1 <= len(symbols) <= 128
                or any(type(symbol) is not str for symbol in symbols)
                or len(set(symbols)) != len(symbols)):
            raise DeploymentError(label + ' needs 1 to 128 unique symbols')
        value[label] = sorted(symbols)
    if type(value['security_source_groups']) is not list or not value['security_source_groups']:
        raise DeploymentError('security source groups must name observed QMT sector nodes')
    return value


def role_contracts(profile):
    from guanheng_qmt_shm_agent import analysis_batch, analysis_reads, history_preparation, security_reference

    reference = dict(schema='qmt.security-reference-limits.v1', max_page_size=64, max_detail_symbols=16,
        max_catalog_symbols=8000, max_catalogs=2, catalog_lifetime_seconds=900,
        max_cache_bytes=4 * 1024 * 1024, max_data_bytes=300 * 1024, source_groups=profile['security_source_groups'])
    return {
        'history': (history_preparation.PROFILE_VERSION, 18000, 65536, {
            'market.full_tick': ('qmt.standard-read.v1', {}),
            'market.history_1m': ('qmt.history-read.v1', dict(schema_version='qmt.history-1m.v1',
                max_calendar_days=2, max_rows=400, max_data_bytes=49152)),
            history_preparation.OPERATION: (history_preparation.POLICY, dict(
                schema_version=history_preparation.LIMITS_SCHEMA, symbols=profile['history_prepare_symbols'],
                periods=['1m'], max_calendar_days={'1m': 1, '1d': 1}, max_tasks=96, max_queued=1,
                total_timeout_ms=27000)),
        }),
        'analysis': (analysis_reads.PROFILE_VERSION, 15000, 65536, {
            analysis_reads.DAILY: (analysis_reads.DAILY_POLICY, dict(schema_version='qmt.daily-history.v1',
                max_calendar_days=28, max_rows=32, max_data_bytes=32768)),
            analysis_reads.FACTORS: (analysis_reads.FACTORS_POLICY, dict(schema_version='qmt.divid-factors.v1',
                max_events=1024, max_data_bytes=49152)),
        }),
        'batch': (analysis_batch.PROFILE_VERSION, 15000, 65536, {
            analysis_reads.DAILY: (analysis_batch.POLICY, dict(schema_version='qmt.daily-batch.v1',
                max_symbols=8, max_calendar_days=28, max_rows=32, max_data_bytes=49152)),
        }),
        'reference': (security_reference.PROFILE_VERSION, 23000, 524288, {
            operation: (security_reference.POLICY, reference) for operation in security_reference.OPERATIONS
        }),
    }


def route_for(account, role):
    tag = uuid4().hex[:16]
    return dict(route_id=f'qmt-{role}-{tag}', executor_id=f'wt-{role}-{tag}',
                route_epoch=account['route']['route_epoch'])


def build_configuration(account, role, contract, port, root, policy_template):
    """用原账户传输预算作基础，建立独立的回环角色和单次执行策略。"""
    from guanheng_qmt_shm import bootstrap, history_preparation_bootstrap
    from guanheng_qmt_shm_agent.protocol import canonical
    from guanheng_qmt_shm.private_files import write_private_new

    version, timeout, size, operations = contract
    route = route_for(account, role)
    key = route['route_id']
    policy_path = root / (role + '-policy.json')
    profiles, policies = {}, {}
    for operation, (policy_id, limits) in sorted(operations.items()):
        profiles[operation] = dict(policy_id=policy_id, policy_version='1.0',
                                   execution_timeout_ms=timeout, limits=limits)
        policy = policies.setdefault(policy_id, dict(policy_template, policy_id=policy_id,
            operation_ids=[], queue_timeout_ms=2500, execution_timeout_ms=timeout,
            response_grace_ms=3500, total_timeout_ms=timeout + 6000))
        policy['operation_ids'].append(operation)
    raw_policy = canonical(dict(schema_version='1.0', policies=list(policies.values())))
    write_private_new(policy_path, raw_policy)
    config = {field: account[field] for field in bootstrap.FIELDS}
    config.update(route=route, http_key_id=key, listen_port=port, max_http_inflight=2,
        journal_path=str(root / (role + '.sqlite')), operation_policies_path=str(policy_path),
        max_records=96, max_result_bytes=size, max_journal_bytes=size * 2, max_frame=2097152,
        transport=dict(account['transport'], name='qmt-broker-' + key, max_mapped_bytes=16777216),
        control_profile=dict(account['control_profile'], schema_version='1.0', max_pending_calls=4,
            max_call_bytes=16384, max_reply_bytes=2 * size + 4096, max_retained_bytes=8388608,
            max_cycle_bytes=1572864, max_call_seconds=40),
        read_operations=sorted(operations), read_profile_version=version, operation_profiles=profiles,
        read_retention=dict(schema='qmt.read-retention.v1', max_lifetime_ms=120000))
    credentials = dict(ipc_secret=secrets.token_bytes(32), http_keys={key: secrets.token_hex(32)})
    owner = history_preparation_bootstrap if role == 'history' else bootstrap
    _, _, public = owner.validate_launch(config, credentials=credentials)
    config['max_journal_bytes'] = config['max_records'] * (public['max_request_bytes'] + size + 16384)
    config, policies, _ = owner.validate_launch(config, credentials=credentials)
    return config, credentials, owner.agent_settings(config, policies, credentials['ipc_secret'])


def require_readonly(config):
    if (config.get('writes_enabled') is not False or config.get('listen_host') != '127.0.0.1'
            or config.get('read_operations') != ['account.trade_detail']):
        raise DeploymentError('expected an account-query-only loopback configuration')


def prepare(args):
    from guanheng_qmt_shm import bootstrap, history_preparation_product, trade_pair
    from guanheng_qmt_shm_agent.protocol import canonical, decode
    from guanheng_qmt_shm_agent.quote_stream_contract import PROFILE_SCHEMA, symbols_digest
    from guanheng_qmt_shm.private_files import create_private_control_directory, write_private_new

    account = decode(trade_pair._read(args.account_config, 65536))
    require_readonly(account)
    profile = load_profile(decode(trade_pair._read(args.profile, 65536)), account['listen_port'])
    account_keys = bootstrap.credentials_from_environment(account)
    root = args.output.parent / DIRECTORY
    if args.output.name != 'pair' or args.output.exists():
        raise DeploymentError('use a new instance with pair as the output directory name')
    policy_template, = decode(trade_pair._read(Path(account['operation_policies_path'])))['policies']
    create_private_control_directory(root)
    configurations, credentials, settings = {}, {}, {}
    for role, contract in role_contracts(profile).items():
        configurations[role], credentials[role], settings[role] = build_configuration(
            account, role, contract, profile['ports'][role], root, policy_template)
    symbols = profile['quote_symbols']
    route = route_for(account, 'quotes')
    quotes = dict(route=route, secret=secrets.token_bytes(32), max_frame=262144,
        transport=dict(account['transport'], name='qmt-broker-' + route['route_id']),
        connect_seconds=5, io_seconds=3, symbols=symbols,
        profile=dict(schema_version=PROFILE_SCHEMA, symbols_sha256=symbols_digest(symbols),
                     max_symbols=len(symbols), max_batch=len(symbols), max_pending_ticks=512))
    history = configurations['history']
    _, quotes, _, preparation, _, _, _ = history_preparation_product._snapshot(
        history, quotes, credentials['history'], trade_pair._read(Path(history['operation_policies_path'])),
        args.reconnect_seconds)
    market = dict(quotes=quotes, preparation=preparation, preparation_reconnect_seconds=args.reconnect_seconds)
    attachments = {role: dict(agent=settings[role], reconnect_seconds=args.reconnect_seconds)
                   for role in ('analysis', 'batch', 'reference')}
    trade_pair.create_product_pair(account, credentials=account_keys, output=args.output,
        sdk_metadata=decode(trade_pair._read(args.sdk_manifest, 65536)),
        stdlib_license=trade_pair._read(args.stdlib_license, 65536), reconnect_seconds=args.reconnect_seconds,
        market=market, source_runtime=dict(schema_version='qmt.source-runtime.v1', mode='strategy_tick'),
        analysis_read=attachments['analysis'], analysis_batch_read=attachments['batch'],
        security_reference_read=attachments['reference'])
    verified = trade_pair.verify_product_pair(args.output)
    write_private_new(root / 'owner.lock', b'0')
    # IPC 原密钥只读同次完整配对。专用 HTTP 密钥由该实例单独持有。
    private_host = dict(pair_sha256=verified['pair_manifest_sha256'], configurations=configurations,
                        http_keys={role: credentials[role]['http_keys'] for role in ROLES})
    write_private_new(root / 'market-host.json', canonical(private_host))
    print(json.dumps(verified))


def load_deployment(instance):
    """沿原配对核验，并把四个 Host 设置和冻结的 Agent 设置逐项对齐。"""
    from guanheng_qmt_shm import bootstrap, history_preparation_product, trade_pair
    from guanheng_qmt_shm_agent.history_preparation import validate_configuration as validate_preparation
    from guanheng_qmt_shm_agent.protocol import decode
    from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration

    pair, root = instance / 'pair', instance / DIRECTORY
    identity, account_snapshot = trade_pair._verified(pair)
    raw = trade_pair._read(pair / 'deployment.json')
    if sha256(raw).hexdigest() != identity['pair_config_sha256']:
        raise DeploymentError('pair configuration changed after verification')
    _, _, _, market, _, source, analysis, batch, reference = trade_pair._decode_reference_deployment(raw)
    account, account_credentials, _, _, _, admitted, _ = account_snapshot
    require_readonly(account)
    if (not all((market, analysis, batch, reference))
            or not source or source['mode'] != 'strategy_tick'):
        raise DeploymentError('expected a complete strategy_tick market pair')
    private_host = decode(trade_pair._read(root / 'market-host.json'))
    if private_host['pair_sha256'] != identity['pair_manifest_sha256']:
        raise DeploymentError('market Host belongs to a different pair')
    snapshots = dict(analysis=analysis, batch=batch, reference=reference,
        history=dict(agent=market['preparation'], reconnect_seconds=market['preparation_reconnect_seconds']))
    ports = {account['listen_port']}
    roles = {}
    bindings = {'account': (account, account_credentials['http_keys'], admitted.profile)}
    for role, frozen in snapshots.items():
        config = private_host['configurations'][role]
        port = config['listen_port']
        if (config['listen_host'] != '127.0.0.1' or port in ports
                or Path(config['operation_policies_path']) != root / (role + '-policy.json')
                or Path(config['journal_path']) != root / (role + '.sqlite')):
            raise DeploymentError('market Host path or listener differs from the instance')
        ports.add(port)
        credentials = dict(ipc_secret=frozen['agent']['secret'], http_keys=private_host['http_keys'][role])
        policy_bytes = trade_pair._read(Path(config['operation_policies_path']), 1048576)
        if role == 'history':
            config, _, _, settings, policies, public, _ = history_preparation_product._snapshot(
                config, market['quotes'], credentials, policy_bytes, frozen['reconnect_seconds'])
            profile = validate_preparation(settings).profile
        else:
            config, policies, public = bootstrap._validate_launch_snapshot(
                config, credentials=credentials, policy_bytes=policy_bytes)
            settings = bootstrap.agent_settings(config, policies, credentials['ipc_secret'])
            profile = validate_read_configuration(settings).profile
        if settings != frozen['agent']:
            raise DeploymentError(role + ' Host settings differ from the paired Agent')
        if 'read_retention' not in profile:
            raise DeploymentError(role + ' requires a retained-read market pair; prepare a new instance')
        roles[role] = (config, policies, public, credentials, frozen['reconnect_seconds'])
        bindings[role] = (config, credentials['http_keys'], profile)
    return account, roles, market['quotes'], bindings


def binding_status(config, http_keys, expected_profile):
    """发送签名请求，核对回环 Host 返回的绑定和配对能力。"""
    from guanheng_qmt_shm import bound
    from guanheng_qmt_shm.auth import sign_request
    from guanheng_qmt_shm_agent.protocol import canonical, decode

    port, key_id = config['listen_port'], config['http_key_id']
    path = '/internal/v1/read-binding'
    timestamp, nonce, body_sha256 = str(time.time()), str(uuid4()), bound.digest(b'')
    headers = {'X-QMT-Key-Id': key_id, 'X-QMT-Timestamp': timestamp, 'X-QMT-Nonce': nonce,
        'X-QMT-Content-SHA256': body_sha256,
        'X-QMT-Signature': sign_request(http_keys[key_id], 'GET', path, timestamp, nonce, body_sha256)}
    result = dict(port=port, status='unreachable', binding_verified=False)
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
    try:
        conn.request('GET', path, headers=headers)
        response = conn.getresponse()
        result.update(status='reachable', http_status=response.status)
        if response.status != 200:
            return result
        raw = response.read(bound.MAX_METADATA_BYTES + 1)
        if len(raw) > bound.MAX_METADATA_BYTES:
            return result
        metadata = decode(raw)
        binding = bound.binding(metadata['binding'], control_version=expected_profile['control_profile']['schema_version'])
        profile = bound.unb64(metadata['read_profile_body_b64'], bound.MAX_PROFILE_BYTES)
        if (metadata['schema_version'] == bound.SCHEMA and metadata['order_ready'] is False
                and binding['route'] == config['route']
                and metadata['binding_sha256'] == bound.digest(canonical(binding))
                and metadata['read_profile_body_sha256'] == binding['capability_sha256'] == bound.digest(profile)
                and profile == canonical(expected_profile)):
            result.update(status='available', lifecycle='connected', order_ready=False, binding_verified=True)
        return result
    except (OSError, http.client.HTTPException, ValueError, KeyError, TypeError):
        return result
    finally:
        conn.close()


def status(instance):
    _, _, _, bindings = load_deployment(instance)
    endpoints = {role: binding_status(*material) for role, material in bindings.items()}
    path = instance / DIRECTORY / 'quote-status.json'
    quotes = None
    if path.exists():
        quotes = json.loads(path.read_bytes())
        quotes['fresh'] = 0 <= time.time() - quotes['observed_epoch'] < 5 and quotes['running']
    print(json.dumps(dict(writes_enabled=False, endpoints=endpoints, quotes=quotes)))


def serve_foreground(instance):
    """持有四个 HTTP Host 和一个 QST 接收器，Ctrl+C 沿原 owner 关闭。"""
    import msvcrt
    from guanheng_qmt_shm import bootstrap, history_preparation_bootstrap, history_preparation_product
    from guanheng_qmt_shm_agent import windows_security
    from guanheng_qmt_shm.quote_stream import QuoteStreamReceiver
    from guanheng_qmt_shm.server import create_server

    account, roles, quotes, _ = load_deployment(instance)
    kernel, _ = windows_security.libraries()
    if windows_security.current_session(kernel) != account['transport']['windows_session_id']:
        raise DeploymentError('use the Windows session recorded by the pair')
    root = instance / DIRECTORY
    with (root / 'owner.lock').open('r+b', buffering=0) as lease:
        try:
            msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise DeploymentError('market Host already owns this instance') from exc

        servers = {}
        for role, (config, policies, public, credentials, reconnect) in roles.items():
            if role == 'history':
                service = history_preparation_bootstrap._build_read_service(
                    config, policies, public, credentials, reconnect_seconds=reconnect,
                    service_type=history_preparation_product._ProductService)
            else:
                service = bootstrap._build_read_service(
                    config, policies, public, credentials, reconnect_seconds=reconnect)
            servers[role] = create_server(service, http_keys=credentials['http_keys'])
        run_market(root, servers, QuoteStreamReceiver, quotes)


def run_market(root, servers, receiver_type, settings):
    counts, last, guard = Counter(), {}, threading.Lock()

    def receive(ticks, kind):
        at = max(tick['time'] for tick in ticks.values()) / 1000
        with guard:
            counts[kind] += len(ticks)
            last[kind] = datetime.fromtimestamp(at, timezone.utc).isoformat()

    receiver = receiver_type(settings=settings, on_batch=receive)

    def publish(state, running):
        with guard:
            value = dict(observed_epoch=time.time(), running=running, connected=state['connected'],
                phase=state['phase'], failure=state['failure'], cleanup_failure=state['cleanup_failure'],
                generation=state['generation'], heartbeats=state['heartbeats'],
                snapshot_ticks=counts['snapshot'], incremental_ticks=counts['incremental'],
                last_source_at_utc=dict(last))
        candidate = root / 'quote-status.tmp'
        candidate.write_text(json.dumps(value), encoding='utf-8')
        try:
            os.replace(candidate, root / 'quote-status.json')
        except PermissionError:
            # Windows 读者如短时占用目标，下一次快照继续，不打断行情接收。
            return

    def serve_one(server):
        try:
            server.run()
        finally:
            server.close()

    with ThreadPoolExecutor(max_workers=len(servers), thread_name_prefix='qmt-market') as executor:
        tasks = {}
        try:
            for role, server in servers.items():
                tasks[role] = executor.submit(serve_one, server)
            receiver.start()
            deadline = time.monotonic() + 15
            announced = False
            while True:
                for role, task in tasks.items():
                    if task.done():
                        raise DeploymentError(role + ' Host exited; check the instance and loopback port')
                ready = all(server.started for server in servers.values())
                if ready and not announced:
                    print('Market Hosts listening; check status for an authenticated QMT source.', flush=True)
                    announced = True
                if not announced and time.monotonic() >= deadline:
                    raise DeploymentError('market Hosts did not finish listening')
                quote_state = receiver.status()
                if quote_state['phase'] in ('closed', 'owner_pending'):
                    raise DeploymentError('quote receiver exited; check the instance and QMT session')
                publish(quote_state, True)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            for server in servers.values():
                server.request_close()
            try:
                receiver.close(time.monotonic() + 8)
            finally:
                publish(receiver.status(), False)
        for role, task in tasks.items():
            if task.exception() is not None:
                raise DeploymentError(role + ' Host did not close cleanly')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    for name in ('account-config', 'profile', 'sdk-manifest', 'stdlib-license', 'output'):
        create.add_argument('--' + name, type=Path, required=True)
    create.add_argument('--reconnect-seconds', type=float, required=True)
    for name in ('serve', 'status'):
        commands.add_parser(name).add_argument('--root', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            prepare(args)
        elif args.command == 'serve':
            # 支持原生控制台 Ctrl+Break，与 Ctrl+C 走同一关闭路径。
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, signal.default_int_handler)
            serve_foreground(args.root)
        else:
            status(args.root)
        return 0
    except DeploymentError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print('QMT market {} failed ({})'.format(args.command, type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
