# 因子研究流程与开源工具选型

研究操作指引与选型记录，2026-11-11（北京时间）。适用于 A 股日频横截面因子、ETF 相对排序及市场时序信号。方法与候选库已调研，库由用户选择，运行适配与策略验证待开展。

## 视频提供的范例

视频的取数、复权与过滤、计算因子、截面排序、IC/IR、分组收益、选股回测构成一条常见的**单因子复现与初筛**流程。Alpha144 是一条已发表公式。因子发现还包括提出候选、定义搜索空间、登记尝试和筛选，研究结论还需要时间外验证和可成交组合的证据。近期已经用于反复比较阈值、出入场或组合的区间，应统一标为已观察。历史结果仍可用于排查规则与数据，并用新窗口重新评价已冻结的候选。已有共振研究的诊断与实验分流见[共振策略研究指引](resonance-research-guide.md#研究方法)。

### Alpha144 的定义与待核口径

国泰君安《基于短周期价量特征的多因子选股体系》（李辰、刘富兵，2017-06-15）附录第 15 页给出 Alpha144。对单只股票，计算近 20 个观测期内各下跌日的 `|日收益率| / 当日成交额`，再取这些下跌日的均值。该值可作为下跌时单位成交额对应价格变动的代理。高值对应更大的单位成交额跌幅，未来收益方向需要独立验证。Amihud 的非流动性度量采用绝对收益与成交金额之比，Alpha144 的下跌日条件应单独保留。[国泰君安原研报（聚宽镜像）](https://file.joinquant.com/198f09d54939dbcd27819bb96f67ac15/%E5%9B%BD%E6%B3%B0%E5%90%9B%E5%AE%89-%E6%95%B0%E9%87%8F%E5%8C%96%E4%B8%93%E9%A2%98%E4%B9%8B%E4%B9%9D%E5%8D%81%E4%B8%89%EF%BC%9A%E5%9F%BA%E4%BA%8E%E7%9F%AD%E5%91%A8%E6%9C%9F%E4%BB%B7%E9%87%8F%E7%89%B9%E5%BE%81%E7%9A%84%E5%A4%9A%E5%9B%A0%E5%AD%90%E9%80%89%E8%82%A1%E4%BD%93%E7%B3%BB-2017-06-16.pdf#page=15) · [Amihud 原论文](https://www.sciencedirect.com/science/article/pii/S1386418101000246)

- 截图以 `close / close.shift(1) - 1` 计算收益，屏蔽缺收益或成交额非正的观测，再用 `rolling(n)` 汇总。按 pandas 整数窗口默认行为，有一个被屏蔽的观测就会使整窗结果缺失。先明确 20 个交易日或 20 个有效报价日的窗口定义，分别处理停牌、零成交额、缺行情、零下跌日及新股预热。若测试只在有效下跌日取均值等其他口径，单独登记并报告覆盖差异。[pandas rolling 文档](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html)
- 收益用经核对的同源复权价格，成交额用单位已证实的原始成交额，成交回放按可成交原价及公司行为处理。固定以元表示成交额，记录输入精度。用手算样例核对涨跌混合、全上涨、缺失、停牌、除权和截面并列，并核对逐日入池数及缺失原因。手算示例中，20 日内只有两次下跌，分别是 2% 对应 5 亿元、1% 对应 1 亿元，且其余观测均有效，结果是 `7e-11` 每元，按每亿元表达为 0.7%。[行情与复权数据合同](../modules/market-data-contracts.md#qmt原始日线分析价与复权来源)
- 先比较 Alpha144、单独成交额、单独下跌幅度这三个基线，再做规模、行业或流动性暴露的诊断与增量对照。将原值、截面排名、去极值或中性化版本分别记录。若 `rank(pct=True)` 后挑最高分，含义是持有原始值更高的一组，方向在开发阶段冻结。

### 视频里做对了什么，证据还缺什么

| 视频中的操作或观察 | 本项目复现时的核验 |
|---|---|
| 约 02:04–04:02，保留 ST 股票历史和持仓估值，另设候选池。明确选择 20 个观测全部有效的严格窗口。 | 保留价格、入池和可成交三层状态。上市天数按交易所日历复核。以真实历史股票池核对退市覆盖和逐日 ST 状态。 |
| 约 04:46–06:37，收盘打分，次日开盘到 20 个交易日后开盘构造未来收益。每天在因子和标签共同有效的证券上重排名，计算 Rank IC 和 ICIR。 | 同日可知股票池先冻结，再用共同有效样本计算相关。未来缺报价导致的剔除单独列覆盖和偏差。按时间外样本重做检验，并对重叠的 20 日标签报告相关性稳健的区间。视频明确将 IC 0.03、ICIR 0.5 视为经验参考。 |
| 约 06:37–08:37，五组的未来均值呈单调。每 20 个交易日选前 50 等权，次日开盘调仓，计佣金、滑点和卖出印花税。视频报告约 43% 回撤，约 78% 持仓落在最小市值五分组。 | 分组均值作为预测诊断。组合用适用的小盘基准、规模匹配组合或中性化消融复核，再验证开盘不可成交、容量和成本。用同一段全 A 历史展示的 Rank IC 均值约 0.071 与组合结果，登记为视频报告值。 |

视频已讲清信号与标签的先后，并揭示了小盘暴露。附件提供的证据缺少独立封存样本、规模匹配对照、实际成交约束细节，以及足以独立复跑的平台数据与完整代码。Alpha144 在观衡的预测增量仍待验证。

## 从假设到正式回测

先写明预测对象和决策。股票截面排序回答同一天哪些股票相对更强。ETF 轮动另行核对小截面的广度、集中度和并列值，并与原组合比较。市场择时用按日期排列的标签，对照原策略、持有基准或现金等适用基线，评估持仓开关和风险敞口。市场广度等对每只 ETF 同日取值相同的信号，日截面方差为零，应用时序评价。

| 阶段 | 实施与可复核产物 |
|---|---|
| 1. 登记假设与对照 | 写下经济机制、适用市场、精确公式或允许算子、可能方向、预测周期、现行基线、主指标、候选预算、通过与淘汰条件。一次实验先固定持仓、退出和执行，逐项改变因子或处理口径。要研究退出或风险规则时，固定因子与入场，另立实验。 |
| 2. 冻结时点数据 | 冻结历史逐日证券池、退市/上市、停牌、交易日历、价格/成交额单位、公司行为、数据可知时间与版本。基本面和指数成分用当日可见版本。原始可知时点未知的数据标为重建样本。保留逐日样本数、缺失率、剔除原因、覆盖日期与来源摘要。 |
| 3. 实现并验证计算 | 分开因子输入、信号时钟和未来标签。收盘后因子若次日开盘入场，示例标签用 `open[t+1+h]/open[t+1]-1` 表示持有 `h` 个交易日的开盘到开盘收益，价格收益需处理公司行为。下一交易日的停牌、涨跌停、未成交等按执行规则计入，保留未成交及缺标签统计。按交易日检查边界、预热、缺失、并列和成交延迟。用截断未来数据的测试验证当天因子、入池和信号一致。拟合型处理器只在训练数据拟合。当日截面处理只读当日可知样本。 |
| 4. 样本内探索与验证 | 按时间划分开发、验证、封存终测，开发/验证内按时间滚动训练和评价。按标签实际起止时刻剔除跨分界或重叠的训练标签。登记全部候选、窗口、方向、过滤、搜索预算、随机种子、失败和被淘汰试验。已看过或用于修改的历史归入探索。多候选检验按预设检验族及依赖结构选择校正方法，或把探索结果仅作筛选并用独立数据复核。 |
| 5. 诊断预测力与增量 | 股票按日计算 Pearson IC 或 Spearman Rank IC，报告均值、波动、日频样本量、正向比例、置信区间和覆盖率。ICIR 明示均值除以标准差及是否年化。标签重叠或日序列相关时使用 HAC 或按时间块重采样等相应推断。看分组收益、单调性、衰减、换手、行业/规模暴露，以及不同时间段的稳定性。用同一数据比较原基线与加入因子的版本。市场时序按条件收益、误报、延迟、暴露和费用后组合结果评价。 |
| 6. 冻结后做终测 | 用开发与验证段确定公式、方向、参数、模型、成本、选择规则与交易方案，再对封存区间运行。记录完整结果与失败。根据终测调整后，给该轮标记已观察，并取得新的独立区间或前瞻观察。 |
| 7. 用 WT 验证可交易性 | 固定策略版本、数据、起止日期、资金、基线和组合规则，在相同执行假设下比较净收益、回撤、换手、成交率和容量。验证费用、滑点、交易制度、涨跌停、停牌、最小手数、流动性与延迟，按品种与日期核实实际模型覆盖。研究输出按 WT 研究回测路径保存。用户要求交付的正式报告使用项目正式 WT 入口，核对完成凭证、正式归档及观衡列表和详情可读。 |

复核时沿实验清单找到假设与通过标准、候选及淘汰记录、输入和切分版本、代码/依赖版本及运行命令、因子与标签覆盖、指标与基线、WT 报告身份。出现覆盖不足、结论不稳定或费用后增量不足时登记原因，保留失败试验作为后续搜索记录。

多重尝试、回测选优偏差、样本外衰减与交易成本的依据分别见 [Harvey、Liu、Zhu](https://www.nber.org/system/files/working_papers/w20592/w20592.pdf)、[Bailey 等](https://escholarship.org/uc/item/4w1110bb)、[McLean、Pontiff](https://doi.org/10.1111/jofi.12365)及 [Novy-Marx、Velikov](https://www.nber.org/papers/w20721)。上表是本项目的实施路径，具体门槛随任务在看结果前固定。

## 开源工具选型

2026-11-11 静态核查。GitHub Star 为公开关注度快照，发行日期来自 PyPI。下表比较能力和接入工作量，本机安装、运行速度与样本外收益留待选定工具后验证。

| 候选 | 能做什么 | 适合观衡的接入方式 | 关注度、许可与发行 |
|---|---|---|---|
| **gplearn** | 用遗传编程组合已有输入，`SymbolicTransformer` 可输出多条表达式。支持自定义算子、适应度、复杂度惩罚和随机种子。 | 通用遗传编程基线。用独立 Python 环境读取冻结样本，从少量已核验的价量与滚动特征开始。默认相关目标按传入的样本计算，逐日截面评分须由观衡保留日期分组并显式接入。时序切分、交易约束与成本仍由观衡负责。 | 约 1.9k Star，BSD-3-Clause，0.4.3（2026-01-07），要求 Python 3.11+、scikit-learn 1.8+。[仓库](https://github.com/trevorstephens/gplearn) · [API](https://gplearn.readthedocs.io/en/stable/reference.html) · [PyPI](https://pypi.org/project/gplearn/0.4.3/) |
| **PySR** | 符号回归，搜索可读的数学公式，提供复杂度约束及多个复杂度水平的候选。适合比较预测质量和公式长度。 | 适合更灵活的公式搜索。与 gplearn 共用预计算的因果特征和同一评价协议。Julia 是实际搜索后端，按上游说明首次导入会安装 Julia 依赖，需单独固定 Python 与 Julia 运行环境。 | 约 4.3k Star，Apache-2.0，2.7.2（2026-10-19），Python 3.10+。[仓库](https://github.com/astroautomata/PySR) · [作者论文](https://arxiv.org/abs/2305.01582) · [PyPI](https://pypi.org/project/pysr/2.7.2/) |
| **Microsoft RD-Agent** | 用语言模型生成和实现候选，`fin_factor` 迭代因子，`fin_quant` 联合迭代因子和模型，量化示例走 Qlib。 | 适合需要研报提取和批量生成假设的阶段。上游支持 Linux，多数场景要求 Docker，示例还使用对话与嵌入模型。观衡可从隔离环境接收公式和实验产物，固定搜索预算，独立复算并保留封存样本。 | 约 15.3k Star，MIT，1.0.0（2026-09-23），Python 3.10+。[仓库及运行入口](https://github.com/microsoft/RD-Agent) · [作者论文](https://arxiv.org/abs/2505.15155) · [PyPI](https://pypi.org/project/rdagent/1.0.0/) |

### 研究底座和诊断组件

- **Microsoft Qlib** 适合建立股票横截面研究基线。它提供表达式、Alpha158/Alpha360 预定义特征、数据处理和模型实验。上游支持将自有 CSV/Parquet 转为 Qlib `.bin`，需要逐项核对复权、成交额、停牌、交易日历与代码映射。Alpha158 默认标签使用未来两个收盘价，次日开盘执行时需定义观衡自己的标签。仓库约 50.2k Star、MIT，PyPI 的 0.9.7（2025-08-15）提供 Windows x64 CPython 3.10–3.12 wheel。选 Qlib 意味着先统一特征与研究输入，自动生成新表达式需要额外搜索器。其组合回测可用于研究诊断，正式结果由 WT 产生。[仓库](https://github.com/microsoft/qlib) · [数据转换](https://qlib.readthedocs.io/en/latest/component/data.html) · [标签源码](https://github.com/microsoft/qlib/blob/main/qlib/contrib/data/handler.py) · [PyPI](https://pypi.org/project/pyqlib/0.9.7/)
- **Alphalens Reloaded** 适合复核已算好的因子，提供 IC、分组收益、换手和分组诊断。已核源码的便捷接口默认过滤未来收益离群值，底层还会前向填充价格。观衡应直接提供按成交时钟算出的标签和可交易掩码，再用 `get_clean_factor` 做分析。仓库约 685 Star、Apache-2.0，0.5.1（2026-10-26）。[仓库](https://github.com/stefan-jansen/alphalens-reloaded) · [标签处理源码](https://github.com/stefan-jansen/alphalens-reloaded/blob/main/src/alphalens/utils.py) · [PyPI](https://pypi.org/project/alphalens-reloaded/0.5.1/)
- **py-alpha-lib** 是现成公式的计算库。BSD-2-Clause，约 126 Star。其 Python 接口调用 Rust 滚动算子，示例覆盖 Alpha101 和 190 条国泰君安公式。固定源码包含 Alpha144，公式与研报一致，实际缺失、零成交和复权口径仍需按本指引验证。可用作已知因子的复算对照。[仓库](https://github.com/msd-rs/py-alpha-lib) · [Alpha144 源码](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/examples/gtja191/al/alpha191.py) · [许可证](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/LICENSE)

### 专用金融因子搜索与采用证据

- **alpha-foundry** 有实际金融公式搜索入口。固定源码的 `run_gp` 使用 DEAP 强类型遗传编程，从行情面板和预定义算子组合公式。上游也实现了 GFlowNet 搜索、Rank IC 和因子池筛选，声明支持 A 股日线。MIT，约 64 Star。适合验证原生金融算子与截面搜索能否接上 WT 冻结面板。其 C++/OpenMP 计算及 Linux/WSL 构建需要实测，正式撮合沿 WT。参与候选准入的评估区间登记为已观察。[仓库及构建说明](https://github.com/Huang-Hg/alpha-foundry) · [GP 搜索源码](https://github.com/Huang-Hg/alpha-foundry/blob/0a87be0034d93adede9b0621ae02b029a96ad309/search/gp/gp_baseline.py) · [许可证](https://github.com/Huang-Hg/alpha-foundry/blob/0a87be0034d93adede9b0621ae02b029a96ad309/LICENSE)
- **AlphaQCM** 是 ICML 2025 的分布强化学习方法。作者仓库提供沪深 300、中证 500 的训练入口和 CSV 公式池输出，依赖 Qlib/BaoStock，复现环境使用 Python 3.8、PyTorch 1.13.1、CUDA 11.6。约 125 Star，顶层声明 MIT，仓库也明确引用 AlphaGen 的搜索环境。采用前按固定版本核对该部分的来源与许可，研究复现先在独立环境中进行。[论文](https://proceedings.mlr.press/v267/zhu25ag.html) · [作者复现说明](https://github.com/ZhuZhouFan/AlphaQCM/blob/dffc695f9ea54e6a54e4dac86ee357be314fead4/README.md)
- **AlphaGen** 用强化学习搜索一组互补的公式，公开外部 `AlphaCalculator` 接口。**AlphaForge** 用生成模型挖掘公式，再做动态组合。两者均有作者代码和发表论文，约 1.3k 和 444 Star，本次仍未查到明确的顶层项目许可。**QuantaAlpha** 用大模型和演化搜索迭代量价因子，约 1.7k Star，打包元数据声明 MIT，本次未找到独立许可证正文。三者先作为方法和实验设计参考。[AlphaGen 源码](https://github.com/ICT-FinD-Lab/alphagen) · [KDD 论文](https://doi.org/10.1145/3580305.3599831) · [AlphaForge 源码](https://github.com/DulyHao/AlphaForge) · [AAAI 论文](https://ojs.aaai.org/index.php/AAAI/article/view/33365) · [QuantaAlpha 实验入口](https://github.com/QuantaAlpha/QuantaAlpha/blob/b7ceb27b1001261d7a95b209a963664ae1f8ab23/quantaalpha/pipeline/factor_mining.py) · [打包元数据](https://github.com/QuantaAlpha/QuantaAlpha/blob/b7ceb27b1001261d7a95b209a963664ae1f8ab23/pyproject.toml)

公开讨论能提供实际使用线索。RD-Agent 用户报告了既有因子跨轮复用和 Qlib 数据安装问题。ICLR 2026 的 AlphaBench 给出了因子生成、评价与搜索的可执行基准，作者报告大模型直接判断因子质量是较弱环节。社区关注、论文实验、许可证与观衡复现各有独立证据。观衡使用同一冻结输入、相同搜索预算和预注册指标比较候选，保留全量试验记录及封存终测结果。[Reddit 使用讨论](https://www.reddit.com/r/quantfinance/comments/1x66bnr/anyone_working_with_rdagent_in_qlib/) · [因子复用讨论](https://github.com/microsoft/RD-Agent/issues/1310) · [数据问题](https://github.com/microsoft/RD-Agent/issues/1002) · [AlphaBench](https://alphabench.cc/)

选型按第一个实验目标推进。直接试金融公式搜索，可将 **alpha-foundry** 列为优先候选，并用 **gplearn** 建一个通用遗传编程基线。先复现 Alpha144 和已知公式，则选 **py-alpha-lib**。想从研究假设自动生成候选代码，则比较 **RD-Agent** 的 `fin_factor` 工作流。

## 观衡接入与选库后的验收

1. 从 [WT 统一日线与证券资料](../modules/unified-daily-data.md)只读取得同一不可变版本的行情、证券资料、日期范围与缺口。严格时点资格不足时，在实验清单标为历史重建，并记录可用于验证的范围。研究环境中生成按交易日和证券标识对齐的面板，保留版本、单位、原价/分析价、可知时刻和可交易状态。
2. 研究库在独立 Python 环境读取冻结面板，输出表达式或因子值、覆盖统计、试验记录及冻结候选。评估只读候选。策略在选定 WT 接缝消费冻结信号或复现同版本计算。选股先核 WT-S02 及实际宿主接线。WT-B01/B02 负责回放及成交模型，WT-B04 的试参能力可用作策略研究。报告沿[策略开发与回测交付](../development/workflow.md#策略开发与回测交付)和[原生回测手册](../runbooks/native-backtest.md#正式归档的唯一位置)处理。[WT 原生能力目录](../development/wondertrader-capabilities.md)
3. 用户选定库后，核对固定上游 commit 的许可证、附带代码和依赖，再 fork 到确认的 GitHub 命名空间。拟议子模块路径为 `third_party/research/<library>`，用于隔离第三方源码，独立适配留在自有研究代码。最终目录和 `.gitmodules` 的采用随选库确认。父仓库锁定 gitlink 与 fork URL，记录上游 URL、版本、许可证、更新策略。Python 依赖另行锁定。子模块交付以干净克隆可初始化、可复现离线验证为准。[Git submodule 文档](https://git-scm.com/docs/git-submodule)
4. 最小适配验收用同一份冻结输入。先手算核对 Alpha144 的数值和边界，交叉核对 Rank IC 与组内样本，再用明确因果约束、可重放预算与种子跑一轮候选生成或模型训练。截断未来数据、对齐验证期和候选输入，并记录目标 Windows 环境与覆盖。如果库负责自动发现，候选评分使用独立评估入口，封存区间与交易凭据对生成器隔离。正式策略报告另沿 WT 主链验收。
