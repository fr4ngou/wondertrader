"""正式采集的只读覆盖验收；只消费原owner投影，完整性与身份分别报告。"""
from collections import Counter
from pathlib import Path
import time
from uuid import UUID

from guanheng_qmt_shm_agent.protocol import decode
from .collection_deployment import load
from .market_generation import read_fixed
from .source_history_transport import require


def accept_coverage(selected, directory):
    """核实际采集代及全集合计数；无网络/SDK/写入，不触发订阅、导入或服务启停。

    directory必须是本候选collection_process.control_root下的真实控制UUID。
    passed表示当前进程、配置和投影身份可核且来源已连接；行情缺失及扫描进度另列，
    不以少量样本、注册数或最近一次报价推断全市场/全日完整。
    """
    from guanheng_wt_runtime.service_control import _process_identity
    from guanheng_wt_runtime.collection_observation import read_observation
    plan = load(selected)
    process = load(plan['files']['collection_process'])
    directory = Path(directory)
    require(directory.is_absolute() and str(UUID(directory.name)) == directory.name
            and directory.parent.resolve() == Path(process['control_root']).resolve())
    ready_path = directory / 'ready.json'
    ready = decode(read_fixed(ready_path, maximum=65536))
    require(ready['schema'] == 'qmt.quote-collector-ready.v1'
            and ready['control_id'] == directory.name
            and ready['configuration_sha256'] == plan['files']['worker']['sha256'])
    pid = ready['pid']
    creation = _process_identity(pid)
    # 原Windows创建身份必须早于本代ready写入，排除旧收据指向后来复用PID的进程。
    require(creation is not None and creation <= ready_path.stat().st_mtime_ns // 100 + 116444736000000000)
    identity = (directory.name, pid, ready['configuration_sha256'])
    observation = read_observation(directory, identity, time.monotonic() + 5,
        clock=time.monotonic, wall_clock=time.time)
    value = decode(read_fixed(directory / 'coverage.json', maximum=8388608))
    require(value['schema'] == 'qmt.quote-collector-coverage.v1'
            and (value['control_id'], value['pid'], value['configuration_sha256']) == identity)
    coverage = value['coverage']; rows = coverage['symbols']
    require(len({row['symbol'] for row in rows}) == len(rows))
    subscribed = sum(row['subscribed'] for row in rows)
    require(subscribed == plan['quote_count'] == coverage['subscribed_count'])
    maintenance = decode(read_fixed(directory / 'minute-maintenance.json', maximum=16777216))
    require(maintenance['schema'] == 'qmt.collection-minute-maintenance.v1'
            and maintenance['producer_sha256'] == plan['files']['producer']['sha256'])
    require(_process_identity(pid) == creation)
    states = dict(Counter(row['quote_state'] for row in rows))
    minute_states = dict(Counter(row['state'] for row in maintenance['rows']))
    current_rows = [row for row in maintenance['rows'] if row['date'] == coverage['trading_date']]
    known_rows = [row for row in current_rows if type(row.get('missing_count')) is int and row['missing_count'] >= 0]
    require(maintenance['scan_symbols'] == subscribed and len(current_rows) <= subscribed)
    known_missing = sum(row['missing_count'] for row in known_rows)
    unavailable = sum(row['state'] == 'reader_unavailable' for row in current_rows)
    connected = observation.get('connected')
    # 是否通过原观察合同沿其实际字段，不复制来源或状态的新解释。
    return dict(
        schema='qmt.minute-coverage-acceptance.v1',  # 整集合只读验收记录，区别于12样本价格读取。
        passed=(observation.get('available') is True and observation.get('status') == 'current'
            and connected is True and observation.get('phase') == 'running'
            and observation.get('error') is None and observation.get('failure') is None
            and unavailable == 0),  # 原状态合同及明确读取失败；扫描进度/缺行情另列。
        control_id=directory.name, pid=pid, process_identity_verified=True,  # 原控制代及Windows真实创建身份。
        observation=observation,  # 原受管观察DTO，保留原连接/新鲜度等业务分类。
        published_at=coverage['observed_at'], trading_date=coverage['trading_date'],  # 投影制作epoch秒/北京时间日期。
        subscribed_count=subscribed, known_and_retained_count=len(rows),  # 配对集合与资料/保留项联合分母。
        quote_states=states, groups=coverage['groups'],  # 逐类实际源时点/未收到/未订阅计数。
        missing_subscriptions=len(coverage['missing_subscriptions']),  # 包含当前协议不支持的已知BSE，保持实际缺项。
        scan_cycles=maintenance['scan_cycles'], scan_cursor=maintenance['scan_cursor'],
        scan_symbols=maintenance['scan_symbols'], scan_completed=maintenance['scan_cycles'] > 0,  # 尚未扫完不能授全量分钟结果。
        minute_states=minute_states, current_day_reported_count=len(current_rows),  # 已产生当日观察行，包含读取失败。
        current_day_checked_count=len(known_rows),  # 原Reader成功返回可核缺口的证券数；失败不计入。
        current_day_unreported_count=subscribed-len(current_rows),  # 本轮尚无当日观察行的证券数。
        current_day_unknown_count=subscribed-len(known_rows),  # 未扫描及读取失败的合计，完整性仍未知。
        current_day_reader_unavailable_count=unavailable,  # 已确认查询失败的当日证券数。
        current_day_known_missing_labels=known_missing,  # 仅成功核查项的已知缺口小计，不推算未知项。
        current_day_missing_labels=known_missing if len(known_rows) == subscribed else None,  # 全集合均核实才提供总数。
        market_complete_coverage=False)  # BSE/未知分母、未扫项及真实缺口继续单列，不据声明自动授予。
