# QMT共享内存开发入口核对

日期：2026-10-22。结论：开发启动条件已满足；WT新绑定、真实账户/交易及生产未验收。

用户明确另一对话已完成共享内存，允许开始WT接口开发，并要求将国信QMT操作、维护资料迁入本仓库。只读核对对话“查找通知应对方案并审视限制”已完成状态，摘要保存在`build/guanheng-workspace/communication-gate-001/shm-readonly-snapshot-004.json`。

静态核对实际交付目录`E:/workspace/qmt-storage/qmt-shm-validation-20261022`的`RUN-012.md`、`run-attestation-012.json`与配对材料存在。运行记录声明北京时间20:10和20:12两次510300.SH真实行情读取及原结果重取一致，链路为外部签名HTTP→Host→pagefile SHM→QMT原策略线程。该记录仅证明当次链路，不推断当前进程仍存活。

源端当前范围为`market.full_tick`、`order_ready=false`；正式原生入口未启动。账户、历史迁移、交易及生产切换不在该证据范围内。此次核对没有停止/重启现有策略或Host，没有下单/撤单，没有更改账户、权限、风险参数及私有配置。

国信QMT[操作](../runbooks/guosen-qmt-operations.md)、[维护](../runbooks/guosen-qmt-maintenance.md)、[排障](../runbooks/guosen-qmt-troubleshooting.md)三手册已迁入，来源映射与冻结记录位于`build/guanheng-workspace/guosen-qmt-docs-001`。根任务逐项核对15项原件及文档身份一致；运行工具尚待独立连接包交付，手册明确标出该缺口，没有沿旧工程命令宣称可用。

静态源码核对发现现有WT `QmtReadTransport`要求`/internal/v1/capabilities`和特定会话字段，已验Host的路由及health不同。接入按[QSW规格](../specs/qmt-shm-wt-binding.md)建立映射，不能直接换URL当成已兼容。旧QMT源码仅静态参考，后续产品构建与运行消除其依赖。
