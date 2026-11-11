"""WT原生目标设置历史的只读投影；数量为份，时间来自行情时钟。"""
from typing import Literal, NotRequired, TypedDict


class TargetHistoryItem(TypedDict):
    id: str  # 来源文件身份、原行序与原行摘要组成的稳定事件身份。
    sequence: int  # 原生CSV完整数据行的序号，从1起，不由页面排序重编。
    changed_at: str  # WT行情actiondate/HHMM/SSmmm，上海时区ISO时间。
    symbol: str  # 原生ETF代码转换的六位证券代码及SH/SZ。
    previous_target_quantity: int | None  # 同证券前次原生目标份数；首次记录保持未知。
    target_quantity: int  # 本次提交给WT的目标份数；不表示已成交或实际持仓。
    change_quantity: int | None  # 两次目标份数之差；缺少前次值时保持未知。
    kind: Literal['initial', 'changed']  # 区分首条可见记录与有前值证明的目标改动。
    reference_price_cny: str  # 原生信号参考价，元/份；区别实际成交价。
    target_weight: None  # 原生CSV没有目标权重，历史保持未知。
    strategy_version: None  # CSV没有历史算法版本，不能倒推为当前版本。
    reason: None  # 原生统一usertag不能证明逐笔业务原因，保持未知。


class TargetHistorySource(TypedDict):
    kind: Literal['wt-native-signals']  # 复用WT逐笔目标设置CSV，保持唯一原始事实所有者。
    source_id: str  # 逻辑实例、策略与原文件物理身份摘要，不公开本地路径。
    snapshot_sha256: str  # 本次固定字节前缀的完整SHA；分页固定相同前缀。
    raw_count: int  # 此前缀内的完整原生设置行数，包含重复提交。
    changed_count: int  # 同证券相邻目标不同的次数，A→B→A保留两次。
    initial_count: int  # 各证券首条原生记录数，前目标未知。
    unchanged_count: int  # 相邻同目标的重复设置次数，不伪造为仓位改动。
    incomplete_tail: bool  # 捕获时末行尚未完整；该行留待下一次刷新。
    first_at: str | None  # 原始记录首个行情时刻，无完整行时为空。
    last_at: str | None  # 原始记录最后行情时刻，无完整行时为空。
    latest_targets: NotRequired[list[TargetHistoryItem]]  # 当前发布标的在固定前缀中的最近变动或首次记录，缺记录时无对应行。


class TargetHistoryResponse(TypedDict):
    schema_version: Literal['guanheng.strategy-target-history.v1']  # 本只读接口协议。
    read_only: Literal[True]  # 不评估策略、不设目标、不查询券商或修改原CSV。
    observed_at: str  # App读取时刻UTC，区别原目标的行情时刻。
    state: Literal['available', 'waiting', 'not_current']  # 明确无来源与非当前选择。
    reason: str  # 来源、空状态或缺失的业务说明。
    requested: dict[str, str]  # 本次选择的策略ID与版本，须同时匹配当前发布。
    source: TargetHistorySource | None  # 已验证的原日志覆盖；未读取时为空。
    items: list[TargetHistoryItem]  # 原日志顺序倒序的变动/首次记录。
    next_cursor: str | None  # 固定源文件/前缀SHA及下一页行边界；无更早记录时为空。
