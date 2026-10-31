# ETF与常用指数一分钟历史维护手册

适用范围：按已冻结清单准备QMT本地一分钟历史，转换为WT原生DSB，并接入统一历史目录。规格见[EIH](../specs/qmt-etf-index-history.md)。本流程不下单、不撤单、不改变账户、风险或行情订阅配置。

## 输入与责任边界

正式输入必须同时保存以下身份：

- QMT板块和证券资料原件、清单JSON及各自SHA256；
- 请求起止日、最新完整交易日及每只证券的上市日；
- QMT缓存根、WtDtHelper、NativeHistory Reader和基础目录的绝对路径及SHA256；
- HPR绑定配置的公开身份。认证值只进入受控环境，不写入仓库、日志或收据。

ETF清单来自当前QMT“沪深ETF”板块和逐证券资料。认购、认购现金、终止及未上市项目单列。指数必须具名、市场代码唯一，并以实际一分钟缓存回读作为可用依据。板块成员、文件存在、下载函数返回和日期覆盖是四个独立事实。

期望指数存在元数据但缺少当前一分钟源时，将元数据身份、检查过的缓存路径、准备/导出市场合同和替代项范围写入独立边界收据。替代项只承担明确写出的观察范围。当前北证50使用`899050.BJ`作为官方身份；QMT元数据可见，当前缓存无一分钟DAT，已部署HPR与DAT导出只覆盖SH/SZ，因此状态为`unavailable`。最终50项以`932000.SH`中证2000承担小盘A股宽基观察，北证50继续单列等待BJ来源和合同验收。

## 执行顺序

### 1. 只读审计

先确认没有同一输出根的活动作业，再执行：

```powershell
python -B -m integrations.guanheng.qmt_history_batch audit `
  --selection <selection.json> `
  --cache-root <qmt-datadir> `
  --output-root <new-audit-root> `
  --seconds 1800
```

审计逐行读取时间戳和有符号量额，保留首末时间、逐日条数、负量额样本、文件SHA和`coverage=unknown`。它不修改QMT缓存。

### 2. 缺口准备

下载必须通过现有已认证HPR绑定调用QMT内置`download_history_data`。先持久化请求ID，再产生调用；结果未知时只按原ID查询。不得因超时生成新ID。

```powershell
$env:EIH_HTTP_SECRET = '<由运行环境注入>'
python -B -m integrations.guanheng.qmt_history_batch prepare `
  --selection <selection.json> `
  --cache-root <qmt-datadir> `
  --source-config <public-bound-config.json> `
  --start-day 20211101 `
  --end-day <latest-complete-day> `
  --max-new-requests <bounded-count> `
  --output-root <new-prepare-root> `
  --seconds 3600
```

每次新调用前，模块对现有DAT留稳定完整快照和SHA。调用结束后重新逐行读取实际DAT，并比较旧、新时间标签和六字段。以下状态需要分别处理：

| 状态 | 含义 | 处理 |
|---|---|---|
| `cache_observed` | 实际DAT已回读；日期覆盖仍可能未知 | 查看`remaining_windows`和逐日条数 |
| `no_data_observed` | 调用后仍没有DAT | 保留原请求和空结果，不导入 |
| `source_quality_rejected` | 源含负量额或Exporter拒绝的原值 | 保留源和快照，停止替换 |
| `source_range_reduced` | 新DAT缺少旧快照已有分钟 | 保留旧WT根，核实来源后重做 |
| `request_budget_exhausted` | 本轮新请求预算已用尽 | 使用同一输出根和原请求续跑 |

`remaining_windows`表示请求计划仍待执行的窗口；空数组只证明计划内原请求已经终结。交付覆盖还须单独比较目标起止时间与DAT实际首末分钟，登记目标起点至首条记录前、末条记录后至目标终点的已知无记录区间。没有权威交易日/停牌日历时，观察区间内部完整性保持`unknown`。下载函数返回成功和请求计划完成都不能改写成“完整覆盖”。

来源能力或资料变化后，可以在同一输出根显式加入“已观察缺口”的新区间：

```powershell
python -B -m integrations.guanheng.qmt_history_batch prepare `
  --selection <selection.json> `
  --cache-root <qmt-datadir> `
  --source-config <public-bound-config.json> `
  --start-day 20211101 `
  --end-day <latest-complete-day> `
  --max-new-requests <bounded-count> `
  --retry-observed-gaps `
  --output-root <existing-prepare-root> `
  --seconds 3600
```

该开关只接受此前请求已成功终结且缓存已回读的剩余区间；已有窗口不重复追加，原请求继续保持原ID。当前来源已实测旧区间不增加数据时，不循环使用该开关。

### 3. 冻结转换输入并生成DSB

转换只消费已审计、非负且稳定的实际DAT副本。先从一个或多个准备根冻结合格状态；冻结入口逐SHA核准备批次`RESULT.json`、逐证券`state.json`和`manifest.json`，并确认结果内嵌状态或状态引用与当前文件完全一致。副本清单记录源路径、字节数和SHA，运行期不再依赖可变化的QMT缓存。

```powershell
python -B -m integrations.guanheng.qmt_history_batch freeze `
  --selection <qualified-selection.json> `
  --prepared-root <cohort-1-root> `
  --prepared-root <cohort-2-root> `
  --max-total-bytes <explicit-byte-budget> `
  --output-root <new-frozen-root> `
  --seconds 3600
