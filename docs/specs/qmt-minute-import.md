# QMT 已下载分钟历史的外部导入与原生策略读取

源值接入采用[源值分钟历史合同](qmt-source-history.md)：新 v2 保留来源 double 量额和时间标签；本页已有 v1 标准化合同保持。存储复用同一 WT Helper/DSB，不增加数据库。

状态：accepted。类型：当前已确认目标的实现规格；前缀 QMI，所有者为行情适配维护者。整体范围沿[当前目标](../roadmap/TARGET.md)；本规格交付离线历史导入及原生分钟策略读取，统一实时接口和在线补洞继续属于完整目标。

## 背景与边界

用户正在国信 QMT 下载历史分钟数据。现有 WT 已提供 `WtDtHelper.store_bars/read_dsb_bars`、标准 DSB 目录和原生 CTA 历史读取/分钟回调。当前缺口是明确导出输入到原生存储的外部适配。源码调查表明原 reader 会缓存历史，本阶段生成新历史根并由新策略进程读取；运行实例热更新资格另验。

适配代码位于 `integrations/guanheng`，使用 Python 标准库及受管 WT 动态库；不修改 WT 框架源码、不依赖 wtpy；在 QMT 外只读解析已验证的本地分钟 DAT 缓存，也可接收显式 CSV/QMI 导出。不改写供应商缓存，不下载数据、不连接账户、不发布服务。本地缓存适配器按下述显式布局准入，CSV 是复用原导入器的中间交换格式。原日线业务和交易 owner 保留。

## 结构与流程

```text
获准的 QMT 外部导出 → CSV 分片 + 显式 manifest/profile
  → 校验/按证券归并/规范化 → 原 store_bars(m1)
  → 原 read_dsb_bars 回读比对 → 标准 DSB + 原 format=1 sidecar
  → 最后写入 qmt-import.json 完成收据 → 新 WT 原生策略进程读取
```

公共入口为 `import_dataset(manifest, output_root, helper, helper_sha256, *, max_bars=1000000, max_input_bytes=268435456, max_total_bars=10000000) -> dict`，CLI 为 `python -B -m integrations.guanheng.qmt_minute_import --manifest ... --output-root ... --helper ... --helper-sha256 ...`，预算可同名 kebab 参数指定。成功打印 JSON 收据，失败非零退出并给出固定类别诊断，不输出输入行或 native 日志内容。

输出 root 须不存在，独占 mkdir 后逐证券写入；完成收据最后通过同目录临时文件替换写入。失败保留未完成根供诊断，禁止覆盖/删除旧根；重试使用新根。调用者仅可选择带完整成功收据的受控新根作为策略输入，不改变活动配置。并发目标冲突直接失败，不自行恢复或扩大已有目录。

## 输入与数据契约

manifest 为 UTF-8 JSON，严格字段、重复 key 拒绝、上限 4 MiB：

```json
{
  "schema_version": 1,
  "profile": {
    "provider": "Qmt", "instance_id": "synthetic-terminal", "session_id": "synthetic-export",
    "generation": 1, "dataset_version": "synthetic-v1", "source_license": "synthetic-only",
    "input_kind": "synthetic", "timezone": "Asia/Shanghai", "minute_boundary": "left",
    "volume_to_shares": 100, "amount_to_yuan": 1000, "adjustment": "none", "factor_version": ""
  },
  "securities": [{"symbol": "510300.SH", "chunks": [{"path": "510300-part1.csv", "sha256": "<64 lower hex>"}]}]
}
```

示例字段值为虚构示例。provider 固定 Qmt；input_kind 为 synthetic/qmt_export，表示输入出处声明，真实来源资格仍需验真。instance_id/session_id 非空且最多128字符，与现有 SourceSession 契约一致；版本/许可非空且最多256字符，拒绝控制字符及无效 Unicode。generation 为正 uint64；时间固定 Asia/Shanghai。证券为六位 SH/SZ，各证券唯一；分片为 manifest 目录内普通相对文件，拒绝越界和符号链接，按清单顺序读取。最多 10000 个证券、总计 10000 个分片；每个证券需至少一个分片和一条记录。

