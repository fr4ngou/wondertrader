# WT统一日线角色安装、更新和回退

类型：运行手册。适用范围：独立WT数据程序、原SMP组合及外部数据根。状态：离线制品、安装及七指标整链验收通过；当前正式入口及回退保留。完整数据/身份要求见[规格](../specs/qmt-source-daily-history.md)，模块资源边界见[说明](../modules/unified-daily-data.md)。

## 构建与离线安装

永久声明`config/unified-daily-data-source.json`固定共享原模块、角色项目、工具、原生身份及基础解释器清单。构建从永久源码生成Core与SDK轮子，沿固定registry收集完整第三方wheel；原件数据和凭据保持在运行数据根。参数均使用受控绝对路径，以下变量表示调用方已核SHA的工具和输入。

部署全类别价格的本地来源时，`price_scope.local_qmt_dat_root` 指向 WT 数据进程可读的现有 QMT `datadir`。该选项在新价格任务中启用日线及完整分钟的本地原价准备。采用前核对声明目录、可读权限、实际证券和日期覆盖，再用固定任务确认 QMT 原价请求及已发布日线。复权请求继续使用原供应商参考。

```powershell
& $sourcePython -I -B scripts/unified_daily_source.py --work $newBuild --python $sourcePython --backend $flitWheel --wheelhouse $fixedWheels --native-directory $verifiedNative --seconds 600
& $sourcePython -I -B $installer --artifact $artifact --manifest-sha256 $manifestSha --destination $newProgram --python $sourcePython --seconds 600
```

`$newBuild`及`$newProgram`须不存在。安装前核对交付ZIP及ARTIFACT清单SHA；安装器校验所有成员、完整固定CPython文件清单、离线wheel哈希和依赖闭包，再确认永久原模块字节。成功安装产生INSTALLATION.json，记录实际python/pythonw、入口SHA、完整依赖和Native身份。安装操作不启动来源、WT或观衡，不修改外部数据。

固定CPython为3.12.13 x64，原文件Reader/Helper/Storage及Windows依赖沿该次制品资格。失败根及日志保留；后继安装选择另一全新程序目录。Source SDK版本与协议版本分别核对，SDK0.16支持统一日线、批量、快照、定日事实及证券资料。

## 固定外部数据配置

数据配置使用`guanheng.daily-data-service.v1`，详细字段以UDI表为准：directory拥有持久INDEX/任务；raw_store拥有原件和回执；template固定原基准、资料、事实、Native、受保护slot和publication_directory；inputs复用原HPR/批读声明，凭据来自原环境引用。cache_seed和prepared_native只复用日期/股票池/原件身份匹配的完成结果。

接通观衡上游补齐时，WT 候选配置的 `observation_repair_root` 指向与观衡采集器相同的本机观察数据根，观衡候选配置启用 `schedule.wt_repair_enabled=true`。先验证两个进程都能访问该目录，再验证手动请求、WT 发布回执和观衡覆盖复核。WT 只以自身配置的证券、来源与历史范围执行原日更，观察请求无法扩大范围。两项缺省沿原运行路径。

市场结构股票横截面启用项为 `inputs.stock_cross_section`。其中 `bigquant_python` 指向经验证且已安装 BigQuant SDK 的隔离解释器，`timeout_seconds` 是单次查询预算，建议首次隔离验证使用 30 秒。`minimum_sample_count` 沿市场结构全市场口径使用 4500 只，防止不完整样本进入信号。可成对配置 ISO 日期 `history_from` 和每轮历史交易日数 `history_days_per_cycle`，在现有 WT 定日股票池范围内增量回填，优先处理从未尝试的日期。运行环境提供 `GUANHENG_BIGQUANT_CREDENTIAL`，值为受控的 AK.SK，不写数据配置或日志。该项作用于 WT 每日定日事实，失败以显式缺口随原发布保留。观衡以 `wt_market_structure_stock` 替换原股票横截面直连来源，保留已有归档历史。上述字段是候选配置用法，实际启用需按相同 WT/观衡快照和配置组合验收。

