# 因子素材目录

本目录保存外部公式、算子、研究假设及实现来源。每个素材使用稳定标识，记录许可、可用字段、适用范围和与本项目的验证关联。应用状态按具体因子版本及实验记录确认。使用步骤见[因子研究全链路方案](../specs/factor-research-lifecycle.md)。

## py-alpha-lib

- 素材源标识 `py-alpha-lib`。本次登记源码为 `7e8edd41912db08360c31667fb8cb2f94b62f344`，源码仓库顶层 BSD-2-Clause。Windows 测试的 wheel 和结果见[本机验证](../evidence/2026-11-11-factor-library-windows.md)。[上游仓库](https://github.com/msd-rs/py-alpha-lib) · [固定许可证](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/LICENSE)
- 素材范围为股票量价公式及滚动算子。仓库示例声明可计算 190 条国泰君安因子及 WorldQuant Alpha101。每条公式单独核对依赖字段、运算轴、单位、交易日历和缺失语义后再进入因子定义。原始研报、上游实现和本项目验证按各自身份保存。[国泰君安实现目录](https://github.com/msd-rs/py-alpha-lib/tree/7e8edd41912db08360c31667fb8cb2f94b62f344/examples/gtja191) · [WorldQuant 公式原文](https://arxiv.org/abs/1601.00991)

### 首个条目 GTJA Alpha144

| 项 | 记录 |
|---|---|
| 素材 ID | `gtja.alpha144` |
| 来源 | 李辰、刘富兵，《基于短周期价量特征的多因子选股体系》，2017-06-15，附录第 15 页。固定 py-alpha-lib 的 `alpha_144` 是复算来源。 |
| 公式 | 对单只股票近 20 日内的下跌日，求绝对日收益除以当日成交额后的均值。 |
| 输入与解释 | 同源复权收盘价、已核单位为元的原始成交额、交易日历与缺失状态。值越高表示下跌时单位成交额对应的跌幅越大。 |
| 首轮验收 | 同一输入复核手算、上游和自有结果，记录零下跌日、零成交、停牌、缺日和复权差异。随后比较成交额、跌幅及规模匹配基线。 |
| 当前状态 | 已登记为研究素材。正式因子定义和真实数据效果待沿对应实验验证。 |

固定上游 `ExecContext` 将 `AMOUNT` 映射到 `vol`。合成样例已分别执行默认映射和显式金额映射。默认结果为 `7e-10`，显式传入以元计的成交额后得到手算的 `7e-11`。本项目复用时保留真实成交额字段，独立验证运算轴及缺失语义。[上游字段映射源码](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/py-binding/python/alpha/context.py) · [本机样例](../evidence/2026-11-11-factor-library-windows.md)

[固定 Alpha144 实现](https://github.com/msd-rs/py-alpha-lib/blob/7e8edd41912db08360c31667fb8cb2f94b62f344/examples/gtja191/al/alpha191.py) · [研报与方法](2026-11-11-factor-research-workflow.md#alpha144-的定义与待核口径)
