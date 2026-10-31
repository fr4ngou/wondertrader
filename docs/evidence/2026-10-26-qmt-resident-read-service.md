# 2026-10-26 QMT常驻只读连接切片

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。状态：自有API、合成WinSHM及目标3.6.8已验；正式配对生成、独立安装、统一启动和实际QMT常驻未验。整体迁移目标active。本轮真实SDK下单/撤单0，旧QMT源码/运行依赖修改0，WT核心新增改动0。

## 根因与实现

原Host/Agent均只处理一轮连接，Host原connect_seconds同时覆盖映射创建及首对端到达。用户晚于该窗口启动策略时，既有HTTP进程可以存在但SHM监听已退出。

显式常驻入口build_read_service冻结配置、凭证和policy，组合原HostReadRuntime；原build_runtime/单连接默认仍保持。Host只在未认领对端的空闲阶段持续等待，映射创建、选中后的认证、每请求及关闭继续原有限期限。管理线程先撤准入、排空HTTP租约，再原close确认I/O/域/Journal全部关闭，最后在同一journal_path重建新代。失败保留旧owner，不以第二次退休延长首次D。

ReconnectingReadAgent由原策略线程tick推进，只在原Agent I/O退出及原close(now)/join(0)确认后建立新代。同步构造/start/SDK错误、已识别认证和资源故障封自动恢复；运输失败按显式间隔等待。QMT内没有新增文件或网络访问，也未启用交易自动恢复。

快速接入仍被已认证旧peer占用时，原join把暂时不可用归ProtocolError。纯反例实际失败后，修正为验证selected MAC：合法旧占用按OSError等待，损坏MAC仍ProtocolError；不覆盖nonce、不写原对端关闭位。原测试仅该异常类别与原因注释更新，其身份及关闭位断言保留。未认证空/陈旧映射由原Connector作为等待处理，超时不能识别全部错误密钥，不能宣称覆盖全部认证故障诊断。

## 实际验证

实际句柄与结果包（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/SOURCE-SNAPSHOT.json`）记录73份连接源/测试的后置摘要；它不替代完整实际模块来源闭包。

| 实跑 | 结果 | 范围 |
|---|---|---|
| 最终纯回归（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/pure-final.json`） | 50/50，root69712/child0 | Agent28、Host14、空闲/占用/认证8；停止/构造竞争、SDK锁外、旧owner保留、原关闭D及默认行为 |
| WinSHM与签名HTTP（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/kernel-final.json`） | 2/2，root53120/child0，4.603秒测试 | 原窗口0.5秒、晚0.8秒启动；两端先后启动；Host断连/重启恢复；新binding变化、旧binding拒绝、旧终态原ID可查；每案SDK替身2次且均原创建线程；native ok与payload实核 |
| 既有回归（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/default-regression.json`） | 34/34，root26656/child0 | 原builtin13、Agent生命周期6、Host5、listener gate3、安全资源6、默认legacy SHM签名全链1 |
| 目标解释器（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/target-python36.json`） | 36/36，root40512/child0 | 国信附带Python3.6.8/x64，独立进程-I -S -B，Agent28和空闲/占用8 |

四轮均无forced，创建期Job/2GiB、原45秒总预算、进程树0、双EOF、join及资源关闭通过。WinSHM测试使用本进程内两端真实内核映射、真实签名HTTP及SDK替身，未宣称独立Host/Agent进程、QMT实际装载或完整解释器/模块来源闭包。当前源码由显式sys.path导入，正式独立发行仍需冻结包、实际来源与安装验收。

失败原件保留：kernel001（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/kernel-original-failure.json`）两案1通过1失败，第二案使用原单连接Agent快速重连未重新绑定；占用纯反例（外部历史/待归仓路径：`../../build/qmt-resident-read-validation-001/busy-original-failure.json`）实际抛原ProtocolError。后继kernel002改用显式resident Agent并补业务结果断言，修正产品占用分类后通过；未把原失败改写为通过。

## 独立审查

final001完整静态审查（外部历史/待归仓路径：`../../build/qmt-resident-read-review-001/final001/REPORT.md`）绑定最终规格及源码，无必要P1/P2；含原默认测试单处占用类别变化。动态窄复核（外部历史/待归仓路径：`../../build/qmt-resident-read-review-001/dynamic002/REPORT.md`）已亲读50/2/34项原stderr及控制器结果后通过，不自动转授安装或生产资格；目标3.6.8的36项由根实跑，未纳入这份窄复核。首次审查full，后继仅在同一QSW-R20内核对占用分类、最终业务断言及实跑结果；原稿保留。

## 未完成与下一步

1. 把显式API接入正式pair/verify及无文件正文依赖闭包，保持原单连接模式可选；构建、搬迁和安装来源分别验收。
2. 完成系统统一启动/停止入口及进程管理，再验证QMT登录就绪与登录自动启动；本轮未设置Windows任务。
3. 实际QMT长期等待、断线、重新认证和账户四查询；当前POSITION4成功，ORDER原记录为operation_interrupted，不能归因SDK自身报错。
4. 交易Agent持续事件/unknown与跨binding恢复、防订单查询空窗重复提交、分钟全量覆盖及其余迁移目标继续。首只读切片不授真实交易或生产切换。

依据：[QSW-R20](../specs/qmt-shm-wt-binding.md#qsw-r20-常驻连接与系统统一启动)、[ADR-0013](../architecture/adr/0013-qmt-connection-lifecycle.md)、[模块](../modules/qmt-connection-lifecycle.md)。本轮没有需要用户追加批准的WT框架修改或必须用户提供的资料。

收尾文档检查：project.py check实际收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-resident-read-doc-check-001/ROOT-RESULT.json`）自然exit0/7.594秒，local document navigation及skill manifest通过；应用构建、实际QMT及发布不在其范围。
