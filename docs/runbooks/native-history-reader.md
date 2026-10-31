# 原生历史 Reader 操作手册

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：操作手册。适用范围：Windows 受管原生 CTA 宿主与本机 reader HTTP 服务。状态：配置和操作契约；执行前核对实际制品与验收记录。模块职责见[模块说明](../modules/native-history-reader.md)，唯一功能要求见[最终规格](../specs/native-history-reader.md)。本文示例使用虚构配置，不包含凭证或生产日历。

## 启动输入

准备同一经验证运行制品中的 `GuanhengHistoryReader.dll`、Python reader 适配、SDK 0.7.0 及其已声明依赖。DLL 放置在宿主 `WtHelper::getInstDir()` 对应的模块查找目录。基础 SDK wheel 独立安装使用，reader 服务还需运行适配目录及受管工厂模块。

受管工厂采用 `module:callable` 标识，零参数调用并返回当前服务器线程内创建的 `StrategyMarket`。工厂负责装配来源、来源数据版本、权威 CalendarProvider、日历版本、资格下限、时钟及容量，所有来源调用须有有限 timeout。运行适配内的工厂使用同一 SDK 模块身份，例如 `integrations.guanheng_market_client.strategy_market.StrategyMarket`；工厂导入由启动配置授权。

| 输入 | 配置位置与约束 |
|---|---|
| reader Bearer | 服务环境 `GH_READER_TOKEN`；原生进程通过配置指定的 `token_env` 读取相同凭证 |
| 工厂标识 | 服务环境 `GH_READER_FACTORY`，例如虚构的 `managed_reader.factory:create_market` |
| 策略版本 | 服务环境 `GH_READER_POLICY_ID`；须与原生 `policy_id` 相同，非空且最多 128 字符 |
| 来源、日历与凭证 | 工厂自己的受管配置；由事实 owner 提供，HTTP 请求不能覆盖 |
| 观察时钟 | `StrategyMarket.clock`；返回带时区 datetime，统一 HTTP as_of 与 SDK 截止 |
| 实例身份 | 服务每次启动自动生成；重启后需要新建原生 reader 绑定 |

不要把 token、来源密钥或完整私有配置写进 JSON 示例、终端命令历史、URL、测试收据或日志。环境值由凭证管理器或受控启动器注入；启动失败时检查配置存在性和资格，不回显原始值。

## 服务启动

下列命令在经验证的运行适配目录执行。示例假定凭证已经注入；`managed_reader.factory` 是部署方提供的模块，仓库不会自动发现 QMT 路径或生成该工厂。

```powershell
$env:GH_READER_FACTORY = 'managed_reader.factory:create_market'
$env:GH_READER_POLICY_ID = 'example-calendar-sources-v1'
python -B -m integrations.guanheng.reader_service --host 127.0.0.1 --port 8766
```

CLI 接受 `--host` 和 `--port`。程序化启动可调用 `from_env(address, **limits)` 或 `ReaderHTTPServer(address, market_factory, token, policy_id, **limits)` 设置预算；创建、serve 和 server_close 必须在同一拥有线程。另一个管理线程可调用 `shutdown()` 发出停止信号，待 serve 返回后由拥有线程关闭服务和 SDK。

| 服务预算 | 默认值 | 作用 |
|---|---:|---|
| `socket_timeout` | 5 秒 | 请求行、头和正文共用读截止，输出 socket 写入也有超时 |
| `request_timeout` | 35 秒 | 本次请求读取、SDK 调用及结果处理总预算 |
| `max_request_bytes` | 4096 | 请求正文大小 |
| `max_response_bytes` | 8 MiB | 超限整批拒绝，不截断历史或谱系 |
| `max_bars` | 10000 | 还受 SDK max_bars 上限约束 |

SDK `timeout` 必须严格小于服务 `request_timeout`。读取正文后，剩余预算不足以容纳 SDK 声明的完整 timeout 时，服务直接返回 Timeout。受管配置须给读取、校验和输出留余量；例如 SDK 10 秒、服务 request_timeout 15 秒、socket_timeout 2 秒、原生 timeout_ms 20000。串行排队也消耗原生调用方的期限，超时由后续独立读取恢复。

