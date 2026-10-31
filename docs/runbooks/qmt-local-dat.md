# QMT 本地分钟 DAT 离线转换

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：操作手册。范围：本机已下载的 SH/SZ 分钟缓存导出与 WT 历史导入。状态：正常样本及来源价格范围异常的3证券完整转换/原生回读已通过；整批库存转换继续。

## 执行链与适用范围

产品入口（外部历史/待归仓路径：`../../integrations/guanheng/qmt_local_dat.py`）在 QMT 外用 Python 标准库只读 DAT，输出 QMI v2 和 source 原值 CSV；`convert` 继续调用原 [Importer](../../integrations/guanheng/qmt_minute_import.py)、WT Helper，生成标准 DSB。命令无需启动 QMT 策略或 Host，不加载 QMT SDK、不访问网络、不修改原缓存。实时和在线读取继续使用既有共享内存链路。

当前适配已验证的 `8 + 64 × 记录数` 布局，缓存位置为 `<cache-root>/SH/60/<代码>.DAT` 或 `SZ/60/<代码>.DAT`。目录扫描表示发现缓存文件，不能证明时间覆盖完整或所有代码均为股票；证券范围由显式清单或 `--all-cache` 选择。

来源值和时间标签遵循 [source 历史合同](../specs/qmt-source-history.md)。未知价格、成交量、成交额单位及分钟边界保留 `unknown`，不擅自做 100 倍换算。输出保持 `value_semantics=source`、`coverage=unknown`，离线来源身份与在线会话分开记录。

## 先清点实际缓存范围

使用同一产品入口的inspect模式生成新根inventory.json，逐文件记录行数估计、首末标签、文件身份、空文件和不可读取分类：

```powershell
python -B -m integrations.guanheng.qmt_local_dat inspect `
  --cache-root 'D:/software/guoxin/datadir' --all-cache `
  --output-root 'E:/managed/qmt-inventory-001'
```

也可用--symbols选择明确清单。该入口只读文件头、长度与首末记录；validation固定header-length-first-last-only，coverage仍unknown。统计全部文件首末日期用于定位缓存尾部；中间OHLC质量、时间倒序、缺失交易日及停牌不由该抽样判断。异常文件保留在清单的unavailable条目中，需核实后再转换；status=passed只表示清点完成。source_bytes与estimated_rows仅累计可读布局，异常文件不计入估计。

inspect不需要Helper和SDK；输出根必须全新，JSON上限4MiB，最多10000个证券。清点使用外部进程的明确执行预算，机械盘全目录随机读取可能超过小样本耗时；超时未发布的根保持未完成，确认原进程退出后才能换新根重新运行。

## 先验证少量证券

在包含 `integrations` 的仓库或开发包根目录，以 Python 3.10+ 运行。以下是 PowerShell 示例；输出父目录须已存在，`--output-root` 须使用尚不存在的新目录。

仅导出 CSV 和 QMI，不需要 Helper：

```powershell
python -B -m integrations.guanheng.qmt_local_dat export `
  --cache-root 'D:/software/guoxin/datadir' `
  --symbols '000001.SZ,510300.SH' `
  --output-root 'E:/managed/qmt-export-sample-001' `
  --max-total-rows 1000000
```

直接转换为 WT 历史，Helper 路径和 SHA 须替换为受管制品的实际值：

```powershell
python -B -m integrations.guanheng.qmt_local_dat convert `
  --cache-root 'D:/software/guoxin/datadir' `
  --symbols '000001.SZ,510300.SH' `
  --output-root 'E:/managed/qmt-convert-sample-001' `
  --helper '<开发包>/app/WtDtHelper.dll' `
  --helper-sha256 '<可信制品清单中的64位SHA-256>' `
  --max-total-rows 1000000
```

`export` 在新根生成 `csv/`、非空证券的 `qmi-manifest.json` 和最终 `export.json`。`convert` 在新根生成 `qmi/`、`store/` 和最终 `convert.json`；原导入成功收据位于 `store/qmt-import.json`，DSB 位于 `store/his/min1/<交易所>/<代码>.dsb`，每证券带独立 metadata。

无记录的缓存单独记录，不进入 QMI；全部为空时 `convert` 返回 `empty`，不调用 Importer、不生成 DSB。失败时保留本次部分输出供核查，原缓存保持原样；重试选择新输出根。

## 批量导出与容量

先核少量证券成功收据、条数、首末时间和实际回读，再扩大批量。`--symbols` 与 `--all-cache` 二选一。以下全缓存导出示例显式提高总行数预算：

```powershell
python -B -m integrations.guanheng.qmt_local_dat export `
  --cache-root 'D:/software/guoxin/datadir' --all-cache `
  --output-root 'E:/managed/qmt-export-all-001' `
  --max-total-rows 1500000000
