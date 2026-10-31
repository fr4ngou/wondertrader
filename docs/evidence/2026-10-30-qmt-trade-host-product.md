# 独立 QMT 交易通信产品验收

日期：2026-10-30。范围：[THP](../specs/qmt-trade-host-product.md) 的独立安装、正式配对与 CLI、WT 父端生命周期、同源认证接续。当前为 SDK 替身开发证据，真实 QMT/真实委托/现场切换分别记录。

## 根因与实现

原交易 runtime 工厂已经具备查询、命令、Journal 和事件能力；部署流程由 QA 外层组装，缺少安装后的正式常驻产品入口。原单代业务 owner 与运输退出绑定，下一认证代际需要保留原业务身份及未确认责任。

新增 trade_cli/pair/product/control/resident/source 和 WT trade_host_process，复用原运行与进程 owner。SourceTradingService 只构造一次，SDK 仍由原策略线程调用。原唯一通信库按显式模式追加认证关系，原事件/命令/创世 binding 和历史来源证明保持；默认入口沿原严格模式。

已保留旧代未确认交接时，借用连接的最终关闭先完成原运输资源退休，长期 owner 如实报告 business unconfirmed。该处理修正在新 reconnecting_trade 模块；WT 框架及原 trade_service 逻辑保持。

## 实际主链

原始材料位于 `build/qmt-trade-host-product-001`，每轮使用独立目录。安装源、wheel、解释器/DLL、SDK 标准库原件、私有配对和完整 QA 依赖分别按 SHA 绑定。产品不经源码仓 sys.path 导入，无观衡安装。

| 原始证据 | 实际结果与资格 |
|---|---|
| main008、control-main008 | installation007 普通安装；Host 等待65秒才启动来源；真实 Windows SHM、实际 Python3.6.8 完整正文；同服务/session 两代认证；账户/持仓/订单/成交各查两次，单笔下单→原命令查询→撤单，事件1/2原身份；正常业务与物理关闭 |
| lost004、control-lost004 | 同007；SDK执行后切断原回复，Host unknown 记录和原envelope保持；再次提交原命令不产生第二次SDK调用，未ACK事件跨代取回；transport关闭，business_closed=false/handoff_unconfirmed=true 如实保留 |
| combined003、control-combined003 | 同007；正式 pair --market-config、verify逐字重建，实际3.6运行99模块完整三owner正文；唯一timer/一次账户订阅/一次行情订阅退订/交易优先tick；正常关闭。无认证Host和业务请求，此证据只授组合材料与源端生命周期 |
| relocation002、main007 | 006角色wheel制品ZIP复制后离线新根普通安装，实际完整交易主链；后继修正按最终新安装另补delta，006原件保持 |

上述实际源端文件/网络禁止计数为0，SDK调用均在原策略线程；真实账户委托和撤单次数为0。外层与嵌套创建期Job、进程树归零、管道双EOF、读取线程join和句柄关闭分别保存原收据。

组合静态异常使用单独的新配对材料：先verify成功，再修改策略正文，verify返回2且未创建Journal。原正常配对及before/after身份保持。连续模式回归覆盖旧默认拒绝新库、原绑定默认严格、来源不符/旧代复活拒绝、旧事件重复、新后缀证明、ACK前沿、容量事务和原截止。

## 默认行为与剩余范围

源端83项回归、原只读重连28项回归通过，输出为 FINAL-SOURCE-REGRESSIONS.txt 和 FINAL-READ-REGRESSIONS.txt；SOURCE-CLOSE-REGRESSION.txt 覆盖新owner的旧交接未确认退出根因。事件/Journal/订单关联108项及新增接续9项原始输出保留。产品私有组合材料测试覆盖默认形状、JSON秘密角色及禁止QMT IPC与外部HTTP身份混用。

失败原件 main001/002/003、lost001/003、combined001/002、relocate001均保留。前置夹具与安装工具问题按实际原因修正；lost003揭示新owner退出责任边界并由本轮代码与重现条件覆盖。失败原件不授通过资格。

独立审查、最终离线安装及源码/wheel/配置精确身份由本模块 build 根最终 DELIVERY 收据关联。公共 WRI 联合数据/历史/交易/执行、真实来源和生产发布由系统集成者核对，单模块证据不授全系统实盘资格。
