# 2026-10-25 未知委托源端准入与关闭

类型：限定验证记录。关联[UC-R1/R2/R6/R9A](../specs/qmt-unknown-cancel.md)。源端实现与独立静态审查完成；完整未知委托取消、Host后继、C++接线和生产恢复继续开发。

## 根因与实现

未知调用、硬故障和生命周期分别保存。unknown只关闭新增insert；具体取消继续核原配置、当前来源、真实目标证明及容量，硬故障或关闭仍拒绝。源端输出显式status.v2，原profile及通信身份保持。

两项根因修正位于自有Agent：已存未知事实且真正CALL回复确认后，实际资源可排空；SDK进入前，事件缺口发布与唯一调用预留共用短锁，预留和SDK实际进入分别记录。SDK与外部回调均在锁外执行。借用、未确认CALL、晚回报或真实gap仍阻止虚假完成。

## 实际验证

所有测试在冻结源码中、隐藏且原截止的进程内执行。SDK为替身，没有连接或重启国信QMT，也没有真实下单或撤单。

| 原件 | 实际结果 | 使用范围 |
| --- | --- | --- |
| source-pure-001 / source-sdk-pure-001 | 各73/73通过 | 修正前初始实现；不作为最终根因回归资格 |
| source-full-002 | Python3.12，211执行，210通过、1 ERROR，0skip | ERROR仅为default-off测试没有发送真实ACK回合的Agent空回复；失败原件保留 |
| source-integration-003 | 修正该测试后1/1通过，0skip | 产品代码保持source revision002；实际ControlPeer完成原ACK往返 |
| source-sdk-full-002 | 目标Python3.6.8，186/186通过，0skip | 12组Agent模块；同一最终产品及fixture003，未含三个Host相关验证/生成模块 |
| unknown-cancel-memory-001 | 目标3.6.8完整生成策略通过，91嵌入模块，文件/外部导入尝试0 | 正常写配置、下撤单替身、四回报确认与关闭；运输启动替身，无QMT会话 |

Python3.12最终覆盖由full-002的210项与integration-003的一项组成，未把failed批次改写为整批通过。Python3.6.8使用独立目标解释器，结果证明兼容性和替身调用链，完整生成正文另在禁用文件入口和外部导入的目标解释器中通过；真实终端安装、真实SDK和C++组合另验。

独立full原两项P2在revision002 delta关闭；根修fixture003仅增加ACK后的实际反向发送，独审delta确认其余断言保持。15份最终源/测试原件与26项最终审查输入由根逐字节核对。初次七次已登记受控执行（含文档检查及Host旧D反证）均实际tree0、stdout/stderr EOF、reader joined、资源关闭，无强制终止；失败结果原样保留。

## 身份与限制

最终代码封存：build/guanheng-workspace/qmt-unknown-cancel-source-final-001/SOURCES-ROOT-VERIFIED.json。六个Agent文件按source revision002身份固定，test_trading_agent.py为6aa62bd3d10c020ced0f7ec75d61a668bccfbe619e842abc708fc3afbdf8d24f。动态原件在同级source-full-002、source-integration-003、source-sdk-full-002等目录；独立审查为build/qmt-unknown-cancel-source-review-001的FULL-REVIEW、REVISION-002-DELTA-REVIEW及REVISION-003-FIXTURE-DELTA。

Host revision002当时完整219项为215通过、4 ERROR，包含三个测试数据错误及一个写门关闭领取竞态；该失败原件保持，后继修正及221项组合结果见[Host证据](2026-10-25-qmt-unknown-cancel-host.md)。C++未知核查/取消尚未接入。Journal原unknown持续关闭新insert，一般恢复解除契约尚未闭合。生产Factory保持原值，event_consumption_complete=0，整体迁移目标active。未新增WT框架修改，旧QMT项目未执行或修改。

后继完整内存探针位于build/guanheng-workspace/qmt-unknown-cancel-memory-001；读取固定source-integration-003/frozen源码，外部生成完整正文，目标执行前禁用builtins.open、_io.open/FileIO及非builtin导入。v2 schema及三个独立准入事实实际断言通过；源码包哈希与生成探针字节由根核同。两次生成/运行控制器均创建期Job、无控制台、tree0/EOF/资源关闭。该探针保留正常SDK替身2次、Kernel替身2次，真实SDK0；运输start为替身，未授真实SHM或终端写资格。
