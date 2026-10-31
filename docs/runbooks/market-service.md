# 独立行情 HTTP 服务

类型：运行手册。适用范围：`guanheng.market.v1` 独立服务及标准库客户端。依据：[QMT HTTP 最终规格](../specs/qmt-http-market.md)。服务只提供行情，观衡研究、策略、Portfolio、Bridge、Console 和 Operations 保持独立发布，适配位置见[业务地图](../migration/business-adaptation-map.md)。

## 安装与受管输入

服务运行于带 `integrations/guanheng` 和 `app/GuanhengMarketBridge.dll` 的 WT 开发包，Python >=3.10，仅使用标准库；无需 wtpy 或 QMT 源码。服务在同一创建线程加载、调用和销毁原生 handle，使用单线程 HTTPServer。不要改成 ThreadingHTTPServer 或在其它线程创建/关闭 handle。其它线程可以调用 server.shutdown 发出停止信号；server_close 由原 owner 执行。

启动进程要求由受管环境提供以下变量；凭证不作为命令参数，不打印，不写回文件：

| 变量 | 含义 |
|---|---|
| `GH_MARKET_LIBRARY` | 此安装的 GuanhengMarketBridge.dll 绝对路径 |
| `GH_MARKET_LIBRARY_SHA256` | 经制品清单核实的 DLL 原字节 SHA-256，小写 64 位 hex |
| `GH_MARKET_CONFIG_FILE` | 受控、Git 外的 UTF-8 JSON 配置文件；没有隐式搜索路径 |
| `GH_MARKET_TOKEN` | 访问独立服务的非空 Bearer token，由受管秘密源注入 |
| `QMT_GATEWAY_KEY_ID` | 原 QMT Gateway HTTP 鉴权的 key ID，独立于服务 Bearer |
| `QMT_GATEWAY_HMAC_SECRET` | 原 QMT Gateway HMAC 秘密，由受管秘密源注入 |

配置文件仅允许 base_url、history_root、timeout_ms、max_response_bytes、profile，以及可选 native_reader。key_id/hmac_secret 出现在文件中会被拒绝；二者只从上述环境变量注入内存。配置文件位置/访问权限由部署 owner 管理，勿将实际配置、token 或历史目录提交到版本库。

`native_reader`启用原生历史查询，字段为 `library/sessions/commodities/contracts/holidays` 五个绝对文件路径，以及正整数 `cache_bytes`（至少一根bar、最大1GiB）。四份基础资料使用与数据相符的WT UTF-8 `.json`配置，禁止把合成测试资料用于生产。存储根只放受管历史，出现`rt`目录即拒绝此路径；QMT源端和其他Reader的实时数据继续各自受管。缓存预算约束已加载原生bar载荷（含待释放代际），实际RSS还包含解压/校验/响应副本及基础资料。具体行为和验收边界见[历史查询规格](../specs/native-history-query.md)。该选项当前只授予通过对应测试的开发资格，生产接线需独立验收。

以下仅是合成配置形状，profile 与许可值需要原 owner 依据真实响应确认后替换。示例不授予真实来源资格：

```json
{
  "base_url": "http://127.0.0.1:18010",
  "history_root": "E:/managed/guanheng-market/history",
  "timeout_ms": 5000,
  "max_response_bytes": 1048576,
  "profile": {
    "version": "synthetic-example-v1",
    "source_license": "synthetic-no-market-data",
    "time_encoding": "epoch_ms",
    "minute_boundary": "right",
    "volume_to_shares": 100,
    "amount_to_yuan": 10,
    "full_tick_cumulative": true
  }
}
```

profile 明确源端时间、左右边界、量额单位及累计快照语义。此处源单位系数只供原生入库转换；HTTP 历史输出已经是股/元，客户端不能再次乘 metadata 中保留的系数。源记录丢失 time、没有同会话源 tick 时间证明闭合或来源会话变化时保持 unavailable/pending/stale，不用 health callback walltime 代替行情时间。

启用原生Reader后，既有`history.query`请求可增加`period_minutes`（1/5/15/30/60）和`limit`（最多1..10000根）。from/to仍显式给定并包含端点；派生bar按右端时间选择，内部起点不会截掉该桶已有基础输入。响应增加selection回显，覆盖保持Unknown；这类选择器不混用m1覆盖网格，也不触发QMT下载。其他历史动作保持原协议。适用时段、数量与闭合限制见[窗口规格](../specs/native-history-window.md)。

