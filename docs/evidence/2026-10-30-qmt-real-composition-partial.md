# 最终回调来源的真实组合验收

2026-10-30，普通 installation007（Agent a6 / Host a7 / WT a4）实际只读运行取得两轮账户发布；全市场行情流启动阶段超时，完整组合验收保持失败。原失败目录、6124项固定输入和QA001保留。

## 已取得的业务证据

WT先等待65.015秒，再由根于09:31:58启动原SHM_READ_PROBE。两轮原NAP分别完成position/order/deal/account查询，均为4个持仓、0委托、0成交和1组资金；独立App的账户HTTP结果与原投影匹配，短窗口来源计数分别保持4→4及8→8。HPR行情及5根历史查询已完成。浏览器验证尚未进入。

根在停止后用只读不可变Journal核对两轮账户：134项来源事实、78个WT ABI值、原请求与结果摘要、执行区间、binding和浮点位全部相符，Journal SHA保持。该核验新增账户业务查询0，未重新计算持仓或资金；仅接收已完成的账户片段。原QA审计要求三轮和整链成功，因此根另建account_slice_audit_001.py，保留原QA及失败结论。

## 当前失败和处理

主QA在main.py第146行等待connected、received_batches和receiver_heartbeats，60秒内未满足。根当时观察隔离采集器为第5代、41批8200条，原Writer处理8200条、心跳0、receiver_failure=connection_ended；完整6982证券初始快照是否完成尚未证明。源码显示先发送初始快照，再进入正常心跳循环，故不能仅删除心跳条件后宣告通过。通信owner正在核查完整初始快照反复断开的触发链，先检查现有批量配置和队列处理，保持全市场范围及原协议预算。新候选使用real-002目录，保留本次失败。

09:34:11仅停止本次SHM_READ_PROBE并逐字恢复原正文，SHA256为35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae。外层正常完成控制收尾，exit2、forced=false；内层WT业务退出2，不能写成成功退出。内外Job树归零、管道EOF、reader join及资源关闭均完成，6124项输入前后保持。完整状态closed未取得，保留为null。

## 现有采集保护

原采集器PID75000、原WT/Host/历史实例保持，GH_WT_MEMORY_VERIFY继续运行。根09:43左右读取原状态：今日来源时间已前进，原Writer累计处理1716085条行情，订阅6982证券、generation=1、connected=true、error=null、receiver_failure=null、来源overflows=0。这证明今日行情进入原Writer；全市场完整性和已完成分钟线仍须分别核对。

根通过原18130服务的history.query只读抽查今日600000分钟线，服务返回NotSupported（来源历史商店仅提供显式来源历史查询），记录保留为LIVE-NATIVE-MINUTES-001.json；该接口结果没有被写成分钟线成功证据，也未触发补数或来源查询。

## 原件与范围

原件在build/wt-callback-observer-real-001：real/RESULT.json、control-real/RESULT.json及real/ROOT-ACCOUNT-SLICE-AUDIT-001.json；根摘要root-operations/ROOT-PARTIAL-RESULT-001.json固定报告SHA。所有实际下单、撤单和生产切换为0。真实账户片段不授予整套实际组合、策略交易或生产资格；唯一策略恢复和独立观衡后继功能继续分别验收。
