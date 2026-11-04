# WT统一日线动态全类别正式验真

类型：验证证据。范围：统一日线角色.5、实际Source目录、正式18136、原历史及正常重启。状态：正式范围验真通过，自然新交易日待验；发布身份及运行入口见[发布记录](../releases/2026-11-04-unified-daily-full-scope-live.md)。规格沿[统一日线UDI](../specs/qmt-source-daily-history.md)。

## 证据根与输入

现场证据根为`E:/workspace/wondertrader-qa/goal-acceptance-20261103-001/unified-wt-entry`，以下路径均相对该根。构建输入主线逐字核对为`formal-deployment001/MAINLINE-ARTIFACT-PARITY007.json`，实际安装及关闭为`CATEGORIES-INSTALL006-CLOSURE.json`，安装后回归为`INSTALLED-REGRESSION006-CLOSURE.json`。两名独立review010评审均已完成，剩余发现为零。

## 真实Source与范围

`formal-deployment001/LIVE-REFERENCE007.json`及`LIVE-REFERENCE007-CLOSURE.json`证明通过Root独立18155实际完成32页目录和126批详情。固定REFERENCE摘要为`e2b2e423b4cc2f2ec9f4c3ea937a0d3d157a987ff37f4bc841a2665494776fd2`。`formal-deployment001/LIVE-REFERENCE-RETENTION007.json`逐槽核对158项全部消费，最长14.147秒，单次目录捕获。

`formal-deployment001/DYNAMIC-SCOPE007.json`核对当前8013、已知价格8086、额外价格2509；沿原158槽字节恢复，同一范围准备新增目录数为零。动态应有数与历史保留数分开；Source不支持北交所ETF，分母保持未知。原失败capture006已独立核清并保留，Source换代后沿新绑定完成本次新目录。

## 正式价格、观察与重启

新版正式数据任务位于外部数据根`data-categories-20261104-007/tasks/2026-11-03`；同一owner实际完成216项HPR准备和186批回读，并发布同一CURRENT。`formal-deployment001/DYNAMIC-FORMAL-READ007.json`及`DYNAMIC-FORMAL-READ007-CLOSURE.json`证明正式18组价格/资料查询、5577指标成员、当前8013/已知8086范围及原158个资料槽保持。旧版可读目标丢失数为零；旧4404份归档全部与新文件SHA逐字一致。

目标日实际Native覆盖为已知范围7884、当前Source范围7883，逐类表见发布记录。缺口保持真实，本轮已声明责任无待推进项，`continuation_required=false`。

| 验证 | 实际证据与结果 |
|---|---|
| 七指标完整调用链 | `formal-deployment001/FORMAL-CHAIN003.json`、`FORMAL-REFRESH003.json`：正式18136，239次HTTP、0次SDK，7指标均生成 |
| 最新及原历史保持 | `formal-deployment001/FORMAL-SERIES003.json`：六项各61点（原60日及最新），T2108原有11月2日/3日两点，逐字段比较差异为空 |
| 独立只读API | `formal-deployment001/FORMAL-OBSERVER-API003.json`：7指标HTTP200、同一观察快照，server及reader关闭 |
| 正常服务启停 | `formal-deployment001/DYNAMIC-STOP007.json`、`DYNAMIC-START007.json`、`DYNAMIC-PROCESSES007.json`：旧两个进程退出，新两个进程存活，同实例/新控制代，组件仅history |
| 原任务与所有原槽 | `formal-deployment001/DYNAMIC-RESTART-BEFORE007.json`、`DYNAMIC-RESTART007.json`：6258份文件逐字不变，含5186个保护旧请求及158个Source资料槽 |
| 首次读取及单一写入 | `formal-deployment001/DYNAMIC-FIRST-READ007.json`、`DYNAMIC-RESTART007.json`：首次读取0.203秒，快照相同，第二发布owner无法取得租约 |
| 接线交付 | `formal-deployment001/CONNECTION-READY007.json`：正式18136、原环境凭据注入方式、实际配置/实例/Source及覆盖，已交Root |

有限验真进程分别由`FORMAL-CHAIN003-CLOSURE.json`、`FORMAL-OBSERVER-API003-CLOSURE.json`、`DYNAMIC-RESTART-VERIFY007-CLOSURE.json`证明根进程回收、进程树为零、读线程结束、EOF及资源关闭。原文件全量冷扫描首次150秒预算不足，`DYNAMIC-RESTART-PREPARE007-CLOSURE.json`保留超时及完整物理回收；扩展预算后`DYNAMIC-RESTART-PREPARE007-RECHECK001-CLOSURE.json`实际56.732秒完成，原线上服务保持运行，重启后全量复核通过。

前版真实证据为`formal-deployment001/CATEGORIES-FORMAL-READ005.json`、`FORMAL-CHAIN002.json`、`FORMAL-SERIES002.json`、`FORMAL-OBSERVER-API002.json`、`CATEGORIES-RESTART005.json`和`CATEGORIES-ORIGINAL-REQUESTS005.json`；这些分别证明上一版价格/资料、7指标、60日历史、独立API、正常启停和5186个受保护槽，不能替代本版全范围验真。

## 未覆盖范围

自然新交易日保持待验；Root拥有的页面接收和账户交易验收单列。T2108现有历史仅两点，本次核验覆盖这两点的保留及实际生成，未宣称取得60日T2108序列。真实缺价、未知单位、动态资料缺字段和PIT不足沿来源事实透传。
