# 自有执行器持续运行与原账接续

类型：验证记录。状态：原生SDK主链及身份回归通过；日常服务工具与现场切换继续验收。范围见[WT服务控制规格](../specs/wt-service-control.md)。本次改动属于自有Python运行层和GuanhengCtaRuntime，WonderTrader框架源码保持原样。

## 问题与实现

原自有执行器仅接受1000..86400000毫秒的运行预算，有限时长到期即进入关闭流程。长期自动运行需要显式选择持续运行；运行时长变化也需要在原账恢复中与账户、模型及资金目录分别处理。

Python配置边界与Native入口均增加`run_ms=0`，持续运行到原停止请求；正数保持原语义。恢复比较只排除经过校验的运行时长，保留全部其他业务字段比较、原配置SHA、前代关闭/故障及金融原件核查。库存准备的模型投影取自已绑定原件，沿用原BASELINE身份；本代实际执行预算保持本代值，历史基准文件不改写。

## 原生调用链

固定SDK来源夹具使用此前已接收的独立源码快照。调用链为独立安装Python监督进程、真实GuanhengCtaRuntime、原CTA及股票执行器、真实WinSHM运输、显式SYNTHETIC券商SDK替身；不连接实际QMT账户。

QA根为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/continuous-runtime`。最终主链目录为`sdk-finite-to-continuous-003`；启动入口`run_sdk_finite_to_continuous003.py`，实际退出码0。

- 首代运行预算70000ms，正常启动、计算、停止并生成实际关闭收据。
- 后继预算0，通过原`prepare_transition`和Native接续同一金融目录；INIT时现金、五项持仓、资本基准、费用及策略记忆保持连续，没有重新初始化资金。
- 后继1.1.2计算沿标准执行器实际产生2笔SDK替身委托；实际券商调用0。
- 两代均正常关闭，Native退出0，子树及输出读取已回收。

Native候选SHA256为`de635108efc06fa2f0fbab99bb4004619f453692aaa2df53bbf09aecf1b9b950`。仅重编自有`CtaProcess.cpp`，WT链接输入沿原冻结安装。Python主链使用`0.1.0a12+integrated.2.market.35.2`，保持35.1固定包，仅替换持续运行相关的两份源码。后续库存投影修正通过下述定向回归验证，最终服务候选另记录其完整制品身份。

SDK夹具使用明确的模拟时钟和SYNTHETIC现金观察；旧静态观察时点过期时，在本次专用模拟目录生成新观察时间，金额保持原值。该处理只属于夹具输入，不改变实际来源时间或生产新鲜度校验。此前失败尝试及原件保留于QA根，不作为通过证据。

## 身份回归与当前边界

`BUSINESS-COMPATIBILITY.json`使用正式配置只读副本，证明有限预算可切换为0，修改资金目录、策略模型或使用非法时长仍拒绝。`INVENTORY-ORIGIN-REGRESSION.json`使用正式已绑定原件，复现旧准备投影会改变身份，修正后投影身份保持且执行预算仍为0；实际BASELINE未修改。

永久回归为`tests/integration/wt_runtime/test_execution_business_identity.py`，三项通过：有限与持续双向切换保留原模型哈希；账户与资金目录变化拒绝；物化配置只改变时长以及非法时长拒绝。该测试覆盖投影与比较，原生启动、接续、计算和停止由上述实际SDK链证明。

本记录不证明现场已采用新Native或完成新一笔券商交易。现场旧实例继续运行；最终服务工具、观衡当前代读取、现场正常重启及真实自然行情计算分别记录实际结果。
