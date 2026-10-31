# 已下载 QMT 分钟历史导入

类型：操作手册。范围：外部导出交换文件、离线开发导入和原生策略读取验证。行为依据为[QMI 规格](../specs/qmt-minute-import.md)。真实国信 QMT 的资格按输入身份和窗口分别记录，见[下载完成后718条原生回读](../evidence/2026-10-22-qmt-downloaded-cache.md)；使用本手册的合成样本只授相应开发验证。

## 准备输入

使用获准的 QMT 外部读取/导出路径取得已下载历史。当前 CSV 是适配中间格式，QMT 内部缓存文件的路径和格式须另行验证。保留原下载数据，将交换 CSV 和 manifest 放在独立目录。

manifest/profile 和严格 CSV 表头见规格。新接入采用 [schema_version=2 源值合同](../specs/qmt-source-history.md)：保留来源 double 量额和时间标签，明确 value_semantics=source；未知单位或区间写 unknown，保留可信未复权声明及来源身份。分片按每证券时间递增排列并记录 SHA-256。旧 schema_version=1 仍要求 left/right 及到股、元的换算系数，保持原标准化行为。两种模式共用 WT Helper、标准 DSB 和导入命令。本期支持未复权 SH/SZ 分钟历史，coverage 与单位分别表达，缺行保持缺口。

下载完成、文件库存、公开接口可读和窗口完整分别核验。2026-10-22缓存库存约90.97GB，近期三股票718条已回读通过；早期历史可见性和ETF范围仍有缺口。现有100倍成交量profile只具有开发转换一致性，不授精确股数。批量导入前逐证券/时间窗取得非空结果并保留原始量值；空返回保持未知，先查来源，避免以零数据覆盖既有历史。北京市场文件虽在缓存库存内，本期SH/SZ导入范围保持。

## 执行导入

以下是 PowerShell 命令模板，尖括号值须替换为受管环境事实。helper 摘要须从可信开发包清单取得；输入文件摘要用于绑定此次导出。

```powershell
python -B -m integrations.guanheng.qmt_minute_import `
  --manifest '<交换目录>/manifest.json' `
  --output-root '<新的历史根>' `
  --helper '<开发包>/app/WtDtHelper.dll' `
  --helper-sha256 '<可信制品清单中helper的64位摘要>' `
  --max-bars 1000000 --max-input-bytes 268435456 --max-total-bars 10000000
```

源码开发可在仓库根运行；搬迁开发包时在包含 `integrations` 的包根运行。HTTP 基础 SDK 保持独立，此离线命令使用本机 WT helper。预算按实际数据量及磁盘容量设置；适配器按证券处理多片，超限中止，避免全市场同时常驻内存。

成功后检查：退出码为0、`qmt-import.json` 的 status=passed、qualification=DevelopmentVerified、manifest/helper 身份匹配，逐证券 DSB/metadata 摘要、条数和首末时间符合导出。v1 收据保留来源系数，DSB 已统一为股/元；v2 收据记录源标签 first_label/last_label，DSB 保持源量额和标签，sidecar format=2 绑定来源语义。首末时间和条数不能替代日历覆盖证明。

v2 使用 `NativeHistory.read_source_store(root, exchange, code, expected_import_sha256=...)` 返回 `SourceHistoryBar` 与 `SourceHistoryMetadata`；可选摘要绑定调用方已有独立收据身份。默认入口也核本根成功收据的 DSB/sidecar 身份，coverage 始终 unknown。原 `read_store` 仅接受 canonical format=1，源值不得直接进入旧标准化服务。WT DSB 本身不携带单位；策略启动入口须显式读取元数据并检查实际所需语义，原框架不会自动加载 sidecar。

## 验证与选择历史根

开发验证入口：

```text
python -B tests/integration/qmt_minute_replay.py --library <app/WtBtPorter.dll> --helper <app/WtDtHelper.dll> --work <独立验证目录> --module-root <包含integrations的根>
```

搬迁包同一脚本位于 `examples/qmt_minute_replay.py`。该命令自行生成带标记的合成输入并调用真实导入和原生分钟策略，检查文件读取、预热、时钟与闭合回调；真实 QMT 导入数据仍需按来源样本单独核验。

历史根仅在完整成功收据和各输出身份校验后，才可作为受管新策略实例的候选数据目录。命令不改运行配置、不切换服务、不启动策略或账户执行。原 reader 可能缓存历史；将数据写到运行目录后即时可见的能力尚未验收，初次验证使用新实例及冻结新根。

## 失败与恢复

目标已存在时直接拒绝，保留既有数据。输入、预算、helper、写入或回读失败均不产生成功收据；失败根保留用于诊断，禁止把它配置为策略数据源。修正输入或依赖后选择新的输出根重试，保持原始下载、已完成根和活动实例。

根没有成功收据时视为未完成；部分 DSB 文件存在只能证明中间写入。输出根的删除、活动历史切换、正式发布和真实策略启用遵循各自受管操作流程。