启动输出只说明监听状态。该服务不提供额外健康路由；采用下述带认证的有限历史读取核对真实数据链。

## 原生宿主配置

以下是虚构的宿主配置片段。`data.store` 交给 reader；其他字段由宿主处理。

```json
{
  "engine": {"poolsize": 0},
  "data": {
    "store": {
      "module": "GuanhengHistoryReader",
      "base_url": "http://127.0.0.1:8766",
      "token_env": "GH_READER_TOKEN",
      "policy_id": "example-calendar-sources-v1",
      "symbols": [
        {"std_code": "SSE.STK.600000", "symbol": "600000.SH"}
      ],
      "timeout_ms": 20000,
      "max_bars": 10000,
      "max_live_bars": 100000,
      "max_slices": 128,
      "max_symbols": 256
    }
  }
}
```

证券映射必须对应宿主实际加载的基础资料；每个 std_code 和 symbol 唯一，避免推断产品或复权身份。服务只接受六位 `.SH`/`.SZ` 证券。`base_url` 使用字面量回环地址和根路径，不放查询串、凭证或 API 子路径。

`timeout_ms` 默认 5000、最大 30000；`max_bars` 默认 10000、原生配置最大 100000，但实际受服务更小上限约束。`max_live_bars` 默认 100000、最大 1000000，必须至少为 max_bars；`max_slices` 默认 128、最大 4096；`max_symbols` 默认 256、最大 1024。设置有限正整数，按策略实际持有切片数量选择容量。释放旧切片可归还容量。

宿主以 `WtDtMgr::init(..., false)` 运行，并使用基础 `m1`、`times=1` 路径。reader 配置不接受 `force_cache` 字段。原 WtRunner 当前调用使用 false 默认值；其他宿主须核对自己的入口。当前保守配置采用 `poolsize=0`；启用线程池前须取得对应 poolsize 的原 CTA 整链、回调内读取和停止验收。

## 验证正常、缺失与空状态

1. 在受管工厂创建的 SDK 上，以合法证券调用 `tail_history_1m(symbol, count, end=..., as_of=...)`；结果应为 Ok、准确 count 条、递增分钟及完整谱系。显式端点和 as_of 使用带时区 datetime，范围不超前。
2. 通过 reader HTTP 对同一证券执行有限 tail，核对版本、id、policy、instance、as_of、股/元单位及 provenance。以下正文为虚构示例，Authorization 由客户端从环境读取。
3. 在同一原 CTA 实例读取 `m1`，持有旧 slice 后再次读取，确认新历史可见而旧值保持；释放 slice 后容量归还。
4. 在隔离样本中检查 Pending→补齐、追加、同数量修订；核对恢复分钟只更新历史，当前事件须同时符合服务和宿主闭合标签。
5. 检查错误认证、未知 policy、服务重启、来源不可用和权威空网格。HTTP 200 仍需判断业务 status；零条返回不得被策略当成可访问末条的非空 slice。

```json
{"api_version":"guanheng.reader.v1","id":"0123456789abcdef0123456789abcdef","action":"tail","symbol":"600000.SH","end":0,"count":2}
```

range 使用同样公共字段，将 count 换为 `"after":202610210931`。端点是上海右端分钟，after 排除；数字示例不代表当前可查询时段。仅做 `range(after=end)` 的空请求可以检查协议和身份，完整来源资格仍需非空读取。

独立 wheel 使用 `guanheng_market_client.strategy_market.StrategyMarket` 的相同 SDK 0.7 接口；在运行适配的工厂中使用同一已加载 SDK 模块，避免混用两个模块身份的实例。日历与来源构造参考[策略统一行情规格](../specs/strategy-market-access.md)和[行情服务手册](market-service.md)。

## 状态与处理

