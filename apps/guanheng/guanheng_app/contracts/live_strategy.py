"""LSP只读展示合同；金额为原人民币十进制文本，份额为整数，时间保留来源。"""
from typing import Literal, NotRequired, TypedDict


class LiveSelection(TypedDict):
    strategy_id: str  # 请求选择的策略ID；与WT实际发布严格比较。
    strategy_version: str  # 请求选择的版本；不接受只按ID匹配。


class LiveCurrent(LiveSelection):
    key_matches: bool  # 两个身份字段同时与本轮WT发布一致。
    runtime_state: str | None  # 原Runtime状态；非匹配选择保持None。
    is_current: bool  # 同key、组件ready且原生命周期/OS进程核实才为True。
    scope_id: str | None  # 完整WT/执行/策略/本金基准的摘要；缓存和观察历史共同隔离。
    process_state: Literal['alive','exited','unknown']  # 只读OS核查；未知不授当前标记。


class LivePosition(TypedDict):
    symbol: str  # 原WT策略证券身份，六位代码及SH/SZ交易所。
    quantity: int  # 券商已发布实际数量，单位份；零与未知分开。
    sellable: int  # 同次券商发布可卖数量，单位份。
    observed_at: str  # 原券商持仓接收时刻，UTC ISO带时区。


class LiveMarker(TypedDict):
    id: str  # 来源scope及原成交身份的摘要，不公开原账户/订单号。
    date: str  # 原成交日，ISO日期；不由页面刷新日期生成。
    time: str  # 原成交上海本地时间，HH:MM:SS。
    symbol: str  # 原账户成交证券，经所选策略证券范围筛选。
    side: Literal['BUY','SELL','UNKNOWN']  # 原48/49方向的投影，其它值保持未知。
    price_cny: str  # 实际成交单价，元/份；无行情重估。
    quantity: int  # 实际成交数量，份。
    attribution: Literal['account-universe-only']  # 证券重合，缺少策略归属证据。


class LiveDeal(LiveMarker):
    amount_cny: str  # 原账户成交金额，人民币元，不重算费用或成交额。
    observed_at: str | None  # 原完整deal分组查询完成/接收时间，缺少时保持None。
    source_time: str  # QMT原成交时间文本；time仅对5位HHMMSS明确补小时十位0。
    runtime_scope_id: str | None  # 此实际成交观察对应的完整WT运行摘要，正常跨代归并仍保留。


class LiveDay(TypedDict):
    date: str  # 该日实际存在某一数据组的来源事实，上海日期；缺日不补行。
    observed_at: str | None  # NAV原估值时间；仅持仓/成交日保持None。
    nav_cny: str | None  # 原策略capital发布的NAV，元；不等同账户全额资产。
    cash_cny: str | None  # 同一次capital发布的现金，元。
    market_value_cny: str | None  # 同一次capital发布的市值，元。
    pnl_cny: str | None  # 原capital发布的本次基准变化，元；口径见summary.pnl_source。
    return_pct: None  # 资金流和策略归因未齐，投资收益率保持未知，不用零占位。
    runtime_scope_id: str | None  # 此NAV点的完整原运行scope，持仓/成交日无NAV时None。
    positions: list[LivePosition]  # 此日最近一次真实券商持仓副本；不向后填充。
    deals: list[LiveDeal]  # 实际观察到的账户成交；同ID去重，保留未知归属。
    positions_state: Literal['available','empty','unavailable']  # 完整空持仓与来源缺失分别表达。
    deals_state: Literal['available','empty','partial','unavailable']  # 部分字段无效或缺来源分别表达。
    positions_observed_at: NotRequired[str]  # 本日持仓最后原接收时间，与NAV估值时钟独立。
    positions_runtime_scope_id: NotRequired[str]  # 本日实际持仓副本的完整原运行摘要。
    price_observed_at: NotRequired[str | None]  # 此NAV点的原报价时间，与现金/持仓时钟分别解释。
    pnl_source: NotRequired[str]  # 此NAV点原损益口径，历史摘要复用同点事实。


class LiveBaseline(TypedDict):
    total_cny: str  # 原WT明确当前总本金，元；不当作旧历史本金。
    baseline_at: str  # 原基准初始化时刻，不由App生成。
    scope_id: str  # 原基准完整正文摘要，基准变化切分观察历史。


class LiveSummary(TypedDict):
    nav_cny: str  # 最近一次实际capital发布的NAV，人民币元。
    pnl_cny: str  # 同轮原发布的基准变化，人民币元。
    return_pct: None  # 连续投资收益资格缺失；明确保持None。
    observed_at: str  # 最近一次NAV原估值时刻，UTC ISO带时区。
    price_observed_at: str | None  # 原报价来源时间；旧发布缺少时None。
    pnl_source: str  # 原发布的broker-cash-delta或native-theoretical来源。
    return_reason: str  # 稳定中文收益率缺失说明，无私有异常。


CoverageRange = TypedDict('CoverageRange', {'from': str | None, 'to': str | None})
# from/to分别是当前窗口实际NAV首末来源日期，缺少时均None；不使用抓取时间。


class LiveCoverage(CoverageRange):
    point_count: int  # 本次有界窗口实际NAV点数，区别仅持仓/成交日期行数。
    basis: Literal['actual-published-observations']  # 真实发布观察口径，不含回测或补造历史。
    history_state: str  # 本地观察历史、单次快照或不可用；不表示连续交易日覆盖。
    history_scope_id: str | None  # 稳定现金原点证明的经济历史key；区别current完整运行scope。
    continuity: str  # stable-cash-anchor允许正常跨代；runtime-only-unproven-lineage保持保守分段。
    reason: str  # 覆盖起点和缺日/收益归因的中文说明。
    deals_truncated: bool  # 展示成交超过单次2000条时True，完整原观察继续保留。


class LiveResponse(TypedDict):
    schema_version: Literal['guanheng.live-strategy-performance.v1']  # 本接口冻结版本。
    read_only: Literal[True]  # 无交易操作；App只保存本地观察副本。
    observed_at: str  # 本次App读取响应时刻，与各组原时间分别表达。
    state: Literal['available','waiting','not_current']  # 匹配可读、等待及非当前选择。
    reason: str  # 数据来源与归属限制的中文说明。
    requested: LiveSelection  # 当前查询选择，前端保留同查询缓存。
    current: LiveCurrent  # 真实发布/进程事实，不按App安装或回测报告推断。
    coverage: LiveCoverage  # 来源日期及覆盖资格；首末日期不取App读取时刻。
    baseline: LiveBaseline | None  # 原WT当前本金，缺少时None。
    summary: LiveSummary | None  # 当前实际资本观察；缺少时None。
    daily: list[LiveDay]  # 最多366个来源日期，按日递增，不补缺日。
    markers: list[LiveMarker]  # 同窗口实际账户成交标记，策略归属未确认。
