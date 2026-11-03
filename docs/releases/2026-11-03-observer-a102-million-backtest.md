# 观衡a102与100万元原生回测报告

类型：本机独立Web发布及实际报告消费记录。状态：Web及报告已部署验真；策略自动执行继续验收。观察时间：2026-11-03 15:41—15:57，北京时间。操作者：Root。

## 用户入口与实际结果

打开 <http://127.0.0.1:18143/strategies?tab=backtests>，在“选择历史回测”中选择 `Current 1.1.2 - CNY 1000000 - continuous native replay`。旧12万元报告继续保留，可作为比较报告选择。页面切换只读归档，保持WT和实际账户状态。

本次100万元结果来自一次全新WT原生连续回测。八只ETF共同冻结输入为2025-03-05至2026-10-28，共401个交易日输入和400条日末结果。原生进程实际完成、退出0、非强制回收，原父Owner已发布完成证明。

| 项目 | 原报告结果 |
|---|---|
| 策略 | 共振市场状态ETF 1.1.2，当前纯核 |
| 初始本金 | 1,000,000.00元 |
| 末个模型净值 | 1,054,490.10元，原值保留在报告 |
| 模型区间收益 | 5.44901% |
| 已观察日末最大回撤 | 20.66385254824737% |
| 原生累计费用 | 29,073元 |
| 模拟成交记录 | 97条，开仓33、平仓64 |
| 日末记录 | 400条可用，区间内缺失0条 |

原费用配置沿历史实验：按数量计费，开仓0.01、平仓/平今0.02；这份结果尚未按实际券商费率核定。回放采用本批次前复权分析、原始价格撮合及历史15:00可知假设；历史首次可知时间和修订未知。共同冻结目录尚缺10月29日、30日和11月2日，这三天未进入本报告。报告用于历史模拟评估，自动执行和真实交易资格分别核实。

新报告运行ID为 `f0594a5440794f35a9707494b6e5ac14`；原完成证明SHA256为 `1f7b9c7697eab5122f4ade54f306662eb1aff57d7a1409acd3637917cd4f5acd`，报告SHA256为 `fdca3c7617c67bca2e587b419383a224b6b9bc54fbd73224272c8b9083e8bf10`。原件位于本机 `E:/workspace/wondertrader-qa/current-million-native-backtest-20261103-001`，接入归档位于 `E:/workspace/wondertrader-data/oar-dev1-20261101-001/formal-backtests`。接入的28个文件共7,070,095字节与原运行CAS逐一相等，原12万元归档保持。

## 报告切换失败的根因与实现

a101冷缓存切换报告时，已取消的旧绩效、旧记录读取仍可能在单Worker中收尾；新绩效和记录随后排队。原2个等待位及5秒截止不足，现场新绩效503发生在5.018秒，新记录在32毫秒因队列满返回503，单独读取同份绩效则2.568秒成功。

a102保持独立的单个报告Worker，将等待位设为4，后端同一次总读取预算设为30秒，前端对应31秒。排队和报告比较继续共用原绝对截止；待执行请求可取消，已执行读取沿原截止收尾。关闭等待覆盖这条读取路径。报告内容校验、原归档格式、账户/行情读取及交易权限沿原实现。规格为[BPC](../specs/backtest-performance-comparison.md)。

实际冷切新报告、400条记录、旧新报告比较及首日详情全部返回200，页面异常0；首日净值和现金均1,000,000.00元、实际空仓。新旧报告各显示自己的本金、收益、费用和覆盖。26项报告API消费回归通过，独立限定差异审查P1/P2为0；未据此授予超过有界队列的并发负载资格。

## 制品及独立部署身份

源提交为 `c76b80a`，与 `f74e527` 比较的7份限定文件差异为29行新增、18行删除。固定CPython 3.12.13、Node及原离线依赖闭包，从干净集成工作树构建；具体命令沿[源码构建手册](../runbooks/observer-source.md)。

| 身份 | 实际值 |
|---|---|
| Web版本 | `0.1.0a102+reports.1` |
| ZIP SHA256 | `7d424bfbcd6b3d41dc2401e0715899e8a47bd66a997312cd1ae8f3ba6a65660f` |
| 包清单SHA256 | `d69f07087cfc156285df39e0d26e5750b7156f271381ecb8b8c4089546a391fe` |
| 角色清单SHA256 | `b203800b8b38fb35ac07a7164c5d79aaba10a42ac0435738016bed54fd97aec2` |
| 安装收据SHA256 | `e34a91a89d8278d0b84947cabc9e395bbbbc72b2a711c453d2de618cec9af86d` |
| Web控制ID | `38c35046-24ab-4a72-b624-2dab4e654cec` |
| Web进程 | 56188，创建身份及启动器另见原instance回执 |
| Profile SHA256 | `82535230fe98b32e6b5d73eb47d3a54b35498863bb3f1142fd60900abf7b4122` |

安装位于本机LocalCache/Local/Guanheng/observer/0.1.0a102+reports.1。a101正常停止，两个读取池线程归零、shutdown_complete=true、Web及启动器退出码0后，a102在18143启动。读取环境字节、市场数据根、独立历史连接、个人自选和其余WT引用保持。升级仅管理Web，保持WT、QMT和独立公开资料更新角色。

完整原件位于 `E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：A102-SOURCE-BUILD.log、A102-INSTALL.log、A102-WEB-STOP/START/DEPLOYED.json、A102-REPORT-DELTA-REVIEW.md、A102-API-REGRESSION.log、MILLION-REPORT-PUBLISHED.json，以及a102-cold-reports-browser中的RESULT.json、原请求记录及页面截图。

## 启动、停止与回退

稳定维护指针为 `E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`，它给出当前解释器、控制工具、原Profile和摘要。按[独立Web维护手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)使用同一配置操作；以下只查询当前Web：

```powershell
$observerDeployment = Get-Content -Raw -LiteralPath 'E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json' | ConvertFrom-Json
& $observerDeployment.python -I -B $observerDeployment.tool status --profile $observerDeployment.source_profile
```

需要启动、正常停止或重启时，将同一命令的 `status` 改为 `start`、`stop` 或 `restart`。保留原运行Profile供停止和未知状态核查使用；新读取配置采用新Profile与控制目录。个人自选和报告归档继续使用外部原目录。

a101安装和原Profile保留，归档格式兼容；它在冷缓存快速切换报告时仍有本次已复现的短截止问题。回退须先正常停止a102，沿原a101配置启动，再核实际归档及数据绑定；本次没有执行a102到a101回退。WT后继绑定必须取实际运行发布身份，旧Profile中的WT身份保持其历史含义。

## 主线剩余与边界

15:57时Web账户/策略仍绑定已正常关闭的Full31；后继Full32五组件就绪，但策略资本仍为空。开发者2正在修正重启时只接受QMT快照、遗漏同账本已确认CTA估值的恢复逻辑；实际资金恢复及Web后继绑定继续，不能用Web报告成功证明策略已自动上线。Full32写入关闭，本次金融命令0。

独立公开资料更新仍为a99，30来源及原三个窗口保持。机构数值后继源码已接收，独立更新角色部署另验。市场观察、T2108及50指数补齐与唯一ETF策略上线主链分别推进。
