# WT统一日线角色安装、更新和回退

类型：运行手册。适用范围：独立WT数据程序、原SMP组合及外部数据根。状态：离线制品、安装及七指标整链验收通过；当前正式入口及回退保留。完整数据/身份要求见[规格](../specs/qmt-source-daily-history.md)，模块资源边界见[说明](../modules/unified-daily-data.md)。

## 构建与离线安装

永久声明`config/unified-daily-data-source.json`固定共享原模块、角色项目、工具、原生身份及基础解释器清单。构建从永久源码生成Core与SDK轮子，沿固定registry收集完整第三方wheel；原件数据和凭据保持在运行数据根。参数均使用受控绝对路径，以下变量表示调用方已核SHA的工具和输入。

```powershell
& $sourcePython -I -B scripts/unified_daily_source.py --work $newBuild --python $sourcePython --backend $flitWheel --wheelhouse $fixedWheels --native-directory $verifiedNative --seconds 600
& $sourcePython -I -B $installer --artifact $artifact --manifest-sha256 $manifestSha --destination $newProgram --python $sourcePython --seconds 600
```

`$newBuild`及`$newProgram`须不存在。安装前核对交付ZIP及ARTIFACT清单SHA；安装器校验所有成员、完整固定CPython文件清单、离线wheel哈希和依赖闭包，再确认永久原模块字节。成功安装产生INSTALLATION.json，记录实际python/pythonw、入口SHA、完整依赖和Native身份。安装操作不启动来源、WT或观衡，不修改外部数据。

固定CPython为3.12.13 x64，原文件Reader/Helper/Storage及Windows依赖沿该次制品资格。失败根及日志保留；后继安装选择另一全新程序目录。Source SDK版本与协议版本分别核对，SDK0.16支持统一日线、批量、快照、定日事实及证券资料。

## 固定外部数据配置

数据配置使用`guanheng.daily-data-service.v1`，详细字段以UDI表为准：directory拥有持久INDEX/任务；raw_store拥有原件和回执；template固定原基准、资料、事实、Native、受保护slot和publication_directory；inputs复用原HPR/批读声明，凭据来自原环境引用。cache_seed和prepared_native只复用日期/股票池/原件身份匹配的完成结果。

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
