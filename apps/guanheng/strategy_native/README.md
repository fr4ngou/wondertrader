# 观衡原生策略数量阶段

`guanheng-strategy-native` 是独立 Python 3.12 标准库包，版本 `0.1.0a2`。唯一推进入口为 `advance`；`generation_id` 与 `target_quantities` 提供可单独核验的身份及精确数量计算。依据 NSQ-R1–R6 与 NSK，当前范围为纯计算、冻结阶段及恢复值验证。

## 事实所有者与原生接缝

WT-S01、WT-S05、WT-B01/B02 对应固定 WT `08b230dd05facf6d650d949bfe51054115a2ecb1` 的 CTA 上下文、CtaMocker、理论持仓/目标和撮合输出。原生继续拥有 actual、pending、成交、现金及损益。本包补充既有 configured 策略特有的经济代际与分阶段数量冻结；不保留旧数据库、委托腿、账本、独立撮合或 wtpy。

本包没有原生 binding，也不执行 HTTP、文件、线程、柜台、下载或订阅。后续宿主取得原生实际量、可卖及 pending 的独立观察后调用本包；宿主还须证明 NSQ-R4/NSK 的全向量预校验、提交、回读、partial 失败隔离和恢复准入。`verified=True` 是调用者关于来源的明确资格声明，来源证据由宿主提供；字段存在本身不证明原生接口已通过实验。

## 稳定身份与资本

首 policy ID 为 `cash-etf-generation-sell-postsell-v1`，profile 为 `cash-etf-cny-share-m1-l100-v1`。数量单位是份，金额乘数1，整手100，价格是未复权的 `CNY/share`。profile 不支持期货、杠杆、账户总资产、复权执行价或其他手数。

`QuantityPolicy` 必填 `initial_capital_cny` 与 `capital_source`。`Basis` 必填原生策略 `nav_cny`、`native_pnl_cny` 及来源；每次核 `NAV = 初始本金 + native flag0 PnL`，包括亏损与零 NAV。`native_nav_verified` 的含义是宿主已核无外部资金流、原生费用及持仓覆盖。这里使用显式研究参数，不设置默认本金。现金是同一时点的原生策略现金估值；全组新增买入费用由显式 `fee_reserve_cny/fee_source` 给出。

`EconomicTarget` 包含 strategy、algorithm、stable config、execution policy、原 allocation date、完整 execution universe 与含零权重的完整向量。stable config 身份须绑定版本、八角色及 signal/execution 映射的完整不可变语义；本模块验证 execution 集合完整且唯一，角色映射由业务核准入。`generation_id(target, policy)` 绑定这些经济值及稳定 quantity policy/profile/本金来源；每日 input SHA、来源更新、价格、NAV、现金、观察时点与部署预算留在独立 basis/观察中。

权重按排序的证券与规范化精确十进制计算身份，`0.5`、`0.500`、`5e-1` 等价。A→B→A 的不同 allocation date 产生三个身份。无 allocation date 的全零是 `initializing`，无 state/提交向量；带日期的全零是有效清仓目标。正权重无 allocation date 拒绝。

## 公共输入及推进

所有集合使用 tuple，证券标识为大写规范化执行 ID。证券集合为1–8个，调用者传完整配置集合。`Weight`、`Price`、`NativePosition` 等 dataclass 均 frozen/slots，嵌套值经过类型校验且不保留可变容器。金额、价格、权重接受十进制字符串、精确 int 或 `Decimal`，拒绝 float/bool；字符串需显式前导整数位（例如 `0.5`）。Decimal 先做有界表示准入；计算使用精确有理数和整数 floor，不使用 Decimal 算术上下文。

`Basis.observed_at` 与 `Observation.observed_at` 使用带时区 ISO 原生事实时点，并要求规范化后相同；两者还须携带相同的 `native_observation_id`，标识宿主核实过的一次 coherent 原生 capture。basis 中每个 raw 价格与 NAV/现金/费用均属于该次同步观察，独立 `input_sha256` 保留本次计算输入。观察身份须由真实原生采集事实给出，不能用本机 wallclock、伪造微秒或每日 input SHA 冒充。价格行完整覆盖 universe，零权重可用 `None` 缺价；正权重缺价拒绝。费用 `None` 保持未知并等待，显式零预留需要来源。

`NativePosition.actual` 是当次真实理论量，`sellable` 是当次资格，`pending_target` 是未解决的绝对理论目标。三者不得用同一个含 pending 的 get_position 回显填充。数量均为0至 `2**53-1` 的精确 int；可卖不能超过 actual。模块允许阶段范围内的整数部分进展；不会把非整手 actual 擅自向下取整。

`advance` 根据当前事实推进，输入不合格抛 `QuantityError`。有冻结 state 时等待/冲突保留该对象；本函数无副作用，异常也不改变原值。