CSV 严格 UTF-8（允许 BOM）表头 `timestamp,open,high,low,close,volume,amount`；时间精确为 `YYYY-MM-DDTHH:MM:00+08:00`，日期限 1992–2099，left 明确加一分钟转换为 right，跨日拒绝。行情时间严格递增，跨片重复/倒序拒绝，缺分钟保留缺口；价格正数、OHLC 一致，量额非负，全部有限数。数据价格为元，成交量和成交额乘显式正有限系数转换为股/元，转换后再次校验。adjustment 首期仅 none/factor_version 空串，避免未经因子校验的复权历史进入原生策略。

文件先按预算读取并以同一字节内容验证 SHA-256 后解析，源修改无法改变已验证输入。按证券有界归并；每证券 <=max_bars（1..1000000），单片 <=max_input_bytes（1..268435456），累计 <=max_total_bars（1..10000000000），超限失败并保留无成功收据的新根。预算限制实际读取和分配，不能只检查声明。

输出 `his/min1/SSE|SZSE/<code>.dsb` 由 WT 编码；WTSBarStruct.date 为 YYYYMMDD，time 为 `(date-19900000)*10000+HHMM`。settle=close，其余非来源字段为零。sidecar 沿现有 format=1 契约，数量已标准化，系数只作来源证据保留，content_id 为 DSB 摘要；qualification 固定 DevelopmentVerified，不由输入提升生产资格。

完成收据 schema_version=1，status=passed，qualification=DevelopmentVerified，coverage=unknown；记录 manifest/helper 摘要、profile、每证券输出相对路径/DSB 与 sidecar 摘要/记录数/首末右端时间/分片身份。不存在“仅凭首末时间/根数推定完整”的路径。

## 原生与异常契约

仅调用既有 `store_bars` 和 `read_dsb_bars`，共享现有 ctypes WTSBar 布局定义。helper 必须与显式 SHA-256 匹配，ABI 大小88；动态库依赖目录在退出时关闭。本阶段 reader 仅回读本次由受管 helper 从有界记录生成的新文件，不作为任意外部 DSB 解码接口。检查实际文件存在及回读条数、count/last 回调与全部字段逐值一致，写入 bool 返回值不能替代回读验真。回调捕获异常并在 native 返回后抛出，禁止异常越过 C ABI。

输入/预算错误、依赖不可用、原生写入/回读失败和目标已存在均不生成成功收据，不动原数据。失败诊断限类别与安全说明；详细源行、凭证和原生日志不外泄。生成目录是导入产物，不新增业务账本或后台作业。

## 要求与验证映射

| ID | 要求 | 验证入口 |
|---|---|---|
| QMI-R1 | 显式格式/身份/单位/时间/版本，严格输入与实际预算 | importer 单元与异常矩阵，跨片时间/单位人工核算 |
| QMI-R2 | 复用原 ABI 编写标准 DSB，完整回读及沿用 sidecar | 实际 helper 原导出、逐字段比较、现有 NativeHistory.read_store 兼容读 |
| QMI-R3 | 新根独占、成功收据最后落盘，失败/重复运行保留旧根 | 多证券后段失败、既有目录哨兵、并发/重试、写入/回读故障 |
| QMI-R4 | 原 WT 策略从实际导入文件读取 m1，时钟/预热/分钟回调正确 | 独立进程 WtBtPorter bin-path 原生 CTA get_bars + bar events，无外部 feed 替代文件读取 |
| QMI-R5 | 外部命令可搬迁，受管制品和正负向入口 | CLI 子进程与新开发包内实际 import/replay，helper 摘要拒绝 |
| QMI-R6 | 资格和架构边界准确 | 核心12文件摘要不变；真实样本待验；统一策略实时/补洞继续登记 |

## 发布、恢复与兼容

