"""独立原生来源历史服务；复用原Reader/HTTP，终端外由统一进程owner管理。"""
from __future__ import annotations

import sys
from pathlib import Path

# 固定安装闭包为本入口的来源；-I忽略外部PYTHONPATH和当前工作目录。
_RELEASE_ROOT = Path(__file__).resolve().parents[2]
if str(_RELEASE_ROOT) not in sys.path:
    sys.path.insert(0, str(_RELEASE_ROOT))

import argparse
import ipaddress
import json
import math
import os
import re
import time
from uuid import UUID, uuid4

from integrations.guanheng.market_service import MarketHTTPServer
from integrations.guanheng.source_market import create_native_source_market
from integrations.guanheng.quote_collection_service import _read, _json, _fields, _need, _path, _sha
from guanheng_qmt_shm.private_files import create_private_directory, write_private_new


def _configuration(path, expected):
    """父配置及source配置各读一次，核原字节身份后才创建原生Reader。"""
    value = _json(_read(path, 65536, expected))
    fields='schema source_configuration listen token_env socket_timeout'
    _fields(value,fields+' daily_update' if 'daily_update'in value else fields)
    _need(value['schema'] == 'guanheng.source-market-service.v1')
    source, listen = value['source_configuration'], value['listen']
    _fields(source, 'path sha256')
    _fields(listen, 'host port')
    _need(type(listen['host']) is str and ipaddress.ip_address(listen['host']).is_loopback)
    _need(type(listen['port']) is int and 1 <= listen['port'] <= 65535)
    timeout = value['socket_timeout']
    _need(type(timeout) in (int, float) and .1 <= timeout <= 30 and math.isfinite(timeout))
    _need(type(value['token_env']) is str and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', value['token_env']))
    source_config = _json(_read(_path(source['path']), 1024 * 1024, source['sha256']))
    _need(source_config.get('mode') in ('source-store', 'source-stores', 'source-catalog', 'source-preparing', 'source-recovered', 'source-collected', 'source-shm-quotes', 'source-daily-overlay', 'source-market-snapshot', 'source-market-current', 'source-current-day'))
    if 'daily_update'in value:
        from integrations.guanheng.daily_data_service import validate_configuration
        descriptor=value['daily_update'];_fields(descriptor,'path sha256')
        update=validate_configuration(_json(_read(_path(descriptor['path']),16777216,descriptor['sha256'])))
        # 分钟组合仅接管分钟请求；每日owner仍绑定原动态市场CURRENT，任务及发布身份保持。
        daily_source = source_config.get('base', {}) if source_config.get('mode') == 'source-current-day' else source_config
        current_source = (daily_source.get('delegate', {})
            if daily_source.get('mode') == 'source-recovered' else daily_source)
        _need(current_source.get('mode')=='source-market-current'
            and os.path.normcase(str(Path(current_source['current_file']).absolute()))==os.path.normcase(
                str(Path(update['template']['publication_directory']).absolute()/'CURRENT.json')))
    return value, source_config


def _stop(directory, control_id):
    try:
        value = _json(_read(directory / 'stop.json', 4096))
    except FileNotFoundError:
        return None
    _fields(value, 'schema control_id deadline')
    _need(value['schema'] == 'guanheng.source-market-stop.v1' and value['control_id'] == control_id)
    deadline = value['deadline']
    _need(type(deadline) in (int, float) and math.isfinite(deadline))
    return float(deadline)


def serve(configuration, expected_sha256, directory, control_id):
    """当前线程独占服务/Reader；父Job拥有原生阻塞与进程树的硬截止。"""
    _need(str(UUID(control_id)) == control_id and directory.name == control_id)
    _sha(expected_sha256)
    native = server = daily_owner = None
    created = server_closed = native_closed = False
    stop_deadline = None
    error = None
    stage = 'configuration'

    def publish(name, value):
        raw = json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False).encode('ascii')
        _need(0 < len(raw) <= 65536)
        # 一次性身份收据先完整写入并关闭，再发布最终名称；父不会读到半份正文。
        temporary = directory / (name + '-' + str(uuid4()) + '.tmp')
        write_private_new(temporary, raw)
        os.rename(temporary, directory / name)

    try:
        value, source = _configuration(configuration, expected_sha256)
        # 凭据由原HTTP server合同校验，不写到控制收据或日志。
        token = os.environ[value['token_env']]
        stage = 'control_directory'
        create_private_directory(directory)
        created = True
        stage = 'native_start'
        if source.get('mode') == 'source-preparing':
            from integrations.guanheng.source_history_preparation import SourcePreparingMarket
            native = SourcePreparingMarket(source)
        else:
            native = create_native_source_market(source)
        if 'daily_update'in value:
            from integrations.guanheng.market_daily_owner import MarketDailyOwner
            stage='daily_update_start'
            daily_owner=MarketDailyOwner(value['daily_update'],directory)
            daily_owner.start(time.monotonic()+30.,stop_request=lambda:_stop(directory,control_id))
        stage = 'http_start'
        server = MarketHTTPServer((value['listen']['host'], value['listen']['port']), native,
                                  token, socket_timeout=value['socket_timeout'])
        server.timeout = .1
        stage = 'ready_publish'
        publish('ready.json', dict(schema='guanheng.source-market-ready.v1', control_id=control_id,
                pid=os.getpid(), configuration_sha256=expected_sha256,
                listen_host=value['listen']['host'], listen_port=server.server_port))
        stage = 'serving'
        while True:
            stop_deadline = _stop(directory, control_id)
            if stop_deadline is not None:
                _need(time.monotonic() < stop_deadline)
                break
            if daily_owner is not None:daily_owner.check()
            # 原server/Reader始终在创建线程处理；这里不引入第二套读取池。
            server.handle_request()
    except BaseException as exc:
        error = {'stage': stage, 'exception_kind': type(exc).__name__}
    finally:
        if stop_deadline is None and created:
            try:stop_deadline=_stop(directory,control_id)
            except Exception:pass
        closing_deadline=stop_deadline if stop_deadline is not None else time.monotonic()+30.
        if daily_owner is not None:
            try:daily_owner.request_close(closing_deadline)
            except BaseException as exc:
                error=error or {'stage':'daily_update_stop','exception_kind':type(exc).__name__}
        try:
            if server is not None:
                server.server_close()
                server_closed = True
                native_closed = True  # 原MarketHTTPServer拥有并同步关闭native。
            elif native is not None:
                native.close()
                native_closed = True
            if stop_deadline is not None and time.monotonic() >= stop_deadline:
                raise TimeoutError('source market close deadline')
        except BaseException as exc:
            if error is None:
                error = {'stage': 'close', 'exception_kind': type(exc).__name__}
        if daily_owner is not None:
            try:daily_owner.close(closing_deadline)
            except BaseException as exc:
                error=error or {'stage':'daily_update_close','exception_kind':type(exc).__name__}
        if created:
            try:
                if error is None and server_closed and native_closed:
                    publish('closed.json', dict(schema='guanheng.source-market-closed.v1',
                        control_id=control_id, pid=os.getpid(), configuration_sha256=expected_sha256,
                        status='stopped', server_closed=True, native_closed=True, error_code=None))
                elif error is not None:
                    publish('failure.json', dict(schema='guanheng.source-market-failure.v1',
                        control_id=control_id, pid=os.getpid(), configuration_sha256=expected_sha256,
                        server_closed=server_closed, native_closed=native_closed, **error))
            except BaseException:
                error = error or {'stage': 'receipt_publish', 'exception_kind': 'unavailable'}
    return 0 if error is None else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--control-directory', required=True)
    parser.add_argument('--control-id', required=True)
    args = parser.parse_args()
    return serve(_path(args.config), args.config_sha256, _path(args.control_directory), args.control_id)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(2)
