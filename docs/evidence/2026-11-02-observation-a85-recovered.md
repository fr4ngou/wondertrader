# 独立市场更新角色a85实际恢复

类型：故障修复及新发行实际恢复证据。日期：2026-11-02。状态：新代运行，原失败代保留。

## 缺陷与正确实现

原a84于11:02退出，只保留通用scheduler失败。正式安装与完整服务失效链均已复现一项确定缺陷：Windows合法读者持有旧状态时，心跳的`os.replace`报PermissionError/13/WinError5，调度退出；旧状态保持完整，随后stopped仍可能发布。原现场底层异常已丢失，其唯一触发原因继续为unknown。

存储层完整写入流程现统一复用已有`replace_readable_file`。Windows使用原ReplaceFileW语义，首发和其他平台保持原契约；合法读者继续读旧完整值，后继读者读新值。真正拒绝仍失败，沿原Owner终结。服务另记录有限的类型、OS码和自有代码位置，保持原failure模式；异常正文、凭据和来源响应不进入诊断。

三个文件按CAS接收，源提交`af6a95553efb626972a680219fa2697dfcab2bfb`。75项受影响回归通过，两轴无未闭合发现；原服务/调度红绿链、非共享读者拒绝及原Supervisor/Job正常关闭分别有原件。本次没有WT框架改动。

## 实际恢复

从干净主干离线构建`0.1.0a85+update.1`，六个永久Python项目及原前端构建成功，普通新目录安装完成。实际安装的storage/service两文件与接收源码逐字相同。App发行包含新的Web维护工具，但本次只启用指标更新角色；观衡18143继续a84，WT18142及原18141保持原进程。

新更新目录`a85-update-20261102-001`沿原外部数据根、原27来源、原私有行情绑定、原时间与请求/字节预算启动。监督者38084、子61324已取得ready；PID以当前控制回执为准。保留旧失败控制代及16份基线文件的逐字摘要。

实际运行中用合法句柄持续持有旧`scheduler-status.json`，新心跳在11:38:40、42、44、46连续推进，原句柄仍读到旧完整正文。a84观衡公开updates接口读到enabled/running，生产新代没有failure或diagnostic。

实际维护status再次确认父子运行、phase=waiting；current仍为05cd，11月2日09:00已完成窗口、attempts及12次来源运行记录逐项保持，新增定时尝试0。既有数据与窗口去重接续正常。该证据证明当前恢复和有限时段持续心跳；27来源的下一自然窗口及各来源后继成功率继续按真实记录判断。

Root没有QMT/SHM调用或下撤单操作。策略资金、模拟交易和账户新发布仍分别继续；本次恢复不授予完整交易资格。

## 固定原件

- 独立候选：`E:/workspace/wondertrader-qa/observation-owner-failure-20261102-001/INTERFACE-001.json`，SHA `1e905e630876fa2868bf0b73cc3135a3ed355add4556d192a9e0e22f6d0d5d17`。
- 稳定交付：`E:/workspace/wondertrader-qa/root-observation-a85-update-001/DELIVERY-001.json`，SHA `45896fec55629b105564b1dfa377b86dfc796016e0589aeec03eafe513e1e758`，包含12项文件。
- ZIP SHA：`36853d31fe683b7fa962a68353510fb5bb1243a7849c8b0f41c6b8ee57576c90`；普通安装收据SHA：`bb2bc58352d941bbc8b4e42d7953a74d361cb06b58a704c1a92014c82b9bebab`。
- 实际恢复、心跳和窗口原件：同交付目录的`A85-OWNER-ACTIVATED-001.json`、`A85-RECOVERY-VERIFIED-001.json`和`A85-ACTUAL-STATUS-001.json`。

安装器实际exit0；外层记录脚本首次将多行输出整体解析为JSON而报错，随后核最后一条JSON及实际安装收据确认完成，未重复安装。相关记录保存在`A85-INSTALL-ENVELOPE-001.json`。

本记录接续[受管Web验收](2026-11-02-observer-a84-web-controlled.md)中的更新故障，后者保留当时事实。操作与回退沿[新角色发布记录](../releases/2026-11-02-observation-a85-update.md)。
