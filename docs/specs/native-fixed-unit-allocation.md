# V2 固定单元纯分配器

类型：功能最终规格。状态：accepted。前缀：NFA。细化[NSK](native-strategy-kernel.md)的下一纯业务切片；保留[完整五策略及全部版本](../migration/business-feature-inventory.md)。本切片只迁入`resonance-regime-v2@0.1.0`固定单元分配。configured1.2.0现有a5、其他V1版本、V3、迟滞版、AI版及通用规则继续保留各自身份。

## NFA-R1 来源与职责

独立包`guanheng_strategy_variants`以标准库实现，拥有固定allocator算法/version/source SHA，调用方字段只能核对该身份，未知值拒绝。源为QMT固定`6cf508a070392ff976b6b4d6b31b0e6219001e71`的V2 allocation SHA256 `6035b1836b3b93e03a02afdde646858745823d45f29dfe226e36a13fee4232f5`及固定八证券常量；来源清单随包保存。运行及安装不导入旧工程。

上海收盘采用包内固定IANA2026c的Asia/Shanghai TZif，内容SHA256 `bf8b7ed82fe6e63e6d98f8cea934eeac901cd16aba85eb5755ce3f8b4289ea8a`，保留tzdata2026.3来源与许可证。标准库ZoneInfo.from_file在模块初始化时读取并校验包内数据，计算不探测宿主时区库、不联网，不增加运行时Python依赖。历史1900偏移和夏令时按该固定数据解释，不能以全年UTC+8替代。数据缺失/损坏使包初始化明确失败，许可证随包发行；时区数据更新须有新发行身份。结果标识固定time_policy及其数据SHA，旧a1证据保持原身份，修正候选另打包。

WT-B01/B02的CtaMocker/回放、撮合和原生输出仍归WT。本包只计算原始完整权重和可解释分配状态，不接NSQ/NSB、ctx、账户、执行、资金、持仓或订单，不实现旧撮合。当前a5及应用依赖保持原样；V2完整特征/信号生产、数量接线与用户入口另验。

## NFA-R2 冻结输入域

后继组合域：保留`guanheng.fixed-unit-input.v1`的每decision最多8项、每项128字符证据原限制；新增显式`guanheng.fixed-unit-input.v2`，每decision最多17项、每项256字符，用于完整消费SST的16项原证据与CSI派生证据。两个schema共用原分配算法、来源身份及联合预算，超限拒绝，不裁剪、去重或截断输入。v1普通输入的规范字节和数学结果保持；v2身份通过其输入schema及完整input_sha256区分。包版本0.1.0a3实施该扩展；此前a2资格仍限冻结v1域。

唯一计算入口`evaluate_fixed_unit_history`接受同版不可变`FrozenFixedUnitInput`或同版普通值/JSON；构造器和JSON均通过唯一有界准入。输入包含固定算法核对字段、profile、feature series证券键、分证券有序decision列表、显式pre_risk_capacity、history/evaluation日期、knowledge_cutoff、trace/source/factor摘要。固定证券是159780.SZ、510050.SH、510300.SH、510500.SH、512100.SH、515080.SH、588000.SH、589680.SH；feature keys须含510300，decision series唯一且为该集合子集。

Decision保留symbol、trade_date、BUY/SELL/HOLD、有限strength、path、reason、有限0..1 confidence、有序evidence_refs，新增aware available_at。每条须满足上海交易日15:00≤available_at≤knowledge_cutoff。evaluation_end须已闭合；所有日期1900-01-01至9998-12-31，history_start≤evaluation_start≤evaluation_end。`legacy-runtime-full-prefix-v1`允许decision从history_start；`legacy-backtest-evaluation-range-v1`从evaluation_start；范围以外拒绝而非截断。所有时间规范为UTC。此profile只标识冻结trace的生产起点，不生成信号或授真实producer因果资格。

该输入域新增严格类型、因果、范围、身份与预算准入。旧allocator数学函数接受域更宽，两者差额公开，不能宣称逐输入完全兼容；合格常规信号域保持原数学算序。空字符串path/reason可保留，未知字段、重复JSON键、非有限数和可变/未知对象拒绝。

公开输入schema为`guanheng.fixed-unit-input.v1`或`guanheng.fixed-unit-input.v2`，顶层字段完整集合如下。普通dict允许list/tuple容器和标准date/aware datetime值；JSON使用对应数组/ISO字符串。准入后统一为规范ASCII JSON和深不可变值，计算不保留调用方容器引用。

| 字段 | 定义 |
|---|---|
| schema / algorithm_id / source_sha256 | 固定输入schema、本模块ALGORITHM_ID、SOURCE_ALLOCATION_SHA256，仅核对 |
| signal_profile | 本节两个profile之一 |
| feature_series_symbols | 1..8个唯一固定证券键，含510300.SH；不包含特征数值 |
| decision_series | 0..8个唯一证券组，每组严格含symbol及有序decisions数组；每条decision严格含本节定义的九个字段 |
| pre_risk_capacity | 显式有限float可表示数值，(0,1]，bool拒绝；不取默认样本值 |
| history_start / evaluation_start / evaluation_end | 规范日期及本节范围关系 |
| knowledge_cutoff | 明确aware时刻，准入后UTC |
| source_revision / factor_revision / trace_sha256 | 每项64位小写十六进制；调用者声明的冻结trace/生产来源/因子内容身份，不等于模块Git版本或真实producer认证 |

