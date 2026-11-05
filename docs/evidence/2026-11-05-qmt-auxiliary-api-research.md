# 国信 QMT 辅助数据接口核查

类型：研究证据。日期：2026-11-05。状态：官方文档核查及既有证券资料通道小样本实测完成，历史份额及市场汇总语义继续核实。适用范围：策略需要的 ETF 总份额、沪深股票成交额、沪深融资余额；沿 [SDO](../specs/strategy-data-and-observability.md) 的单位及知晓时间约束。

## 结论与证据边界

优先从国信内置 QMT 取得与原策略口径一致的原始事实，经现有共享内存通道交给 WT。当前证据支持继续核查成交额和股本入口；ETF 历史总份额与全市场融资余额仍需真实返回和口径证明。文档检索没有命中某字段，只能登记“尚未确认”，不能据此断言终端没有此能力。

官方文档研究没有操作终端；随后 Root 复用已运行的 v9 证券资料 Source 完成一次只读详情查询。没有修改 QMT 正文、订阅、下载、下撤单或启停服务。在线通用文档、国信安装版本和已开放的共享内存 operation 分别核实。本机 API 索引只表示手册收录，见 [索引](../modules/qmt-native-api-index.md) 与 [运行手册](../runbooks/guosen-qmt-python.md)。

## 官方接口核查

| 目标 | 已查入口与已确认内容 | 接入前仍须证明 |
|---|---|---|
| 日线成交额 | 内置 `ContextInfo.get_market_data_ex` 提供 `amount`、日期范围和日周期；`download_history_data` 补历史。 | 当前返回单位、历史尾日、股票汇总范围；指数 `amount` 与原沪深股票汇总是否等价。 |
| 当前 ETF 总份额候选 | 内置 `get_instrument_detail` 的 `TotalVolume`、`FloatVolume` 文档为股本、单位股；`get_total_share` 返回总股数。 | ETF 返回的实际含义、对应统计日、更新时点；当前值不能直接充当逐日历史总份额。旧版函数拼写须核本机。 |
| 历史总份额候选 | `get_financial_data` / `get_raw_financial_data` 可取股本表及时间范围。 | ETF 是否覆盖、是否逐日更新及单位；股票股本表存在不能证明 ETF 逐日份额已覆盖。 |
| 沪深融资余额 | 本次已查内置行情目录未确认全市场汇总入口。 | 确切接口、字段、权限、沪深范围、融资单项及统计日，随后核历史覆盖。 |

