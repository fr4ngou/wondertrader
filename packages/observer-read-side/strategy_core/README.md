# 观衡 configured Resonance 1.2.0 业务核

独立包 `guanheng-strategy-core==0.1.0a6`，Python 3.12+。业务实现来源固定旧QMT `6cf508a070392ff976b6b4d6b31b0e6219001e71`；来源摘要及逐文件适配见 `source-manifest.json`。公开规格为仓库 `docs/specs/native-strategy-kernel.md`。包安装后只依赖标准库，Windows增加锁定 `tzdata==2026.3`。构建后端为 `flit_core==3.12.0`。

## 单一计算入口

```python
from datetime import datetime
from guanheng_strategy_core import (
    ConfiguredStrategyConfig, FrozenHistory, evaluate_history,
)

config = ConfiguredStrategyConfig.from_dict(config_json)
history = FrozenHistory.from_dict(history_json)
result = evaluate_history(config, history, datetime.fromisoformat(knowledge_cutoff))
public_result = result.to_dict()
```

入口精确签名：`evaluate_history(config: ConfiguredStrategyConfig, frozen_history: FrozenHistory, knowledge_cutoff: datetime, *, budget: EvaluationBudget = EvaluationBudget()) -> EvaluationResult`。输入/输出使用frozen dataclass，集合为tuple。`from_dict`接收JSON值，拒绝未知字段；`to_dict`将日期编码为ISO，时间统一UTC带Z。异常为`KernelValidationError(code, message)`，message为中文；失败不返回可提交目标。样例 `examples/config.json`、`history.json`、`result.json` 全部标识合成输入，不属于真实来源或交易资格。

## 精确配置字段

| 字段 | 类型与含义 |
|---|---|
| config_revision | 1..128字符明确配置修订；内容本身另算config_sha256 |
| symbol_roles | tuple[(role, signal_symbol)]；from_dict也接受role字典 |
| execution_symbols | tuple[(role, execution_symbol)]；键为角色；from_dict也接受role字典 |
| benchmark_role | 已配置角色，其信号证券产生全部标的regime |
| valid_from / valid_until | 必填、带时区datetime；最新收盘及knowledge_cutoff须在半开有效期内 |
| minimum_history_days | 当前日之前所需完整交易日数，默认100，1..10000且覆盖三个窗口 |
| regime_ma_period / position_window / volume_window | 默认100/60/20，每项整数2..10000；EMA平滑20保持原规则 |
| budget_weight / symbol_cap_weight / max_weight_change | 默认.8/.25/.25，原范围(0,.95]/[.05,.25]/[.01,.25] |
| strategy_id / strategy_version | 固定resonance-regime-v1 / 1.2.0 |
| observation_version / warmup_policy | 固定resonance-daily-closed-v3 / regime-available-v1 |

支持角色为csi300/sh50/zz500/zz1000/kc50/kc_composite/sc50/dividend，可显式配置其子集。信号角色与执行角色集合一致、各自证券唯一；证券格式六位代码.SH或.SZ；字符串使用规范大写，直接DTO不做隐式证券转换。基准角色必须存在。策略模型支持角色与证券分离，未按证券名称猜算法。

max_weight_change保留原allocation intent的约束事实；纯分配核不会据此增加一层逐日限幅。风险审批与执行消费者另按本领域契约处理，该字段参与配置内容身份。mode、kill switch和paused属于宿主准入，账户、旧StrategyIntent、批准订单、原目标账本不进入本包。

## 冻结历史字段

`FrozenHistory(observations, source_revision, factor_revision)`；两个revision为小写64位SHA-256。observations是严格按`(trade_date, symbol)`排序的完整前缀，每日所有配置证券恰好一条；同标的错日、重复、不足均拒绝。包不自行推断交易日历缺口；完整已知交易日范围与停牌资格由原生输入owner提供，未核真实覆盖不能声称全市场完整。

每条 `DailyObservation`：