```

此预算是示例，应按当次库存调整。默认总行数上限为 10000000，单证券 `--max-rows` 默认 1000000；`--max-input-bytes` 限制单个输入文件，`--block-records` 控制 DAT 读取块。使用 `convert --all-cache` 时补上 Helper 参数，并预留 CSV、DSB 与收据同时存在的空间；CSV 文本尺寸可能超过原 DAT。执行前确认输出盘可用容量，必要时按证券清单分批。

2026-10-27 的库存快照（外部历史/待归仓路径：`../../build/qmt-local-dat-001/INVENTORY.json`）发现 5342 个文件、约 82.58 GiB；按长度推算约 13.85 亿条记录，其中 2 个文件无记录。这是当时的文件库存与长度推算，尚不代表全部记录内容有效或全市场历史完整。

## 读取与当前证据

导入成功后，按[分钟导入手册](qmt-minute-import.md)用 `NativeHistory.read_source_store(store, exchange, code, expected_import_sha256=...)` 读取原值及来源 metadata。成功收据不自动切换正在运行的策略；原 WT CTA 不会自动加载 sidecar，策略入口须明确消费所需元数据。

缓存与真实来源对照（外部历史/待归仓路径：`../../build/qmt-local-dat-001/COMPARE.json`）已核 `000001.SZ` 287966 行、`510300.SH` 13980 行，合计 301946 行；时间和 open/high/low/close/volume/amount 六字段逐值完全一致。该证据确认这两份样本的解码对应关系。正式产品 `convert` 已实际转换两证券共301946行（约4.82秒），原生读取与逐行核对通过（约5.08秒）；两个DSB的SHA与原SHM链产物一致。具体输入、源码与DLL身份、命令、成功收据及范围见[实际记录](../evidence/2026-10-27-qmt-local-dat.md)。全库存尚未执行。


转换后可直接以显式 source-store 模式启动[独立行情服务](market-service.md#离线导入数据的来源原值服务)，由观衡 source 配置展示基础分钟图。两证券实际 HTTP/SDK 与浏览器主路径见[图表证据](../evidence/2026-10-27-qmt-source-chart-main.md)。

后继已实际完成17只股票4860337根批量转换（约70秒），原生逐行回读（约73秒）全部一致；另3只来源OHLC差异已核对国信官方接口并完成820254根转换/逐值回读，8条异常原值保留且带质量声明；见下节。成功样本均起于2021-11-01，尾部实际到2026-10-21，完整库存与尾部更新仍待完成。见[批次证据](../evidence/2026-10-27-qmt-local-dat.md#后继17只股票批量转换)。

清点完成的实际案例见[全缓存清点](../evidence/2026-10-27-qmt-local-dat-inventory.md)：5342文件中5284份尾部为2026-10-21。inventory-items.jsonl保留已完成的逐文件观察；没有最终inventory.json的目录只作未完成进度，不能据此选择全量导入已完成状态。


## 来源价格超出high/low的处理

本机国信官方接口与DAT逐值对照确认，部分来源分钟的open低于其low。这类来源原值在source导入中完整保留，不能重建或改写成标准OHLC。导出export.json的每个非空证券含price_range_quality：checked_rows、inconsistent_rows、固定类别counts和至多8个first_labels。异常证券的原QMI成功收据项与metadata sidecar也保存该摘要；正常旧产物字段保持。

SourceReader对摘要与实际DSB逐条重算，返回metadata.price_range_inconsistent_rows；每条SourceHistoryBar.price_range_status可明确检查consistent/open_outside_range/close_outside_range/open_close_outside_range/inverted_range。需要标准OHLC的策略须检查该项；canonical导入与读取继续拒绝范围不一致。来源HTTP/SDK保留原字段和原值，消费方按自己的指标输入要求检查；观衡标准K线图遇异常分钟显示具体质量原因，保留原值且不静默删行。

非有限数、非正价格、负量额、重复倒序时间、布局与源身份变化仍失败。此规则适用于全部source记录，不按证券或09:31特判。现有SHM分钟协议的严格OHLC准入保持，本项不改变活动源协议。当前已发现8条异常（600000.SH 1条、600015.SH 1条、000007.SZ 6条），全文件转换和原生回读共820254根通过；[修复证据](../evidence/2026-10-27-qmt-source-price-quality.md)记录同源核对、原文件SHA保持及实际来源查询。来源内部为何产生该价格组合仍无供应商解释，记录不将其归因为集合竞价。

## 全目录与刷新批次装配

已经结束的导入目录可先通过原source_market生成健康配置，不等待其它尾部刷新。源目录、成功收据、失败/空集合和tail_refresh分别保留。读取服务按证券唯一注册原store；刷新同一证券时先按完整旧store闭包形成去重的新catalog，再交现有配置准备入口核全部成员，不能靠配置顺序覆盖。

作业到期时保留原失败终态与已完成批次；先确认原进程及子进程关闭，再核完整成功收据、导出身份和成员。后继任务明确剩余/新增选择及自己的总预算，不重导原成功集合，也不回写旧截止或把新任务成功归入旧预算。进行中journal供观察；仅在原作业终结、完整成功批次验证后，才可据它准备明确范围的已完成切片。

最终首尾/条数与源文件stat核对是尾部证据，完整源SHA或全分钟验证分别声明。已下载缓存库存与当前股票/ETF清单分别统计，缺ETF文件不能解释成已经具备该ETF完整历史。当前运行实例见[全目录证据](../evidence/2026-10-28-qmt-history-full-catalog.md)，候选准备不自动切生产。
