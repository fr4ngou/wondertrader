# WT持续运行与日常启停上线

类型：发布记录。日期：2026-11-04。状态：已部署，实际原账停止/重启和观衡自动跟代通过；唯一1.1.2策略等待首次自然行情计算。账户仅限用户确认无真实资金的模拟账户尾号1314。

## 当前入口

操作目录为`E:/workspace/wondertrader-data/wt-service`，双击`启动WT.lnk`或`停止WT.lnk`；链接直接调用安装后的无窗口Python入口，未新增定时任务。重复启动保持同代，不创建重复Host或执行器。`查看系统状态.url`打开独立观衡；观衡入口为`http://127.0.0.1:18143/strategies`，系统状态为`/operations`。

需要读取命令结果时，在PowerShell执行：

```powershell
& 'E:/workspace/wondertrader-data/runtime-service-20261104-003/venv/Scripts/python.exe' -I -B -m guanheng_wt_runtime.service_control status --service-config 'E:/workspace/wondertrader-data/strategy-capital-real-20261102-001/private-service-20261104-001/service003.json'
```

把`status`改为`start`或`stop`执行相应动作。安装索引为`E:/workspace/wondertrader-data/wt-service/DEPLOYMENT.json`；公开当前代为`E:/workspace/wondertrader-data/wt-current/CURRENT.json`。控制器维护恢复材料，操作员无需编辑UUID。QMT原通信/行情策略继续运行；停止WT不会停止独立采集或观衡，重新启动WT时原Source能自动重新配对。

## 版本及源码

- WT Python角色：`0.1.0a12+integrated.2.market.35.3.service.4`，精确SDK依赖0.15.0。wheel SHA256为`55d5c09181cdcf3cf03a6ac7b62c5752fa7609d744cc3d183618785a6a221694`。
- 自有GuanhengCtaRuntime SHA256为`de635108efc06fa2f0fbab99bb4004619f453692aaa2df53bbf09aecf1b9b950`。WT框架链接输入保持原冻结版本，未新增框架差异。
- 账户Host角色：`0.1.0a22+mdphttp.3.tes.1.uc.1.sdkreturn.1.accountdiag.1`；仅更新首次故障诊断的两份模块，wheel SHA256为`4856500fcd08c7dc358056be6d29ced3d7f88cdd6ec1a6be5e2278e49610e3b7`。
- 实际QMT组合正文SHA256保持`b581bf707281290465201b0964d9ef2c6a224935131f160fd13047d1f47f90d9`，未修改或重启QMT策略。新增Host配对的Agent设置与原件逐项相同。

持续运行与恢复比较见[实现及SDK证据](../evidence/2026-11-04-continuous-execution.md)，服务控制普通安装见[模块验收](../evidence/2026-11-04-wt-service-control.md)，Host诊断见[诊断切片](../evidence/2026-11-04-host-failure-diagnostic.md)。普通执行owner现在保存实际配置原字节；库存准备已生成物化配置时沿原件复用。恢复核对原ready、实际配置SHA、前代收据和金融状态，保留原资本及策略记忆。

## 实际业务结果

QA根为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/continuous-runtime`。`SERVICE-RESTART-PROOF.json`记录日常入口的实际正常停止和同账重启；`FINAL-LIVE-PROOF.json`记录最终版本，`SERVICE-FINAL-ROLE.json`及`NATIVE-INSTALLED.json`记录安装身份。

最终控制代为`8e7c0d65-fc34-4cd3-98d5-9bb2f5b2dee4`，逻辑实例保持`a309716d-1288-4328-ac57-abd6ef0bb2e9`，Runtime配置SHA256为`710028bec785a62056326f2113e0d5da69e8fe0e3aab1ae928121fdc365dbac0`。当前身份以公开CURRENT为准，日常重启会正常换代。

- 账户Host、账户观察、交易Host、历史服务及Native执行器实际ready。
- 运行预算显式0，持续运行至正常停止。两次实际停止均走原关闭链并成功重新启动。
- 策略基准100万元，现金633075.20元，五项非零持仓完全连续，未导入旧成交记录。原BASELINE SHA256保持`8701e1ae8e632d8e1229079b60a7137f0bc0a0663b47ceca694909da70c6eac3`。
- 观衡Web PID60848及其创建时间保持，API自动读取新代并返回available/ready；展示五项非零持仓和同一策略现金。最终渲染补验由观衡交付记录关联。
- 独立行情采集、历史服务和市场观察进程保持运行。本次未发送新的券商下单/撤单；Native策略setter计数0。

## 故障、回退与剩余

前代账户Host在01:22出现`runtime_failed`，触发Runtime按原依赖关闭；Native正常退出。原Journal仅保留8/128条、约2.23/32MB，未耗尽容量。原错误未保存内部分类，具体根因仍未知；原收据保留，新版增加有界首次故障诊断。首轮新安装还修正了Host配对生成使用python.exe、实际入口使用pythonw.exe的不一致；失败代Native从未启动，金融原件未变，配对已按实际入口重新生成并核验。

发生新故障时保留CURRENT、服务代际目录和Host的`failure-diagnostic.json`，使用同一状态入口核查；用户显式启动沿原恢复链核未决责任，控制器不会自行循环重试或重复委托。

回退前先正常停止本代。旧Python角色、原Native DLL与安装清单均保留，Native原件备份位于QA根`native-release-before`。回退使用原恢复入口生成新代并保留当前账本，禁止将已消费控制目录直接当成新运行目录。

当前为非交易时段，首次自然策略计算及其后续券商业务结果尚未观察到。全市场日线/前复权和指标持续接线由数据模块继续交付；最终产物清理需保留当前安装、原账、依赖及未合入成果。整体目标继续进行。
