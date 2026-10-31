# HPR确定拒绝后的持续分析恢复

类型：验证证据。日期：2026-10-30。规格：[AWP6](../specs/qmt-analysis-window-producer.md#awp6-可选已确认只读结果回收)。

## 根因与实现

AWP a9将公共RetainedReadFailure与Pending一起转为SourcePending，原capture及过期HPR截止持续保留。公共Failure已经确认受理前拒绝或调用前拒绝。a10在HPR消费层把该确定失败转原SourceUnavailable，由原owner下一业务轮创建独立capture；旧请求/拒绝/结果保持。Pending及网络未知、404/410继续原ID，原默认路径保持。

生产差异仅preparation.py分类及两处版本元数据。Host a13/Agent a10、WT a11、core a2和原Native算法字节保持。没有新增持久层、线程或交易权限。

## 实际验证

原普通a9的两项短红例复现：明确拒绝仍SourcePending；同一owner在来源恢复后保留同capture、无法完成准备。后继普通a10的29项回归通过，含原默认、丢回执/未知、同根恢复及确定拒绝下一capture。

隔离正式SDK链先把首个原HPR票据设为过期，实际签名Host返回400/read_ticket_ended；公共Client保存原admission_rejection且result仍null。服务下一capture完成8次HPR实际缓存更新及32次v7原SDK读取，再原Import/Reader/QNA发布，原R24成功读取3208根。重复读取原拒绝slot无HTTP、无SDK；原拒绝capture无Native作业。

业务69.859秒，1392固定输入前后相同。两份关闭后的原Journal以immutable方式核完整性及原字节，最终均0行；40个成功slot完整原值/内容ID/绑定/时间/consumed核对通过，另有1个原拒绝slot保留。正式3.6.8正文一个原timer、SDK原线程、禁用file/network入口0、运输线程0；下单撤单0。外层四Job和Native Job均exit0、整树0、EOF/join/句柄确认关闭。

固定原件位于build/root-analysis-retained-reads-002，交接INTERFACE-001.json与SOURCE-FINAL-001.json。a9/final004三轮正常证据仅复用未变路径；a9/final002缺原结果的原因继续unknown，后继确定拒绝恢复成功不倒推该旧故障。

## 资格与剩余

本证据覆盖隔离SDK、普通WT角色及HPR确定拒绝恢复。实际QMT、跨日常驻、生产与整包由根分别验收。C++账户四查询及混合v4交易Host查询尚未接回收，本模块不给这些路径长期无限资格。