算法来源Git身份由模块`SOURCE_REVISION`及包内source_manifest单独固定。返回`input_sha256`是完整准入后规范JSON的SHA256；修订输入重新计算，不接受外部active/previous状态套用新身份。

## NFA-R3 原算法与结果

从active空、CSI强度0、sequence0、previous=None开始，按日期聚合，日内以`(action != SELL,symbol,path)`稳定排序。CSI每条decision刷新strength；其他SELL移除active，BUY递增sequence并更新rank，HOLD保持。CSI强度>0设0.25×strength，其他active先设0.125，再按rank倒序/symbol顺序尝试第二个0.125，条件为used+0.125≤pre_risk_capacity+1e-12。pre_risk_capacity显式(0,1]，只约束升级，不能用它修剪初始仓位。

完整八标的向量含零；第一次decision即使全零也保留dated事件，后继各标的差≤1e-12时抑制事件。无decision产生无allocation，最后向量None及日期None；无新事件保持最后原allocation日期。paths及evidence保持排序后顺序，evidence按首次出现去重。float原分组、稳定同键顺序与容差保持；不归一化、缩放或新舍入。

CSI强度1加其他7个BUY的输入可产生原始总量1.125，结果如实保留。输出明确`execution_qualified=False`，原始权重/诊断不构成可执行目标资格；任何数量接缝与行为修正另有身份/规格。状态仅为active/rank/sequence/CSI强度/previous的纯计算投影，不接收外部恢复状态作权威。

返回`FixedUnitEvaluation`由唯一计算入口生成，普通构造拒绝。其schema为`guanheng.fixed-unit-result.v1`；`allocation_events`与`state`为深不可变公开属性，`to_dict`返回独立普通值，`to_json`返回规范ASCII JSON。每个event含trade_date、按证券排序的八项target_weights二元数组、decision_paths和首次出现顺序evidence_refs。结果另含固定算法/策略版本/source SHA、time_policy及timezone_data_sha256、input SHA、输入来源/因子/trace身份、profile、三日期和cutoff；latest_event_date/latest_raw_weights从最后实际event取得，空历史均为None；new_event_for_cutoff表示最后实际event日等于evaluation_end。state含active_buy_ranks、sequence、csi300_strength、previous_raw_weights；raw_diagnostic含最后权重和、显式capacity及两个超额布尔值。execution_qualified和scope标识本节限定资格。该结果支持解释与重算，不作为执行恢复账本。

## NFA-R4 联合预算与时间

默认和硬上限：raw JSON及规范ASCII输入各8MiB、输出8MiB、输入全部文本8Mi字符（包括重复evidence及键）、树1048576节点/12层、8个series、32768条decision、4096个不同decision日、history至end跨度20000自然日。单字符串≤256字符，其中path≤128、reason≤256、v1每条evidence≤8项且每项≤128字符，v2≤17项且每项≤256字符；调用者可收紧数量/文本/字节/跨度/深度预算。任一联合上限先到即明确拒绝，不能按行数单独授最大规模资格。

构造器整数先受1024位上限，JSON数值token≤400字符，随后都须可表示为有限float；bool不作数值。时间为标准timezone/ZoneInfo的aware datetime或带秒和明确偏移的ISO字符串，JSON小数秒最多6位，日期必须规范YYYY-MM-DD。字符串偏移小时须00..23、分钟须00..59，在调用datetime解析前校验；禁止将+00:60等非法表示归并为合法时刻。这些均属新增公开输入域边界。

每次公开计算以一个monotonic起点计量，默认及硬max_seconds=5，可收紧。raw扫描、树准入、日期/身份、分组、排序key提取前后、状态循环、证据收集、冻结和分块JSON序列化共用同一截止；超限统一`calculation_timeout`。stdlib JSON解析及排序比较等有界非抢占单步须记录实测，不承诺Python硬实时。公开to_dict/to_json是各自有界的独立操作；跨进程绝对截止归未来宿主。

## NFA-R5 验证与资格

后继硬限准入：公开预算值是调用方输入；计算、输入构造/投影及结果投影入口须完整快照预算字段并重新校验硬限，拒绝缺字段、bool、NaN或扩大上限，后续只读本次快照。该要求保护声明的数据契约，不隔离同进程任意恶意Python代码。扩域须覆盖v1拒绝/v2接受的相同长证据、17/18项和256/257字符、重复/Unicode/联合字节上限及安装后入口；与SST的真实组合、原v1数学及时间证据按实际影响验证。

以新仓库静态来源及独立人工oracle验证空/dated-zero、CSI/HOLD、SELL先于BUY、同键稳定顺序、重复BUY rank、最近买优先、容量/1e-12边界、证据顺序与重复计量、1.125、profile/日期/available_at边界、前缀重算及输入修订隔离、全部联合预算和单一期限。输入/结果深不可变，修改返回普通值不能改变后续读取。安装后的相同入口覆盖正常/错误/容量且无旧树导入；不运行旧工程或旧测试作oracle。

源码、规格、源摘要、隔离包/依赖及实际结果冻结后交另一作者独立full。本切片不授V2真实trace生产、NSQ/NSB接线、原生撮合、实时、HTTP/SHM、完整策略迁入、真实交易或生产资格。后继事项保留在范围清单，分别取得资格。
