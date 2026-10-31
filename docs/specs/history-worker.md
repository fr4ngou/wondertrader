# 独立历史执行进程与有界排空

类型：功能最终规格。状态：accepted。承接 [HSA](history-lifecycle-and-service-adapters.md) 与 [HES](history-evidence-storage.md)，范围是已授权的独立历史执行入口；原 QMT 工程只读，真实发布另验。

## HW-R1 所有权与入口

独立 SDK 提供 `python -m guanheng_market_client.history_worker`。必须显式指定 job UUID 和受管部署工厂 `--factory module:function`；工厂是部署者安装的可信代码，零参数返回当前线程创建且尚未推进的 HistoryRunner，负责注入 Operations、Market、权威 CalendarProvider、EvidenceSink 和固定 binding。工厂仅构造依赖，准备任务及业务推进由启动器承担。工厂名称仅由部署启动参数提供，禁止从 job 或网络读取。凭据通过部署工厂的受管环境获得，禁止放入命令参数或诊断。

入口沿原 step 执行；只调用已有 GET/PUT checkpoint 和原生任务接口。创建、resume、控制面 stop、持久断点继续归 Operations。生产配置须具备已验证的权威分钟日历服务，缺少此依赖时不得启用；隔离测试可以使用明确标为合成的完整替身。SDK正式组合入口见[HDF规格](history-deployment-factory.md)，既有自定义factory保持可用。

## HW-R2 关闭语义

HistoryRunner 新增 `close()` 和不可变关闭结果，保持构造线程与非重入约束。首次合法 close 先关闭新的 step 受理，再在独立的 budget_ms 截止内最多发送一次已知任务的幂等 release；后续 close 允许重试同一身份。Ok/StaleSession 可清除已知任务，其余结果保留 Releasing。close 不查询或修改 Operations、不请求新准备、不推进 work；本地关闭不等于用户停止作业。

close 结果分别表达状态码、已知任务尚待释放及队列 owner 恢复需求。无任务且无未知准备风险可确认排空。准备交换可能已受理但回复未知时保留保守恢复标记，即使后续重新准备成功也不能凭新身份清除；正常查询无法证明丢失的终态编号已回收。该标记只在内存用于真实退出诊断，不建立任务账本；队列 owner 通过独占实例受管回收处理崩溃/未知 prepare 遗留。禁止自动重启共享市场服务或隐式淘汰任务。

## HW-R3 运行与退出边界

启动器以单线程运行，显式限制最大步数、最大运行秒数、步间等待及关闭尝试/总关闭时间。默认关闭窗口 35 秒，上限 60 秒，须严格大于所注入 runner 的单次预算，给准入/调度留出余量；相等或更小在调度前作为配置错误拒绝。每个 step 和 close 的完整预算必须在剩余相应总预算内才准入；依赖本身超时不可抢占，外部进程监督承担硬停止。等待可由 SIGINT/SIGTERM 中断；信号处理仅设置本地停止标志，正在进行的步骤在安全边界返回，然后排空。

Ok 为原 runner 已观察到的终态/完成；Pending、Backpressure、Unavailable、Timeout、StaleSession 可在上述边界内再次 step；其他结果停止推进并诊断。不能根据 step 的状态将原作业擅自置 failed。退出码：0 已观察完成/终态且排空；2 输入/配置错误；3 步数/时间/本地信号导致有界暂停且排空；4 排空未确认或存在队列 owner 恢复需求；5 契约/不可恢复步骤错误且排空。排空异常优先为 4。终态的具体业务成功/失败继续以 Operations 为准。

## HW-R4 单工作者与诊断

执行前按规范 job UUID 在显式受管锁目录获取 OS 进程锁，持有到排空结束，竞争者在构造工厂和访问远端前拒绝；锁文件只是进程排他句柄，可残留空文件，不保存业务断点或 task_id。锁目录须预先创建，库不默认选择机器磁盘。此锁只覆盖共享同一可靠本机文件系统的进程，跨主机排他由部署 owner 确保单副本/分配；Operations CAS 继续作为修订保护。

运行诊断 stdout 只输出有界固定结构 JSON 事件，包含已验证 UUID、阶段、受限状态枚举、计数和退出码。禁止输出任意异常文本、工厂返回值 repr、远端 body、result_ref、token 或 secret；配置/工厂失败输出固定原因。参数解析错误也保持固定去敏输出。`--help` 提供固定 CLI 帮助文本，直接退出，不加载部署工厂或访问远端。

## HW-R5 验收与发行

覆盖 close 同线程/重入/重复、未执行或丢回复 release、背压、StaleSession、准备回复未知、step 关闭后拒绝；验证实际源 work 数和 Operations 未被本地关闭变更。启动器用真实 subprocess/loopback HTTP 完成一次完整 job，并覆盖操作面 stop、终态、限制/信号、工厂失败/凭据去敏、错 family、进程锁竞争/崩溃释放。独立 wheel 离仓安装，保持标准库基础依赖；仅部署 factory 可注入存储 extra。新源码纳入锁定清单、包验证、自动化测试和可搬迁开发包。独立 full 审查按实现/发行两轴分工；真实依赖与原日线 CLI family 路由仍另验。

## 实施归属

执行 Agent 维护 canonical history_runner 的 close/准备风险诊断及独立回归测试；主 Agent 维护 history_worker、启动测试、发行/构建/文档。独立 Reviewer 仅接收最终规格、规则和源码，检查异常恢复与发行边界。原生队列和 HTTP 协议保持现契约。
