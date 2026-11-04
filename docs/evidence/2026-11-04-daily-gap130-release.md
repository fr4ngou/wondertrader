# 130项目标日缺价正式补齐验收

类型：后继验证证据。状态：数据角色已正式发布并验真；两项国证行情的观衡消费者SDK升级由Root另行接收，自然新日待验证。承接[原调查](2026-11-04-daily-gap130.md)，本记录追加正式运行结论。

## 根因与正确实现

原2026-11-03当前名册8013项中，130个目标日缺价分为：48个ETF网上现金认购/资金代码、14个成交量统计指标、8只来源报告停牌且数量未知的股票、53个券商未提供可用日线的价格指数，以及7个官方只有收盘参考、缺开高低字段的三板指数。

SDK按实际Source类型与交易所业务规则确定非价格用途，原名册/计数/原件保留，价格适用范围另计。已确认返回的旧HPR经过原请求、票据、profile、完整绑定、结果及业务投影验真，保持原身份并允许后继按实际缺口准备。未知原责任继续保护。中证/国证原价由同一数据owner采集、保存原件并经原Helper/Reader落盘，日期合并保留全部旧值和逐段来源；消费者继续只读WT入口。

正式运行进一步重现预生成Native复用候选失配：42项HPR完成后，新回读SHA已改变，旧候选仍被当成必选项，native阶段重复ValueError。修正为先核旧成功候选，实际capture和Helper匹配时复用，失配沿原已完成回读转换。原请求、原候选及回读字节保持。Source共享日期规则采用Python3.6.8已有标准库能力。

## 正式身份与实际结果

- 主干提交：`58d26e55de6cb279f2aebd77a0eb57853b8ca045`；注释标签：`guanheng-daily-data/0.2.0a1+unified.7`。
- 制品：`role-build019`，清单SHA256 `d58c4ee7d08a5722ee990a67895e4d30caefdcedf8629ebab34e332b0880d73c`。176项源码输入与固定干净主干一致，LICENSE仅有Git正常Windows检出行尾转换，规范化字节相同。安装157成员逐字节核同，SDK0.17.0，依赖检查通过。
- 正式入口：`http://127.0.0.1:18136`；CURRENT：`fe720a4468c9fd03063cd65ad8019019e131641b72e79936c338a12d3aa72b92`，目标日2026-11-03。
- 当前Source原名册8013项，价格适用7951项，目标日Native实际可读7936项。53项新增指数已逐项通过正式公开SDK读取；62项业务记录独立排除，8项停牌事实和7项官方OHLC缺项如实保持。含历史身份的已知总范围8086项，可读7937项。
- 原4636份补充行情档字节全部保持，6255份旧任务/原请求文件保持；复用失配恢复前后556份原请求/完成回读保持。
- 七指标通过同一正式HTTP入口实际计算并发布，239次HTTP、0次SDK调用，业务值及旧历史一致。T2108的source_received_at正常更新到新回读接收时刻，历史PIT资格保持。
- 正常停止/启动后，7257份任务、请求、输入及CURRENT文件保持，首次实际读取含四个样本共0.359秒，CSI/CNI/Qmt均成功。数据任务published，continuation_required=false，维护owner为waiting、active_date=null、last_success=2026-11-03。

## 证据位置与限制

受控证据根为 `E:/workspace/wondertrader-qa/goal-acceptance-20261103-001/unified-wt-entry/gap130-20261104-001`：`CLASSIFIED.json`及人读CSV为130项逐项原因；`MAINLINE-ARTIFACT-PARITY019.json`、`FORMAL-READ011.json`、`RECOVERY-NATIVE-VERIFIED012.json`、`FORMAL-CHAIN004.json`、`OLD-SDK-COMPAT011.json`、`RESTART-VERIFIED012.json`和`MAINTENANCE-HANDOFF012.json`分别固定源码、覆盖、恢复、指标、兼容、重启及维护责任。红绿、63项回归、安装和独立两轴审查的原失败/后继成功闭包均保留。

本轮验收脚本曾沿旧输出名写运行摘要，旧摘要已从observer003原仓库run恢复语义，旧系列文件字节保持；本轮输出改为独立004记录。首次指标比对因接收时刻更新失败，后继在同一已完成实际采集上核业务值、历史和接收时刻，不重拉来源。

SDK0.16实测兼容51个CSI指数及4个Qmt样本；两个CNI消费者需要SDK0.17，页面升级由Root独立模块维护。完整OHLC缺少的7项不制作K线；8只停牌证券不填零。首次自然新日及09:00调度尚待时间条件。Root通信owner切换另行执行，本模块没有修改Host、Source界面、账户或交易运行。

本模块当前活动v8/HPR请求为0，174份本轮HPR已确认返回，872份v8保留记录均terminal/consumed。两项原未知HPR责任仍保留：`98a6fb12-43d4-51e4-9378-fcedc3c4dd77`（000517.SZ）、`d596de3d-47a8-583c-b74f-deb5be168dc5`（000518.SZ）；原slot和参数详见维护交付，切换须保留原Journal及身份。
