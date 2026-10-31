# QMT未知委托与只读审计混合容量

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-26。状态：C05/C06各1/1实际通过；独立静态full及两轮delta、接线和驱动审查通过。独立动态复核及根原件核验通过。完整矩阵、首次/重连与生产继续待验。

## 目的与真实路径

依据[标准事件规格](../specs/native-qmt-standard-events.md)及[未知委托契约](../specs/qmt-unknown-cancel-cpp.md)，以唯一worker/owner的真实Standard候选验证unknown Pending、自动ORDER只读审计、普通Query、EventChain及Pair/Resolve同时持值与转交。真实Host/HMAC/Win32 SHM、原线程SDK替身及固定原版WT Adapter参与；SDK insert进入后抛错，原委托保unknown且只调用一次，cancel调用0。

三道透明响应门分别暂留普通ACCOUNT terminal、自动ORDER terminal及后继空EventPage，原响应不改写。Audit新只读D从正式调度时固定，原写D、next_due、普通Query D、EventChain D分别保留；原unknown与后续每个HTTP步骤的成功/失败分别核查，原first_error不掩盖新审计错误。补查ORDER完整同token收据沿原Pending转交，不向WT重放金融回报。

专用ABI v2通过gh_test_audit_resident_snapshot输出固定POD。活动Audit仅读稳定调度字段；ready Summary在原mutex/commit边界后读取；完整receipt三个文本有显式硬界并直接复制到EXE预分配输出，不传STL/锁/私有地址。复制与测试观察开销不作为产品resident额度或进程RSS。原C03/C04 ABI及正常DLL保持各自资格。

## 修订、构建与来源

候选001的Closed后晚SPI断言会跳过实际Factory delete，独立full发现后在002将诊断断言纳入首异常保护，使Closed时继续delete及registry核后重抛；未Closed不强删。原晚SPI断言完整保留。002实际首编译因同作用域resident指针与JSON变量重名失败，C2040衍生C2661；crs-002及72.859秒正常回收记录保留。003只改第92行局部指针及同一行两引用为audit_adapter，旧包不覆盖。

正式4新测试文件与2测试构建接线独立集成；产品Standard.cpp db13dc15a03a30db861d0e2c7d416370a9f598d4e24e2b419556647f99b844c6、26项框架保护摘要保持。新短根crs-003在固定上游08b230dd05facf6d650d949bfe51054115a2ecb1下177步、72.781秒编译两目标通过，174自有/323上游输入逐份SHA核验，20所选对象最大绝对路径219字符。

NqpAuditResidentTrader独占bin/audit-resident-test-traders/TraderQMT.dll，SHA03c69e533917feb0013f1e957c5d4a826aa9f953342367e034e25a85e6b7683e；NqpAuditResidentProbe SHA68071f381b35ea153302afc1297f85976114212d14248fff55c898d7cf68f1c5。DLL仅audit_resident_snapshot.cpp同TU包含一次真实Standard.cpp，真实StandardFactory另编；AUDIT宏全DLL/EXE，BUILD_DLL只DLL，正常及旧resident目标保持。

Python运行闭包171项在原170基础上只新增test_audit_resident.py；manifest e147bc3dfeae6ab724f3f337ff534eeef39c8c038749d4c17a0a57679bd976f5。冻结驱动08023d8d3361c1e8c7b8cc992f425054de0428b0ba8efff018bea05ce8c5f58c保持事前事后精确来源/模块核验、原uptime D、首异常和有限日志；本例代理取证上限明确1024，其余既有字节/页界保持。

## 实际结果

| 输入 | 容量 | unittest | 控制器 | 结果 |
| --- | --- | --- | --- | --- |
| C05 | 256 MiB | 1方法，12.934秒 | 14.703秒 | 通过 |
| C06 | 512 MiB | 1方法，12.856秒 | 14.672秒 | 通过 |

两案除容量/case及自然生成身份/期限外同一输入：q16、H262144、request8000、原event poll150，原工作截止30秒。它们各自独立原总D，均只选1方法，不合称同D批次或完整矩阵。

六点账单分别为before103268900、borrow0同值、borrow1=103319752、after_query=102683720、audit_ready同值、audit_settled=99053772字节；逐点独立复算相等。原Query转交增加Pair50340+Resolve512，旧Query真实析构退款636032。P0=2034，AuditReserve=3629790+P0=3631824；新增完整ORDER receipt组1876，P1=3910；审计完成值析构与组转交后净退3629948。原own receipt、ready ORDER组、Pending最终组及Closed组分别按原始字节核相等。

最终WT持仓/可用/未完成量100/100/100，账户2、委托/成交推送0，原未知错误保留；SDK替身insert1/cancel0，自动ORDER新只读请求1且同token lookup/no_cancel各依真实HTTP原件核查。无源交易事件，published/acked均0，真实空页按after_seq0完成。关闭后Pending1、payload3910是仍被持有的原unknown通信收据费用；实际drain/join后执行Factory delete并核registry消失。Closed保留状态与最终实例删除分别核实。

两组创建期Job、原deadline、双EOF、真实worker/Host/Source/代理回收、无强杀与无清理错误各自核验。SDK全为替身，真实SDK调用0。

## 证据与剩余范围

实施收据目录（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/TEST-INTEGRATION.json`）登记49/51候选原件、38前置及静态审查；首编译失败（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/BUILD-001-FAILED.json`）、新构建（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/BUILD-002-ROOT-VERIFIED.json`）、C05（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/C05-ROOT-VERIFIED.json`）与C06（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/C06-ROOT-VERIFIED.json`）分别保存实际身份与控制器回收。full审查（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/audit-resident-four-source-full-001/REPORT.md`）、002 delta（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/audit-resident-four-source-full-001/revision002/REPORT.md`）、003 delta（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/audit-resident-four-source-full-001/revision003/REPORT.md`）保留各自失败及闭合范围；静态根核（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/STATIC-FINAL-ROOT-VERIFIED.json`）与动态独审（外部历史/待归仓路径：`../../build/qmt-event-query-standard-tests-independent-001/audit-resident-dynamic-001/REPORT.md`）分别登记：51检查通过，73份新raw根逐项核同，见动态根核收据（外部历史/待归仓路径：`../../build/qmt-c-audit-resident-implementation-001/INDEPENDENT-DYNAMIC-ROOT-VERIFIED.json`）。先前清理P2已静态闭合，本轮正常输入未故意触发该断言失败分支，保留该故障注入缺口。

本片只授专用instrumented DLL的两个指定混合窗口；没有重证全部Static/Owner/Worker最大值、need/need−1、真实HTTP满槽、双Started/取消U/多Pending轮转、所有分配/父死亡平台矩阵或一般未知insert解除。正常DLL、前轮C03/C04与33/默认12分别沿旧身份，未在本片改动或重复运行。查询/回报共同覆盖、真实券商交易和整体发行继续待验。
