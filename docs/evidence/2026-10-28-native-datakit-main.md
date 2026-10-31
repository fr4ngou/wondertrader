# 原生 DataKit 主链与真实行情来源核查

类型：开发验证证据。日期：2026-10-28。状态：原生合成主路径 passed；真实全市场持续采集 pending-verification。

## 结论与职责

采集主链复用原 QuoteFactory → WtDtCore::ParserAdapter → DataManager → WtDataStorage。行情插件提供 tick，原 Writer 生成分钟线和保存 DMB/DSB，StateMonitor 按原 session 管理收盘。历史缺口准备与持续采集分别验收。此前误建的 Codex 定时检查任务已删除；它不承担行情采集。本轮未操作 QMT 界面、未启动或修改终端策略、未发真实下单或撤单。

## 固定原生输入与范围更正

原生来源固定为上游 08b230dd05facf6d650d949bfe51054115a2ecb1；在 build/qmt-native-datakit-clean-001/snapshot 独立展开。SOURCE-MANIFEST.json 对全部原生源码逐份记录 SHA，并在运行前后验证。此次原生采集组合没有框架覆盖。

共享 checkout 的 Writer 包含冻结 CORE-005；此前 build/qmt-native-datakit-001 的编译和夹具只能证明当时 checkout。其 framework_changes=false 表示该轮没有新增改动，不能解释为未修改上游。旧日志和输出保留，以本记录更正上游资格；本次未修改或回退共享框架文件。

干净 Writer SHA256：075d07b16938a742f1d1baeb09c0a175b8bd333edb3b05ab1a65a63dac06c35a。Windows 编译沿自有构建层先包含 objbase.h 并定义 NOMINMAX/WIN32_LEAN_AND_MEAN，原 WTSDataDef.hpp 保持。实际构建 QuoteFactory、WtDtCore、WtDataStorage、WtDtHelper、自有 ParserQMTHost 和探针成功；QuoteFactory --help 通过。没有 wtpy 依赖。

## 原生采集实际结果

首个干净组合配置每次 pump 处理4096证券，Writer 同步落地；实际在30054ms来源停止，已投递2461，源端13批/2600证券。这证明本配置的轮询工作量把同步 Writer 回调带入单次30秒预算。该观察不证明 WT 的订阅硬上限或框架故障。

后继只将自有夹具 batch_limit 配置为200；full_tick_batch_size=200、5343合约、每证券四快照、接收总90秒、原请求30秒和 async=false 均保持。移除冻结 Writer 专用 mapping_check_interval_ms。未启用原生异步队列，未修改原生 Writer。

实际 ParserQMTHost DLL → 原 DataKit Adapter → 原同步 Writer → 原收盘归档 → 原 Helper：

- 原Adapter订阅5343，源端5343均至少读四次，插件投递21372条（去重后的四快照/证券）。
- 原Writer归档5343份DSB，选择两证券共四根分钟逐项核日期、时间、OHLC、量额通过；其它文件本轮核数量，未逐值声明全体资格。
- source_requests=107，maximum_request_batch=200，SPI错误0；插件停止确认、Adapter release、Writer release均返回。
- 主程序exit0；外层实际100.188秒（含增量编译和归档），Job整树归零、输出EOF、读取线程join和资源关闭均确认，forced=false、own_console=false。

主输出：build/qmt-native-datakit-clean-001/revision-002/{INPUTS.json,RESULT.json,plugin-market/PLUGIN-VERIFIED.json,plugin-market/PLUGIN-DIAGNOSTIC.json,plugin-market/PLUGIN-FLOW-DIAGNOSTIC.json}。受管收据：build/guanheng-workspace/qmt-native-datakit-clean-main-003/build-qmt-native-datakit-clean-main-003/result.json。最终自有probe SHA256=db3ad90d7b8c22a84511353cc612a6d0f5a61905698bc59bc85c27b03800e24c。

原200批量接线已有17项polling及5项真实签名协议替身流通过，见 build/qmt-native-datakit-001/batch-002；这些没有调用真实QMT。原5343为历史库存规模，真实当前清单见下节；本记录不将该规模误称为当前全市场全覆盖。

## 真实来源清单与采样瓶颈

终端外使用安装内 qmt_api.get_stock_list_in_sector，只读取得沪深A股5224（SH2318/SZ2906）、沪深ETF1758（SH992/SZ766）；并集6982、无重叠。ETF板块名返回空，实际有效名称为沪深ETF。来源清单 build/qmt-datakit-universe-001/universe.json，SHA256=aa3cf8a1d51a51935e1a8315c96eff8d9a21497ee0f4121d75029614ce890be1，收据 RESULT.json；进程正常退出。

现有 pair.py 固定1nSecond回调，RestrictedReadAgent.tick每次最多执行一次原生请求；原full_tick每请求最多200。6982证券最少35次策略回调/轮，另有运输和处理成本。调小终端外poll_interval不能突破该来源限制。它是自有来源桥接的限制，与DataKit原生生成分钟线的能力分开。

安装中的 xtquant.xtdata 有公开 subscribe_whole_quote / get_full_tick 包装器，但本轮终端外实际调用未取得可用来源：6982和两证券快照均JSONDecodeError，全推订阅返回失败整数，callbacks=0。两证券/订阅分开核对，避免首次快照异常遮住订阅结果。记录 build/qmt-datakit-whole-quote-001/RESULT.json 与 qmt-datakit-whole-quote-002/RESULT.json。没有把包装器存在或连接状态授予真实推送资格；场外6秒零回调本身也不证明盘中没有行情。

厂商说明将 get_full_tick 与全市场增量 subscribe_whole_quote 列为全推接口：https://knowledge.thinktrader.net/docs/python/question_answer.html 及 https://knowledge.thinktrader.net/docs/cloud/data_function.html（2026-10-28核对）。该通用文档不证明当前国信安装的终端外接口已可用；真实内置ContextInfo能力仍须核实。

## 历史及剩余主路径

本轮读取后台快照：005成功4850份/1285536010根、remaining=487，状态running；旧根尾部刷新成功880份/238259630根、remaining=997，状态running。两组有重叠，不相加。源文件、原截止及活动Writer保持；最终尾部、额外28批和统一全目录仍待完成。

真实全市场持续采集尚未启动或取得新分钟证据。下一步集中解决高吞吐的QMT行情来源接缝，优先复用内置全推与既有共享内存运输；为报价流选择适合持续数据的容量和生命周期，避免直接把命令Journal的小型测试配置用于全天采集。默认路径/已有账户和交易保持原合同，公共契约变化先更新规格。当前没有需要用户选择或批准的框架修改，界面不作为等待条件。