| 字段 | 类型、单位与缺失语义 |
|---|---|
| symbol / trade_date | 规范沪深信号代码 / date |
| open/high/low/close | 正有限价格，须满足OHLC关系；复权口径由factor_revision冻结 |
| volume / amount | 非负有限成交量/金额；源单位由来源manifest说明，核保持输入单位 |
| market_available_at | 必须显式带时区；须≤该交易日15:00 Asia/Shanghai收盘时刻 |
| market_source_sha256 | 必填小写64位原始日线来源摘要 |
| shares_delta_yi | 可选，ETF份额变化，亿份，允许负数 |
| share_probability / turnover_percentile / margin_percentile | 可选0..100有限值 |
| auxiliary_available_at | 存在任意辅助值时必填；须≤该行收盘，逐历史帧检验 |
| auxiliary_source_dates | tuple[date]，有辅助值时非空；来源统计日≤本行交易日，最多64项 |
| auxiliary_source_sha256 | 有辅助值时必填64位摘要；代表该行已冻结辅助事实内容来源 |
| evidence_refs | 必填tuple[str]，1..16项，每项1..256字符，指向本输入来源 |

没有辅助事实时用None与空tuple，保留原灰灯。auxiliary_source_sha256始终只允许None或规范64位摘要，任意辅助值存在时再要求非None；辅助全缺失也执行相同类型/长度检查。时间对象仅接受标准datetime.timezone/zoneinfo.ZoneInfo时区，拒绝携带可变自定义时区引用。csi300三辅助灯、sh50/kc50/kc_composite/zz500份额缺失写入auxiliary_gaps并qualified=False；sc50/zz1000/dividend自身不使用这些辅助字段。缺失不合成零值、不伪造满足入场资格。knowledge_cutoff必须带时区且不早于最新收盘；每行价格/辅助知晓时间仍受本行收盘限制，最终可知不能回填早年。市场闭合时间按固定交易所规则构造；机器当前时间不参与计算。

## 输出字段与状态

`EvaluationResult`包括kernel_version、strategy_id/version、config_sha256、input_sha256、source_revision、factor_revision、knowledge_cutoff、first_ready_date、last_closed_date；这些身份用于逐前缀对照和修订后重建，不代表旧全局哈希兼容。

- daily_frames：每个输入交易日一个DailyFrame(trade_date, decisions, auxiliary_qualified)，包括预热及无变化日。decisions为该日真实信号转移；action/strength/path/reason/confidence/evidence_refs沿原算法，SELL先。
- allocation_events：真实变化的分配快照，含trade_date/target_weights/decision_paths/evidence_refs。无变化不制造新allocation。
- current_targets：完整全部角色，CurrentTarget(role, signal_symbol, execution_symbol, target_weight, source_allocation_date)，含零；从未发生allocation时source_allocation_date=None；日期始终保留最后原allocation日期。
- latest_features：各标的最后DailyFeature，含原DailyObservation和change_pct/price_position/volume_ratio/trade_direction/regime_score/regime_label。
- signal_states：每角色SignalState(role, symbol, state_json)，state_json为不可变JSON字符串，包含对应level/position/hold_days/peak/cluster/distribution/top/watch等实际模型记忆。它是确定性重建后的模型状态，与柜台实际持仓分开。
- auxiliary_gaps：AuxiliaryGap(trade_date, symbol, missing_fields)；qualified与qualification_reasons表述辅助数据资格。qualified=True仅证明本包输入约束通过，不授真实来源、native运行或交易资格。

核从完整前缀重建EMA与所有记忆。基准首次MA可用后才启动信号机；完整EMA从首次ready连续递推。单元min(cap/2,budget/(标的数+1))、入场regime锁定、先卖再买与最近买升级规则保持原语义。状态修订通过input_sha256变化公开；宿主对原生持仓/状态兼容及在途交易另行负责。

## 容量与验证

EvaluationBudget默认且硬上限：4096完整日、32768行、全部来源文本8388608字符、序列化输出8MiB、5秒计算阶段截止；调用者可收紧。文本包括配置/角色/证券/摘要/evidence，所有可携文本/容器在canonical与算法前先验类型、长度及容量。配置业务窗口仍保留上限10000，超出首包可取得完整预热数据容量的配置返回容量/预热阻断。硬输入/文本上限约束内存；每阶段与各行检查单调截止，宿主还须以独立进程绝对期限收敛C调用和取消。