Gateway 明文连接仅允许回环 IP，远端须正常验证 HTTPS；原生客户端不跟随重定向或使用自动代理。独立服务绑定仅允许字面回环 IP（例如 127.0.0.1、::1），拒绝 0.0.0.0 和依赖 DNS 的绑定名。

## 启动与公开接口

受管 owner 注入环境后，在开发包根目录运行：

```powershell
python -B -m integrations.guanheng.market_service --host 127.0.0.1 --port 8765
```

启动只检查本地依赖和配置，不连接 QMT。capabilities、history.prepare、quotes.query 可执行原生 prepare/只读 HTTP；history.work 显式推进一项已排队工作；history.query 只读已存 DSB，没有隐式采集。缺少 DLL、摘要不匹配、ABI/配置或认证输入不合格时启动失败并给出固定脱敏原因。

所有请求带 `Authorization: Bearer <受管token>`。仅 GET capabilities，其余动作使用 POST、application/json 和单一 Content-Length；禁止 chunked 请求、任意 RPC、账户或交易动作。每个连接处理一项请求后关闭。

| 路径 | 请求 JSON |
|---|---|
| `/api/market/v1/capabilities` | GET，无 body |
| `/api/market/v1/history/query` | `{"api_version":"guanheng.market.v1","action":"history.query","request":{...}}` |
| `/api/market/v1/history/prepare` | 同上，action 为 history.prepare |
| `/api/market/v1/history/work` | `{"api_version":"guanheng.market.v1","action":"history.work"}`；没有 task_id 参数 |
| `/api/market/v1/quotes/query` | `{"api_version":"guanheng.market.v1","action":"quotes.query","symbols":["SSE.600000","SZSE.000001"]}` |

历史 request 包含 exchange、code、from、to，可选 expected_minutes 和 calendar_version。分钟为 Asia/Shanghai 右端 `YYYYMMDDHHMM` 整数；from/to 均包含。exchange 为 SSE/SZSE，code 为六位代码。expected_minutes 必须升序、唯一、在范围内，有网格时必须有其权威 calendar_version。服务不自行编造交易日历或停牌分钟。

服务请求体最多 262144 字节、快照证券最多 64 个、预期分钟最多 10000 个；单次历史输出最多 10000 条。默认 HTTP 响应预算 8 MiB（构造可收紧，硬上限 16 MiB），HTTP 头另有 32 KiB 预算。服务 socket 读取默认总预算 5 秒，可收紧且不能超过 30 秒；原生工作遵守受管配置的原生预算。同步 native 调用没有任意抢占能力，客户端超时不能证明原生 worker 没有完成；恢复后先查询原存储/任务状态。

合法原生结果（包含 Pending/Unavailable/Backpressure）保持 HTTP 200 和原 envelope；认证错误 401、坏请求 400、超大体 413、非法内容类型 415、读取超时 408、坏原生响应 502、原生依赖异常 503。错误不回显配置、远端正文或凭证。

所有 envelope 为 api_version、status `{code,reason}`、data。成功历史必须有可校验的来源/资格/许可/内容身份及 bars/coverage/missing_minutes；有效数据集筛选后可返回空 bars。未准备存储不冒充带来源的空成功。失败可以 data={}。capabilities 包含 source（可为 null）、snapshot/history/trading 能力；trading 始终不支持。源码枚举、未知字段、未知主版本或来源语义不合格时客户端明确拒绝。

成功 quotes 的 data 精确包含 snapshots 与批级 metadata。metadata 为 qualification、profile_version、source_license、timezone、price_unit、volume_unit、amount_unit、volume_to_shares、amount_to_yuan；时区固定 Asia/Shanghai，价格/金额为 CNY、数量为 share。资格、profile/许可缺失或为空、单位不符、换算系数非有限正数时客户端拒绝。系数仅记录源证据，快照数值已经归一化，禁止再次乘系数。成功快照必须完整覆盖本次请求证券集合，空列表、缺项、重复、额外证券或混会话均拒绝；来源不可用通过非 Ok 状态明确返回。

