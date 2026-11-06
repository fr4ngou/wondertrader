"""已停止交易owner的绑定维护；原租约/构造校验/连接/关闭由Journal拥有。"""
from .trade_event_maintenance import _MaintenanceValidation
from .trading_journal import HostTradingJournal
from .read_retention_journal import RetainedTradingJournal,HttpRetainedTradingJournal
from .trade_binding_extension import VERSION,TABLES
from .journal import construct_journal


class _BindingMaintenance(_MaintenanceValidation):
    def _maintenance_schema_matches(self,tables):
        return tables==self.schema_tables-TABLES or tables==self.schema_tables


class BindingExtensionJournal(_BindingMaintenance,HostTradingJournal):
    """原普通交易Journal维护；不会启动Runtime/域/SDK。"""


class RetainedBindingExtensionJournal(_BindingMaintenance,RetainedTradingJournal):
    """原read_retention交易Journal维护；原tickets保持。"""


class HttpRetainedBindingExtensionJournal(_BindingMaintenance,HttpRetainedTradingJournal):
    """原独立HTTP读票据交易Journal维护；不把HTTP能力塞入Agent profile。"""


def open_binding_extension_owner(path,route,*,deadline,failed_owners=None,retention_clock=None,http_retention=None,**original_configuration):
    """调用方先沿原受控材料验证完整配置；此处只开原同一路径维护租约。

    原配置来自已核完整配对材料，不接受从数据库猜账户/权限。构造期所有原件
    继续由原Journal和profile验证，queued/dispatching恢复或schema补写使维护
    在提交前拒绝。failed_owners沿原construct_journal单槽保留未确认关闭责任。
    """
    cls,extra=BindingExtensionJournal,{}
    if http_retention is not None:
        if retention_clock is None:raise ValueError('original HTTP retention clock required')
        cls=HttpRetainedBindingExtensionJournal;extra=dict(retention_clock=retention_clock,http_retention=http_retention)
    elif 'read_retention'in original_configuration.get('read_profile',{}):
        if retention_clock is None:raise ValueError('original retention clock required')
        cls=RetainedBindingExtensionJournal;extra=dict(retention_clock=retention_clock)
    return construct_journal(cls,path,route,failed_owners=failed_owners,maintenance_deadline=deadline,
        trade_binding_extension=VERSION,binding_extension_maintenance=True,**original_configuration,**extra)