计算期限由kernel单一单调deadline拥有，显式check回调贯穿输入逐行准入、模型校验/分组、EMA和特征逐行、全部八角色逐行、分配收集/逐日、结果构造及canonical值转换/编码。精确Fraction窗口按32项检查，价格窗口/量提取按32项检查，canonical递归逐节点检查并每32个JSON块复核，输出字节在编码过程中提前限界。check为可选内部参数，独立helper默认None保持原语义；预算从公开evaluate_history统一注入，不持有全局时钟或signal状态。测试可替换kernel.monotonic并按内部检查计数推进确定时钟。这属于协作截止：单次有界操作仍须完成，包含至多32768条排序、至多10000项普通sum/max或窗口切片、至多32项有界Fraction/JSON块、单个已限长字符串转义，以及有输入/输出容量上界的缓冲区扩容/最终bytes复制与SHA。信号内部固定回看最多60条，单行辅助来源日期最多64项；这些固定小单元不另引入时钟状态。各块之间复核同一截止，超期抛calculation_timeout且无资格输出；不承诺硬实时或调度延迟上限。宿主仍拥有独立进程绝对期限，覆盖单个Python/C操作及调度。

价格与成交量共用稳定正数均值：普通有限总和保留原算序及舍入，求和本身抛出溢出或总和溢出时先按最大项缩放再求均值，公开int/float及其混合均适用。非零比率/正均值下溢到0返回`derived_value_unrepresentable`；真实全零成交量保留原缺量语义。均值进入IEEE binary64次正规范围时，对原始窗口的有界精确二进制有理数求均值，真实均值须可精确表示；比率、乘法及加减法的次正规中间结果使用同一精度资格。同时检查舍入到最小normal的邻界；真实值属于normal范围时保持原普通舍入。不可精确表示的次正规中间值稳定返回`derived_value_unrepresentable`，阻断失真值跨越业务阈值；恒定最小正float价量等精确可表示输入仍可计算。该规则覆盖价量MA、量比、涨幅、价格位置、EMA平滑/score、峰值止损、配置单元及权重乘法/累加。clamp前统一验证有限范围。精确路径只在极小表示范围进入：每个公开int/float已限于有限binary64范围，有界窗口最多10000项，float分母为2的幂，因此分子/分母位宽有界；硬输入及计算期限仍适用。不增加业务价格上限或最小成交量阈值，不把异常置零或灰灯。原普通计算分组、阈值的严格比较与等号行为保持。

配置生效/失效、knowledge_cutoff和每行市场/辅助时间，在特征与身份计算前统一验证UTC可表示；标准timezone/ZoneInfo并不自动保证转换范围。落在datetime最小/最大UTC边界之外的时间返回`time_unrepresentable`。编码与准入复用同一UTC函数，正常带时区时间的规范编码保持。

测试目录：`tests/integration/strategy_core`。只运行本仓库已迁入的新包与用例，固定旧测试仅作为来源参考。范围包括八角色真实分支、退出等号/年龄/份额豁免、完整前缀、EMA、因果、零目标、角色映射、修订、拒绝路径和容量。安装/压测证据写`build/guanheng-workspace/strategy-core-001`。native ABI、真实日线/辅助事实、CTA/回测、HTTP/页面与生产仍按NSK分别验真。

## a6 配置校验接口

新增公开 `validate_configuration(ConfiguredStrategyConfig.from_dict(value)) -> None`，复用计算入口原 `_config` 规则，失败保留 `KernelValidationError`。此入口核配置内部合法性，当前有效期和数据/运行资格分别判断；`evaluate_history`仍以实际知晓截止核有效期。算法身份保持configured 1.2.0，数学、状态及计算算序保持。

## a7 显式历史日末回测模型

`evaluate_historical_model(config, history, HistoricalEodModel, model_cutoff)`复用同一算法，接纳历史首次可知未知的事后日线快照。原始行market_available_at保留None，模型单独记录真实received_at、批次SHA、amount单位unknown及按CNY解释的假设。结果qualified=False，模型条件参与输入SHA并随结果返回。默认`evaluate_history`继续拒绝未知/晚到的市场可知时间；辅助事实原先的因果约束保持。该回测模型及`nsb-historical-report-v1`授予明确范围的历史回测资格，实时和交易入口继续分别验收。严格输入的原规范JSON及结果字节保持。
