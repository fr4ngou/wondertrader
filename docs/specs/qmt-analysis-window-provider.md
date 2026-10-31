# 持续 QNA 来源快照合同

类型：最终接口规格。前缀：AWP-P。状态：accepted / implementing。消费者为 WT 的唯一 1.1.2 分析窗口生产者；来源通信 owner 负责将本合同适配到后继显式 SHM profile。现有冻结 Host、Agent 和 QNA 算法保持。

## AWP-P1 调用及责任

Python 接缝为 `provider.capture(request, output_directory, *, deadline) -> Path`，返回新目录内完整快照 JSON 的绝对路径。`deadline` 是单次业务刷新的 monotonic 绝对截止；来源 owner 负责每次 RPC 的原请求身份、未知结果恢复及真实接收时点。生产者在调用前持久保存 `capture_id`；未确认的 capture 继续同一 ID。生产者不调用 QMT SDK。

request 精确字段：`schema=guanheng.qna-capture-request.v1`、`capture_id`（UUID）、`symbols`（QNA 原八证券排序数组）、`start_date`（ISO 日期）、`max_rows_per_symbol`（100..4096）。八证券是唯一策略的输入集合；本合同不建立全市场补充证券白名单。

来源适配器在 QMT 原线程调用 SDK：读取原价日线；读取 `get_divid_factors` 七列原事件；最后针对共同闭合基准读取 none/front_ratio 的同日 OHLC 参考。沿显式 v7 只读操作，不附带下载；缺缓存报告等待，由既有历史准备模块处理。WT 外部 SDK 替身必须独立计数实际日线、因子、参考 API 调用，不能直接返回预制 QNA 窗口。

来源 profile 沿 [QAS](qmt-analysis-source.md) 的 `qmt.read-profile.v7`：`market.market_data` 使用 `qmt.daily-read.v1/1.0`，`market.divid_factors` 使用 `qmt.factor-read.v1/1.0`。原 v6 / BoundHistorySource 的 1m 默认路径保持。真实 QMT 资格单列；既有闭合能力集不静默升级。

## AWP-P2 快照纯值

顶层精确字段：

- `schema=guanheng.qna-source-snapshot.v1`、`capture_id`。
- `source`：精确为 `provider=Qmt`、`instance_id`、`session_id`、`generation`、`sdk_version`、`source_license`、`input_kind`（`synthetic` 或 `qmt_export`）。身份和单位由原来源提供。
- `closed_through`：来源凭会话收盘事实确认的 ISO 日期上限。`closure_evidence`：非空说明/引用；不能从日线 00:00 标签推导闭合。
- `daily`、`factors`：各为八证券键的 receipt 映射。
- `references`：八证券键映射，每证券精确 `none`、`front_ratio` 两个 receipt，均为同一共同基准日。

daily/factors/reference 的 receipt 精确字段为 `request_id`、`requested_at`、`received_at`、`reply`。时间为真实 UTC aware ISO，`requested_at<=received_at`；reply 保留原结果封装，必须含 `request_id/operation_id/ok/error_code/data`、成功且关联相同请求。所有原 reply 完整落盘并绑定 SHA。

daily reply 的 operation_id=`market.market_data`，data 为 `{symbol:{YYYYMMDD:{open,high,low,close,volume,amount}}}` 原价源值；每证券日期唯一递增、有限价格/量额，原价 CNY、volume lot、amount unknown。factors reply 的 operation_id=`market.divid_factors`，data 为原毫秒时间键到七列数组；不改倍率、不补 factor-one。references 沿相同日线结构，none/front_ratio 日期和证券一致。

完整快照必须自包含纯 JSON、最大 16MiB。生产者重算八证券原始日期交集，选择 `<=closed_through` 的最新日为 basis；参考必须正好该日。需要至少100个共同日期。Source 缺席/截止未确认用 `SourcePending`，保留原 capture_id；明确无数据/未闭合用 `SourceUnavailable`。错误不伪造空成功或窗口。

## AWP-P3 时间与资格

逐项真实 received_at 保留在原件。最早 received_at 用于完整快照年龄检查，最晚 received_at 是本次来源事实已完整接收的时间；生成完成时刻单独记录 `generated_at`。重复使用旧快照不能重写源时间。

QNA 原函数先形成原始候选窗口及原 NativeRead 收据。发布适配只把候选 `analysis.known_at` 和 `current_view.received_at` 绑定为本次完整来源实收时点，记录候选/发布双 SHA；OHLC、factor、raw_close、revisions、单位及其余字段保持。该时点表达 current-visible 输入已经接收，不表达历史首次可见或物理计算完成。实际生成/发布时间在生产者状态中另列。此时间适配使原 R24 的年龄判断使用真实来源实收时间，不修改 QNA 金融算法和 B 消费者。

运行前和发布前均核全部来源年龄及未来时间；缺源/过旧保持最后成功窗口字节，发布者状态转 waiting_source。真实来源、SDK 替身和历史重建分别记录，不授历史因果、交易或生产资格。

显式回收来源按RR6固定capture认证：raw/factor/reference均须匹配该capture的完整原binding。新slot认证换代在受理前报告SourceUnavailable，下一capture重新观察；旧slot未知继续原ID，已确认原值保留。
