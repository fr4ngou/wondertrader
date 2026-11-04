# 2026-11-04 分钟采集与动态日线正式采用候选

类型：验证及交付记录。状态：`pending-verification`，MCC-10最终候选已开发及离线准入；正式Source、角色切换和实际采集覆盖由Root维护后验收。本记录接续[原分钟候选](2026-11-04-continuous-minute-collection.md)，保留该记录当时的材料及边界。

## 最终行为与输入

正式日线SMP原配置同时承担动态查询与每日生产。直接用分钟叶配置替换Snapshot.base会丢失其日线覆盖层、证券资料及后继发布连接。最终实现将`history.source-query`连接到同一分钟producer及标准Reader，其余请求完整委托原`source-market-current`，批量日线沿原`read_scope`；原`daily_update`、市场CURRENT、任务根和保护槽保持。新日线角色使用独立的控制CURRENT，原控制器保留完整回退入口。

本次Root基线为`41a08380e862382b01053b3d21842f0b8b152478`（日线`.9`）；分钟代码为`76b14e3`、`2c93579`，并入`.9`的工作树提交为`61120ae`。最终文档提交另在交接登记。工作树为`E:/workspace/wondertrader-worktrees/minute-adoption-v8-20261104`。

新程序和材料根为`E:/workspace/wondertrader-data/minute-adoption-20261104-001`；证据及操作材料根为`E:/workspace/wondertrader-qa/minute-adoption-20261104-001`。所有本次新产物、日志和临时目录位于E盘。原每日配置既有`raw_store`仍指向原受控目录；本任务未迁移或写入该目录。

| 固定对象 | 路径（相对材料根） | SHA256 |
|---|---|---|
| 程序 | `program002/INSTALLATION.json` | `fea78eb3a656321c88ea2efbca667d0728d7f825157f82e8e9f175accf62649c` |
| 部署描述符 | `configuration002/DEPLOYMENT.json` | `ef46946dc7324659f1d6627f15207a68a46b788ca75b100c4bba73efdc048277` |
| Source CAS | `source001/SOURCE-CAS.json` | `68eb139ac0561222808b1e6a84c2f879ace901c0f0ea67ef4960ac5f87cf3e4a` |
| 新完整Source | `source001/strategy.py` | `166418dab7fb25f3b639384d56bacb947c066878afbf802fabac823fa5143c6c` |
| quotes及回退绑定 | `bindings001/BINDINGS.json` | `09c6a0201273f7bee5c388402370c491f153048ec851f0e8fd19ddb6c3f3522b` |

Source仅更换同一QST证券/profile并移除无消费者旧交易owner；原HPR配对、profile、Journal以及v7/v8设置逐值保持。当前原Source before SHA为`4450295ed1a4d39504e447380cac1543c0340292ab4af85132b92e02ddf9c34b`。HPR沿原max_rows=10/max_data=4096/result=8192/frame=65536及1024条Journal，闭合日分页37页、15次后继共630条的需求在原额度内；没有扩大原Host持久状态。

`collection_acceptance.py`原聚合将读取失败的`missing_count=None`按0计算，会把未知缺口误作已确认无缺口。修正后分别报告已报告/成功核查/未报告/未知/读取失败；总缺口在全订阅集合均核实后才提供数值，其他情况保持None，已知缺口另列小计；明确当日Reader失败使`passed=false`。

## 实际验证与审查

| 证据（相对QA根） | 实际结论及范围 |
|---|---|
| `DAILY-PRESERVATION001.json` | 66次请求逐字段响应相等，含53个官方指数、两个CNI各84根及原Snapshot/资料/事实；不启动服务 |
| `BATCH-SCOPE002.json` | 实际CurrentReader及生产批查询中切换局部CURRENT，同批保持原版本，下一请求跟随后继；正式CURRENT未写入 |
| `FINAL-SOURCE-INPUTS001.json` | `.9`完整Source输入与9项自有Native输入匹配；复用`mca001`的79文件构建 |
| `ACTUAL-SMP-ADMISSION002.json` | 实际`.9`SMP解释器按runpy入口加载program002；完整SDK及App日历来自原安装，未注入sys.path，原daily_update相等；0 Source/资源 |
| `FINAL-PREFLIGHT002.json` | 全部新Runtime/子组件/日线ServiceConfig准入及程序逐文件验证通过；0服务/Source |
| `BINDINGS-PREFLIGHT001.json` | 最终quotes-new、data-rollback、quotes-rollback各自实际薄启动入口`--preflight`通过；没有创建owner或服务 |
| `HANDOFF-PREFLIGHT001.json` | 原2950保护槽全在，两笔未知请求ID及保护成员资格保持；原HPR配对/Journal保留，金融WT八组件归属保持；日线仍updating，维护等待Root交接当前轮责任 |
| 根因回归 | full 15项实际通过；未知缺口修正后定向4项通过，当前总用例16项，Reader失败+未扫描分母场景明确保留未知；未重复未变Native输入 |
| `REVIEW-SPEC-001/002.md` | full及P2 delta规格复核完成；代码遗留P1/P2为0 |
| `REVIEW-STANDARDS-001/002.md` | full发现未知缺口P2；`2c93579`修正后delta关闭，代码遗留P1/P2为0 |

最终`.9`合并、固定包及操作材料另以两轴delta复核，具体源码身份和结论在QA最终报告登记。原WT框架代码未改；金融模拟下单/查询/成交/撤单已验范围由Root保留，自然行情后续归日常运行观察。

## 可执行交付与现场边界

QA根`HANDOFF-001.md`列固定对象、完整步骤和剩余范围；`commands001.ps1`按Root显式选择的单一Phase调用原CLI、原ServiceController及已审DataRoleProcess。新进程使用隐藏窗口，正常关闭核原closed/进程树结果；超时保留现场，不强杀、不删锁、不自动重派。`accept-final001.py --day 2026-11-04`核同一新data owner，查询18130/18136各12样本并读取实际collector覆盖，在全新时间目录保存结果。

本轮尚未改变实际GH Source或启停服务。正式切换须等当前日线轮次/原请求责任交接，由Root统一维护；金融八组件及其分析owner保持。原2笔未知prepare沿原ID继续核查，槽正文允许原owner合法推进，身份及保护关系保持。

7649为候选QST集合，非实际收到行情数。已知北交所366项被当前自有QST/HPR分钟合同拒绝；双市场样例准入证据在`BSE-CAPABILITY001.json`，底层SDK/WT分钟能力未据此推断。真实12样本、整集合当日缺口、未收到/旧日、未扫/失败及当日历史准入须分别报告，不能据声明/少量样本授全市场完整。
