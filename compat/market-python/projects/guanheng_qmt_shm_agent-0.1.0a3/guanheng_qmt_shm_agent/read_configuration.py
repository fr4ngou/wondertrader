# -*- coding: utf-8 -*-
"""Host、配对工具和Agent共用的纯配置准入；不构造SDK或通信owner。"""
from .protocol import TransportBudget, canonical, decode, identity
from .control_profile import ControlProfile
from .transport_profile import validate_transport_profile
from .read_capabilities import build_read_profile, explicit_profile_version


_REQUIRED = frozenset(('route', 'secret', 'allowed_operations', 'execution_timeout_ms',
    'max_frame', 'max_pending', 'max_result_bytes', 'connect_seconds',
    'io_seconds', 'transport', 'control_profile'))
_READ_EXTRA = frozenset(('read_profile_version', 'operation_profiles'))


class ReadConfiguration(object):
    def __init__(self, value, route, budget, control_profile, profile, secret):
        # 私有准入快照保留同次核验的不可变密钥，不再读取调用者dict。
        self.secret = secret
        self.value, self.route = value, route
        self.budget, self.control_profile = budget, control_profile
        self._profile_bytes = canonical(profile)

    @property
    def profile(self):
        return decode(self._profile_bytes)


def _admit_configuration(value, build_profile, require_profile=None):
    """两个显式入口共用原预算/布局算法；附加关系先于运输布局校验。

    build_profile 必须使用实际版本的唯一字段准入。require_profile 仅做
    该版本的跨字段关系，不创建 SDK、Journal、运输 owner 或线程。
    """
    route = identity(value['route'])
    timeout = value['execution_timeout_ms']
    if type(timeout) is not int or not 100 <= timeout <= 30000:
        raise ValueError('invalid native timeout policy')
    budget = TransportBudget(value['connect_seconds'], value['io_seconds'])
    max_frame, max_pending, max_result = value['max_frame'], value['max_pending'], value['max_result_bytes']
    if type(max_frame) is not int or not 8192 <= max_frame <= 4194304:
        raise ValueError('invalid frame budget')
    if type(max_pending) is not int or not 1 <= max_pending <= 1024:
        raise ValueError('invalid pending task budget')
    if type(max_result) is not int or not 1024 <= max_result <= max_frame - 4096:
        raise ValueError('invalid result budget')
    control = ControlProfile(value['control_profile'], max_frame, budget)
    control.require_native_budgets(max_result)
    profile = build_profile(value, control.configuration)
    if require_profile is not None:
        require_profile(profile, control)
    # 按显式运输版本复用纯布局校验；此处不分配内核对象、不调用LocalTransport。
    validate_transport_profile(value['transport'], route, max_frame, profile)
    return route, budget, control, profile


def _build_read_profile(value, control):
    return build_read_profile(value['allowed_operations'], value['execution_timeout_ms'], control,
        value.get('operation_profiles'), max_result_bytes=value['max_result_bytes'])


def validate_read_configuration(trusted_bootstrap, *, allow_preparation=False):
    """一次校验完整权限、control及运输额度；复制配置以隔离调用者别名。

    secret保存在准入快照，不进入公开value/profile。SDK callable由Agent
    独立核验，Host不能凭伪context将配置校验冒充SDK可用性。
    """
    if (type(trusted_bootstrap) is not dict
            or set(trusted_bootstrap) not in (_REQUIRED, _REQUIRED | _READ_EXTRA)):
        raise ValueError("read-only bootstrap has missing or unsupported fields")
    secret = trusted_bootstrap['secret']
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("missing trusted bootstrap secret")
    value = decode(canonical({key: item for key, item in trusted_bootstrap.items() if key != 'secret'}))
    version = explicit_profile_version(value['allowed_operations'])
    if version == 'qmt.read-profile.v6' and allow_preparation is not True:
        raise ValueError('history preparation requires its explicit constructor')
    public_fields = _REQUIRED - {'secret'}
    if (version is None and set(value) != public_fields
            or version is not None and (set(value) != public_fields | _READ_EXTRA
                or value.get('read_profile_version') != version)):
        raise ValueError('explicit read profile version required')
    route, budget, control, profile = _admit_configuration(value, _build_read_profile)
    return ReadConfiguration(value, route, budget, control, profile, secret)