## 客户端与三天分窗

观衡消费者只依赖版本化 HTTP，不需要 WT DLL、私有 QMT checkout 或业务规则。仓库提供的标准库客户端接口：

```python
import os
from guanheng_market_client import MarketClient, iter_history_windows

client = MarketClient("http://127.0.0.1:8765", os.environ["GH_MARKET_TOKEN"], timeout=5)
capabilities = client.capabilities()
request = {
    "exchange": "SSE", "code": "600000",
    "from": 202610210931, "to": 202610210933,
    "expected_minutes": [202610210931, 202610210932, 202610210933],
    "calendar_version": "synthetic-calendar-v1"
}
existing = client.history_query(request)
# 作业 owner 根据 existing 和能力决定是否显式 prepare / work。
task = client.history_prepare(request)
progress = client.history_work()
result = client.history_query(request)
```

请求/返回均为独立 dict，量额、source/session/generation、许可、qualification、content_id 和覆盖状态原样保留。API 没有自动重试、自动切源或循环下载；错误 HTTP 返回 MarketHTTPError，非法契约返回 MarketProtocolError，连接/截止失败返回 MarketUnavailable。超时不改换请求身份盲重试。客户端不跟随重定向、不读取环境代理；HTTPS 使用标准验证。

源 HTTP 历史单窗口最多 **72 小时自然时长**。QMT count 可能返回尾部，因此一个月/十年历史由受管作业逐窗 query → prepare → work → query，并保存自己的任务进度；不宣称一次完成全市场下载。`iter_history_windows(request, hours=72)` 仅生成不重叠的包含端点分钟窗，不执行网络或 worker，也不生成交易日历。返回不足、截断、缺源时钟、已知网格缺口与 Unknown 覆盖分别保留。大范围 job 应按每窗请求相应权威分钟网格，单次不能提交超过 10000 个 expected_minutes。

## 隔离验证与发布边界

普通契约/HTTP/预算测试（不连接账户、不访问真实 QMT）：

```powershell
python -B -m unittest discover -s tests/integration/service -p test_market_service.py -v
```

真实原生链资格用例另需 `GH_MARKET_LIBRARY` 指向本次构建/包内 DLL，`GH_QMT_SOURCE_ROOT` 指向受控原源根，仅用于复用原纯 HMAC/DTO HTTP fixture。缺少条件时明确 skipped；服务及正式客户端本身不读取该外部源。测试使用真实 loopback Gateway 替身 → 原生 HTTP/HMAC → DSB → 独立服务 → 标准库客户端，核对非 1 单位系数只换算一次。外部源存在时此用例必须实际通过。

生产仍需原 owner 提供真实 listener、许可/profile 及兼容契约、异常/恢复和原页面验收；隔离通过不提升实机/生产权限。本轮服务不提供 QMT 交易、TDX 交易、共享内存绑定或 Tushare 透传；Tushare 独立能力的实际授权与资格单独记录。观衡与 WT 使用各自制品身份、升级及回退流程。


## 定向准备任务与实例恢复

独立客户端的发行与安装见[SDK 手册](client-sdk.md)。规范实现维护在 integrations/guanheng_market_client，原 integrations.guanheng.market_client 仅兼容转发。包版本以 wheel/收据及规范模块声明为准，与协议版本 guanheng.market.v1 分别核对。

以下四条新增路径均为 POST：/api/market/v1/history/task/prepare、/inspect、/work、/release。prepare 请求为 `{api_version, action:"history.task.prepare", request:{...}}`；其余为 `{api_version, action:"history.task.<操作>", queue_id, task_id}`，queue_id 为 32 位小写十六进制、task_id 为正整数。非空 data 精确包含 queue_id、task_id、state；state 为 Pending/Complete/Unavailable/Failed/Released。错误可以 data={}；编号0不授予任务身份。

```python
task = client.history_task_prepare(request)
# 先核对 status/data；只有有效身份才能使用以下调用。
identity = {k: task["data"][k] for k in ("queue_id", "task_id")}
state = client.history_task_inspect(**identity)
progress = client.history_task_work(**identity)
released = client.history_task_release(**identity)
```

