# 因子研究库 Windows 验证

2026-11-11，北京时间。范围为本机 Windows 11 x64（26200）、i5-13400F、31.8 GiB RAM、Intel Arc B580。以独立环境执行合成输入冒烟，策略研究与正式回测验收见[全链路方案](../specs/factor-research-lifecycle.md)。CPU 研究环境使用 CPython 3.13.14、NumPy 2.2.6、Pandas 3.1.1。Qlib 使用独立 CPython 3.12.13，PySR 使用独立 CPython 3.13.14 及 Julia。alpha-foundry 用独立 CPython 3.13.14 和 PyTorch CPU 版。Docker daemon 停止，本轮使用原生 Windows 执行。

## 安装和实际调用

| 库 | 实际运行证据 | 本轮建议与后续条件 |
|---|---|---|
| **py-alpha-lib 0.4.1** | Windows wheel 可导入。执行固定源码的 Alpha144，显式接入真实金额的合成值后等于手算 `7e-11`，默认 `AMOUNT=vol` 得到 `7e-10`。 | 作为素材来源。复现先确认成交额、缺失、零下跌与多标的分组。 |
| **gplearn 0.4.3** | Windows CPU 的 `SymbolicTransformer` 在 240 行合成输入生成三条公式，最优公式相对已知乘积目标的绝对相关为 1。另一轮输出重复公式。 | 首期轻量搜索基线。显式定义日截面适应度、时序切分和重复候选登记。 |
| **alpha-foundry 0a87be0** | Git Bash 和便携 UCRT MinGW-w64 GCC 16.2.0 构建两份 CPython 3.13 `.pyd`。CPU 入口对 180×64 的合成 OHLCV 跑种子 42、种群 32、两代，产生 7 条有效候选，3 条进入其内部因子池。运行验证 `torch.cuda.is_available()=False` 且未导入 CuPy。 | 可在这台机上跑 CPU 遗传编程。公开 A 股 CLI 缺少数据加载器，真实面板需适配。GPU、GFlowNet、全 A 用量和真实研究结果继续待验。 |
| **PySR 2.7.2** | CPython 3.13 和 Julia 1.13.3。执行 CPU 符号回归拟合 60 点平方样例，输出 `x0*x0`、MSE 0。首次下载 Julia 约 281 MB，Julia 依赖预编译阶段报告 144 秒。 | 可独立作为符号回归扩展。Python 之外需固定 Julia 和 Julia 依赖，记录首次安装及预编译成本。 |
| **Qlib 0.9.7** | CPython 3.12 的 Windows wheel，独立环境装入 193 项依赖。创建 15 日日线合成 provider，实际 `D.features` 读回 14×2 的收盘和滞后收盘，尾行 `[24, 23]`。 | 本机可做数据和特征实验。真实 WT 快照转换、模型训练、全 A 覆盖及运行成本另验。 |
| **TA-Lib 0.8.3** | Windows wheel。80 日单调价格的 RSI(14) 为 100，固定价差输入的 ATR(14) 为 2。 | 首期经典指标计算和数值对照。缺失和预热按定义验证。 |
| **pandas-ta 0.4.71b0、pandas-ta-classic 0.9.0** | 两者各自的 Pandas RSI(14) 都得到 100。原版显式关闭 TA-Lib 后端，并实际解析到 Numba 0.61.2 和 NumPy 2.2.6。 | 使用 Classic 补充表格探索与缺项指标，固定后端和指标定义。 |
| **Tulipy 0.4.0** | 源码构建成功，RSI(14) 为 100，80 项输入返回 66 项。 | 已能运行，保留为数值对照。记录日期对齐、LGPL 许可及重建成本。 |
| **Alphalens Reloaded 0.5.1** | 用三天四股、预先构造的未来收益运行 `get_clean_factor`，12 行全部保留，三日 Rank IC 均为 1。 | 首期作为截面诊断对照。输入用项目按交易时钟生成的标签。 |
| **Pyfolio Reloaded 0.10.2、Empyrical Reloaded 0.7.2** | 用 80 日日收益跑无界面 Pyfolio returns tear sheet，得到 12 个图轴。Empyrical 最大回撤约 -2.6982%，与手算净值一致。 | 用于 WT 归档后的指标复核与扩展图表。 |