本阶段只产开发候选，原生 helper 为现有开发制品，包含此前待审框架差异，不能据此声称已在纯净上游验证。旧开发包和冻结证据保持原件。Python 新模块随自有 integrations 发布，HTTP 基础 SDK 不引入 DLL 依赖或无关版本升级。失败根保持未完成状态，换新根重试；已完成根按收据冻结后由受管切换选择，真实运行切换另验。

## 待核实与风险

真实国信 QMT 导出接口、格式、权限、分钟标签、单位、复权及十年覆盖由实际来源样本证明；当前以显式合成分片开发，不阻塞适配实现。文件修改后的现有 WT reader 缓存刷新、在线订阅及历史到实时的补洞继续按完整目标实施。历史停牌/退市排除由日历/证券 owner 提供，本阶段 coverage 保持 unknown。

## QMI-DAT：已下载本地缓存的离线入口

状态：accepted。用户选择首次批量历史导入优先在 QMT 外直接读取缓存，实时与在线只读操作继续使用共享内存。该程序属于外部适配层；QMT 策略内部的无文件、无网络访问要求保持。

QMI-DAT-R1：读取显式 cache_root 下 SH/60 与 SZ/60 的六位证券 DAT；支持给定证券列表与 all-cache 扫描。当前布局为8字节头 feffffffffffff7f 加64字节定长记录；offset0是小端uint32 Unix秒，4/8/12/16是小端uint32 OHLC/1000，24是uint32源成交量，32是uint64源成交额。未消费字段保持未解释；未知文件头、截断记录与不合格价格/时间不按该格式输出。布局来自实际缓存对照，支持范围按已验类型记录，不宣称供应商所有DAT版本通用。

QMI-DAT-R2：按有界块读取；同一源句柄读取前后核size/mtime/文件身份，导出记录原DAT SHA、字节数、修改时间与实际首末标签。转换不加载QMT SDK、不启动/连接终端、不改原DAT，缺分钟保持原样。

QMI-DAT-R3：export_cache生成原QMI schema2/source及CSV，多证券按既有securities清单；convert_cache再直接调用原import_dataset生成同一WT历史根。保持源值与标签，单位/分钟边界unknown；离线批次的SourceSession显式local-dat身份，不冒充在线认证连接。原Importer/Helper/DSB及NativeHistory承担最终文件写入与读取，不新增行情数据库。

QMI-DAT-R4：每证券行数、总行数、单源文件字节数及读取块大小有明确预算；输出使用新独占根，失败不发布完整成功收据，原文件/旧导入根保留。首次主路径按实际股票与ETF校验全部行；整体模块主路径完成后再集中验证边界、恢复和代码评审。

公开入口：integrations.guanheng.qmt_local_dat 的 scan_cache、export_cache、convert_cache；CLI使用 export 或 convert 子命令、显式 cache-root、symbols/all-cache 与 output-root，convert提供受管Helper及SHA。历史库存扫描结果仅表明当前文件存在与大小；完整交易日覆盖单独核实。


QMI-DAT-R5（accepted）：inspect_cache及inspect CLI在QMT外只读清点所选沪深缓存，逐文件核布局、文件身份、长度和首末记录时间，输出新根inventory.json。完整扫描与首末抽样分别标识；该入口不遍历中间记录、不判断交易日缺口、不保证OHLC有效或覆盖完整、不生成DSB。异常文件记录固定分类并保留在清单，不作为可导入成功；单文件异常不妨碍其余库存清点，根身份变化和输出失败使整次清点失败。目录上限沿原10000文件，JSON输出沿4MiB；源文件无修改、无SDK/网络操作。该清单用于选择转换批次和定位实际缓存尾部。

inspect逐文件观察同时写入新根inventory-items.jsonl，容量同样上限4MiB；它只代表已完成的单文件观察。最终inventory.json写入后才声明整次清点完成；两者按实际顺序一致。超时或异常保留部分观察，不能把部分清单视作完整成功收据。