定向 work 只推进指定任务；release 丢弃该任务和未发布暂存，保留 DSB。worker 在途时统一背压释放，重复释放同一实例中已移除的正编号幂等成功。已完成任务由调用方释放以回收容量；长期作业不能依赖重启清空队列。

任务身份只在本次 Bridge 实例有效，不作为持久 checkpoint。重启后旧 queue_id 返回 StaleSession，并保持新队列不受影响；恢复先 query 已发布 DSB，再按缺口重新 prepare。超时先核查，避免盲重试或推进其他任务。旧 FIFO history.work 入口和返回结构保持兼容，业务持久作业继续由原 Operations 管理。


## 离线导入数据的来源原值服务

该模式与上文旧 HTTP 来源配置分别选择；配置文件显式 `mode=source-store`。示例中的路径、SHA 与证券需替换为本次受管输入：

```json
{
  "mode": "source-store",
  "store_root": "E:/managed/qmt-convert/store",
  "import_receipt_sha256": "<store/qmt-import.json 的 SHA-256>",
  "native_reader": {
    "library": "E:/managed/app/GuanhengNativeBarFile.dll",
    "sha256": "<可信制品 SHA-256>"
  },
  "max_bars": 1000000,
  "max_cache_bars": 1000000,
  "preload_symbols": ["SZSE.000001"]
}
```

沿既有启动命令设置 `GH_MARKET_CONFIG_FILE` 与受管注入的 `GH_MARKET_TOKEN`。此模式使用配置内的 Reader DLL，无需 `GH_MARKET_LIBRARY`、原 Gateway 地址或 QMT Gateway 凭证；启动时校验成功收据并预热指定证券。服务继续绑定回环地址，部署 owner 负责进程生命周期。

消费者沿独立 SDK 调用：

```python
result = client.source_history_query({
    "exchange": "SZSE", "code": "000001",
    "from": 202111010000, "to": 202610272359, "limit": 2000
})
```

日期仅为示例，区间包含端点；返回保留 source_label 与来源单位，coverage 为 Unknown。观衡配置同一服务 URL/token，并显式设置 `GUANHENG_HISTORY_SEMANTICS=source`，即可在行情页面读取 1m。canonical 仍是默认；该选择不自动切换策略或生产运行实例。当前真实开发主路径已通过，独立安装包和发布验收仍继续，见[验证记录](../evidence/2026-10-27-qmt-source-chart-main.md)。


## 同一服务读取多个成功批次

全市场分批导入后，显式选择source-stores。以下为示例；每一根使用其自身qmt-import.json的真实SHA，Reader配置、缓存及认证沿前节：

```json
{
  "mode": "source-stores",
  "stores": [
    {"store_root": "E:/managed/history/batch-a/store", "import_receipt_sha256": "<该根成功收据SHA-256>"},
    {"store_root": "E:/managed/history/batch-b/store", "import_receipt_sha256": "<该根成功收据SHA-256>"}
  ],
  "native_reader": {"library": "E:/managed/app/GuanhengNativeBarFile.dll", "sha256": "<可信制品SHA-256>"},
  "max_bars": 1000000,
  "max_cache_bars": 1000000,
  "preload_symbols": []
}
```

空preload使服务启动时只注册原收据，首次查询对应证券才调用同一个原Reader。最多1024个根、10000证券、16MiB收据输入；此模式的受管配置文件上限1MiB。其余模式继续64KiB。重复根或证券直接拒绝，不按配置顺序选优先级。各根须来自同provider/instance_id；不同来源实例分别建立服务。请求与SDK方法保持source_history_query，同一HTTP按证券选择原成功根。

能力页source仅表示离线收据集合：session以source-stores:开头，排序或搬迁不改变同一集合身份，任一收据变化则换代。每次历史结果metadata.source保留对应批次的实际session/generation。使用者核对每证券来源，不能将集合会话当作原采集会话。

对于带catalog.json的全库存作业，部署准备可从最终status=completed的entries中，按(store,import_receipt_sha256)去重生成stores列表；导入中的progress或catalog-items.jsonl只供运行跟踪，不能用来热更新服务。保留catalog引用的全部原batch store，扁平native目录没有原批次成功收据。若目录搬迁，先更新新受管配置、核对所有摘要，再用新实例验证；原服务及历史数据继续保留到切换获授权。

