# 历史准备与业务作业

类型：模块说明。职责：把已有 Operations 持久历史作业连接到独立行情准备接口，保持调度缓存与业务事实的归属。

Operations 持有不可变 JobSpec、CAS 修订、已确认 checkpoint 和停止/恢复状态。WT 的 HistoryPreparationQueue 仅持有有界待办/部分源页；queue_id/task_id 在创建进程内有效。DSB 是可回查的数据事实，任务重启恢复先回查 DSB，业务进度读取原 Operations，原生队列不持有第二份作业账本。

SDK 的 history_runner 提供单次有界 step；显式 job_id、单 QMT 一分钟 family、绑定摘要与权威日历/证据 sink 由调用者注入。每段确认要求完整分钟网格、真实来源/profile/单位和不可变证据；只有显式权威空日历证据才能确认零记录段。业务审批、账户与交易不进入该调用链。

CAS 保护进度修订，不表示分布式 worker 租约。部署监督者保持同一 job 单一活动 worker，冲突与丢回复先重读原状态；确认记录不可重写。runner 不调用旧日线子进程，也不生成原 QMT capture 证明。

定向推进/释放保护并发与容量，单次工作和待办均有上限；没有日历/资格/证据 owner 时保留 Pending/Unavailable。正常服务不自动采集十年或全市场，长期任务由受管调度分窗和分作业推进。

规格见[HSA-R1–R8](../specs/history-lifecycle-and-service-adapters.md)，操作见[作业手册](../runbooks/history-runner.md)，独立发行见[SDK 手册](../runbooks/client-sdk.md)。验证入口为原生 lifecycle tests、service task tests 和 history_runner 隔离测试；原数据库/业务服务切换保持独立验收。

`history_evidence.MinioEvidenceSink` 接已有对象存储 owner：固定命名空间、规范 JSON 内容地址、已有内容比对和写后回读；原 Operations 保存的 checkpoint/result_ref 指向可重新解析的证据。可选 storage extra 使用官方 SDK，基础客户端保持标准库。适配器不创建 bucket 或改变保留策略，真实命名空间/读取 resolver 资格由部署 owner 提供；要求见[证据存储规格](../specs/history-evidence-storage.md)，配置与恢复见[操作手册](../runbooks/history-evidence.md)。

`history_worker` 作为独立 SDK 的进程入口组合部署工厂、显式 job、OS 进程锁、有界 step 与 close。正常停止在创建线程关闭新 step，并核查已知任务的幂等 release；Operations 的 stop/resume 与本地暂停分别归属。准备回复未知可能丢失编号，close 保留队列 owner 恢复需求，退出码明确回收未确认；不把正常关闭推广为崩溃后的自动回收保证。契约与验收见[HW-R1–R5](../specs/history-worker.md)。

`history_factory:create` 是正式部署组合入口。受管环境提供严格版本化配置及显式凭据引用，它在worker持锁后、同一调用线程构造既有Operations、行情、日历和证据客户端。构造期间零网络、零线程、零作业推进；日历绑定版本和调用预算在构造时一致校验。工厂不持有新的业务状态，实际数据和进度仍沿上述所有者流转。配置失败在首次业务请求前固定去敏；安装、运行及退出码见[部署手册](../runbooks/history-deployment-factory.md)，契约见[HDF规格](../specs/history-deployment-factory.md)。