```

```powershell
python -B -m integrations.guanheng.qmt_history_batch convert `
  --selection <conversion-selection.json> `
  --cache-root <frozen-cache-root> `
  --helper <WtDtHelper.dll> `
  --helper-sha256 <sha256> `
  --reader <GuanhengNativeBarFile.dll> `
  --reader-sha256 <sha256> `
  --output-root <new-conversion-root> `
  --seconds 3600
```

转换入口在Helper调用前后各确认一次选择SHA、冻结完成收据、冻结快照收据以及每个实际DAT的路径、字节数和SHA；转换条目中的来源SHA还必须与冻结输入全集一致。原DAT导出器逐行生成QMI输入，原Importer/WtDtHelper写DSB。随后NativeHistory Reader逐时间戳核对OHLC、volume、amount。外部DAT、DLL和DSB读取均受命令截止时间和显式字节上限约束。任一身份、字段、条数或顺序不一致时，转换不发布成功收据。

### 4. 组装统一目录

旧目录中同一store的成员形成不可拆分闭包。替换其中一只证券时，先用旧目录计算闭包，把该store全部成员加入准备、冻结和转换清单，再执行装配；其余旧股票、ETF和失败记录保持原条目。装配入口重新核转换结果、冻结收据、Helper/Reader和逐行回读；随后解析每个原生导入收据，逐成员核证券、市场、代码、条数、首末时间、DSB路径和SHA，并要求收据成员全集与本次转换store成员全集一致。

```powershell
python -B -m integrations.guanheng.qmt_history_batch assemble `
  --base-catalog <existing-catalog.json> `
  --fresh-conversion <conversion-1-RESULT.json> `
  --fresh-conversion <conversion-2-RESULT.json> `
  --output-root <new-catalog-root> `
  --seconds 3600
```

目录按来源实例分组生成原`source-stores`配置：

```powershell
python -B -m integrations.guanheng.qmt_history_batch catalog `
  --catalog <assembled-catalog.json> `
  --reader <GuanhengNativeBarFile.dll> `
  --reader-sha256 <sha256> `
  --output-root <new-source-config-root> `
  --seconds 3600
```

组装完成后用原NativeHistory和公开SDK分别查询新ETF、新指数、旧ETF、未替换股票；用例固定角色、首末时间、精确条数及完整六字段序列SHA。临时Bearer只存在于进程内存：

```powershell
python -B -m integrations.guanheng.qmt_history_batch qualify `
  --source-config <source.json> `
  --cases <qualification-cases.json> `
  --output-root <new-qualification-root> `
  --seconds 3600
```

## 中断与恢复

- 先读取作业`result.json`和子进程树；缺少结果文件不等于作业已经停止。
- `plan.json`、`request-*.json`和`state.json`是恢复依据。窗口参数与已有请求不一致时停止，不覆盖原请求。
- 原请求已提交且结果未知时只继续GET。确认终态后才能推进同一证券下一窗口。
- HPR主机退出后可在同一配对和日志上恢复原结果；达到任务容量时创建新配对，并保持QMT策略正文中的行情配置、映射名和凭据字节一致。
- 冻结根按清单身份恢复：已完成副本按SHA复用，部分副本改名保留后重新快照；完整清单发布后保持原字节。转换输出中断时使用新的输出根重做。

## 完成标准

完成收据至少包含：清单和元数据SHA、逐证券实际首末时间/条数/剩余窗口、全部请求ID及终态、源快照和修订比较、Helper/Reader身份、逐条回读结果、完整store闭包、旧股票保留证明、公开SDK查询结果、独立评审和`python -B scripts/project.py check`结果。任何来源范围未知或不可得证券继续单列，不计入已完整覆盖。

## 当前正式交付定位

- 最终目录：`build/qmt-etf-history-001/assembled-main009/RESULT.json`；
- 统一只读配置：`build/qmt-etf-history-001/catalog-final001/source.json`；
- 公开查询资格收据：`build/qmt-etf-history-001/qualify-final002/RESULT.json`；
- 装配与旧证券保留审计：`build/qmt-etf-history-001/FINAL-ASSEMBLY-AUDIT.json`；
- ETF逐只覆盖：`build/qmt-etf-history-001/ETF-FINAL-COVERAGE.json`；
- 50指数逐只覆盖：`build/qmt-etf-history-001/INDEX-50-FINAL-COVERAGE.json`。

QMT指数元数据当前对50项统一返回`open_day=19901219`。该值属于市场级默认值，不能作为逐指数发布日期。目标日起算时，先查指数公司或交易所官方发布日期；仅对2021-11-01后正式发布的指数使用实际发布日期，其余维持2021-11-01。历史准备请求从有效目标起点终态成功后，若DAT和既有目录仍无更早记录，将前缀登记为`source_limited_prefix_gap`，保留请求与本地库存扫描证据，不循环提交相同窗口。
