# 正式标准插件与查询优先运行组件主路径

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-27。状态：正向开发调用链通过，完整模块及生产资格继续。依据 [STQ-P10](../specs/native-qmt-standard-trader.md)。

## 改动与事实所有者

新增正式可选 CMake 产品入口及 StandardTargets 正常源码清单，输出 TraderQMTStandard.dll。原 StandardFactory/StandardQmtTrader 保持唯一实现，旧Factory不变。新增 BrokerQueryAdapter/BrokerQueryLocalExecuter 运行组件，完整ORDER只读投影和整次提交门由自有扩展承担；WT继续拥有持仓、执行拆单、原委托身份、通知和统计。持仓使用此前获批的position_by_query，未新增WT核心修改。源端仍在共享内存上通信，QMT内部无新增文件或网络入口。

## 输入与构建

实际独占构建根 `build/sp-001`，固定上游为 `build/sg-002/composed`（原08b230dd基线加此前批准的持仓两文件差异），未带入当前树冻结的其他框架差异。自有快照247文件及上游343文件后核均无变化；当前源码与最终覆盖见 SOURCE-IDENTITY-004（外部历史/待归仓路径：`../../build/sp-001/SOURCE-IDENTITY-004.json`） 和 POSTFLIGHT-FINAL（外部历史/待归仓路径：`../../build/sp-001/POSTFLIGHT-FINAL.json`）。

首编译因新组件头未先包含boost noncopyable而失败；仅补自有头的显式依赖，首日志保留在build-001.log。后继产品及主路径驱动编译退出0；随后只增加活动ORDER主路径验证，增量编译退出0；最后显式禁止复制拥有原生资源的Context对象，最终版本编译退出0（约9.94秒）。正常DLL无测试宏；实际制品SHA见 BUILD-RESULT-004（外部历史/待归仓路径：`../../build/sp-001/BUILD-RESULT-004.json`）。

## 实际正向链

正式模块装载 → 原Adapter.init/run → P/O/D/A四查询 → 产品Context/Local → 原WT buy/委托身份 → 真实签名HTTP外部Host/WinSHM/源服务 → SDK替身 → 四次真实ORDER刷新 → 正常release/Factory delete。HTTP属于QMT外部Host，QMT内部通信仍为命名共享内存。

最终三案实际约13.00秒，进程退出0，结果见 RESULT（外部历史/待归仓路径：`../../build/sp-001/main-003/RESULT.json`）：

| 场景 | 原查询总数 | SDK替身提交数 | 查询剩余量 | 业务结果 |
|---|---:|---:|---:|---|
| 显式native、ORDER空 | 8 | 4 | 0 | 四次调用均沿原base进入 |
| query_first、ORDER空 | 8 | 1 | 0 | 首批准入，后三次原base之前等待；不造虚拟挂单 |
| query_first、活动ORDER | 8 | 1 | 80 | 券商每次返回已成20/剩余80，Context始终直接读80 |

三案查询持仓始终为来源返回的100；活动ORDER中的已成交20没有用于本地增加持仓。这个输入仅验证来源查询投影，不证明真实成交后的账户持仓一致性或跨查询原子性。真实券商SDK调用为0；每案各原生8查询、SDK替身调用与源owner线程均由外层夹具独立核实。第三案还读取到原券商委托对象的20/80及当前WT归属。

最早两案记录保留在main-001，首次三案在main-002；最终使用当前所有权版本及新输出main-003。当前root构建与验证整树归零、stdout/stderr EOF、读取线程join、资源关闭均通过，无强杀；各Host/Agent/代理线程关闭由夹具确认。

## 未完成范围

该结果已让查询优先逻辑形成正式可链接运行组件，实际策略宿主装配仍待接入。当前取消沿原Adapter，完整活动订单刷新/取消、终态订单后下一轮调仓的组释放、首次/重连查询与实时回报交接、跨进程恢复、独立包和真实账户交易尚未完成。不能据此宣称完整交易插件可实盘。原native对照保留已批准position_by_query=true，只对订单上下文选择作比较。

整体主路径完成后再集中边界、恢复矩阵和独立代码审查；本次未启动review，无生产切换、真实下单或撤单。

本轮项目文档导航及技能清单检查实际退出0；该检查范围与上面的编译、真实SHM正向链分别记录。
