# 读取新观察的当前认证与单次捕获一致性

类型：验证证据。日期：2026-10-30。最终规格：[RR6](../specs/qmt-read-retirement.md#rr6-新观察与来源换代)、[AWP6](../specs/qmt-analysis-window-producer.md#awp6-可选已确认只读结果回收)。

## 根因与实现

原公共Client以父BINDING给新slot准入，跨Host epoch使用旧认证。票据层零SDK短例返回400；真实Runtime门面更早返回409/source_binding_changed，成为永久Pending。两个原件范围分列。

Host a14的新slot每次GET当前binding，不读取或覆盖业务capture的BINDING。可选expected_binding在plan/POST前比较完整认证，差异抛RetainedReadBindingChanged。旧slot沿原ID/binding/result恢复，未知不改身份；已确认持久消费后再核期望。

AWP a11的v7与HPR分别传本capture固定认证。新认证不符时沿原Unavailable结束已确认观察，原窗口/请求/结果保持，下一capture重新观察。默认省略retention保持原路径。生产差异为1个公共Client、2个AWP调用接缝和4个版本元数据；Agent a10/WT a11/core a2及原Native算法字节保持。

## 完整主路径

普通23发行仅替换Host与AWP。正式3.6.8单正文、WinSHM及原签名HTTP：先在epoch A完成原Native/QNA发布；第二capture收完HPR及第一条旧代日线后，由隔离QA控制线程正常停止原Host，以同配置/控制根的新owner UUID启动新Host。实际epoch B就绪后，下一slot在POST前发现差异，未创建新slot/快照/Native，旧窗口SHA保持。后继capture沿B完成原Import/Reader/QNA及R24，基准由2026-10-28推进29。

共24次HPR、65次v7实际SDK、16次真实缓存内容改变；2次Native/R24，153.031秒exit0，1392输入前后相同。89个成功slot完整内容ID/原结果/绑定/时间/consumed冷核通过；每capture的完整认证一致，原Journal最终0行，immutable读取前后SHA相同。旧epoch实际成功slot在服务关闭后直接重读，原值/ID/实收时间不变，强制禁止exchange/plan，HTTP与SDK均0。

43项回归通过，覆盖新slot当前认证、期望冲突前置拒绝、旧结果恢复、未知原ID只lookup/410保持Pending、原默认/HPR拒绝恢复。原正式正文无诊断尾、单timer/SDK原线程/运输线程0/禁入口0/下撤单0。外层、两代Host及Native逻辑/物理正常关闭。

## 原件及限制

原件build/root-retained-binding-refresh-001，INTERFACE-001和SOURCE-FINAL-001固定制品与证据。最初final001替换Host使用了尚未创建的控制根，启动校验拒绝；同时原HPR出现host_exit导致逻辑close=false，Source及外层物理已关闭，该HPR首因保持unknown。后继只修QA装配、产品不变，成功不反推旧故障修复。

QA显式重建已停止Host owner，用于外部Host换代测试；不授WT自动重启owner策略。HTTP准入与来源换代之间的未知响应仍沿公共原责任，不凭409/404/410或无记录重派。实际QMT、生产、跨日、账户/v4无限常驻及整个系统恢复由根另行验收。
