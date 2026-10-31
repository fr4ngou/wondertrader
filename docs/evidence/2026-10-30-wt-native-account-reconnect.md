# 同一 WT 与 Host 下的两代真实原生账户读取

类型：实际运行证据。日期：2026-10-30。范围：常驻只读连接、源策略正常停止及重新认证。

普通安装的 WT 公开 CLI 管理原只读 Host。第一代真实 QMT 策略完成原生四查询后，根仅停止 `SHM_READ_PROBE`；原 Host 自动关闭旧代通道并进入等待。重新启动同一策略后建立不同的 transport_generation，第二个原生 Scan 完成另一轮四查询。WT与Host在两轮之间均保持同一实际进程。

| 项目 | 第一代 | 第二代 |
|---|---|---|
| 实际 WT / Host | 76372 / 60860 | 76372 / 60860 |
| WT 启动包装 | 66776 | 66776 |
| 原生 Scan | 27492 | 73656 |
| 持仓 / 委托 / 成交 / 资金 | 4 / 0 / 0 / 1 | 4 / 0 / 0 / 1 |
| 原生完成耗时 | 20,045 ms | 21,029 ms |
| 原通信 Journal 终态条数 | 4 | 8 |
| 原源事件 | 04:55:00 doRun、04:55:42 stop success | 04:56:01 doRun、04:56:45 stop success |

transport_generation实际由 `7a14e8c3015a4cc59670fb24e235282b` 变为 `977554450d5f4ca487f914266b7e47ab`。第二轮重新查询产生四个新请求；第一轮原请求摘要、终态状态和结果bytes摘要保持。没有重新POST第一轮请求，没有额外证券、财务投影或恢复账本。

第二代完成后，根实际停止源策略、确认Formula事件并逐字恢复原 `35d020…` 正文。两个原生Scan、WT启动包装及其实际WT/Host均正常退出，Job树清零、双EOF、reader join、句柄关闭，forced=false。外层控制器55632及原生入口协调器22832退出码均为0，总耗时120.237秒；159份运行输入SHA前后相同。真实下单、撤单及生产切换均为0。

## 制品与验收边界

实际目录：`build/wt-native-account-reconnect-002`。`DELIVERY-001.json` SHA为 `d564b73d999c9b2885f4ff32ffa91f8a2c967d744443cf92a53cf0867b4e23e3`，绑定15份原件、实际命令和失败前件。原账户、凭据、响应正文及Journal保留在受控 `real/private`，公开资料只列计数、状态和摘要。

前件001完成第一次真实原生查询后，QA将状态中的实际WT PID与启动包装PID比较，触发错误断言；随后正常停止、恢复及回收。原记录完整保留于 `build/wt-native-account-reconnect-001/QA-QUALIFICATION-001.json`。后继002沿真实状态固定实际WT/Host身份，启动包装另记；未修改产品行为。前件没有开始两代重连，不作为产品恢复故障。

该原生制品仍沿[真实原生消费者](2026-10-30-wt-native-account-consumer.md)的4个1 ULP精度缺口，当前不授全字段精确资格。统一FullPrecision修正及新制品另验。两代正常停止/认证成功不证明此前004/run002异常的根因已解决，也未覆盖源进程崩溃、整机重启、非空订单、真实交易或观衡页面。完整系统继续开发。

适用规格：[独立运行](../specs/independent-wt-runtime.md)、[共享内存](../specs/qmt-shm-wt-binding.md)、[账户读取](../specs/qmt-shm-account-read.md)。

独立delta审查完成：`build/wt-native-account-reconnect-002/REVIEW-001.json` SHA `2010655fd94b35b3cfcbaf04a9865068115cefee448cb80487ce658e0dabb1d9`，新增P0–P3为0，接受同进程两代真实原生读取、旧终态保持及正常关闭恢复的限定资格。补充只读 `JOURNAL-AUDIT-001.json` 核总条数8、全部terminal、null结果0，前后Journal SHA一致；不授前述保留范围。
