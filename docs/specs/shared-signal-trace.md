# 共用特征与信号轨迹

2026-10-29后继a4：新增公共`prepare_signal_history`，复用同一严格准入所有者，返回本次独占的冻结日线/规范身份，供V1历史版本调用原公开数学；原八证券与direct-KC八证券以固定policy区分，保留589680/589000实际行情身份。原evaluate_signal_trace的默认域、数学、结果身份及起点规则保持。V2/risk/App消费新a4时统一更新依赖身份；旧a3固定安装保持历史资格，实际新候选见[LVH](legacy-v1-history.md)。

类型：功能最终规格。状态：accepted。前缀：SST。细化[NSK](native-strategy-kernel.md)五策略迁入中的共用数学producer，首先支持V2两种既有起点语义，供后续[NFA](native-fixed-unit-allocation.md)组合使用。源码存在、数学轨迹和完整策略运行分别验收。

## SST-R1 模块、接口与复用

独立包`apps/guanheng/strategy_signals/guanheng_strategy_signals`以一个计算接口`evaluate_signal_trace(request, *, budget=SignalTraceBudget())`承担严格准入、特征计算、正确起点的信号机回放、来源身份和不可变结果。公开输入`SignalTraceInput`持有既有a5的`FrozenHistory`、`signal_profile`、`evaluation_start`、`evaluation_end`及`knowledge_cutoff`；构造普通类型值不授已验证资格，唯一计算入口重新准入并取得自己的不可变快照。原始JSON输入不属于本版接口，后继运输解析不得绕过该准入。

精确依赖`guanheng-strategy-core==0.1.0a5`，复用其具名模块公共接口：`features.build_daily_features`、`signals.run_signal_machines`、`models.DailyObservation`及`contracts.utc_timestamp/canonical_bytes/json_value`。数学及信号规则只有该实现来源；新模块不复制八角色状态机，不调用`kernel._history`，不伪造configured1.2.0配置。a5源码、固定wheel、现有应用依赖和锁文件保持原样。来源清单绑定原归档、a5模块与wheel摘要，正式安装核对身份。

原生能力对应WT-S01/S02/S03、WT-B01/B02：CTA调度、上下文、理论仓位、回放/撮合及原生结果均由WT拥有。本模块是其尚不提供的观衡特征/信号规则，不管理持仓、目标、订单、资金、任务或数据库，不创建HTTP/SHM/终端连接。架构职责沿[系统架构](../architecture/overview.md)。

## SST-R2 两种起点及原算法

固定信号证券集合为159780.SZ、510050.SH、510300.SH、510500.SH、512100.SH、515080.SH、588000.SH、589680.SH。历史可包含其1..8个唯一证券，必须包含510300.SH；各证券可有不同历史起点及日期缺口，保留原先的上市前/不同批次历史，不新增每日必须八证券齐全的隐含规则。此数学域不代替旧dataset完整覆盖和consumer准备门槛。

先将截至`evaluation_end`的全部已准入历史交同一`build_daily_features`，固定MA100、位置60、量20及既有EMA20等规则，不能先裁观察记录再计算特征。随后按`signal_profile`选择送入状态机的特征序列：

| profile | 信号输入与状态 |
|---|---|
| `legacy-runtime-full-prefix-v1` | 每证券完整特征前缀，从该证券真实首行开始；空初始状态 |
| `legacy-backtest-evaluation-range-v1` | 特征计算完成后，每证券仅选择evaluation_start..evaluation_end，再以空初始状态启动 |

调用原具名dispatcher，保持日内顺序、SELL/BUY/HOLD、strength、confidence、path、reason、证据顺序和浮点算序。禁止采用configured1.2.0的first_ready裁剪，禁止仅截结果或替换state来模仿特征切片；回看窗口和index从真实送入序列重新计数。无外部实际成交周期注入：固定V2的runtime/backtest均只调用默认dispatcher，未传position_cycle/boundary_override；这不代表带真实fill周期的其他版本已迁入。

短人工历史可用于数学验证，缺辅助事实保持原灰灯和原分支。运行consumer的100 prior、旧离线预热范围、dataset严格覆盖与真实因果资格仍由未来组合接口分别拥有，本模块不据一次计算成功宣称运行ready。

## SST-R3 严格输入及因果

仅接纳本版`SignalTraceInput`、本版预算和精确a5`FrozenHistory/DailyObservation`类型。容器须为tuple，字段须为声明的不可变普通类型；拒绝自定义对象、bool作数字、NaN/Inf、重复/非规范证券、乱序和重复(date,symbol)。历史按(date,symbol)升序。数值保留原int/float算序；整数先核最多1024位并可表示为有限float。价量/OHLC及百分位业务校验复用原公共特征/模型逻辑，新增的严格类型、容量和因果准入集中在本模块。

日期须为精确date，范围1900-01-01..9998-12-31；derive的history_start≤evaluation_start≤evaluation_end，历史不含evaluation_end之后行，evaluation_end须在knowledge_cutoff前闭合。至少一条历史；backtest切片为空时允许空决策。整个历史至evaluation_end跨度≤20000自然日，不推断交易所开市或上市覆盖。