以上接口依据为迅投 [内置行情函数](https://dict.thinktrader.net/innerApi/data_function.html)：财务接口需预先补充财务数据，公告日与报告期取数语义不同；`subscribe=False` 读取已有数据，下载返回 `None` 应另行回读验收。该页没有为上述 ETF 候选证明历史总份额语义。

另外两类容易混用的数据已核实：内置 `get_etf_info` 是申赎清单，`get_etf_iopv` 是份额参考净值；PCF 的 `reportUnit` 表示最小申赎单位，见 [官方函数检索表](https://dict.thinktrader.net/VBA/check_sheet.html)。这些字段各有用途，不能直接作为存续总份额。信用账户对象的融资负债、市值和额度属于该账户，见 [内置数据结构](https://dict.thinktrader.net/innerApi/data_structure.html)，不能替代沪深市场融资余额。

## 特色数据与版本边界

[场内基金数据字典](https://dict.thinktrader.net/dictionary/floorfunds.html) 另列 `etfstatistics`：尊享投研端的实时申赎数据，示例使用外部 `xtquant.xtdata`，含申赎数量、金额及时间。它可作为进一步核查线索，当前国信内置权限、完整性与总份额等价性均未实测。

[XtData 文档](https://dict.thinktrader.net/nativeApi/xtdata.html) 描述外部 Python 与 MiniQMT 的交互。外部示例及其特色周期不能自动转为国信内置调用保证。[内置引用函数](https://dict.thinktrader.net/innerApi/quote_function.html) 提供扩展数据、因子和 VBA 模型读取入口，但具体辅助字段名称、数据订阅及版本支持仍需本机核查。VBA `CAPITAL` 文档为流通盘、单位手，见 [系统函数](https://dict.thinktrader.net/VBA/system_function.html)，同样需要 ETF 口径证明。

## 旧项目的实际做法

只读核对 `D:/workspace/qmt/src/qmt_platform/services/strategy/strategies/resonance_regime_v1/official_sources.py` 与 `publication_bundle.py`，没有导入或执行旧服务。该辅助链登记上交所/深交所官方 HTTP 来源，归档原件后再解析；它没有直接证明原来由内置 QMT 提供这些字段。

| 原字段 | 旧实现定位与含义 |
|---|---|
| ETF 份额 | `parse_sse_share_publications`：`TOT_VOL / 10000` 转为亿份；深市另有基金规模解析。 |
| 沪深成交额 | `parse_sse_turnover_yi` 取产品代码 `17` 的股票汇总，`parse_szse_turnover_yi` 取“股票”行；两所相加。 |
| 沪深融资余额 | `_margin_value` 分别取 `RZYE/rzye` 与 `jrrzye`，核日期和单位后合并融资余额。 |
| 生效时间 | `publication_bundle.py` 保留来源归档和单独的知晓时间政策。当前实时接入仍遵循 SDO 的实际知晓边界。 |

这些是旧源码的解析行为，作为 QMT 样本的对照基准；切换来源前还须比较原件、口径和统计范围。保留旧项目只读，不恢复旧数据库或旧服务。

## 现有共享内存真实小样本

2026-11-05 20:40:49（北京时间）调用既有 `market.security_details`，原 QMT 策略线程执行 `get_instrumentdetail`。四只均 observed；本机实际拼写为 `TotalVolumn` / `FloatVolumn`，二者本次相等；整个结果的 `source_as_of=null`。

| ETF | QMT原始TotalVolumn | 除以一亿的候选数值 | 已归档2026-11-04交易所总份额（亿份） |
|---|---:|---:|---:|
| 510300.SH | 41401380000 | 414.0138 | 463.630877 |
| 510050.SH | 12866160000 | 128.6616 | 163.338668 |
| 588000.SH | 95612660000 | 956.1266 | 1071.746682 |
| 588030.SH | 2297830000 | 22.9783 | 22.948381 |

本表仅证明当前读取返回和数值差异。QMT未给出该资料统计日，不能判定两者同日、推断缓存失效或确认某方错误；除以一亿仅为单位候选对照。该字段暂未作为每日份额输入，更不能用一个当前值填满历史。

环境原件：`E:/workspace/wondertrader-qa/current-day-20261105-001/qmt-auxiliary-reference001/RESULT.json`、`COMPARISON.json`；原请求/完整回执留同目录 `details.json`，包含受控运输身份，只在本机保存。采样脚本 `qmt_auxiliary_reference_read.py` 位于该QA根，凭据仅在进程内提取，不写报告。外部采样使用既有参考Host的v9普通安装及017已安装运输模块组合，未修改运行安装。对照依据为辅助原件目录 `auxiliary-official-001/sse-shares/2026-11-04.json` 及其摘要绑定压缩原文。

## 最短实测与接入步骤

1. 由唯一现场操作方复用现有 QMT 来源策略和共享内存入口，先读取少量标的与少量日期；不为本研究新开诊断策略。终端内仅调用已核内置 API，外部 WT 负责落盘、对照和派生。
2. 对 ETF 核 `TotalVolume`、`FloatVolume`、`get_total_share` 的实际值与当前官方份额；再尝试财务历史入口。记录本机版本、字段名、返回日期和缺失原因。只取得当前值时，从真实取得日积累，不回填历史。
3. 成交额先核两个市场明确的股票汇总证券/数据对象。若改为逐股求和，须按统计日证券清单核完整性、上市退市、A/B 股及重复覆盖；不能直接将两个指数的成交额相加就宣布同口径。
4. 融资余额先查本机已有数据字典、特色数据或明确的市场统计品种；取得返回后和两所融资单项对照。账户融资数据继续保留账户用途。
5. 每项合格事实记录 `statistic_date`、值、单位、实际 `received_at`、有依据的 `available_at`、来源身份；两种来源切换时显式记录来源，禁止静默混拼。缺项保留未知，由诊断展示。

优先级是“可验证同口径的国信 QMT 数据 → 已核官方来源补充”。份额概率、热度与分位继续由唯一策略公式派生；接口返回原始事实并不直接证明派生指标已更新。下一步验收为真实样本读取、单位/日期对照、历史覆盖和持续增量回读，现阶段不声明辅助主链已完成。
