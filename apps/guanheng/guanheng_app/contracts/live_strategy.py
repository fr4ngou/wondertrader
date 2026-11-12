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
    sellable: int  # 同次原owner发布可卖数量，单位份。
    observed_at: str  # 原持仓owner观察时刻，UTC ISO带时区。


class LiveMarker(TypedDict):
    id: str  # 来源scope及原成交身份的摘要，不公开原账户/订单号。
    date: str  # 原成交日，ISO日期；不由页面刷新日期生成。
    time: str  # 原成交上海本地时间，HH:MM:SS。
    symbol: str  # 原ASA分配或旧账户范围成交证券，归属见attribution。
    side: Literal['BUY','SELL','UNKNOWN']  # 原48/49方向的投影，其它值保持未知。
    price_cny: str  # 实际成交单价，元/份；无行情重估。
    quantity: int  # 实际成交数量，份。
    attribution: Literal['account-universe-only','strategy-allocated']  # ASA已归属或旧账户范围未确认，明确区分两个来源。


class LiveDeal(LiveMarker):
    fee_cny: NotRequired[str | None]  # ASA原分配实际费用，元；未知None，旧账户范围未提供时可缺。
    amount_cny: str  # 原已归属分配或账户范围成交金额，人民币元，不重算费用或成交额。
    observed_at: str | None  # 原完整deal分组查询完成/接收时间，缺少时保持None。
    source_time: str  # QMT原成交时间文本；time仅对5位HHMMSS明确补小时十位0。
    runtime_scope_id: str | None  # 此实际成交观察对应的完整WT运行摘要，正常跨代归并仍保留。


class LiveDay(TypedDict):
    date: str  # 该日实际存在某一数据组的来源事实，上海日期；缺日不补行。
    observed_at: str | None  # NAV原估值时间；仅持仓/成交日保持None。
    nav_cny: str | None  # 原策略capital发布的NAV，元；不等同账户全额资产。
    reference_nav_cny: NotRequired[str | None]  # 未扣未知手续费的原owner参考净值，元。
    reference_cash_observed_at: NotRequired[str | None]  # 参考现金原owner clock，与后续实际现金分别保留。
    reference_cash_cny: NotRequired[str | None]  # ledger参考现金，不冒充确定现金。
    reference_observed_at: NotRequired[str | None]  # 参考估值原UTC时刻，与实际NAV分别保留。
    valuation_state: NotRequired[str]  # actual/reference-fee-pending，本日最后合格资格。
    valuation_source_sha256: NotRequired[str]  # 原profile估值输入/资格摘要。
    valuation_baseline_cny: NotRequired[str | None]  # 原配置资本，元；只作参考变化。
    reference_change_cny: NotRequired[str | None]  # 相对配置资本变化额，非投资损益。
    reference_return_pct: NotRequired[str | None]  # 相对配置资本变化率%，非资金流调整收益。
    valuation_runtime_scope_id: NotRequired[str]  # 此实际/参考估值的原运行来源。
    cash_cny: str | None  # 原capital或ASA自有现金，元；ASA费用未知时None。
    cash_observed_at: NotRequired[str]  # ASA现金原owner读取时刻，UTC ISO；不是NAV估值时刻。
    cash_runtime_scope_id: NotRequired[str]  # 此现金观察的原运行scope，独立于NAV来源。
    market_value_cny: str | None  # 同一次capital发布的市值，元。
    pnl_cny: str | None  # 原capital发布的本次基准变化，元；口径见summary.pnl_source。
    return_pct: None  # 资金流和策略归因未齐，投资收益率保持未知，不用零占位。
    runtime_scope_id: str | None  # 此NAV点的完整原运行scope，持仓/成交日无NAV时None。
    positions: list[LivePosition]  # 此日最近一次真实归属或旧账户范围持仓副本；不向后填充。
    deals: list[LiveDeal]  # 实际已归属或旧账户范围成交；同ID去重，归属分别保留。
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


class CapitalFlowItem(TypedDict):
    id: str  # 绑定策略经济身份的事件摘要，用于稳定展示。
    direction: Literal['inflow', 'outflow']  # 实际归入或离开策略的资金方向。
    amount_cny: str  # 实际资金金额，人民币正十进制字符串。
    effective_at: str  # 资金进入或离开策略的原时刻，带时区。