中证2000成交额备用方案在 `inputs.supplement_facts` 添加目标 `metric=index_turnover`、`symbol=SSE.932000` 和所需历史起日 `from`。候选起日为中证2000发布日 2023-08-11。在 `external_fallback` 追加 `BigQuant`，并设置 `bigquant.bigquant_python` 为隔离解释器、`bigquant.timeout_seconds` 为 30 秒。沿用同一环境凭据、既有补充任务和发布策略。历史请求使用原补充事实阶段剩余预算，已发布的可用数据在重试时复用。观衡仅用这项事实补充同日 WT 日线的缺额或未核单位，用原始价格继续核算价格指标。启用范围由实际配置决定。

券商回撤看板的候选补充事实为 `metric=margin_purchase`、`symbol=CN.MARGIN_REPORT`、`from=2025-10-13`，使用既有 `Eastmoney` 备用来源。观衡接入 `wt_broker_heat` 可从 2026-10-26 起验证显示，计算会自动读取之前的预热窗口。隔离读回 265 行，历史已覆盖 2025-10-13 至 2026-11-12 的官方交易日；2026-11-13 原报表缺行，继续标注待补。生效范围由实际配置决定。

IPO 供给回购比看板使用三项 `CN.SH_SZ` 补充事实 `ipo_gross_proceeds`、`shareholder_reduction_gross`、`buyback_execution_disclosed`。候选配置追加 `Eastmoney` 和 `CNINFO`，并把 `www.cninfo.com.cn` 与 `static.cninfo.com.cn` 纳入 WT 公共数据来源主机清单。`wt_ipo_supply` 的 `history_from` 是看板显示起点，三项补充事实需覆盖该日起始窗口之前的 19 个开市日。隔离检查已读回 2026-11-11 至 2026-11-13 的科创50真实收盘。该区间回购仍有歧义缺口，因此比例留空。生产配置需单独启用验收。

沪深300 ETF 市值占比候选配置在 `inputs.supplement_facts` 登记 `index_free_float_market_cap/SSE.000300` 及 510300、510310、510330、159919 的定日 `etf_total_shares`。分母来源启用 `external_fallback` 中的 `CSI`，在原 `inputs.public_facts.allowed_hosts` 加入 `oss-ch.csindex.com.cn`。建议隔离验收先使用已核的 2026-11-12 起日，历史扩展按实际日报覆盖与可用预算确定。观衡候选来源为 `wt_csi300_etf_cap`，日期策略为 `cn-prior-day`，指标为 `csi300_etf_cap.ratio`，证券列表为 `SSE.510300/SSE.510310/SSE.510330/SZSE.159919`。该来源从 WT 同一快照读取四只基金与指数的价格、份额和自由流通市值。

2026-11-14 隔离验收使用已归档的真实 QMT 批次与既有单位证明生成四只基金的八行原生日线，另经实际 QMT 能力绑定检查及沪深交易所、中证指数日报取得十行补充事实。独立 WT 回环 HTTP 同一快照返回全部字段，观衡发布后从看板目录及序列端点核对读回，两个交易日缺口为零。11 月 12 日和 13 日的占比分别为 1.812731% 和 1.803908%。实现基线为 `45b8ba4f`，受控工作树材料位于 `build/observation-csi-cap-joint-qa/observation-api-result.json`，SHA256 为 `462adc302ae74aeb42924effdb6e7c5f9b365a5d3652be6d9be6752affccb8ed`。本次验收覆盖冻结数据的发布和读取，实际日更、长期历史覆盖及正式切换另验。

来源连接、Native路径及其他配置身份在持久根中固定。普通程序重装沿用同一数据配置及数据根；配置引用的旧Native程序/固定资产仍是有效依赖，回收任务须计入引用。改变来源或归档政策时按原槽/配置身份做显式迁移，保留原根和保护引用。新程序先通过真实读取、更新和关闭验收，再由Root统一采用。

首次切换保留已成功数据。先用固定的已完成版本初始化新CURRENT，再用独立入口按实际目标日接续；单轮成功要求原始缓存、事实、Native及快照身份一致，调用返回和完整覆盖分别登记。命令形状如下，日期为示例：

```text
pythonw -I -B daily_data_service.py --config <daily.json> --config-sha256 <sha256> --control-directory <root/uuid> --control-id <uuid> --once --as-of 2026-11-03
```

同任务恢复沿原目录、capture_id、slot、截止事实和已完成阶段。已有来源责任暂不可续核时保留原ID与保护区间，其他计划及新缓存继续核查。当前未出现的旧价格键保留原DSB和复权参考；来源截短旧日期时拒绝本候选，当前成功数据继续可读。