知晓截止和每条market_available_at使用精确aware datetime，时区只接受标准timezone/ZoneInfo，并经原公共UTC转换核可表示性。每行market_source_sha256、FrozenHistory的source_revision/factor_revision为规范64位小写SHA256；market_available_at须≤该行上海15:00且该收盘≤knowledge_cutoff。缺少时间或来源拒绝。

四项辅助值shares_delta_yi/share_probability/turnover_percentile/margin_percentile分别保留可空及原数值域。存在辅助值时必须有辅助来源SHA、可获知时间及非空来源日期；辅助时刻≤该行收盘，来源日期≤该行交易日。辅助metadata即使数值全空也须核类型/格式/范围。辅助日期tuple最多64项；证据tuple每行1..16项，每项1..256字符。市场/辅助证据及源摘要保持，不合成实际来源。

每条返回decision的`available_at`为已经核实上述输入约束后的派生上海收盘边界，规范为UTC。这是确定性计算的最早逻辑可获知边界；`historically_produced=False`，不冒称当时确有生产记录。source_qualified及execution_qualified恒False，真实来源、完整producer准备和可执行目标另验。

## SST-R4 身份、结果与跨模块接缝

算法/profile身份由模块常量和source_manifest拥有，调用方不能选择未知算法；profile是明确输入身份的一部分。返回`SignalTraceResult`仅由计算入口创建，schema为`guanheng.signal-trace.v1`。结果至少含：固定算法与依赖身份、input_sha256、trace_sha256、source_revision/factor_revision、profile、history_start及evaluation日期/UTC cutoff、feature_series_symbols、按证券排序的decision_series、每证券最后特征诊断和限定资格说明。

decision保留原八个数学字段并附available_at。每证券末尾诊断只含最后交易日、price_position/volume_ratio/trade_direction/regime_score/regime_label等有限公共值；不复制每帧完整历史到逐日结果。无决策返回空序列，不虚构零目标或分配日期。结果不包含allocator权重或数量。

input_sha256来自全部准入后的历史、profile、日期、cutoff和模块身份的有界规范ASCII JSON；trace_sha256来自不含自身摘要字段的规范结果body。输入证据原顺序与重复出现完整参与输入身份及预算；输出保持a5原机实际产生的证据（包括CSI原有去重、其他角色原有重复），本模块不额外增删或改写。结果递归不可变，to_dict返回独立普通值，to_json返回规范ASCII JSON；修改返回值不能改变后续结果或身份。

a5每行可有16项256字符证据，CSI信号会追加派生证据，因此结果允许最多17项。冻结NFA当前仅接纳8项128字符，二者交集外的组合必须明确拒绝并保留完整轨迹；禁止截断、丢弃或重写证据来取得NFA准入。后继扩域须有明确发行身份及回归，不能回写冻结NFA。原始V2权重1.125及旧离线风险缩放与runtime完整目标拒绝的差额继续单列，不由本模块归一化。

## SST-R5 容量、期限和错误

默认及硬上限：4096个不同历史日、32768行、8个证券、32768条decision、输入规范ASCII 8MiB、全部输入文本8Mi字符、输出8MiB。单个证据/metadata文本长度先核，逐项累计并在复制/编码前停止；输入所有字段文本纳入计量。调用者可收紧数量、文本、字节、日期跨度与时间预算，超过硬上限的预算拒绝。联合上限先到即拒绝，不能以最大行数通过代替最大字节资格。

唯一计算使用一个monotonic截止，默认及硬max_seconds=5，覆盖准入/快照、输入编码/哈希、特征和窗口、profile切片、全部信号循环、结果冻结、编码和哈希；复用原公共函数的check参数。超时统一`calculation_timeout`，没有部分可采用的轨迹。序列化公开操作各有有界独立预算；明确最大非抢占stdlib排序、JSON编码/复制等单步及实测，不承诺Python硬实时。未来宿主的OS绝对截止独立覆盖原生进程。

公开错误为固定code和去敏中文reason的`SignalTraceValidationError`，不回显完整输入或外部异常。非法输入、来源/因果缺项、数值不可表示、容量和超时分别可判断。模块无副作用、后台线程或持久状态；恢复由同一冻结输入重算，改变profile/来源/历史会改变身份。

## SST-R6 验证及交付

1. 手算CSI短前缀三次BUY、runtime/backtest起点差异；KC composite局部index与窗口差异；全历史先features与错误先裁行情的反例；灰灯及不同证券起点保值。
2. 对全部八角色和两个profile，与显式调用已验a5公共函数的固定输入做调用链对照；人工oracle/已核静态来源说明原数学，禁止运行或导入旧工程作oracle。
3. 覆盖不可信typed值、未来/缺少/畸形来源时间、未知时区/对象、NaN、乱序/重复、可变证据、证据17项不丢失、空切片及输入/输出深不可变。
4. 同一期限传播、各联合预算、上限组合与超限、序列化独立预算实测；不同输入修订及profile不共享身份。
5. 正式非editable独立安装及公共接口回归；来源/依赖/wheel/源码字节绑定，a5和应用锁保持，旧树不进入构建/导入/运行。冻结后交另一作者独立full。

本模块验收不代替NFA组合、完整V2输入准备/风控、NSQ数量/原生撮合、实时恢复、HTTP/SHM、券商及生产。后继沿完整目标继续，不能据纯数学producer通过宣称V2全部迁入。
