"""组合正文的原只读设置快照；核验/文件读取仅在外部生成阶段执行。"""
from pathlib import Path

import guanheng_qmt_shm_agent
from guanheng_qmt_shm_agent.protocol import canonical, decode
from guanheng_qmt_shm_agent.read_capabilities import ACCOUNT
from guanheng_qmt_shm_agent.read_configuration import validate_read_configuration
from .lifecycle import validate_connection_lifecycle


def admit_account_read(value):
    """原v3读取准入保持；返回脱离调用者别名的设置、原profile及间隔。"""
    if type(value) is not dict or set(value) != {'agent', 'reconnect_seconds'}:
        raise ValueError('explicit account read composition fields differ')
    admitted = validate_read_configuration(value['agent'])
    if (admitted.value.get('read_profile_version') != 'qmt.read-profile.v3'
            or ACCOUNT not in admitted.profile['read_operations']
            or admitted.value['transport']['kind'] != 'builtin-shm'):
        raise ValueError('account composition requires its original builtin v3 read profile')
    interval = validate_connection_lifecycle(dict(schema_version='qmt.read-resident.v1',
        mode='resident-read', reconnect_seconds=value['reconnect_seconds']))['reconnect_seconds']
    return dict(agent=dict(admitted.value, secret=admitted.secret), reconnect_seconds=interval), admitted.profile


def _read_material(value, admit, *, decode_secrets=False):
    """原IPC秘密在私有JSON用hex保存；QMT快照恢复原bytes，不带HTTP身份。"""
    if type(value) is not dict or set(value) != {'agent', 'reconnect_seconds'} or type(value['agent']) is not dict:
        raise ValueError('account read material fields differ')
    agent = dict(value['agent'])
    incoming, outgoing = ('secret_hex', 'secret') if decode_secrets else ('secret', 'secret_hex')
    if incoming not in agent or outgoing in agent:
        raise ValueError('account read secret role differs')
    secret = agent.pop(incoming)
    if decode_secrets:
        if (type(secret) is not str or not 64 <= len(secret) <= 8192 or len(secret) % 2
                or any(char not in '0123456789abcdef' for char in secret)):
            raise ValueError('account read secret encoding differs')
        secret = bytes.fromhex(secret)
    if type(secret) is not bytes or not 32 <= len(secret) <= 4096:
        raise ValueError('account read requires its original IPC secret')
    agent = decode(canonical(agent))
    normalized, unused_profile = admit(dict(agent=dict(agent, secret=secret),
        reconnect_seconds=value['reconnect_seconds']))
    if decode_secrets:
        return normalized
    exported = dict(normalized['agent']);exported.pop('secret');exported['secret_hex'] = secret.hex()
    return dict(agent=exported, reconnect_seconds=normalized['reconnect_seconds'])


def _load_read_pair(directory, admit, *, installed_agent=None):
    """原pair验证器拥有身份准入；此处只导出同次已核内存设置，不构造服务。"""
    from .pair import _verify_pair_material
    from .bootstrap import agent_settings
    agent = Path(guanheng_qmt_shm_agent.__file__).resolve().parent
    if installed_agent is not None and Path(installed_agent) != agent:
        raise ValueError('account read pair installed agent differs')
    unused_public, private, unused_identity = _verify_pair_material(directory, installed_agent=agent)
    if private is None:
        raise ValueError('account composition requires original resident read pair')
    config, credentials, policies, unused_limits, lifecycle = private
    settings = agent_settings(config, policies, credentials['ipc_secret'])
    value, unused_profile = admit(dict(agent=settings,
        reconnect_seconds=lifecycle['reconnect_seconds']))
    return value


def account_read_material(value, *, decode_secrets=False):
    """原账户快照继续通过同一只读材料编解码边界。"""
    return _read_material(value, admit_account_read, decode_secrets=decode_secrets)


def load_account_read_pair(directory, *, installed_agent=None):
    """核原配对身份后只导出原账户设置；不创建运行资源。"""
    return _load_read_pair(directory, admit_account_read, installed_agent=installed_agent)