## 市场补充事实和历史补齐

按[MSF规格](../specs/market-supplement-facts.md)在原`inputs`增加可选配置。日期为示例；应使用已核上市起日及实际授权窗口：

```json
{
  "supplement_facts": {
    "schema": "guanheng.market-supplement-plan.v1",
    "targets": [
      {"metric": "etf_total_shares", "symbol": "SSE.510300", "from": "2024-09-02"},
      {"metric": "margin_balance", "symbol": "CN.MARGIN_REPORT", "from": "2024-09-02"},
      {"metric": "market_turnover_proxy", "symbol": "CN.SH_SZ", "from": "2024-09-02"}
    ],
    "policy": "qmt_preferred",
    "external_fallback": ["SSE", "Eastmoney"],
    "required": false,
    "max_requests": 24
  }
}
```

原`public_facts.allowed_hosts`须显式包含实际使用的主机：`query.sse.com.cn`、`www.sse.com.cn`、`www.szse.cn`、`datacenter-web.eastmoney.com`、`data.eastmoney.com`。总请求、字节和时间额度继续由该原配置负责；先核当前QMT绑定，代理读取使用原持久slot。历史窗口较长时同一任务可能多轮pending；沿原输入目录运行才能复用成功原件并只补缺。`supplement/COVERAGE.json`记录应有数、成功数和逐项原因；required模式完整后才冻结UPDATE、进入原发布链。

`required=false`允许带缺口发布，避免晚到份额/融资或旧官方金额缺口阻断完整事实版本；原price-first仍可先发布价格。次北京时间自然日09:00后，对partial同市场日创建一次原INDEX修订；失败按原节拍恢复，同日partial成功后等待新自然日或新的闭合日。`max_requests`为本阶段HTTP＋SDK份额，仍扣原总账；新日优先取最新事实，再补旧gaps。新配置/新程序先使用独立目录验收，保持生产CURRENT；安装和采用分别执行。补充查询SDK0.19.0为`source_supplement_query(request)`，请求固定snapshot_id，日期和分页沿MSF；价格、股票daily_facts与这些补充指标各自保持事实定义。

已有历史目录通过`template.supplement_facts`固定描述符作为首次seed；daily.raw_store必须与seed目录的raw_store一致。跨库迁移先逐SHA复制能力/proof/父原件并核闭包，再生成新描述符，保持原目录与原收到时刻。后继日自动优先采用CURRENT中的补充目录。

新任务根沿`inputs.previous_requests`携带实际存在的旧REQUEST；对于旧INDEX已登记、外层REQUEST尚未物化的任务，固定其实际存在的`inputs/INPUTS.json`并放入`inputs.previous_inputs=[{"path":"E:/example/old/inputs/INPUTS.json","sha256":"<sha256>"}]`。原来源读取可能在完整REQUEST之前已经派发，不能从REQUEST缺失推断无责任。原input recovery只续核已尝试slot，不为未尝试旧批次派新请求；保留旧INDEX和未物化意向的迁移记录。

发行清单以已运行角色为基线，包含补充模块与原生目录实际读取所需的内部模块闭包；SDK0.19与角色普通安装一起验证。原件仍在外部受控对象库，安装及日常采用分别登记。

## 原WT托管组合

