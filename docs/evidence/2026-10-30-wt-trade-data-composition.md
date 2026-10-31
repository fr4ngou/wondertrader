# 独立WT交易与数据联合运行

类型：实际安装的SDK替身主链证据。日期：2026-10-30。适用规格：[WRI](../specs/independent-wt-runtime.md)、[THP](../specs/qmt-trade-host-product.md)。完整真实账户及唯一策略组合继续验收。

## 已运行的完整链

普通安装的公开WT CLI依次管理HPR、交易Host、历史服务和原生采集四个owner，观衡包与FastAPI均未安装到WT环境。正式trade_cli pair --market-config及verify生成并重建同一策略的三owner正文；国信附带CPython3.6.8实际执行该正文，SDK为明确的合成替身。一个QST订阅、一个timer和原策略线程保持；四类账户查询、一次下单、订单查询及一次撤单沿原WinSHM和Journal完成。该运行的真实委托与撤单均为0。

行情快照、显式历史准备和分钟查询沿原HPR接口完成。4个合成tick进入原collection、DataKit及已批准的WtDataStorageLifecycle，正常关闭时原Helper从DSB回读2根分钟线；同一真实历史基准在运行前后各读取5根，时间与原值保持。该用例没有配置原生策略或execution owner，不能据此授予唯一策略整链资格。65秒晚到、两代认证及未知委托不重发由[交易产品](2026-10-30-qmt-trade-host-product.md)的精确安装证据分别覆盖。

## 实际原件及结果

| 运行 | 安装来源 | 实际结果 |
|---|---|---|
| main002 | installation006 | 完整合成主链通过，16.907秒，1220项输入前后一致；旧外层工具身份不足由后继补齐 |
| main003 | installation007 | 交易Host意外退出，HPR快照查询超时；原运行失败保留，外层及子树已完整回收 |
| main004 | installation009 | 同一完整主链通过，19.562秒；1220项业务/安装输入和6项外层工具身份前后一致 |
| main005 | installation009 | 与离线打包并行的主链通过，18.313秒；无强杀，原件保留 |
| main006 | 系统候选003的搬迁后安装roles | 直接从离线安装目录及其payload运行同一主链，17.532秒，1220项输入保持，原生写入及5根真实历史基准一致 |

上述成功运行均确认源、WT CLI与外层Job退出0、整树0、EOF、reader join及句柄关闭。main006正式正文的forbidden_attempts=0、original_thread_only=true、三owner业务/运输关闭均通过；该计数覆盖受限正文的禁用入口，不能扩大为对整个QMT进程的操作系统审计。

精确原件：build/wt-trade-data-composition-001下各main及control目录；本轮汇总DELIVERY-003.json。原DELIVERY-002.json的case和文件成员为main004，但command数组误写main005；本次新增更正映射，原文件及独审摘要保持。实际main005另有独立原件，没有把它冒充main004。

独审REVIEW-002.json已接受main004正常合成组合并关闭外层工具身份P2。main006是新搬迁安装资格增量，由最终发行增量复核；审查与真实来源资格分别记录。

## 已知风险及剩余

main003旧版Journal的5次账户读取均终态，委托/撤单为sdk_returned，事件水位及身份连续；当时没有持久保存具体异常类型，其退出根因仍unknown。009增加有限首故障分类，后继成功只证明对应运行，不证明旧故障已修复。原故障及JOINT-FAILURE-FACTS-001.json继续保留。

真实QMT账户消费者、交易型常驻正文的现场接入、唯一1.1.2策略/原执行器联合、完整恢复及生产切换继续pending-verification。现场采集、原HPR配对和下载Journal保持；本模块无新增WT核心修改。

后继独立增量审查：build/wt-trade-data-composition-review-001/REVIEW-003.json，SHA256为0cebe6c8d09c122bb694ab4f879f2c46878f89fc017fa262825cf37db4da0419，P0–P3新增发现均0。接受本次离线安装和SDK替身联合主链开发资格；根精确接收另见候选003的ROOT-ACCEPTANCE-001.json。真实账户、唯一策略和生产资格仍未授予。
