# 原生隔离回测运行

类型：运行手册。适用范围：受管安装中的本机操作员回测。接口要求见[NBC](../specs/native-backtest-cli.md)，原生模型与结果边界见[回测模块](../modules/backtest.md)。浏览器入口、真实来源及生产资格另验。

唯一1.1.2日线接缝使用显式最终批次模型，固定JSON输入及原生run入口见[RR112-R5/R6](../specs/retained-resonance.md)。[独立WT安装](../evidence/2026-10-30-standalone-native-backtest.md)已完成401日输入/400次闭合、原持仓/费用及用户状态保存；当前操作员入口沿[NBC-R5](../specs/native-backtest-cli.md#nbc-r5-独立wt运行侧回测)。观衡只读报告与最终统一候选分别验收。

## 研究回测与查看

按[策略开发与回测交付](../development/workflow.md#策略开发与回测交付)区分研究输出与观衡正式归档。

1. 按策略适用的 [WT 原生入口](../modules/wondertrader-strategy-capabilities.md#三原生回测实际调用链)运行，固定策略版本、数据、时间范围、本金及成本模型。已有项目受管接缝的策略可用下文 CLI，将 `--work-root` 指向独立研究目录，并省略 `--archive-label`。研究输出目录置于观衡读取根之外。
2. 默认复用用户当前打开的 WT 官方 [`WtBtSnooper`](https://github.com/wondertrader/wtpy/blob/master/wtpy/monitor/WtBtSnooper.py) 查看。本机先核 `http://127.0.0.1:8081/backtest/backtest.html` 及 `/bt/qryws`，确认现有实例和工作空间。研究回测目录独立于查看器进程。只有当前实例确实不可用，或有明确的兼容性隔离要求时，才另开查看实例，并在交付时说明入口和原因。
3. 用户指定收录报告时走[正式归档](#正式归档的唯一位置)。已有项目报告须具备有效的 WT 父完成凭证才可按原件采用；只有研究输出时，以冻结输入通过正式入口运行并生成完成凭证。

### 在现有查看器中登记结果

1. 将各对照方案作为同一个工作空间根目录的直接子目录。每个子目录应有 `summary.json`、`btenv.json` 和原生 `funds.csv`、`trades.csv`，按当前查看器版本补齐其他分析所需原件。结果根目录由当前实验选择。需要更改显示名或裁去预热行时，使用独立只读展示副本，保留原生输出。
2. 先按路径核对 `/bt/qryws`。尚未登记时使用查看器「回测工作空间」旁的加号，将工作空间根路径和显示名登记到现有实例。每次复用同一登记项。登记后刷新左栏，用 `/bt/qrybtstras`、`/bt/qrybtinfo`、`/bt/qrybtfunds`、`/bt/qrybttrds` 核对方案数、评价日、净值和成交，确认旧工作空间仍可读。
3. K 线历史由当前查看器的数据服务提供，单独核 `/bt/qrybars` 的日期和输入口径。若只覆盖部分区间，在同一交付中写明覆盖，提供完整净值或已冻结的行情原件。正式观衡归档沿第 3 步的完成凭证流程单独判断。

## 本机 WT 原生回测查看页

浏览器打开 **http://127.0.0.1:8081/backtest/backtest.html**。本机 WtBtSnooper 工作空间包含共振原版仓位实验对照和 177 日长窗口报告。

若地址未监听，从既有查看器安装启动。入口使用 UTF-8 读取中文工作空间配置，启动日志与入口文件同目录。

```powershell
$viewer = 'D:/wt-build/wt-bt-snooper-exposure-20261108-001'
$entry = 'E:/workspace/wondertrader-data/reboot-adoption-20261109-002/start-wt-snooper.py'
Start-Process -FilePath "$viewer/venv/Scripts/pythonw.exe" -ArgumentList '-X','utf8','-B',$entry -WindowStyle Hidden
```

启动后检查页面响应与 `POST /bt/qryws`，并打开既有工作空间核资金曲线。WT 回测执行仍沿下文 CLI 按任务启动。

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

CLI路由/准入/信号/退出码测试位于`tests/integration/strategy_cli`，实际安装后的CLI→原宿主→原DLL链另取证。执行本仓库测试时，将pytest临时目录与XML显式指定到受控独占输出根；回测及延迟敏感数据沿用户指定D盘，并先建立其父目录。初次准入失败、业务回测失败、测试配方超期及完整成功分别保留记录；资格以实际证据为准。

## 正式归档的唯一位置

观衡只读已有完成报告；WT原生回测CLI拥有新运行和父完成证明发布。正式位置由受控运行环境的 `backtest-current/STORAGE.json` 记录，字段 `state=active`、`archive_root`、`work_root` 与实际采用收据一起核对。该文件是运维采用记录，CLI显式参数与App环境分别沿其原入口配置。

当前受控记录为 `E:/workspace/wondertrader-data/backtest-current/STORAGE.json`，已采用根为 `D:/wondertrader-data/formal-backtests-20261107-001`。观衡使用 `GUANHENG_BACKTEST_ARCHIVE_ROOT` 指向此根，在正常重启时绑定。为用户指定的报告直接运行并归档时，WT CLI 显式使用同一位置：

```powershell
& "<已安装Python绝对路径>" -I -B -m guanheng_wt_runtime.backtest_cli `
  --binding "<安装manifest绝对路径>" `
  --binding-sha256 "<已核小写SHA256>" `
  --work-root "D:/wondertrader-data/formal-backtests-20261107-001" `
  --session "<冻结会话JSON绝对路径>" `
  --start 202401030930 --end 202401091500 --seconds 1800 `
  --archive-label "<本次回测中文名称>"
```

CLI独立解析 `--work-root`，由操作员核对STORAGE记录；Observer环境变量只配置读取应用。`--archive-label` 要求WT父责任在原期限内完成回收与原件校验，再于原run目录发布 `completed-archive.json`。回执 `archive.status=available` 和固定receipt SHA才授予正式归档资格，详见[NBC-R7](../specs/native-backtest-cli.md#nbc-r7-wt父责任层发布原完成证明)。archive为unknown时保留原运行核查，子result或stdout不足以补造父证明。

原版 `0.2.0a1` 开盘报告使用[ONB-7 冻结会话](../specs/original-native-backtest.md#onb-7-次交易日开盘正式回测)。`--start` 为评价首日前一个交易日的 14:59，`--end` 为评价末日的 15:00。按份费率和成交额万三分别使用匹配的安装绑定、会话文件和可区分的 `--archive-label`。运行完成时 WT 直接在原运行目录发布完成证明；观衡的回测列表按策略版本归类，已打开的列表可用“刷新列表”重读。隔离脚本与归档外的试跑不进入正式列表。

完整已完成run采用新根时，沿受控采用流程逐文件复制、核源前后与目标SHA，再用支持该报告族的普通安装归档owner核所有引用、摘要和详情投影。保持报告、完成证明、原安装绑定、相对输出和run身份原字节；源目录保留备份。当前D盘9run/252文件已逐件核验，见[采用记录](../releases/2026-11-07-observer125-data-update-and-d-archive.md)。进行中的旧E运行继续由原owner在原根完成，完成后再按完整原件采用流程处理。回测及延迟敏感数据按用户指定放D；C盘候选从未线上采用。

## 浏览器只读报告

从 `/backtests` 或策略页的“回测与报告”打开。列表核完成证明后展示轻量目录，用户选择报告才读取完整绩效和分析。报告切换保留各自绑定；比较、曲线、悬停日摘要和固定日明细沿[BPC](../specs/backtest-performance-comparison.md)及[读取性能规格](../specs/backtest-report-read-performance.md)核验。收益、回撤与费用按原报告显式资本及原生日末值解释；模型持仓、策略目标与实际成交分别展示。

读取失败保留原目录，按提示核完整性、权限、容量及原件再显式重读。同报告刷新失败保留上次成功结果和读取时间；切换报告使用新绑定。重跑沿WT CLI启动，页面不负责新回测或交易。旧 `GUANHENG_BACKTEST_CONFIG` 托管运行配置属于历史阶段；当前观衡只读入口沿上述归档环境，原历史实现见Git及[NBC](../specs/native-backtest-cli.md)。