日更的QMT批读入口按[批读来源托管](qmt-analysis-batch-source.md#独立日更的来源托管)独立常驻，避免金融执行退出同时关闭数据依赖。HPR、证券资料、批读和本日更沿既有服务组按依赖顺序管理；自动09:00/15:30任务与原请求恢复由日更owner拥有。

Root沿原SourceMarketProcess创建描述符，pythonw/entry来自安装收据，control_root为新的E盘受控目录。SMP主配置增加可选daily_update固定引用，原监听/认证合同保持。下面是虚构路径示意，SHA在准备时计算：

```json
{
  "schema": "guanheng.source-market-service.v1",
  "source_configuration": {"path": "E:/example/data/read.json", "sha256": "<read-sha256>"},
  "daily_update": {"path": "E:/example/data/daily.json", "sha256": "<daily-sha256>"},
  "listen": {"host": "127.0.0.1", "port": 18100},
  "token_env": "EXAMPLE_MARKET_TOKEN",
  "socket_timeout": 6
}
```

read.json使用source-market-current，current_file与daily.template.publication_directory/CURRENT.json相同。ready要求生产者实际取得租约；HTTP和生产各用自己的线程/资源。日常09:00起处理最近闭合交易日，15:30前处理前日最近交易日，15:30后沿同一owner自动推进当日；周末/休市沿官方日历回看，同日已成功且无需接续时直接复用。日期选择与原公开输入库共用北京时间闭合规则，实际来源可获性另行核对；显式手动as-of另行选择日期。未配置daily_update时沿原读服务。

停止使用原SMP stop.json及原单调截止，父WT owner确认进程树、EOF和线程关闭。数据线程独有closed证明其owner退出，SMP成功closed还要求Reader及数据线程均关闭。父Job处理不可协作硬阻塞，Source/QMT外部业务责任继续保持原身份。

## 验收与回退

安装后检查沪深北股票、ETF、指数的实际首尾、数值、单位和价格口径；单/批量绑定同一snapshot_id。新价只从同一WT入口读取，原生归档及历史来源分别保持。观衡采用新wt_breadth/wt_t2108来源配置后，生成最新可用交易日七项结果，并通过独立只读API逐项核同同一观察快照。

程序更新先部署新目录，保留旧程序、原数据和运行描述符。数据回退沿原GenerationPublisher锁和expected_current_sha256采用已保留不可变配置；重新启动原入口后核对其数据日期、Source版本和实际查询。程序切换、数据采用和生产发布分别登记。来源价格冲突、未知单位/因子、覆盖不足和未执行自然新日的范围沿交付HANDOFF明确记录。

同业务来源的Host正常重启后，日线批读沿原capture接续。原BINDING及slots保留，后续新批次通过原SDK认证当前通信代并在read-generations留存metadata；已有未知批次继续原ID。来源路由、权限、profile或额度变化保持明确失败。RetainedReadBindingChanged应先核实际变化字段及当前运行代，按[批读接续规则](../architecture/adr/0027-daily-batch-transport-generations.md)处理，保留当前成功日线和原请求。


全类别接续由可选price_scope启用，同一publication锁覆盖Source名册、缓存准备、Native落盘和发布。baseline_reference只保留已知证券；reference_connection为空或缺少新Source能力时，各组应有数保持未知。价格任务使用独立于指标池的UNIVERSE，保存逐组应有/实际Native覆盖数、真实尾日分布和逐证券缺口原因。新增配置或扩展处理范围使用新的数据任务根，原CONFIGURATION、INDEX、任务和所有来源请求槽保持；publication_directory继续指向同一正式CURRENT。采用之前固定旧任务引用及跨任务保护槽，并先核旧同类owner实际退出；只有新数据owner取得唯一租约后切入读取。配置迁移、完整源端目录资格、原价/前复权和自然新日各自登记。


## 公共辅助事实暂缺时验价

持续服务已有成功CURRENT且启用price_scope后先做价格阶段，无需改日期、额外名单或人工启动。检查数据INDEX目标日的price_state/price_result与控制目录status.last_price_success，再按原结果的counts/securities核实际尾日、Source分母及缺口原因。auxiliary_observation_date仍为最后真实公共日事实日期，不能据此判定新价格未更新；指标池和辅助事实晚到时沿原任务自动补成完整定日快照。

程序采用需要同时包含daily_price_refresh、daily_data_service、daily_price_scope/update、daily_data_inputs、daily_input_recovery和原公共事实窗口重试接缝。安装/构建声明必须纳入新模块；沿同配置、同数据根、同publication及全部原slot恢复。SourceMarket当前日展示包装由独立入口拥有，与价格写入线程分别发布和关闭。

## Native读取的受控临时目录

部署Source角色时从原受控环境副本保留全部原值，显式追加TEMP和TMP，并先创建对应物理D/E目录。环境文件及service descriptor按原SHA绑定，原ServiceController正常关闭/采用后复核实际业务查询。项目正式临时根使用D盘，C盘保留系统用途。

服务ready仅证明生命周期就绪。验收必须从正式HTTP读取实际单/批历史、量纲及所选策略消费者，并核同CURRENT身份。若多个证券同时出现固定Native读取错误，核启动环境和临时目录存在性，再检查原文件/Reader；原进程继承值缺证时保留未知，不能由配置缺省推断某个盘符故障。
