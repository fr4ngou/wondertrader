# QMT共享内存历史分钟读取

类型：操作手册。适用范围：已安装`GuanhengQmtHistory`、与其匹配的Host/Agent历史能力及WT原生文件消费者。源码契约见[QH规格](../specs/qmt-shm-history.md)，当前安装和真实来源资格见[证据](../evidence/2026-10-23-qmt-shm-history.md)。

## 材料与范围

先核对当前发行清单中的CLI及CRT完整目录、Host解释器/Agent包、私有配对、历史能力profile、请求根和运行根。`market.full_tick`已可用仅证明该快照能力；历史需要双方匹配的`market.history_1m`能力和预算。终端原线程经SHM调用只读QMT API；终端之外的Host签名HTTP与已退役的终端内HTTP分别归属，旧接口不作为回退。

实际来源加载沿[国信操作手册](guosen-qmt-operations.md)，终端策略启动/停止及私有配置替换按对应授权执行。新的安装、离线配对验证、合成联调、真实终端读数与正式生产分别登记。历史只读入口不授下单或撤单能力。

配置由已验的本版模式生成，包含Host地址与凭据引用、明确请求/运行根、单总截止、页数/总行数/输出字节及文件数上限、source profile。请求文件声明具体证券、起止窗口、行数和分页政策。源时间、分钟边界、复权与量额换算来自已确认来源；未知单位保持未知，禁止为生成CSV临时填1或100。

## 首次读取

下列尖括号均为受管材料中的绝对路径占位，不是可直接粘贴的现场配置。

```text
<CLI> --help
<CLI> fetch --config <私有配置JSON> --request <已冻结计划JSON> --run-root <新的独占运行目录>
```

请求文件位于配置允许的请求根，运行目录位于运行根。新目录只创建一次；同目录已有运行时使用恢复入口。首个POST前保存原请求字节、身份、配置/profile和计划摘要；输出包含每页原始观察及本次`observation.json`。完整安装目录一起使用，不能只搬EXE后假定CRT身份仍相同。

开始现场历史验收时使用小而明确的已下载窗口，逐一确认证券/上市日期、实际time字段及类型、上海时区/分钟边界、原OHLC/volume/amount。之后才扩大范围。空窗口、满行数拒绝、未知终态和真正的完整覆盖分别表达；不根据稀疏返回补造零量分钟。

## 结果与恢复

| 结果 | 处理 |
|---|---|
| `observed` / `empty`，退出0且`callbacks_drained=true` | 本次允许的观察已保存；继续核覆盖和来源资格 |
| `partial`，退出3 | 保留已观察页及失败/未完成页，按原身份核查 |
| `unknown`，退出4 | 请求可能已交给来源；保留原运行根，恢复只GET原ID |
| `timeout` / `interrupted`，退出124/130 | 核当前receipt、回调排空及输出状态，再按原根恢复 |
| `failed`，退出2或其他非零 | 核具体原因及是否已有receipt，不自动重建运行身份 |

```text
<CLI> resume --config <同一私有配置JSON> --run-root <原运行目录>
```

`resume`没有`--request`参数，不提交新POST，不换ID重做未知页。配置/profile改变或原计划身份失配会拒绝；先查明原因，再按明确的新任务处理。分页父窗口的已知终态与未知受理分别判断；恢复缺少子页时保留未完成状态，不偷偷启动新页。请求、receipt、原始结果和计划保持原字节，不能通过手工删除状态文件“解除阻塞”。

读取`output_manifest`对应的观察清单，并核`pages_completed/pages_pending/rows_observed`和原页摘要。进程自然退出、回调排空、观察保存及来源完整覆盖分别检查。CLI当前保留`coverage=unknown`、`source_qualification=not-qualified`；退出0不会自动提升这些资格。

## 进入原生文件消费者

新接入选择 config schema=`qmt.history-cli-config.v2`，按[源值历史合同](../specs/qmt-source-history.md)声明 source_profile。可信来源已确认未复权时，量额单位及分钟边界可显式为 unknown；非空结果仍导出 `qmi-manifest.json` 与逐证券 CSV，数值和时间标签保持来源原值。身份由真实 SourceSession 派生，来源版本和许可绑定本批证券及日期范围；配置 v2 与线上 read_profile_version 分别校验。

沿[QMT分钟导入手册](qmt-minute-import.md)和同版 Helper/文件 ABI 生成标准 DSB 后，使用 `NativeHistory.read_source_store` 读取 bars 与单位、来源和时间元数据。unknown 区间的覆盖保持 unknown，直接使用原 WT CTA 的策略仍须由自有启动入口接入所需元数据并验证时间语义。旧 config v1 保持原标准化行为：需明确分钟边界及换算系数才输出 QMI。策略回放与订阅分别验收，具体已验范围见[当前证据](../evidence/2026-10-27-qmt-real-account-budget.md)。

正式文件源准备、同实例补齐及修订沿[原生Reader手册](native-history-reader.md)。每次导入保留来源、配置/计划、数据摘要和目标文件身份；来源修订新建数据身份。Journal达到容量上限时按[维护手册](guosen-qmt-maintenance.md)处理，当前没有自动清理或轮换；禁止为继续采集直接丢弃未知请求或原终态。

## 长区间批量入口

显式 v5/control3.0 的 bulk 配对使用自有 C++ 程序 GuanhengQmtBulkHistory。它复用已有 SHM 和 Host 通道，支持一次证券长区间请求，由 Host 分页落 CSV/QMI，再交既有 Importer 和 WT 原生文件读取。普通 GuanhengQmtHistory 入口继续使用上文合同。批量入口目前处于本仓源码和开发配对联调阶段，正式统一系统发行接线继续推进；实际结果见[真实月窗](../evidence/2026-10-27-qmt-bulk-real-month.md)与[长区间股票/ETF](../evidence/2026-10-27-qmt-bulk-real-full.md)。

私有配置 schema 为 qmt.bulk-history-cli-config.v1，显式给出 Host HTTP 配置、请求根、运行根、产物根身份及路径、read_profile_sha256 和 limits。摘要应匹配本次配对的完整 v5 profile；Host 负责等待源端连接，CLI 在已取得该认证绑定后发业务请求。HTTP 响应额度须覆盖 Host 公布的 max_http_response_bytes。CLI 输出文件预算 max_output_bytes 上限为 268435456；该预算与 Host 产物目录的总量额度分别管理。

请求 JSON 精确包含四个字段，日期与行数均由本次任务明确指定。以下仅为格式示例：

```json
{"symbol":"000001.SZ","start_time":"20211101000000","end_time":"20211130235900","max_rows":20000}
```

```text
<批量CLI> fetch --config <私有配置JSON> --request <四字段请求JSON> --run-root <新独占目录>
<批量CLI> resume --config <同一私有配置JSON> --run-root <原运行目录>
```

fetch 在唯一 POST 前保存原 receipt；resume 只查询原 ID。成功摘要 schema=qmt.bulk-history-cli-result.v1，status=complete 或 empty，包含实际 rows/pages、manifest_path/manifest_sha256 与 callbacks_drained。非空产物凭该 manifest 和摘要进入既有导入流程；unknown 保留原运行根，按原身份恢复。完整返回覆盖以实际源行的起止日期与交易日库存核对：请求五年区间可以只返回终端当前缓存的一段，不据此填造缺失分钟。
