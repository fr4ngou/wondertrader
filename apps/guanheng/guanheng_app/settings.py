"""独立应用配置；只读取显式环境，不探测旧目录或加载.env。"""

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

_RETIRED_ENV = ('GUANHENG_ACCOUNT_SCAN_EXECUTABLE','GUANHENG_ACCOUNT_SCAN_CONFIG',
    'GUANHENG_BACKTEST_CONFIG','GUANHENG_BACKTEST_CONFIG_SHA256',
    'GUANHENG_QMT_HOST_CONFIG','GUANHENG_QMT_HOST_CONFIG_SHA256',
    'GUANHENG_QMT_HISTORY_PREPARATION_CONFIG','GUANHENG_QMT_HISTORY_PREPARATION_CONFIG_SHA256',
    'GUANHENG_QMT_COLLECTION_CONFIG','GUANHENG_QMT_COLLECTION_CONFIG_SHA256',
    'GUANHENG_SOURCE_MARKET_CONFIG','GUANHENG_SOURCE_MARKET_CONFIG_SHA256',
    'GUANHENG_EXECUTION_CONFIG','GUANHENG_EXECUTION_CONFIG_SHA256',
    'GUANHENG_STRATEGY_CONFIGURATION_ROOT','GUANHENG_OBSERVATION_COLLECTION_CONFIG',
    'GUANHENG_OBSERVATION_COLLECTION_CONFIG_SHA256')


class StrategyRegistration(BaseModel):
    """由部署明确登记的策略身份，只供观衡目录展示。"""

    model_config = ConfigDict(extra='forbid', frozen=True)
    strategy_id: str = Field(pattern=r'^[A-Za-z0-9_.+-]{1,64}$')  # WT部署声明的策略ID。
    strategy_version: str = Field(pattern=r'^[A-Za-z0-9_.+-]{1,64}$')  # 同一策略声明的非空版本。
    display_name: str = Field(min_length=1, max_length=80, pattern=r'^[^\x00-\x1f\x7f]+$')  # 用户可见的策略名。


class ConsoleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    wondertrader_market_url: str = ""
    wondertrader_market_token: SecretStr = SecretStr("")
    wondertrader_market_connect_ip: str = ""
    # 来源历史首次读取会解码整只证券；部署预算沿SDK最大30秒，默认2秒保持。
    wondertrader_market_timeout_seconds: float = Field(default=2.0, gt=0, le=30.0)
    # 显式选择来源标签读取；默认标准化服务的单位和时间合同保持。
    wondertrader_history_semantics: Literal["canonical", "source"] = "canonical"
    # 当前实例公开指针绝对路径；非空时每轮读取，优先于固定四项身份，缺失时等待恢复。
    wt_current_file: str = ""
    # 只读策略登记。默认空列表；配置在Web启动时读取，运行事实另由WT发布。
    strategy_registrations: tuple[StrategyRegistration, ...] = Field(default=(), max_length=32)
    # WT公开状态绝对路径；当前指针为空时使用固定四项，不加载运行配置或凭据。
    wt_status_file: str = ""
    # 固定模式控制UUID，属于本次启动代。
    wt_control_id: str = ""
    # 固定模式逻辑实例UUID，与控制UUID分别校验。
    wt_instance_id: str = ""
    # 固定模式配置原字节SHA256，64位小写十六进制。
    wt_configuration_sha256: str = ""
    account_source: Literal['wt_strategy','wt_account_publication'] = 'wt_strategy'
    # 仅读已发布归档，不加载回测运行绑定或会话执行配置。
    backtest_archive_root: str = ""
    # 个人观察偏好根，安装目录之外显式准备；空值关闭，不影响行情或交易配置。
    watchlist_root: str = ""
    observation_root: str = ""
    # 证券目录是部署时发布的只读制品；名称、拼音和规范证券身份在同一制品中闭合。
    security_catalog_file: str = ""

    @classmethod
    def from_environment(cls):
        # 旧环境可能继承WT部署参数；观衡不消费这些值，读取功能继续独立工作。
        return cls(
            wondertrader_market_url=os.environ.get("GUANHENG_MARKET_URL", ""),
            wondertrader_market_token=os.environ.get("GUANHENG_MARKET_TOKEN", ""),
            wondertrader_market_connect_ip=os.environ.get("GUANHENG_MARKET_CONNECT_IP", ""),
            wondertrader_market_timeout_seconds=os.environ.get("GUANHENG_MARKET_TIMEOUT_SECONDS", "2"),
            wondertrader_history_semantics=os.environ.get("GUANHENG_HISTORY_SEMANTICS", "canonical"),
            wt_current_file=os.environ.get("GUANHENG_WT_CURRENT_FILE", ""),
            strategy_registrations=json.loads(os.environ.get("GUANHENG_STRATEGY_REGISTRATIONS", "[]")),
            wt_status_file=os.environ.get("GUANHENG_WT_STATUS_FILE", ""),
            wt_control_id=os.environ.get("GUANHENG_WT_CONTROL_ID", ""),
            wt_instance_id=os.environ.get("GUANHENG_WT_INSTANCE_ID", ""),
            wt_configuration_sha256=os.environ.get("GUANHENG_WT_CONFIGURATION_SHA256", ""),
            account_source=os.environ.get('GUANHENG_ACCOUNT_SOURCE','wt_strategy'),
            backtest_archive_root=os.environ.get("GUANHENG_BACKTEST_ARCHIVE_ROOT", ""),
            watchlist_root=os.environ.get("GUANHENG_WATCHLIST_ROOT", ""),
            observation_root=os.environ.get("GUANHENG_OBSERVATION_ROOT", ""),
            security_catalog_file=os.environ.get("GUANHENG_SECURITY_CATALOG_FILE", ""),
        )