Alpha144 合成样例含两次下跌，2% 对应 5 亿元，1% 对应 1 亿元，其余时间价格不变且报价齐全。显式传入元成交额与按股数映射的结果相差十倍。上游在零下跌日窗口除零会出现非有限值警告，采用时需把该原因作为定义的一部分。组合诊断及搜索的合成目标用来验证 API 和执行路径，真实收益需另做样本外和正式 WT 回测。[固定字段映射](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/py-binding/python/alpha/context.py) · [固定 Alpha144](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/examples/gtja191/al/alpha191.py)

## 专用搜索项目的本机限制

- alpha-foundry 固定版默认 `device=cuda`，并启用需要永续合约字段的 crowding 中性化。测试仅在下载的上游副本把 `[evaluator].device` 设为 `cpu`、`[neutralize].neutralize` 设为 `beta`。第一次按默认 CUDA 配置导入失败。先用临时的进程内配置验证 CPU 后发现中性化选项在导入时初始化，随后用上游 INI 入口重新运行成功。正式 WT、QMT 和观衡的配置及解释器属于各自受管环境。[固定 CPU 构建脚本](https://github.com/Huang-Hg/alpha-foundry/blob/0a87be0034d93adede9b0621ae02b029a96ad309/backtest/build.sh) · [配置](https://github.com/Huang-Hg/alpha-foundry/blob/0a87be0034d93adede9b0621ae02b029a96ad309/config/config.ini) · [缺少数据加载器说明](https://github.com/Huang-Hg/alpha-foundry/blob/0a87be0034d93adede9b0621ae02b029a96ad309/README.md)
- AlphaGen、AlphaForge、AlphaQCM 的固定训练入口选择 CUDA。此机没有 NVIDIA CUDA 设备，原训练路径缺少硬件条件。CPU 改造、所需运行时间及结果没有运行证据。QuantaAlpha 需单独配 LLM、Qlib 和预计算行情，留作研究参考。RD-Agent 依用户取舍留到后续。[AlphaGen 入口](https://github.com/ICT-FinD-Lab/alphagen/blob/259687e8f316994426416c530a94842a2fe6405e/scripts/rl.py) · [AlphaForge 入口](https://github.com/DulyHao/AlphaForge/blob/d0cfc27df23c60f271bc885fd43027b86b787746/train_AFF.py) · [AlphaQCM 入口](https://github.com/ZhuZhouFan/AlphaQCM/blob/dffc695f9ea54e6a54e4dac86ee357be314fead4/train_qcm_csi500.py) · [QuantaAlpha 说明](https://github.com/QuantaAlpha/QuantaAlpha/blob/main/docs/experiment_guide.md)
- 基础研究环境最初要求全部使用预构建 wheel。Empyrical Reloaded 0.7.2 依赖 `peewee<3.17.4`，该约束下没有匹配的 wheel。允许在隔离环境内构建 `peewee==3.17.3` 后 53 个包安装成功，`uv pip check` 通过。以后复建优先用受控目录缓存 wheel 和完整依赖锁。

## 本机复验位置

受控实验目录为 `E:/workspace/wondertrader-data/factor-library-windows-20261111-001`。以对应子环境的 `Scripts/python.exe` 执行 `cpu-smoke.py`、`gplearn-search.py`、`qlib-smoke.py` 、`foundry-smoke.py` 和 `pysr-smoke.py`。脚本、输出日志、冻结包版本、固定上游源码与构建材料保留在该目录。alpha-foundry 的构建沿 `backtest/build.sh`，指定便携 UCRT 编译器及目标解释器。PySR 首次安装的 Julia 项目和 Manifest 保留在 `pysr/julia_env`。合成用例及本机编译证据范围独立于真实 WT 数据、正式归档、观衡读回和线上策略资格。

## 指标计算与诊断库的上游口径

以下发行信息来自上游仓库及 PyPI 固定版本的 wheel 或元数据。能取得发行包和在本机运行代表不同验证阶段，本机运行结果以实测记录为准。

| 包 | 适用职责、选择和约束 |
|---|---|
| **TA-Lib 0.8.3** | 优先用于 RSI、ATR、EMA 等经典时序指标的研究计算及数值对照。此版有 CPython 3.13/3.14 Windows x64 wheel，自带 C 库。Python 封装为 BSD-2-Clause，C 核心为 BSD-3-Clause。登记预热、输入中段 NaN 及参数。用分段行情和手算用例核对返回值、时间位置与缺失传播，再决定策略实现采用的口径。[PyPI](https://pypi.org/project/TA-Lib/0.8.3/) · [上游封装与 NaN 示例](https://github.com/TA-Lib/ta-lib-python) · [封装许可](https://github.com/TA-Lib/ta-lib-python/blob/master/LICENSE) · [C 核心许可](https://github.com/TA-Lib/ta-lib/blob/main/LICENSE) |
| **pandas-ta 0.4.71b0 / pandas-ta-classic 0.9.0** | 用于 Pandas 表格里的指标探索。原版 wheel 含 MIT 许可证，版本为 beta，声明 Python 3.12+ 并锁定 Numba 0.61.2，组合实际要求 CPython 3.12/3.13 与 NumPy 2.2.6。Classic 为 MIT 社区维护版本，要求 Python 3.11+、Pandas 2.0+、NumPy 2.0+。其指标默认走原生实现，部分可显式指定 `talib=True`。研究定义固定具体包、版本、参数和后端，验证预热及数值差异，适合补充 TA-Lib 没覆盖的指标。[pandas-ta 发行包](https://pypi.org/project/pandas-ta/0.4.71b0/) · [Numba 支持表](https://numba.readthedocs.io/en/stable/user/installing.html#version-support-information) · [Classic 发行包](https://pypi.org/project/pandas-ta-classic/0.9.0/) · [Classic 安装说明](https://xgboosted.github.io/pandas-ta-classic/installation.html) |
| **Tulipy 0.4.0** | C 指标库的 Python 封装，LGPL-3.0，上游标为非活跃维护。该版 Windows wheel 只覆盖 CPython 3.7，当前 Python 要从源码构建。不同长度输入会按右端对齐并裁剪，输出也可能短于输入。先作为算法对照来源，有独有指标需求时再核构建、许可证和日期对齐。[PyPI](https://pypi.org/project/tulipy/0.4.0/#files) · [上游及对齐示例](https://github.com/cirla/tulipy) |
| **Alphalens Reloaded 0.5.1** | 用于单因子的截面 Rank IC、分组收益、分位换手和因子衰减。Apache-2.0、Python 3.11–3.15。研究代码传入已对齐的因子值、按成交时钟构造的未来收益及覆盖掩码，使用 `get_clean_factor`。该版便捷入口默认按未来收益筛离群值，底层算收益前会前向填充价格。固定分组及并列处理并记录样本剔除。适合做因子评价对照，与本地已有评价输出核对一致后再采用。[PyPI](https://pypi.org/project/alphalens-reloaded/0.5.1/) · [工具源码](https://github.com/stefan-jansen/alphalens-reloaded/blob/main/src/alphalens/utils.py) · [分析文档](https://alphalens.ml4trading.io/) |
| **Pyfolio Reloaded 0.10.2** | 用于在隔离研究环境里读取已完成的组合日收益、日持仓、成交和基准，生成扩展分析图表。Apache-2.0、Python 3.11–3.15。首期沿 WT 和观衡的原报告消费，确有跨策略的额外归因或报告需求时再引入。报告输入从 WT 归档提取，基准、收益频率、费用和持仓口径随报告绑定。[PyPI](https://pypi.org/project/pyfolio-reloaded/0.10.2/) · [报告入口源码](https://github.com/stefan-jansen/pyfolio-reloaded/blob/main/src/pyfolio/tears.py) · [WT 正式回测与归档](../runbooks/native-backtest.md) |
| **Empyrical Reloaded 0.7.2** | 在研究环境对 WT 日收益复核复合年化收益、波动、Sharpe 与最大回撤。Apache-2.0、Python 3.11+。固定年化因子、无风险收益、缺失政策、资金流及已扣费用口径后再比较。Pyfolio Reloaded 与 Alphalens Reloaded 都声明此包为依赖，可复用同一研究环境的版本。[PyPI](https://pypi.org/project/empyrical-reloaded/0.7.2/) · [统计函数源码](https://github.com/stefan-jansen/empyrical-reloaded/blob/main/src/empyrical/stats.py) |

原 Quantopian 的 `alphalens` 0.4.0、`pyfolio` 0.9.2 和 `empyrical` 0.5.5 的 PyPI 最新发行在 2019–2020 年，所列诊断用途采用仍在发布的 Reloaded 版本。两代项目沿用相同导入名，研究依赖清单登记发行名及版本以保证复算。[Alphalens 原版](https://pypi.org/project/alphalens/0.4.0/) · [Pyfolio 原版](https://pypi.org/project/pyfolio/0.9.2/) · [Empyrical 原版](https://pypi.org/project/empyrical/0.5.5/)
