"""显式本地数据根；构造不创建文件、不联网、不启动线程。"""

from .contracts import ObservationError
from .query import ObservationReader, prepare_parquet_runtime
from .storage import ContentStore, SnapshotRepository


def build_reader(root):
    if not root:
        raise ObservationError('not_configured', '尚未配置独立市场观察数据', 503)
    return ObservationReader(SnapshotRepository(root), ContentStore(root))


def build_prepared_reader(root):
    """App在本模块就绪前初始化codec；失败保持观察域错误供其余工作区独立服务。"""
    if not root:
        return build_reader(root)
    try:
        prepare_parquet_runtime()
        return build_reader(root)
    except ObservationError:
        raise
    except Exception as error:
        raise ObservationError('observation_runtime_unavailable',
            '市场观察读取依赖加载失败，请检查本次安装的运行库；账户、策略和报告可继续读取', 503) from error


def market_client_factory():
    """读取显式连接配置；只在来源请求时创建原SDK，不保存凭据到快照。"""
    from ..settings import ConsoleSettings
    settings=ConsoleSettings.from_environment()
    def create(seconds):
        from guanheng_market_client import MarketClient
        if not settings.wondertrader_market_url or not settings.wondertrader_market_token.get_secret_value():
            raise ObservationError('market_source_not_configured','尚未配置统一行情连接',503)
        kwargs=dict(timeout=min(seconds,settings.wondertrader_market_timeout_seconds))
        if settings.wondertrader_market_connect_ip:kwargs['connect_ip']=settings.wondertrader_market_connect_ip
        return MarketClient(settings.wondertrader_market_url,settings.wondertrader_market_token.get_secret_value(),**kwargs)
    return create