1. 首次合格代际用当前 basis 算完整 `Q=100*floor(weight*NAV/raw_price/100)`。有非零卖差时才进入 `selling`，冻结 `min(actual,Q)` 的卖出向量。全组所需可卖不足时 `waiting_sellable`，本次提交向量为空；该阶段价格/NAV 漂移保持原目标。
2. 真实卖出阶段 actual 全部达到冻结向量，且全部 pending 已解决后，要求新的 coherent native capture，时点不能早于冻结 basis；同一原生时钟的新合格 capture 可以推进。重复旧 capture 返回 `waiting_basis`，每日 input SHA 改变不会使它变新。若新 Q 低于现存 actual，冻结残余卖出；完成后再取新 capture/basis。
3. 首次没有任何卖差时，尚未发生本代际卖出与费用，直接用同一 coherent basis 判断买入，无需等待下一回调或虚构新的时点。费用/现金不足时保留 `awaiting_buy` 状态及原代际，sequence为0；它明确表示没有需要结算的卖出阶段。恢复时若新 Q 已低于现存 actual，则按统一规则冻结真实卖出阶段。
4. 没有残余卖出时，全组新增买入名义额加显式费用预留须小于等于同 basis 现金。未知费用返回 `waiting_fee`；不足返回 `waiting_cash`；均保留原 state。整组一次冻结，不缩权重，不分证券抢余额。
5. 买入向量冻结后返回 `buying`，在允许范围内的部分 actual 保持冻结量；全部 actual 到达且 pending 为空后 `converged`。此后每日新输入/价格/NAV/现金变化均复用同代际冻结量。当前现金、原生费用及实际写入资格仍由宿主执行边界核对。
6. pending 等于冻结目标返回 `waiting_pending`，即使 actual 回显与目标相等也不确认成交；pending 冲突返回 `blocked/native_pending_conflict`。actual 超出阶段冻结范围返回 `blocked/actual_outside_frozen_stage`。
7. 新代际由同一 `advance` 核对旧冻结阶段。actual全部到达且pending为空时，已结清卖出或尚未提交买入的等待阶段可接纳最新目标；卖出结清须使用新的原生capture。旧阶段尚有未决或实际未到目标时，继续该阶段；universe改变返回显式交接要求。运行和报告均只使用本次消费目标的费用basis，原冻结阶段另存诊断，不计算过期买入。

`Outcome.submit_targets` 非空仅表示本次纯阶段判定允许宿主考虑整向量；它不表示已经提交或成交。同一 state/观察重复调用输出一致，宿主须在每次推进前刷新 actual/pending；不能将重复纯输出解释为新命令身份。

## 恢复与预算

`StageState` 绑定版本1、target、policy、冻结 basis、sequence、starts 与 targets。`starts` 是冻结时点数量快照，用于该阶段允许范围和可重现决策，不累计成交或更新持仓。恢复应从完整冻结输入构造同一组不可变值；构造器重新计算并核卖出向量、买入向量及冻结现金资格。`state_id` 绑定全部内容，`generation_id` 继续只绑定经济值。受管宿主须在启动 native 前校验来源/配置/版本/状态身份；本包未定义新的持久化 owner 或 JSON 文件格式。

资源预算 `Limits` 只限制输入文本量（默认16384字符，最多65536），数值和证券行沿原有边界准入。阶段序号只用于诊断，16次、64次及跨日继续均沿同一业务逻辑推进。每次调用只处理当前观察及一个不可变状态，保持最多8行的纯计算，不积累历史状态链。运行接缝在已结清旧阶段收到新经济目标时，从本次实际观察建立新计划；未决委托及实际数量未到冻结目标时保留原计划。旧报告单独按其原模型只读复核，新回测显式记录数量模型身份。

## 安装与验证

构建仅用锁定 `flit_core==3.12.0`，运行依赖为空。源码来源及固定旧源摘要见随 wheel 安装的 `guanheng_strategy_native/source_manifest.json`。所有测试使用合成值，主入口为：

```text
python -B -m unittest discover -s tests/integration/strategy_quantities -v
```

应在隔离 wheel 安装环境运行，并从包外目录启动；开发源路径不进入 Python 搜索路径。验证覆盖 NSQ-R1–R6、200个独立整数参考向量、同代际漂移、A→B→A、dated/initial zero、费用跨整手残余卖出、现金/费用等待恢复、T+1、pending/actual 区分、冻结状态重建、不可变性和数值/容量拒绝。实际命令与结果保存在本次构建证据目录。

当前纯转换通过不授实际 BT/CTA 成交、原生提交/恢复、HTTP/页面、真实行情、账户或生产资格。固定原生 `get_all_position/get_position` 的 pending 覆盖、void setter 和撤销限制由另行原生实验核实；本包没有猜测这些接口能力。
