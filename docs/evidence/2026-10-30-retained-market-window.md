# 原生实时策略持续消费已发布窗口

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发证据。状态：NRT-R24消费主链及模型边界已验证，审查和交接范围见下文；完整模块继续。范围沿[规格](../specs/native-realtime-strategy.md#nrt-r24-已发布分析窗口的持续消费)和[模块B](../migration/module-b-delivery.md)。本轮新增运行、缓存、临时文件和制品全部写入E盘，C盘仅执行已有工具。

## 根因与实现

旧实时桥每轮核对启动时的固定历史，读取恰好N条原日线。后续日线进入原Reader后，返回窗口向前推进，固定输入与原生日线发生冲突；桥会沿native_history停止。这一限制位于自有输入接线。

可选python_strategy.market_window指定A发布的QNA v1文件及显式接收年龄。每轮沿原计算截止读取一份完整窗口，以原C wire模型解码，仅替换history、analysis、current_view；策略配置、本金、原实际周期、退出记录和NSQ保持原owner。原Reader核对声明日期内的OHLCV及金额，额外一条窗口外bar不进入纯核。缺源、源过旧或原生尚未匹配时进入waiting_market_input；格式、单位或未来输入错误继续沿原health失败。缺省配置保留原冻结窗口路径。

未增加行情发布者、复权算法、金融账本、数据库、后台线程或WT核心行为。源路径和年龄进入原恢复身份；每次发布的摘要进入观察投影，不另存行情进度。Windows沿原文件共享规则读取，发布者应原子换名并在短暂共享冲突时保留原代、沿自己的截止继续发布。

## 安装与正式主链

原件根为build/ms-retained-market-window-001。普通venv --without-pip、六个离线wheel、732条hashed RECORD逐项匹配；未安装观衡/Web及退役策略。冻结A公共运行源、叠加当前16个B模块；原生仍使用R23 native002的23文件，WT核心候选未应用或编译。

| 身份 | SHA256 |
| --- | --- |
| INSTALLATION-001.json | c79c870f48111c68d69b0f8574799e8842abdd1323944b7c318dd1c8ca8080c1 |
| Runtime开发wheel | f478a7b3ffc878ea22b59b63410b5eba49f0da282a2f1b844348362414cf677c |
| MAIN-SUMMARY-002.json | d637b3c9be145657e638b60b85138530f2f4ff7bf88920e8a6daf6e533a6caf4 |
| values002 RESULT.json | 246c03d816e86f2ccae8fd0a4139f72501ac8d130a8d06f40f063d801e92bc8a |

R24-C1：rt-main003从安装Runtime入口沿原Factory/CTA调度、原日线Reader、唯一正式1.1.2、NSQ、原执行器/Adapter及真实WinSHM到SDK替身。首轮文件缺失，sequence1明确等待且SDK调用0；原子发布A真实分析窗口后sequence2形成四个买入目标，实际四笔SDK替身买入、29次查询及四个开仓周期，后继sequence3/4达到converged。输入为A原main006的401日/八证券/3208行，窗口SHA a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859，来源时间与原值保持，量为lot、金额单位unknown且不用于算法；资金和成交明确为隔离模型。对应主链摘要（外部历史/待归仓路径：`../../build/ms-retained-market-window-001/MAIN-SUMMARY-002.json`）。

rt-main002保留为首轮失败：验证配置的原Reader max_bars恰好401，新增N+1请求402被容量边界拒绝，未取得发布后求值资格。rt-main003明确把日线容量配置为4096后重跑；生产代码和原Reader容量校验保持。实际连续新增日线所需容量由部署配置负责。

关闭仍失败：同次原生执行进程17720由调试器捕获c0005；执行部署受管wrapper 54428退出2，外层QA wrapper 42796退出1。WRI ready身份34896单独保留，其退出码不由wrapper状态推定。原host/source及服务/代理六项关闭标记均true，外层Job确认子树归零、EOF、join及资源关闭，未生成成功clean。沿[关闭故障](2026-10-30-stock-close-release-trace.md)继续保留未批准的最小框架方案，本轮不授正常两代或稳定关闭资格。

运输夹具在运行前冻结174份Host/Agent/QA源码。A随后更新trade_cli.py和trade_pair.py，原冻结副本及摘要保持；本轮证据仅覆盖实际使用的冻结版本，统一新源组合须另验。

## 连续窗口、边界和恢复

R24-C2：安装后的完整RetainedStrategy及原C纯核通过17个检查：缺文件零setter；两个不同闭合日模型依次消费；原生落后保持原NSQ并等待；窗口外bar剔除；同日修订产生新输入身份；相同配置原KV恢复后读取最新文件且不重复setter；源配置变化拒绝旧恢复身份；缺省静态路径仍严格；坏schema、错单位、未来源、坏分析值、越权配置字段、重复字段在setter/KV前拒绝；显式年龄过期等待；原总截止；句柄关闭瞬间原子换代返回完整旧代。值回归（外部历史/待归仓路径：`../../build/ms-retained-market-window-001/values-002/RESULT.json`）明确Context与两日修订均为模型。

首轮values001保留了最后一项QA失败：测试在仍打开的Windows读句柄中强制同步换名，原共享规则返回WinError5。后继values002按实际发布顺序在句柄关闭瞬间换名，核完整旧代成功；产品读取仍沿原文件共享实现。atomic-diagnostic保留其实际原始错误，未通过改产品共享权限绕过。

R24-C3当前只证明模型KV恢复及配置身份。C的状态白名单需要新增waiting_market_input，精确候选、原文件期望SHA及差异保存在c-consumer-candidate，生产C文件未应用。独立审查和最终打包结果在本记录后继登记。

## 剩余范围

A目前交付了明确的分析窗口文件；持续新基准日的发布服务尚未交付。本轮正式链使用一份真实冻结发布，模型两个日窗口证明消费逻辑，完整真实跨日持续链继续待验。当前来源接收年龄604800秒仅为此次历史资料隔离回放的显式配置，不授实时行情新鲜度资格。

完整模块仍需稳定关闭与正常两代恢复、实际T+1跨日、完整费用和全周期BT/RT一致性、标准Trader真实v4唯一账户运行、C最终消费及A后继公共源统一候选；真实下撤单和生产切换仍须明确授权。

## 审查与交接

独立执行/状态审查（外部历史/待归仓路径：`../../build/ms-retained-market-window-001/REVIEW-EXECUTION-001.json`）与接口/生命周期审查（外部历史/待归仓路径：`../../build/ms-retained-market-window-001/REVIEW-PROTOCOL-001.json`）分别核源码、六发行/732 RECORD、174份实际冻结源、正式主链和模型回归；当前确定的新增P1/P2为0。MAIN-SUMMARY001保留原绑定，其managed_exit_role沿旧QA原报值；002依据同次ready/outer/debug身份更正四层进程角色，WRI直接退出码unknown，不从wrapper推定。

AST、安装两产品文件与当前源逐字一致、C生产投影未改、五文件框架提案未应用均已核实。文档总检仍因并行新增docs/specs/qmt-account-composed-source.md未入索引而失败；本轮正文已挂接，未改写并行规格或共享索引来消除此项。

最终开发包及成员SHA见DELIVERY-001（外部历史/待归仓路径：`../../build/ms-retained-market-window-001/DELIVERY-001.json`）和同根PACKAGE-MANIFEST-001.json，包名B-PUBLISHED-MARKET-WINDOW-DEVELOPMENT-001.zip。交接含六离线wheel、冻结运行源/原生安装、实际运输快照、QA入口、观察摘要、独立审查及未应用C/框架候选；私有运行配置、原始金融转储和大型POSTFLIGHT留在受控根，不进入交接包。此包继续标记完整模块与生产资格false。
