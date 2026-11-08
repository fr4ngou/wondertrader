# 共振策略研究指引

类型：研究操作指引。适用范围：共振策略诊断、市场指标与因子评估、风险和入场实验。状态：研究资料入口已建立；候选交易规则的实现、回测验证和部署分别登记。

## 资料位置与Git边界

具体研究保存在项目根的 `research/resonance-20261105/`，该目录已在根 `.gitignore` 屏蔽。文档、来源笔记、诊断脚本、CSV和JSON证据均属于本地资料。项目版本库保存本指引和导航，研究正文需要沿本机资料目录读取；全新克隆需要另行取得这些本地文件。Git忽略只控制版本追踪，文件仍保留在本机。

在项目根用编辑器打开该目录的 `README.md`，按以下分类阅读：

| 分类 | 本地文件 | 阅读目的 |
|---|---|---|
| 当前策略诊断 | `00-current-strategy-audit.md` | 读取原算法、实际数据与成交，区分信号、组合、执行和费用影响 |
| 指标 | `01-indicators-and-divergence.md` | PCR、VW-MACD、CCI、TRIN及广度的公式、适用范围、背离与失效条件 |
| 风险与入场 | `02-risk-and-entry.md` | 风险预算、股票风格覆盖、剧烈行情降风险、入场与执行比较 |
| 因子 | `03-factor-combinations.md` | 因子定义、独立信息簇、环境分流和组合候选 |
| 实战经验与验证 | `04-practice-and-validation.md` | 原归档案例、可迁移经验、实验顺序、评估及淘汰标准 |
| 数据准入 | `05-data-readiness.md` | 观衡实际覆盖、可知时间、来源映射与待补字段 |
| 因子库与评估 | `06-factor-libraries.md` | 技术计算库、特征/公式库、因子评价工具与静态源码核查 |
| 自动因子发现 | `06b-automated-factor-discovery.md` | 强化学习、生成模型、遗传规划的目标、许可及适配边界 |
| 扩展因子族 | `07-expanded-factor-families.md` | 从经济机制寻找更多指标和因子，区分择时、排序、风险与执行 |
| 问题摘要 | `08-strategy-problems-summary.md` | 可单独阅读的当前策略问题与影响 |
| 金融条件 | `09-financial-conditions.md`、`09a-bonds-funding-credit.md`、`09b-margin-and-leverage.md` | 股票量价以外的资金、信用、债券、杠杆和两融研究，区分来源存在与预测验证 |
| 复合金融因子 | `10-composite-market-state.md`、`10a-existing-composite-indices.md` | 现成组合方法、六类市场状态候选、分簇/交互/状态组合与验证 |
| 原版还原 | `11-original-restoration.md`、`11a-upstream-data-audit.md`、`11b-upstream-algorithm-audit.md`、`11c-reference-verification.md`、`11d-independent-implementation-review.md` | 固定上游原始算法、数据差异、独立入口及验证边界 |
| 原版真实数据重跑 | `12-qmt-wt-data-and-replay.md`、`12a-qmt-data-capability.md`、`12b-wt-data-compatibility.md`、`12c-auxiliary-data-readiness.md`、`12d-replay-validation.md` | QMT和WT实际能力、行情补齐、份额/融资/成交额来源、缺项与真实输入试跑 |
| WT持久采集与补历史 | `13-wt-supplement-collection.md`、`13a-original-data-collection.md`、`13b-original-margin-replay.md` | 原库取数路径、QMT优先证据、融资原表校正、持久缺口与真实查询验证 |
| 实际补历史与原库重核 | `14-actual-backfill-and-original-routes.md`、`backfill-20261106/` | 历史原件纳入WT、实际全量HTTP读回、原库/AkShare请求复测及当前剩余缺口 |
| 远端对照、取数根因与上线差距 | `15-server-comparison-and-source-fix.md`、`server-comparison-20261106/` | 同数据逐笔净值对照、独立QMT差异、官方HTTP补齐、自动更新/策略可见性的实际状态 |
| 每日更新与WT框架接入 | `daily-auto-development/`、`server-comparison-20261106/` | 原owner跨日补采、普通安装与采用、原版信号的WT原生撮合与原组合对照 |
| 证据 | `audit/`、`data-readiness/`、`VERIFICATION.md` | 复现脚本、冻结输入摘要、统计结果及检查范围 |

## 研究方法

每个指标和因子记录：经济假设、精确公式、输入字段及单位、股票池、参数、预热、信息可知时刻、适用行情、失效行情、与其他指标的冗余、候选规则和验证结果。一手来源用原作者论文、交易所规则或所用软件的官方算法文档，并登记访问日期。

证据分四类：源码可证的行为、冻结归档中的观察、外部研究支持的机制、项目待验证假设。观察到的相关性、个别成功交易和回测内最优参数分别标识。跨市场、跨资产、跨频率的外推需要本项目重新验证。

对“顶底识别”先定义可交易事件和预测周期，再统计误报、漏报、确认延迟与净收益。价格、量价、广度、期权情绪和风险条件各有职责；同一原始变量衍生出的多个指标需要核对冗余。历史极值标记可以用于事后评价，实际信号只能使用当时已经确认的事实。

## 复现与实验

先阅读本地 `VERIFICATION.md` 和脚本的输入说明。在项目根使用Python 3.10+运行本地诊断脚本，明确报告身份、费用和时钟假设。候选回测沿[研究回测与查看](../runbooks/native-backtest.md#研究回测与查看)在独立目录运行；归档读取和实验输入保持只读。观衡观察GET请求用于冻结已发布数据，策略、账户、委托和运行生命周期分别沿原所有者维护。

实验先恢复可解释的基线，再逐项比较信号、风险和入场改动。记录全部试验，包括失败组合；采用按时间的样本外验证、交易成本压力和市场环境分组。已经用于诊断或调参的区间登记为已观察数据，后续验证使用独立时期或前瞻观察。

现有策略继续沿[唯一策略规格](../specs/retained-resonance.md)、[原生回测入口](../runbooks/native-backtest.md)、[验证规范](../development/verification.md)和[研究原生接缝](../modules/backtest.md)维护。用户2026-11-06追加授权还原所给上游，按[原版独立规格](../specs/original-resonance-reference.md)建立[离线独立入口](../../apps/guanheng/strategy_original/README.md)，现策略保持。交易规则生效按相应运行验收处理。

## 维护与检查

更新具体研究时保留报告/数据/源码摘要及原观察日期，正文维护一个权威位置，相关文件从本地README索引。研究数据与个人配置保持在忽略目录中，材料中引用外部资料的使用范围按来源许可处理。

交付时运行 `git check-ignore` 和 `git ls-files` 核对研究正文未进入版本追踪，运行 `python -B scripts/project.py check` 检查公开文档；本地研究文件的相对链接与证据文件另行检查。研究完成、规则已实现、样本外验证通过和生产生效分别说明。
