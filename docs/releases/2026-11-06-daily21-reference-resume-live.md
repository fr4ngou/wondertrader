# 2026-11-06 日线21资料恢复接续上线

状态：deployed，正式owner已经恢复同日补充，最终日线覆盖继续观察。目标为本机独立日线角色；沿用户主线发布授权执行，仅Root操作，主交易、分钟采集与独立观衡持续运行。

## 根因与实现

11月5日价格批次按当时可见证券发布，名册来源暂不可用。价格任务的接续判断只检查已知证券的价格责任，未包含名册恢复责任，导致`price_continuation_required=false`。名册接口恢复后，已发布批次继续停在原来的未知覆盖分母。

对应[UDI-R56](../specs/qmt-source-daily-history.md)：原数据owner在既有观察周期从不可变价格结果重新推导接续责任，名册暂缺时继续原日的修订链。真实捕获后的合法unsupported保持原语义；股票、原HPR责任、取消和CAS链共同保留。源码仅修改两个自有日线模块，WT上游框架保持原状。

## 发布身份与验证

- 源提交`008492d`，注释标签`deploy/daily21-reference-resume-20261106`；发行`guanheng-daily-data 0.2.0a1+unified.21`，SDK0.18.0。
- 固定CPython3.12.13、Flit3.12.0离线构建；制品清单SHA256为`44162ee70964383ac844762265cf0d6393d40825cdfd8d61c37301bb7584f1cc`，168个原源码成员安装逐字节核同，27个wheel安装后pip check通过。
- QA根：`E:/workspace/wondertrader-qa/current-day-20261105-001`。构建`daily21-build001/BUILD.json`，安装`E:/workspace/wondertrader-data/unified-daily-20261104-001/program-reference-resume-20261106-001/INSTALLATION.json`。运行导入返回版本21，版本常量改为读取已安装METADATA，避免旧常量漂移。
- 根因回归：`E:/workspace/wondertrader-qa/daily-reference-resume-20261106-001`下，原HEAD两项断言失败，候选31项通过；独立增量复核确认原责任/取消/未知名册与captured unsupported分支均保持。

## 现场采用与当前结果

原日线控制代`b56e57a2`的Runtime61676和数据进程18028正常退出后，保留原CURRENT原件；通过正式控制器启动新版。新Runtime46676、数据进程33644，控制代`926edb2b-f34f-49a2-a80a-62964681d7b1`；稳定CURRENT、实例、端口18136、原数据配置、历史任务及来源请求均保留。原INDEX、SCOPE与结果没有手工修改。

新owner实际把11月5日的价格接续恢复为true，沿`price-first/r000`建立`r001`；完整日任务沿原REQUEST建立同日r001。真实来源捕获完成126个明细批次，形成8086个保留证券范围；当前资料返回8013个条目，额外保留旧证券及明确生命周期信息。证券名册条目数与实际可读日线覆盖分别核算。

资料来源实际覆盖：沪市股票2318、ETF995、指数270；深市股票2906、ETF770、指数388；北交所股票354、指数12。北交所ETF来源标为unsupported，各组名册完整不代表每个证券当天都有价格。

`DAILY21-START.json`和`DAILY21-ACTUAL-POSTFLIGHT001.json`记录正式启动、同日修订和六角色真实ready；原主交易Runtime41052/Native49624保持。日常操作组改为group020，启动/停止快捷方式同时核对解释器和组配置实际目标。`DAILY21-ACTUAL-RECOVERY002.json`保存本次有界观察的最终状态；价格实际发布与剩余源缺口以该结果及不可变RESULT为准。

## 日志、回退与剩余

从新控制代启动检查Runtime状态、数据owner的`daily-update/98df3532-ee62-411d-a563-014ee82444b5/status.json`及INDEX：恢复期间updating、无error_type；原数据/任务持续推进。本角色业务状态按原文件协议落盘，独立stdout/stderr历史文本覆盖仍有限，不能把空日志作为无故障证明。

回退保留旧service010、program-currentday-20261105-003和CURRENT原件。先由service011正常停止并核实际退出，再按旧服务的原安装/配置建立新控制代；已产生的r001请求与发布数据保留。回退不恢复旧INDEX、不删除源请求。

后续：核本次价格实际发布及各组覆盖；交易时段核本代自然策略计算→目标→模拟执行，真实后继收盘辅助生效和最终清理继续。用户本次截图的回测读取、市场观察慢和自动更新问题按要求在主线发布之后另行处理，当前未宣称修复。
