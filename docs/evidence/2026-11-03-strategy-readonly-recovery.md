# 策略只读边界、原资金恢复与持续行情候选

类型：验证记录。日期：2026-11-03。状态：候选主路径已启动；自然行情计算、统一采用及页面资格分别登记。范围：原1.1.2/NSQ模型、模拟账户当前基准和自有接入/执行适配，WT框架与外部金融写权限保持。

## 根因与实现

原只读交易开关约束外部Trader，策略target setter仍会推进WT理论账。Retained从同一交易开关派生空execution_symbols，Python和Native两层拒绝目标提交；允许计算和资金观察，发布observing/analysis_only，NSQ执行状态保持。原价使用WT已应用tick的不可变副本，原日线读取改变CTX缓存时仍保留真实报价和原事件时点。现金沿WT成本、已实现盈亏和费用读取，浮点表示残差限制为1e-8 CNY。

保留结果的Parser在未决续核期间保留原请求/结果与ACK身份；只对明确网络故障、429和500/502/503续核，鉴权、协议和会话身份冲突锁存原错误。异常关闭、进程丢失、正常关闭及显式原件恢复分别准入；契约见[执行故障恢复](../specs/execution-fault-recovery.md)。

27初始化失败的直接原因是恢复时选用了缺少publication能力的早期Reader。当前原版native-008构建支持原日线发布及分钟读取，最终实现沿用其原源码。27成功准入后在ready前退出，原clean已经消费；EFR-20沿其真实failure/close-prepared/reconciled核进程退出和状态逐字节未变，以原已接收状态owner解释KV，保留最新前代故障身份。

## 可复现材料与当前证据

受控候选根：`E:/workspace/wondertrader-qa/strategy-capital-handoff-20261102-001/strategy-live-021`。原金融/账户原件留在受控运行目录，仓库只记录校验结论。

- `READONLY-REGRESSION.json`：完整策略callback只读零setter，启用执行正对照一次setter；日线缓存变化不能替代已应用tick，INIT已有NSQ状态保持。
- `READONLY-GRANT-ABI.json`：实际Native接受空读取专用执行集合及原非空授权；布局1..8保持，Python只读目标入口拒绝提交。
- `STATUS-REGRESSION.json`：实际Native HTTP层验证500/502/503及401/403/409/400、协议和会话冲突分类；原两项Endpoint审查问题已关闭。
- `ORIGINAL-READER-REGRESSION.json`：原版Reader SHA `3fb74cd68c110461013881dca712682f7e028ec979d486d5572c0cd52cd96fd3`，8标的日线均非空、分钟读取各1根。
- `INITIALIZATION-ABORT-REGRESSION.json`：原27合法材料通过，状态/引用变化、ready冲突、成功关闭冲突、存活PID及consumed关闭/安装身份冲突均拒绝。
- 原23理论账错误结果与原clean保留归档，外部正式Host交易命令表为0。原20三份金融/用户文件逐字节找回；25实际restored_snapshot接收，26从25正常clean接续。28实际initialization_abort_reconciled接收未变原状态，并正常关闭产生本代clean。
- 29使用最终Python `0.1.0a12+integrated.2.market.21.12` 与Native `5f5045cf273e611b1d47b4cedeb077bcfe0aa2af59de9e7aa99bac68bf3461bf`，已从28真实正常clean启动。初始5周期、现金/可用633075.2元，目标setter与正式交易命令计数均0；INIT保留原估值日期，不冒充当前决策。
- `APP-PROJECTION-28.json`：实际App解释器动态加载两个候选投影，读取真实28资金；合成observing支持与分币实际误差拒绝分别验证。正在运行的Web配置保持。

两轴独立审查：`SPEC-REVIEW-021.md`、`STANDARDS-REVIEW-021.md`，当前已报告P2均修正。29主路径、自然计算和正常关闭范围继续按实际原件追加。

13:06后继实证：`NATURAL-CALCULATION-29.json`记录原1.1.2自然事件计算，decision_cutoff为11月3日13:06:00.587046北京时间，闭合日11月2日，原价事件13:05:55.627。多轮计算保持observing/analysis_only、outcome=null、原5周期和现金633075.2，Native setter与正式Host交易命令计数0，费用/已实现盈亏0。`APP-PROJECTION-29.json`使用真实observing结果通过两个候选App投影，原资金保持；1e-12表示残差和数值格式合法的实际一分误差分别验证。

原历史units为price=CNY、volume=lot、amount=unknown，CoreResult原source_qualified=false/execution_qualified=false保持。因此本轮证明真实只读计算及恢复链，成交额单位资格仍由来源owner核准。

29随后正常关闭，原closed.v2的closed/ok/recovery_ready/resources_closed均true、exit_code=0，原clean绑定本代状态。`MODEL-BINDING-REGRESSION.json`拒绝纯模型、解释器、输入和金融权限变化。完整WRI后继Full30已沿29真实clean冻结并通过RuntimeConfig读取校验，仅准备、尚未启动；账户24全程保持运行。Root采用时沿`PREPARED-full30.json`和原运行/停止协议统一切换。

## 限制与后继

账户24四组件持续ready，独立策略实例不拥有其生命周期。QMT图表保持关闭。共享源码、Git集成、完整WRI后继采用及App页面验收由统一集成主会话处理；本记录不授页面上线资格。

`python -B scripts/project.py check`仍报告工作树既有30份未索引文档，名单与本轮前置检查相同；该检查不证明实际页面或运行调用链。