按需加载复用原全文件验证，首次读取耗时受该证券全历史长度影响；缓存命中按时间定位。缓存总量有界，未加载全市场到内存。原生量额/时间语义和价格质量约束仍按[RS7—RS9](../specs/qmt-source-history.md)执行；该配置不授完整日历覆盖或策略闭合分钟资格。


## 从导入完成目录自动准备配置

外部离线命令可根据完整catalog.json自动整理各批次路径，避免手填。输入须为已完成目录：status=completed、coverage=unknown、value_semantics=source；先核对原作业FINAL及证券总数，进行中的progress/catalog-items.jsonl保持运行记录用途。工具核目录证券与原收据的完整注册集合、根、SHA和条数，不将成功配置理解为完整日历覆盖。

以下为示例模板，输出父目录须已存在，目标文件须为新路径：

```powershell
python -B -m integrations.guanheng.source_market `
  --catalog 'E:/managed/history/catalog.json' `
  --output-config 'E:/managed/config/history-next.json' `
  --native-reader 'E:/managed/app/GuanhengNativeBarFile.dll' `
  --native-reader-sha256 '<可信制品SHA-256>'
```

可选--catalog-sha256绑定调用方已有的目录身份；未传时成功摘要仍返回本次实际catalog_sha256。--max-bars和--max-cache-bars沿原服务条数预算，--preload-symbol可重复指定观测证券；默认空预载，准备时验证受管Reader依赖并关闭，不解码全市场。source配置与API请求继续保留源标签/未知单位。

成功机器JSON给出stores、imported_securities、empty_securities、source_rows及config_sha256。准备阶段验证或Reader关闭失败时不写候选；候选在同目录临时文件完整写入关闭后，使用不覆盖的硬链接发布，当前NTFS路径已验。已有目标/竞争保持原目标；文件系统不支持该操作时保持失败，无自动覆盖降级。temporary_file_retained=true表示发布成功后仍留有已关闭的临时副本，按原作业物料处理。配置不含token，不启动服务或QMT，不自动修改GH_MARKET_CONFIG_FILE；按独立发布步骤核对摘要及实际调用链后再选新实例。