| 观察结果 | 处理 |
|---|---|
| Ok 且有历史 | 核对资格、单位和闭合时间后消费；原生调用方负责释放 slice |
| Ok 且零条 | 权威空范围或空网格；原生返回 nullptr，策略按无可用历史处理 |
| Pending | 权威分钟不足、来源缺口或尚未完成；保留原基线，下次按同一业务需求重新读取 |
| Timeout / Backpressure | 核对总预算、排队、持有切片和容量；释放已不用的 slice，保持有限重试 |
| InvalidInput / NotSupported | 修正字段、证券、日期、基础 m1 或配置；不使用任意透传绕过验证 |
| Unavailable / IoError | 检查工厂、来源服务及受管配置；reason 为固定文本，诊断不得输出私有配置 |
| Conflict / StaleSession | 核对来源、policy 与服务 instance；身份更换按停止和重建流程重新绑定 |
| SubmissionUnknown（宿主回调） | 隔离事件；重建 reader 和相关 sink，按业务事实核查已执行效果后恢复 |

服务鉴权失败返回 401；错误请求、上游畸形结果和超时还可能返回非 200。客户端须同时校验 HTTP 和业务 envelope，任何失败 data 都为空。原生 `readKlineSlice` 对失败、未就绪和零条返回 nullptr；`StrategyReader::last_status()` 提供固定诊断。原 `initStore` 的布尔成功只证明工厂和 init 调用已发生，首次合格读取才证明 reader 配置与来源链可用。

## 停止、重启和未知结果恢复

停止成功包括在途读取/批回调结束及HTTP系统最后回调返回。所有等待共用传入截止；任何线程在批回调期间调用stop都可能得到Pending，应在外部重试确认。超时后保留资源，原式析构的排空兜底可能无界，不能替代受管停止。

受管宿主先停止新的行情/策略调用，再调用 `stopDataReader(reader, timeout_ms)` 或 `StrategyReader::stop`。返回成功后可删除 reader 对象；插件 DLL 及其依赖必须保留到所有已返回 slice 最后一次 release 完成之后，才能卸载。slice 的虚表、析构和预算归还代码位于插件，stop 不等待调用方释放 slice。回调或 pool 内请求 stop 会返回 Pending；让已准入整批执行至 `on_all_bar_updated`，由外部管理线程再次确认停止。等待超时保留对象和依赖，继续有界等待或按宿主受控退出处理。

每个 reader 只初始化一次。服务重启、policy 修改或来源配置换代时，停止旧 reader、创建新 reader 并重新验证身份；旧 slice 继续由原调用方持有至 release。服务启动新 instance 后，旧 reader 不静默跟随新实例。

sink 回调异常时，其业务效果与暂存 bar 指针均可能未清理。停止旧 reader，保留隔离数组直到相关 sink 停止使用，重建 sink/reader 组合并核对业务事实后恢复。不能只更换 reader 并继续使用持有旧指针的 sink。

原 WtDtMgr 析构当前未接入 `deleteDataReader`，受管宿主必须提供明确的停止、销毁和卸载编排。原 WtRunner 进程退出与优雅释放属于不同验收项；操作记录分别说明实际退出方式与已验证资源边界。

## 验收和发布边界

服务测试入口为 `python -B -m unittest discover -s tests/integration/reader_service -v`。native Store 测试还需要 `GH_MARKET_LIBRARY` 指向经验证 DLL，`GH_QMT_SOURCE_ROOT` 指向只读协议源码，解释器须满足该协议依赖。隔离环境使用唯一临时目录，保持运行实例和生产文件。

原 WtDtMgr/CTA 验证脚本为reader_host_flow.py（外部历史/待归仓路径：`../../tests/integration/reader_host_flow.py`），需要匹配的原生 probe、独立 work 目录及前述依赖。原生构建、制品打包、搬迁路径和每种 poolsize 的通过结果由对应验收记录提供。本手册描述启动和恢复方法；真实来源、生产日历、现场业务恢复及发布切换需另有匹配环境的授权与证据。
