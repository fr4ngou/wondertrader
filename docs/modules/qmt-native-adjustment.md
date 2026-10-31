# QMT原生复权适配

类型：模块说明。状态：developed，安装验真与独立复核在专用候选登记。范围：[QNA规格](../specs/qmt-native-adjustment.md)。

模块入口为`integrations/guanheng/qmt_native_adjustment.py`。它校验冻结因子/日线身份、生成WT累计因子JSON，并把原WT Reader实际读取的raw/front值装配为RR112 1.1.2的AnalysisWindow纯值资料。OHLC复权计算由原Reader拥有，来源接收、版本和空事件语义由适配层保留；策略辅助事实和实际决策继续由业务核拥有。

原生能力复用WT-D05/WT-D09的IDataReader、adjfactor与“-”后缀；原生配置adjust_flag=0，量额保持来源原单位。输入store只读，所有派生文件和探针运行写入调用者独占新根。基准日显式且输出同一basis，Reader JSON只包含该基准前的累计事件。

`analysis/history`使用八证券实际日期交集，保持策略当前矩形输入的逐日配对；`native_securities`保留各证券完整的原生raw/front窗口。两者覆盖范围分别表达：晚上市证券会缩短共同窗，其他证券更早的已读历史仍保留。持仓周期早于共同窗时，消费者须通过支持逐证券历史的周期恢复契约接入，现有矩形策略入口会报告`opening_history_missing`。完整原值存在与该策略已经支持早期周期恢复分别验收。

当前资料属于current-visible-reconstruction，历史首次可见与修订历史未知。空返回保持原始空事件；原生空乘积恒等、独立QMT交叉证据及全部范围资格分别输出。amount保持unknown/unused。该模块不提供账户、下载、行情订阅、数据库或策略规则。

调用顺序为`prepare_inputs(factor_manifest, daily_store, basis_date, new_output)`→`read_native(input_path, request_path, new_native_output, reader=Artifact(...), probe=Artifact(...), timeout=...)`→`assemble_window(NativeRead, reference_receipts)`。二进制摘要由安装清单提供；读取配置显式绑定raw目录、累计因子文件、adjust_flag=0、最新共同日、八证券和产品/合约元数据。输入与输出目录各自独占，原件在读前与读后核SHA；适配层重新推导source_revision/factor_revision。

当前固定输入为2026-10-28基准，八证券8,870条完整原生日线、59个事件及三份空表；八证券共同401个日期为2025-03-05至2026-10-28，输出3,208条AnalysisBar。全部raw六值与原采集逐行相同；WT复权与独立累计关系、八证券真实早期参考及两证券除息日前后参考逐OHLC核验。唯一RR112 1.1.2安装分发中的AnalysisWindow/AnalysisBar、FrozenHistory、CurrentHistoryView已按实际值实例化。

专用构建/交付根为`build/qmt-native-adjustment-module-001`。安装候选包含标准库Python模块、薄探针、原WtDataStorage.dll、固定原件、配置与纯值资料。环境为Python 3.10+、Windows x64、Microsoft Visual C++ 2015-2022 x64 runtime与Windows UCRT。`installed_run.py --bundle <安装目录> --output <新目录>`在隐藏有界父进程内复验；每个文件由MANIFEST锁定，搬迁后source/factor版本与全部读回/分析值保持。

交付资料供C继续装配辅助事实和原业务核。辅助事实、历史首次可见、完整策略结果和账户/交易资格仍缺少对应证据；这次只授当前可见同基准原生价格分析资格。共享模块索引登记由根集成。

## 每个交易日的回放窗口

显式扩展入口为 `integrations/guanheng/qmt_native_replay.py`，要求见 [QNA4/QNA5](../specs/qmt-native-adjustment.md#qna4-逐日原生回放窗口)。它接收原 QNA 最新读回收据及八证券真实参考，复用同一因子解释、raw 验证和版本计算；旧 `prepare_inputs/read_native/assemble_window` 接口保持。

原 `IDataReader` 的纯历史路径从库存尾部取 count；历史日期定位使用同原 DLL 已有的 `IRdmDtReader.readKlineSliceByCount`。薄 `WtReplayProbe` 固定公开接口、基准日期、元数据和 Reader 身份，复制原有有界切片并释放、删除 Reader。WT 核心保持原件。按规范累计因子 JSON 完全相同的日期分组后，每组读至组末；组内各日的事件前缀与分母均相同，窗口只裁切原生 OHLC，不在 Python 重算价格。当前401共同日形成13组；每个日期仍有独立的 factor revision。

构建调用：

```python
receipt = build_catalog(native_read, reference_receipts, new_output,
    probe=Artifact(fixed_replay_probe_path, fixed_replay_probe_sha256),
    deadline=original_monotonic_deadline)
```

构建进程必须处于隐藏有界外层 Job，Reader 子进程继承该 Job；每个 Reader 调用最多60秒，并受原总截止约束。源清单、DSB、因子回包及二进制在复制前后核摘要，全部派生物写入新目录。根的 `MANIFEST.json` 固定目录、逐组原读回、源原件、代码和二进制；请求中的原构建绝对路径只用于追溯。搬迁消费仅使用相对目录原值，保持身份。

正式消费者安装 `guanheng-market-client==0.15.0` 与可选的 `guanheng-native-analysis-core==0.1.0a2` 后，使用以下公开入口。该安装闭包要求 Python 3.12+；基础行情 SDK 的既有源码和入口保持原版本。可选 core 提供回放模块，基础 SDK 单独安装时不包含这项能力。

```python
from guanheng_market_client.qmt_native_replay import ReplayCatalog
catalog = ReplayCatalog.open(bundle_directory, externally_pinned_manifest_sha256)
wire = catalog.window(catalog.dates[120])
# wire['analysis'] / ['history'] / ['current_view'] 供原 RR112 wire 解码。
```

该入口直接转发到原 `integrations.guanheng.qmt_native_replay.ReplayCatalog`，复用同一个类与原目录格式。目录中的 `lib/qmt_native_replay.py` 保留为独立开发消费及比较基线；产品入口通过安装闭包解析模块，无需修改 `sys.path`。构建和安装方法见[客户端手册](../runbooks/client-sdk.md#可选的原生逐日回放能力)。

`open` 核全包及分组、日期、因子和 raw 配对后，在内存持有有界纯值；`window` 无磁盘、网络和 DLL 调用，返回独立容器。日期来自八证券实际 raw 交集，每窗从交集首日至 basis，首100日仍由原核处理预热。`known_at` 保留实际重建时间，`market_available_at` 保持缺失；历史首次可见及修订历史均 unknown。输出属于当前可见重建，辅助事实及历史因果回测资格仍需单独提供。

专用验收根为 `build/qmt-native-replay-001`，主路径入口 `tests/integration/qmt_native_adjustment/replay.py`；边界入口 `replay_boundaries.py`，隔离安装消费入口 `installed_replay.py`。实际发行身份和结果由该根交付收据提供，不替换既有 QNA 冻结候选。

本次真实401日、独立原Reader小样本及隔离安装结果见[逐日原生回放证据](../evidence/2026-10-30-qmt-native-replay.md)。

正式可安装入口的原件保持及401日逐值比较见[回放安装入口证据](../evidence/2026-10-30-replay-installed-api.md)。
