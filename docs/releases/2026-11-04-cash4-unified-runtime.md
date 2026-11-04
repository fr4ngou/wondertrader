# WT现金精度与持续分析统一启停上线

日期：2026-11-04。角色`0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.4`，正式操作目录`E:/workspace/wondertrader-data/wt-service`。仅沿用户已确认的模拟账户及现有1.2.1策略权限运行。

## 最终行为

正式金融WT统一拥有交易、账户和两类分析通信、账户发布、历史查询、持续分析窗口及原生执行共八个组件。启动和停止快捷方式已更新至013解释器与正式service.json。独立观衡110、全市场采集、HPR及日线服务保持各自运行；关闭观衡不影响交易。旧的独立分析发布进程与分析通信WT已正常退出。

当前已完成实际正常stop/start：新代自动选择新的Reader派生cache叶，无需手工移动目录；同一逻辑实例、financial-state008及initial-inventory008保持。当前3个非零持仓市值为278688.9元、现金721311.1元、净值精确为1000000元，原49条委托没有新增或重复提交。

报价档位来自本代已准入的WT品种资料。仅消除double表示尾差，实际离档报价仍拒绝；市值和NSQ共用精确报价，现金比较、均价及佣金保持各自精度。恢复时Python与自有Native只排除派生cache定位差异，行情来源和金融配置继续严格比较。Reader正常退出按原协议回收自己的派生文件与空目录，Controller保留原行情和金融输入。本次没有新增WT框架修改。

## 身份与证据

- 主干现金精度为`5e60c96`，缓存恢复为`26992b4`，完整cash.4源码为`a2a147f`，不可变注释标签`guanheng-wt-runtime/cash4-20261104`。43模块仅更新已审4项，其余39项及旧角色中的5项历史差异保持；V1a9、QNA及依赖保持。
- 固定wheel SHA256：`77f4b2cfcefd9389700437a58a061758a55e745424465d3c27b866cc05a311d1`，从正式永久入口重建整包一致。原生组件SHA256：`02737c3a93256133c860351cfc435aae3a6c7af50826755c8533daf99af075db`，仅重编自有CtaProcess，沿原固定链接输入。
- 当前control为`a4009704-823c-4cc0-a1ac-d0450a815371`，金融WT PID25080、Native PID49784；实际身份随后继重启变化，以稳定CURRENT及部署索引为准。
- 实际service为`E:/workspace/wondertrader-data/strategy-capital-real-20261102-001/unified-analysis-service001/activation001/service.json`；正常停止和重启均exit0，八组件ready，新旧cache定位不同，原金融基准SHA不变，HPR保持运行。
- 新owner已实际读取并发布11月4日分析窗口，published_count为31，source_error为空；观衡策略、持仓及状态三页无需重启即可跟随新代，实际刷新/截图通过，控制台错误为0。

证据根`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`：`CASH4-ROLE.json`、`cash4-mainline-wheels001/REBUILD-RESULT.json`、`cache-successor-native001/RESULT.json`、`unified-analysis-service001/MANAGED-PUBLICATION.json`及`CASH4-LIVE-UI.json`。实际启停原件位于上述activation001的`NORMAL-STOP.json`、`NORMAL-RESTART.json`和`NORMAL-RESTART-ACTUAL.json`。首次核验曾误要求旧cache目录继续存在，原脚本保留；后继只读核验确认Reader正常回收派生目录，没有再次启动或改写业务结果。

## 剩余与恢复

当前reason为awaiting_first_strategy_calculation，处于盘后等待。本代首次自然计算、新ETF柜台受理及自动下单/成交/撤单仍待交易时段验真。分钟完整Source和角色正式切换、全市场日线自然新日推进及最终无引用产物清理继续，不将本记录作为整个系统验收完成。

原012角色、旧配置和原Native备份保留；备份位于activation001/native-before。金融版本恢复必须先停止当前代，沿实际关闭证据、原金融状态及安装身份重新准备交接；不能直接用旧Reader缓存定位或重放旧委托。正常日常启停使用当前快捷方式及service入口。
