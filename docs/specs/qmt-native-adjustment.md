# QMT原生因子到WT前复权分析窗口

类型：最终规格。状态：accepted。范围：冻结QMT因子、已导入raw日线与原WT Reader的纯值适配，供唯一RR112 1.1.2消费。

## QNA1 目标与输入

正式八证券为510300.SH、510050.SH、510500.SH、512100.SH、588000.SH、589000.SH、159780.SZ、515080.SH。只读FACTOR-INPUTS及逐项原回包/接收时间、已导入原始日线store与成功收据/元数据、原生Reader二进制及固定头。默认原读取参数与原文件保持，不使用活动跨夜Writer根，不操作QMT/账户/UI或现有实例。

QMT第7列是单次事件倍率。按上海日期排序累乘得到WT所需累计因子C(d)，每个事件保留原时间键/七列/回包SHA。事件在其日期起生效；按明确basis_date截取事件，不让之后事件进入该基准。WT factor JSON按exchange/ETF.code输出date/factor；factor使用17位往返十进制字符串，由原getDouble/strtod读取，保留源double精度并避开原JSON数字经WTSVariant固定10位小数的损失；日期仍为整数。三份空数组保持，不伪造factor-one事件。

## QNA2 原生行为与输出

复用原WtDataStorage的IDataReader、adjfactor JSON与“-”前复权后缀读取OHLC；不在Python计算复权OHLC，不改WT算法。WT以C(d)/C(basis)调整价格，原Reader默认adjust_flag=0保持volume/amount原值；此处volume仍为源lot、amount仍unknown且unused。空事件由原Reader的内置基线形成空乘积恒等，来源空返回的含义与独立raw/front核实范围分别标识。

输出可序列化AnalysisWindow/AnalysisBar纯值：同一basis_date、原raw_close、从原生读回得到的factor及分析OHLCV。按(date,symbol)唯一排序，提供八证券共同日期窗与逐证券完整窗；raw历史与native行逐日期配对。source_revision绑定原数据内容/元数据，factor_revision绑定完整因子回包、basis及WT JSON，另锁定Reader/探针和读回正文SHA。

本入口基准限于八证券导入清单共同的最新封闭日期；其他历史基准须另供该基准的冻结输入与参考。prepare_inputs与assemble_window共用原件校验/版本推导，重新从原清单核定每个事件、日线库存和两项revision。read_native直接运行固定原Reader/探针，冻结输入、请求、元数据、二进制和读回文件的不可变NativeRead收据；assemble_window要求该类型并逐项重核摘要及请求绑定。该收据约束模块调用与可变文件身份，进程内部任意Python代码仍处于调用者信任域。真实参考每证券至少含一日OHLC，并要求requested_at不晚于received_at。

保留实际received_at与current-visible-reconstruction；historical_first_available和revision_history均unknown，不按历史收盘时间伪造已知时间，不补辅助策略事实，不授权历史因果回测。原native-empty含义不得被改写为来源已确认无除权。

## QNA3 验收与交付

先完成8证券实际原生raw/front读取、原日期和OHLCV配对、同一基准末日原价，再核59事件的累计/日期与除息前后。原生调整与独立累计关系逐字段核实，真实QMT小范围none/front_ratio参考作交叉验证；三份空表核原生raw/front恒等并单列来源资格。随后核错误摘要/证券/日期/倍率/基准/容量与原数据不变，独立审查、搬迁及文件SHA交付。所有子进程隐藏、有界并正常关闭。共享源码/索引/发行与真实源操作由根负责。

## QNA4 逐日原生回放窗口

显式入口 `qmt_native_replay.build_catalog` 接收已通过 QNA1—3 的 `NativeRead`、原参考收据及全新输出根，产生可独立搬迁的摘要目录。QNA2 的最新单窗口入口保持原行为。回放日期取八证券原生 raw 实际日期交集，不填交易日或缺数；每个计算日窗口包含交集首日至该日的 raw/analysis 配对，首100日的预热资格由原 RR112 核判断。

每个计算日重新调用同一 `load_factors`，只包含截至该日的事件。仅当八证券累计因子 JSON 的规范字节完全一致时将连续日期分为同组；这同时证明各证券事件前缀与分母一致。每组使用固定薄 `WtReplayProbe` 调同 DLL 的公开 `IRdmDtReader.readKlineSliceByCount` 和该组 JSON 读取到组末日；各日只裁切读回原值，价格仍由原 Reader 计算。原 `IDataReader.readKlineSlice` 的纯历史路径从库存尾部取 count，回放使用原随机 Reader 的时间定位接缝；最新 QNA 接口保持。不得从最新基准价格换标签产生历史窗口。原 Reader 请求保持 `adjust_flag=0`，量额保留原值。

目录固定源清单、原回包、raw DSB/元数据、Reader/probe、请求、逐组读回及逐日 basis/factor revision。`ReplayCatalog.open(path, manifest_sha256)` 以调用者固定摘要核全包，装入有界只读纯值，`window(date)` 返回与 QNA2 相同的 analysis/history/current_view 字段；日期越界或文件身份变化拒绝，不修改原件。一次装入后只用内存原值，单次窗口最多32768条。

`known_at` 和 `current_view.received_at` 为本次重建实收时间，不能回填历史日期。`historical_first_available`、`revision_history` 保持 unknown，范围保持 current-visible-reconstruction，不授历史因果回测、辅助事实、账户或交易资格。source revision 对整套 raw 冻结内容稳定；factor revision 同时绑定完整源因子清单、逐日基准和该组 JSON，因此同组不同日期也有独立身份。

## QNA5 回放验收

完整八证券共同401日逐日构建原生窗口，核首末日、事件前后、每窗末日价格等于 raw、量额原值、日期前缀及逐日版本。不同组及同组内部代表日期以独立原 Reader 调用逐字段对照裁切值。对实际 RR112 1.1.2 安装逐日实例化 AnalysisWindow/AnalysisBar、FrozenHistory、CurrentHistoryView。主链后覆盖错误摘要、改动原件、日期越界和非法组归属，独立审查与安装搬迁再核。所有 Reader 子进程由隐藏有界外层 Job 管理并正常退出；运行实例及 WT 框架源码保持。

## QNA6 普通安装的逐日读取入口

产品消费者使用 `guanheng_market_client.qmt_native_replay.ReplayCatalog`，与 QNA4 的 `open(path, manifest_sha256)`、`dates`、`window(date)`及 `manifest_sha256` 保持同一实现。原生分析 core 后继制品包含原回放模块及 SDK 的薄重导出，基础行情 SDK 的原文件保持；消费者显式安装该可选能力，不从数据目录的 lib 注入产品代码。

构建只添加已固定原模块，原因子及其他旧代码逐字保留，来源清单绑定原 wheel 和源码摘要。打开目录只验证文件并装入纯值；窗口读取不调用来源、加载 Native 库、创建子进程或写文件。新窗口容器与原日期、实际接收时点及历史可知性 unknown 保持。普通离线安装后逐一比较全部401日期与原固定目录 API，另核返回值改动隔离、错误摘要和越界；完整 CLI、策略运行和发行各自验收。