开发验证可使用明确声明的已完成批次切片，此类切片只证明所含集合的准备与消费，整库最终验收仍需真实全清单目录。行为依据见[RS10](../specs/qmt-source-history.md#rs10-已完成目录生成统一读取配置)。


### 已结束目录含失败项时先读取健康证券

默认配置准备仍要求completed。需要先提供健康子集时，核对原作业已经结束、失败集合和原目录身份，显式重复--exclude-failed-symbol，精确列出全部failed证券。示例（证券代码仅表示本例失败集合）：

~~~powershell
python -B -m integrations.guanheng.source_market --catalog 'E:/managed/history/catalog.json' --output-config 'E:/managed/config/history-subset.json' --native-reader 'E:/managed/app/GuanhengNativeBarFile.dll' --native-reader-sha256 '<可信制品SHA-256>' --exclude-failed-symbol 000001.SH --exclude-failed-symbol 000300.SH --exclude-failed-symbol 399001.SZ
~~~

只有终态completed_with_failures可使用该选项；少列、多列、重复、排除成功/空项、运行中目录均拒绝。原失败目录保持，结果返回catalog_status、excluded_failed_symbols及tail_refresh；pending_current_qmt_download表示新尾部仍待更新，未声明为unspecified。候选仅覆盖登记的成功证券，完整日历/市场及尾部就绪分别验证。

离线source历史首次查询会完整解码一只证券；部署观衡时可显式设置GUANHENG_MARKET_TIMEOUT_SECONDS=30，上限与SDK一致，默认2秒保持。主图/基准共用该请求总截止，超时不自动延长或盲重试；首次与缓存命中分别验真。安装服务启动后直接从观衡首次查询验证，避免先手工预热掩盖真实耗时。

## 显式源值按需补齐

类型：可选接线，默认离线配置保持。合同见[RS13](../specs/qmt-source-history.md#rs13-最近n根选择有限尾窗与分段来源)，原身份与恢复沿RS12。把原source配置作为`base`，外层改为`source-preparing`，交给原`source_market_service.py`的受管配置路径/SHA。新模式使用系统统一管理的HPR/QST Host及内存源，read-profile必须为v6且含`market.history_1m`和`market.history_prepare`；该Host与源的离线配对、Journal、任务/结果容量继续按[HPR产品手册](qmt-history-preparation.md)配置。服务就绪只表示本地配置与原生依赖可用，来源可晚到，查询Pending时按原窗口重读。

以下为虚构路径和证券的配置模板，`base`内容采用已验证的原source-store/source-stores/source-catalog配置：

```json
{
  "mode": "source-preparing",
  "base": {"mode": "source-store", "store_root": "E:/managed/base-store", "import_receipt_sha256": "<原收据SHA>", "native_reader": {"library": "E:/managed/app/GuanhengNativeBarFile.dll", "sha256": "<Reader制品SHA>"}, "max_bars": 1000000, "max_cache_bars": 1000000, "preload_symbols": ["SSE.510300"]},
  "preparation": {
    "enabled": true,
    "workspace": "E:/managed/private/source-preparation-next",
    "host": {"base_url": "http://127.0.0.1:18761", "key_id": "example-read-key", "secret_env": "SOURCE_HOST_READ_SECRET", "timeout": 10},
    "helper": {"library": "E:/managed/app/WtDtHelper.dll", "sha256": "<Helper制品SHA>"},
    "source_profile": {"dataset_version": "explicit-shm-source-v1", "source_license": "unknown", "input_kind": "qmt_export", "timezone": "Asia/Shanghai", "minute_boundary": "unknown", "adjustment": "none", "factor_version": "", "value_semantics": "source", "price_unit": "unknown", "volume_unit": "unknown", "amount_unit": "unknown"},
    "timeout_seconds": 25,
    "max_windows": 128,
    "max_window_minutes": 60,
    "max_pages": 16,
    "max_import_attempts": 4,
    "max_rows": 10000,
    "max_bytes": 2097152,
    "overlay_cache_bars": 10000
  }
}
```

正式补齐配置省略preparation.symbols，并使用Host的qmt.history-preparation-limits.v2来源市场范围；沪深证券按查询需要读取及补齐。原含symbols的配置作为既有配对兼容材料保留，旧实例的收据和范围保持。

Host凭据通过环境注入；配置不存secret。Helper/Reader按制品SHA与原ABI校验。workspace须为已有普通E盘父目录下的新私有目录，单写者OS锁固定配置字节；以后使用同一配置与工作目录恢复。外部Host可使用loopback HTTP，终端内正文仍仅内存SHM。新配置生效前保留旧实例和旧根，独立候选验收后再按部署授权切换。

所有预算显式提供。timeout_seconds为单次服务调用的总秒数，范围0.1..30；Host每次交换消费其剩余量。max_windows(1..1024)限制精确证券/起止窗口收据数，limit不改变窗口身份；max_window_minutes(1..7200)限制一次尾窗的自然分钟容量，不限制公开from/to选择跨度。max_pages(1..128)限制完整读取的页数，max_import_attempts(1..16)限制每窗口的原Importer独占尝试根及残留收据临时文件数；半成品保留，重启沿原冻结缓存结果使用新根，原HPR不重派。max_rows(1..100000)限制全窗口实际条数，overlay_cache_bars(1..1000000)独立限制活动窗口Reader。max_bytes(1..64MiB)限制收据/CSV读取与聚合输入，原私有文件创建还保留每文件2MiB上限，按两者较小值部署；Host响应也受原声明及4MiB上限。收据含前后两轮全部页及原终态，选窗前须按实际结果大小和原Host Journal公式核容量，满额保留原身份，已有可读值返回Partial/Budget，无法返回值时明确Backpressure/Pending。示例预算只供小窗接线，不授整库吞吐资格。

公开调用仍为`MarketClient.source_history_query({exchange, code, from, to, limit})`。from/to界定选择范围，limit取其中最近最多N根；服务先读base和已发布根，已有N根且尾标签等于to时零Host操作。其他情况最多推进一个有限尾窗；缓存实际条数不足min(limit,尾窗自然容量)时允许原HPR一次，再读完整窗口，经原Importer/Helper/Reader验证才发布。已有可读值在预算/来源失败时继续返回Ok及明确Partial观测。跨谱系返回SourceSelection集合与连续provenance原metadata，原UUID及准备状态保留在observation。稀疏数据也只表示本次缓存事实，coverage=Unknown；空窗口返回Pending并保留该观测，后继仍为空，不造空DSB。原v6继续严格OHLC准入；含异常原值的缓存需后续版本协议，离线原值Importer能力保持独立。

请求/响应丢失后保留原UUID，终态未知继续核原GET，禁止换工作目录/改窗口来规避原未知并再次下载。晚回的原生调用不可抢占，超期先Pending；同一窗口后续可恢复原产物。收据写入保留进程重启恢复依据，文件系统断电事务资格另验。已发布窗口重复查询零新增HPR，Reader重启从原成功收据加载，按需接线保留所有旧根。停止沿原ready/stop/closed和ManagedLocalProcess/Job，关闭未确认保持owner。

当日及未来窗口不启动源请求；已有档案返回Partial/NotSupported，无数据时返回NotSupported；昨日及以前源范围保持QH-R2。当天断线补齐还缺独立协议、可信同会话源时钟与形成中分钟边界，生产部署不得把当前入口当作当天实时恢复能力。真实QMT下载、市场完整覆盖、单位提升、App自动接线及生产发布分别验收。

固定Appa17可原样消费集合原值及集合内容身份，当前图表DTO投影不包含完整provenance/observation；需要核部分/未知状态时读取同一SDK原响应。页面新增状态展示由App模块独立接线。SDK工程候选仍为0.14，正式版本及App依赖升级由整合步骤处理，部署需核固定wheel身份。


## 异步下载后的有限缓存再观测

类型：显式可选接线，合同见[RS14](../specs/qmt-source-history.md#rs14-异步下载后的有限缓存再观测)。preparation缺少follow_up时保留原固定空观测；提供时在原HPR之后、原after为空且未发布时允许有限只读再观测，已发布根保持且重复零源调用。SDK015字段/枚举保持，不改App或当日协议。

以下片段为小窗部署示例，须合并到原preparation并使用独占新workspace；journal声明必须由实际Host配置核实，例值不代表产品默认或当前生产授权：

```json
{"follow_up":{"enabled":true,"max_attempts":8,"interval_seconds":1,"total_seconds":60,"rpc_timeout_seconds":10,"journal_records":128,"journal_bytes":134217728}}
```

max_attempts=1..16计算每次公开调用实际推进的次数，包括恢复未决原只读ID；间隔0.1..3600秒，总时限1..86400秒，rpc_timeout_seconds=0.1..30，均由本配置明确。一次公开查询最多推进一轮，间隔内不访问来源，来源仍晚到或断开也消费已受理的本次预算。固定总截止从原HPR规划开始，服务重启/页面刷新保持。Windowsuptime配墙钟锚核时钟连续性，倒退/重启/墙钟跳变超过5秒时停止，修正时钟后也不隐式清除停止事实。

Host Journal需要的最坏记录为max_windows*(1+(2+max_attempts)*max_pages)，字节下界为记录数*(bound声明max_request_bytes+max_result_bytes+16384)。journal_records与journal_bytes是该workspace的静态容量声明，准备层在首次HPR之前和后续绑定时核足够；Host实际配置、保留期限及共享使用仍由部署核验，来源服务不会自动扩容或清Journal。满额沿原背压保存原身份。

原收据v2保留before/prepare/after和有限后续capture，每项仍是原bound协议UUID和终态；后续只读使用market.history_1m，原HPR CallReturned/Unknown均保持。响应Unknown时不再下载；每次来源再观测独立绑定其真实来源，旧空事实保留。成功非空结果先由原Helper/Reader完整验证再注册根；如果本地导入中断，从同一已冻结非空结果恢复，零来源交换。失败根继续沿原max_import_attempts保留。

SDK的observation给出原preparation_request_id及状态，reason说明等待或跟踪耗尽。次数/总时限耗尽后，有档案返回Partial及预算原因；无原值返回Backpressure。原下载Unknown继续Unknown。原SDK和App正常查询会在后续刷新看到实际发布的新值，当前App图表DTO仍只投影原值及集合身份，完整准备/分段证据取同一SDK响应。历史覆盖、单位和边界继续unknown/Unknown。