class CapitalReturn(TypedDict):
    baseline_at: str  # 本次策略收益的原起算时刻，带时区。
    valued_at: str  # 本次收益的实际估值时刻，带时区。
    valuation_nav_cny: str  # 本次收益所用期末净值，元，可早于当前净值。
    cash_observed_at: str  # 本次收益所用实际现金快照时刻。
    coverage_required_at: str  # 资金流水需覆盖到的时刻，取现金与持仓估值较晚者。
    inflow_through: str | None  # 已核追加资金事实截至时刻，未知为None。
    outflow_through: str | None  # 已核提取资金事实截至时刻，未知为None。
    flow_count: int  # 本次估值范围内有效资金事件总数。
    flows: list[CapitalFlowItem]  # 最近最多20条已登记资金事件，完整原始记录保留在受控环境。
    state: str  # 收益已计算或缺覆盖、估值、基准、记录原因。
    return_pct: str | None  # 投资收益率，单位%；数据缺口为None。
    reason: str  # 来源固定说明，无原凭据或私有异常。


class LiveSummary(TypedDict):
    reference_nav_cny: NotRequired[str | None]  # 未扣未知费用参考净值，实际资格时None。
    valuation_state: NotRequired[str | None]  # 原估值资格；旧NAP来源可缺。
    reference_change_cny: NotRequired[str | None]  # 配置资本参考变化额，元。
    reference_return_pct: NotRequired[str | None]  # 配置资本参考变化率%，非投资收益。
    baseline_cny: NotRequired[str | None]  # 本条原配置资本声明，元。

    nav_cny: str | None  # 参考资格时None；最近一次实际capital发布的NAV，人民币元。
    pnl_cny: str | None  # ASA未提供投资损益时None；同轮原发布的基准变化，人民币元。
    return_pct: str | None  # WT计算的资金流调整收益率，单位%；缺覆盖时为None。
    capital_return: NotRequired[CapitalReturn]  # 同次WT收益结果及有限公开流水，旧发布可缺。
    observed_at: str  # 最近一次NAV原估值时刻，UTC ISO带时区。
    price_observed_at: str | None  # 原报价来源时间；旧发布缺少时None。
    pnl_source: str  # 原发布的broker-cash-delta或native-theoretical来源。
    return_reason: str  # 稳定中文收益率缺失说明，无私有异常。


CoverageRange = TypedDict('CoverageRange', {'from': str | None, 'to': str | None})
# from/to分别是当前窗口实际NAV首末来源日期，缺少时均None；不使用抓取时间。


class LiveCoverage(CoverageRange):
    reference_point_count: NotRequired[int]  # 参考点数，不计入实际point_count。
    reference_from: NotRequired[str | None]  # 当前参考点首个原日期，空为None。
    reference_to: NotRequired[str | None]  # 当前参考点最后原日期，空为None。
    valuation_state: NotRequired[str | None]  # 本轮原profile估值资格，可与历史最近点不同。
    valuation_reason: NotRequired[str | None]  # 本轮缺价/未知费用的固定分类，原时间不更新。

    point_count: int  # 本次有界窗口实际NAV点数，区别仅持仓/成交日期行数。
    basis: Literal['actual-published-observations']  # 真实发布观察口径，不含回测或补造历史。
    history_state: str  # 本地观察历史、单次快照或不可用；不表示连续交易日覆盖。
    history_scope_id: str | None  # 稳定现金原点证明的经济历史key；区别current完整运行scope。
    continuity: str  # stable-cash-anchor允许正常跨代；runtime-only-unproven-lineage保持保守分段。
    reason: str  # 覆盖起点和缺日/收益归因的中文说明。
    attribution: NotRequired[Literal['strategy-allocated','account-universe-only']]  # 本策略真实归属或旧账户范围；旧响应可缺。
    deals_truncated: bool  # 展示成交超过单次2000条时True，完整原观察继续保留。


class LiveResponse(TypedDict):
    security_names: NotRequired[dict[str, str]]  # 本次持仓和成交涉及的已准入证券简称，缺项沿规范代码展示。
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
    markers: list[LiveMarker]  # 同窗口真实成交标记，ASA归属与旧账户未确认口径分别标识。
