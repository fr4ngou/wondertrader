# 原生隔离回测运行

类型：运行手册。适用范围：受管安装中的本机操作员回测。接口要求见[NBC](../specs/native-backtest-cli.md)，原生模型与结果边界见[回测模块](../modules/backtest.md)。浏览器入口、真实来源及生产资格另验。

唯一1.1.2日线接缝使用显式最终批次模型，固定JSON输入及原生run入口见[RR112-R5/R6](../specs/retained-resonance.md)。[独立WT安装](../evidence/2026-10-30-standalone-native-backtest.md)已完成401日输入/400次闭合、原持仓/费用及用户状态保存；当前操作员入口沿[NBC-R5](../specs/native-backtest-cli.md#nbc-r5-独立wt运行侧回测)。观衡只读报告与最终统一候选分别验收。

## 安装输入

使用已核对版本/内容摘要的独立WT wheel及固定六发行，另提供匹配的WtBtPorter、ABI探针、基础资料和`nsh-wt-install-v1`安装绑定。Python依赖包含原策略纯核和数量包；该环境使用无`.pth`启动钩子的标准非editable安装。通信Host和观衡沿各自角色环境安装。原生DLL不从Python公共索引获取；安装绑定、SHA和本机固定盘运行根由操作员显式指定，运行根须预先存在。

安装器通过`guanheng_wt_runtime.backtest_installation.write_binding`传入目标解释器、原生目录、ABI探针及sessions/commodities/contracts/holidays/fees五种资料，完整校验后生成新绑定。搬迁或升级后按实际新路径重新生成绑定，保留旧运行目录及旧绑定，不直接复用指向旧安装的机器路径。

会话JSON沿NSB/NSH公开值结构提供配置、完整冻结历史、信号/执行代码映射、原生日线、显式资本与费用来源；完整输入最多16MiB。先核来源、日期/闭合时钟、复权与量价单位，再选择对应回放时刻。合成测试资料明确标记，不能因程序运行成功提升为真实行情资格。回测callback不联网或临时下载，QMT终端通道替换按[DEC-001](../migration/decisions.md)独立推进。

事后取得的历史日线按[历史回测模型](../specs/historical-eod-model.md)显式声明批次、实际实收和模型假设，使用`nsb-historical-report-v1`。页面沿“策略 → 原生回测与报告”读取，详情显示上海时区的实际批次接收时间、15:00日末假设及源金额单位未知/按元解释。模型资金显示到分，完整原值保留在报告详情。完成后核归档状态，重启可读取同一份归档；读取失败按页面按钮手动重读。历史首次可知与修订未知仍保留，本报告的模型结果用于历史回测。

## 操作员命令

以下路径和摘要均为占位示例，使用实际受管安装中的解释器执行：

```powershell
& "<已安装Python绝对路径>" -I -B -m guanheng_wt_runtime.backtest_cli `
  --binding "<安装manifest绝对路径>" `
  --binding-sha256 "<已核小写SHA256>" `
  --work-root "<已建立的运行根绝对路径>" `
  --session "<冻结会话JSON绝对路径>" `
  --start 202401030930 --end 202401091500 --seconds 1800
```

起止为上海回放时刻`YYYYMMDDHHMM`。总预算默认1800秒，`--seconds`只能收紧到0.1秒；准入和文件读取耗时会扣除，不因进入子进程重新取得完整预算。`--name`默认为resonance，具体合法范围沿宿主检查。Ctrl+C交给原运行owner取消并回收，不需要按进程名终止其他程序。

`--help`输出固定说明并退出，不读取会话或启动宿主。运行参数错误统一返回JSON，不回显原参数；日历、小时/分钟和起止顺序在原生装载之前检查。

## 解释回执

stdout只有一条ASCII JSON回执，中文使用JSON转义以跨Windows代码页保持原值。`status=completed`且退出0要求原宿主确认非forced、子进程exit0、结果与原生输出核验通过、进程及管道已回收；完整报告保留在回执directory下的原宿主输出。`scope`说明模型和来源资格，回执不另存一份全部逐日历史。

准入拒绝同样保留完整字段，尚不存在或未确认的run/pid/回收事实以null表示；scope解释原生尚未启动或owner结果未知，不能把null当作已回收成功。

busy退出3，普通失败退出2，已请求取消的不完整运行退出130。超时、部分提交、结果身份不符和回收未知均保持不完整，原运行目录保留；处理具体原因后再显式启动新运行。没有自动重试、自动删除旧运行或生产终端变更。原生CSV、共享历史及完整前缀重建接口用于结果核对，理论持仓和损益保持回测归属。

## 验收

CLI路由/准入/信号/退出码测试位于`tests/integration/strategy_cli`，实际安装后的CLI→原宿主→原DLL链另取证。执行本仓库测试时，将pytest临时目录与XML显式指定到E盘独占输出根，并先建立其父目录。初次准入失败、业务回测失败、测试配方超期及完整成功分别保留记录；资格以实际证据为准。

## 浏览器回测配置

逐日原生基准的开发API及报告读取见[R28证据](../evidence/2026-10-30-per-date-native-replay.md)。新族guanheng.retained-per-date-replay-report.v1使用独立逐窗模型，由WT的backtest_reports.validate_report_dict及project_session_record读取；原最终批次会话和报告族保持。逐日产品入口沿R28-C4及下文R6验收，观衡只读归档消费由其模块owner核实。

逐日CLI接线沿[NBC-R6](../specs/native-backtest-cli.md#nbc-r6-逐日基准的配置入口)验收。该角色在原六发行之外安装匹配的 `guanheng-native-analysis-core` 后继，保留原market-client wheel；通过固定SDK import读取原ReplayCatalog。部署生成绑定时显式提供 `replay_catalog={path,manifest_sha256}`，会话采用R6的纯值外层，包含原session和完整逐窗source绑定。操作命令保持上文形式，行情目录路径归安装配置。默认最终批次角色仍使用原六发行和原会话。运行资格以安装后CLI证据为准，逐日模型保持历史15:00假设及真实首次可知未知。

需要在观衡重启后读取本次结果时，给同一安装CLI增加`--archive-label "逐日回测示例"`。沿[NBC-R7](../specs/native-backtest-cli.md#nbc-r7-wt父责任层发布原完成证明)，WT在本次原总期限内完成进程回收与原件核验，再发布原运行目录的`completed-archive.json`。回执的archive.status为available及固定receipt_sha256时，观衡可将已有归档根指向该runs目录，只读原配置、报告和绩效。执行已完成但archive为unknown时保留完整目录核查；子result.json和旧stdout不能用于补造父完成证明。省略该参数保持原CLI行为，历史R6目录保持原件。具体安装及消费资格沿[完成证明证据](../evidence/2026-10-30-wt-backtest-completion.md)。

本节保留原App托管制品的配置和报告读取背景。当前独立WT新运行使用上述命令；观衡消费新绑定/完成报告的只读接线由其模块owner集成，按独立证据授予资格。

已完成归档可在“回测与报告”标签页查看“回测绩效与比较”。先选择历史回测，再选择另一份比较报告；每次读取核验原配置、报告、安装及原生输出摘要。收益以显式初始本金和末个合格日末净值计算，回撤以初始本金及已观察日末峰值计算，费用为末次原生累计值。缺失观察保留为空，详情见[BPC规格](../specs/backtest-performance-comparison.md)。条件差异用于解释各自结果，报告范围和来源资格沿原件保留。

读取失败时保留原运行目录，按提示核查完整性、权限或容量，再点击“重新读取绩效”。此操作只读文件；重跑需要从原运行入口显式启动。两份报告共用一次读取截止。同一报告或报告对刷新失败时保留上次成功结果和原读取时间；首次失败按提示重读。切换报告后显示所选报告自己的结果。可选择“仅查看当前报告”分别核查。升级或回滚须保留运行根及原completion receipt，使用与归档报告族相匹配的应用版本。

独立应用可通过`GUANHENG_BACKTEST_CONFIG`和`GUANHENG_BACKTEST_CONFIG_SHA256`读取有摘要的部署文件。以下JSON为占位示例，路径和摘要须替换为实际受管值，运行根预先建立：

```json
{
  "schema": "nbw-config-v1",
  "binding": {"path": "E:/guanheng/installation.json", "sha256": "<安装manifest的64位小写SHA>"},
  "work_root": "E:/guanheng/backtests",
  "session": {"path": "E:/guanheng/frozen-session.json", "sha256": "<冻结会话字节的64位小写SHA>"},
  "start": 202401030930,
  "end": 202401091500,
  "name": "configured",
  "label": "示例冻结输入",
  "max_seconds": 30
}
```

路径、安装和会话由部署管理，浏览器仅操作当前owner/request身份，不上传源码或替换DLL。只配置回测不接入券商终端，也不开放真实交易。部署文件默认关闭，变更后重启本业务应用生效；回测配置错误时该功能保持不可用，其他已配置能力继续提供服务。

从`/backtests`或`/strategies?tab=backtests`打开：核对策略名称、版本和北京时间回放范围后点击“启动回测”。当前新运行固定为共振市场状态ETF策略1.1.2；旧版本保留已保存报告读取。内部输入摘要、运行及进程身份归维护诊断资料。重复同一request只认领原运行；接收超时后先“刷新状态”核查，再点击“核查运行结果”，继续核查原任务。取消先发停止请求，进程及管道回收事实由原宿主结果确认。关闭页面只停止该页面读取，原运行继续。

本进程状态投影至多128次受理；完整实验保留在NSH原运行目录，报告按页和当日读取，不新增任务数据库。业务进程重启更换owner_id，旧请求拒绝，原目录保持且不自动执行。容量满或线程启动/关闭尚未确认时，按中文原因核查原运行证据；启动未知持续时由运维关闭业务进程、确认自有子进程回收，再启动新的owner，禁止按同名进程批量终止。

CLI与浏览器若显式配置同一运行根，仍受NSH的OS排他锁保护；繁忙保持原任务，操作员等待原任务结束后再提出新的运行。模型资金、实际模拟持仓、目标和提交阶段分别展示，完整增长历史与原生CSV归对应实验。
