# WT市场补充事实采集与历史补齐

类型：功能规格。状态：accepted / in-progress。前缀 MSF。用户2026-11-06要求WT采集开源原版所需数据并补历史，随后明确QMT优先。现有策略保持；生产切换另验。

## MSF-01 唯一owner与QMT优先

复用WT-D01/D03/D09/D11的数据接入、日线及来源准备扩展，按ADR-0025由既有统一daily data owner采集补充事实。WT原bar没有ETF每日份额/市场融资字段，股票daily_facts保持原八字段。新增独立事实合同及目录；不另起调度、账户账本、撮合或观察服务采集链。

每轮先核现已配对QMT只读binding及开放operation。当前本机只开放market.market_data和market.divid_factors，份额和全市场融资记录为`not_exposed_by_bound_profile`；这不证明供应商产品不支持。已核QMT能力优先；数据权限、字段单位/历史范围未经实证的financial/PCF/etfstatistics不能冒充每日总份额。未来开放新QMT事实入口需另作原协议版本与实机验证。

外部源仅按配置external_fallback显式允许，在保存QMT不可提供该事实的本轮证据后使用。网络未知/超时不能当成NotSupported自动换源。个人信用账户、当前总股本和申赎篮子不参与市场历史替代。

## MSF-02 配置和采集

原daily-data-service.v1的inputs增加可选supplement_facts；省略保持原流程。配置为schema=`guanheng.market-supplement-plan.v1`，targets为最多64项`{metric,symbol,from}`，同metric/symbol唯一；from是显式要求覆盖起点YYYY-MM-DD，实际截止为本轮闭合日。每个ETF可用已核上市资料设置自身起点，未知上市时间不自动推断为无缺失。

`index_turnover` 的目标范围为 `SSE.932000`。WT 日线的已核元成交额在读取时优先；启用 `external_fallback` 中的 `BigQuant` 后，由原补充事实任务批量查询 `cn_stock_index_bar1d` 的 `932000.CSI`，只归档日历选中、标的匹配且金额为正的交易日。补充目录保存原查询结果及逐行谱系，现有目录复用和缺口重试适用。观察通过同一快照的补充事实补足单位未核或缺量的日线。其余补充指标查询继续返回原有指标的能力字段。

启用 `CSI` 时，`index_turnover` 仍缺失的日期允许用中证指数定日行情原件补齐。验证指数代码、交易日及唯一记录，`tradingValue` 从亿元换算为元，保存中证指数来源及原件。已归档同日 BigQuant 成交额继续复用。

`index_free_float_market_cap` 的目标为 `SSE.000300`，外部来源为 `CSI`。采集中证指数沪深300日报，核首页日期、规模指数表头、唯一 000300 行及两处收盘点位。日报市值列表只列字段名，换算采用同发布方[沪深300指数单张](https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/indices/detail/files/zh_CN/000300factsheet.pdf)公开的市值亿元口径。日报实测 2026-10-29、2026-11-12、2026-11-13 的自由流通市值分别为 230026、230145、228573 亿元。原 PDF 进入原件库，缺报、表结构或显式单位不符保留缺口。该事实可作为四只沪深300 ETF 市值占比的分母。

`margin_purchase` 沿 `CN.MARGIN_REPORT` 的原供应商覆盖，从东方财富综合统计 `RPTA_WEB_MARGIN_DAILYTRADE` 读取 `FIN_BUY_AMT`，原亿单位转人民币元。余额继续使用 `margin_balance`。2026-11-12 实取 173379043429 元，2026-11-13 当次查询为待披露。旧指标查询继续返回原支持范围内的能力字段。

「两融」看板沿东方财富历史汇总 `RPTA_RZRQ_LSHJ` 取得原有六个字段。WT 在 `CN.MARGIN_DAILY_SUMMARY` 保存融资余额 `margin_summary_fin_balance`、融资买入额 `margin_summary_fin_buy`、供应商披露的融资净买入额 `margin_summary_fin_net_reported`、融资偿还额 `margin_summary_fin_repay`、融券余额 `margin_summary_short_balance` 和两融余额 `margin_summary_total_balance`。六项为人民币元，净买入额允许负数。报告范围沿原汇总表，历史首次可知时间保持未知。`CN.MARGIN_REPORT` 继续代表综合统计表，两个报表各有独立事实身份。

历史汇总的可选同源备用为东方财富公开分市场融资融券汇总。显式准入 `datapc.eastmoney.com` 后，WT 仅对原汇总缺日或缺字段尝试沪、深、京三份同日结果。每份需匹配市场身份、日期和人民币元字段，三个值均有效时才求和并归档三份原件。先提交原汇总已核字段，分市场结果逐日提交。单市场日缺失后仅重取该市场，来源运输失败或预算耗尽后停止本轮地域请求。分市场结果适用 `CN.MARGIN_DAILY_SUMMARY` 的六项字段，综合统计表仍独立取数。2026-11-02 至 11-12 的九个开市日中，六项合计均与原历史汇总逐值相等。

申万 A 指 `SW.801003` 采用申万宏源研究公开市场表征日表。一批请求共同读取市盈率、市净率、收盘点位、成交额原值及换手率，逐日逐字段附原页摘要。市盈率、市净率保留倍数，收盘保留指数点，换手率为百分数，成交额保留供应商原值及未知单位。观衡从同版 WT 补充目录读取上述五项，分别用于原股债差、加权 PB 和现有研究计算。覆盖由 WT 已存字段核对，旧图历史继续可用。

同一范围内一次获取这六个字段，检查实际交易日、分页完整性和日期唯一性，保留响应原件。独立字段缺失时保留对应事实缺口。同一任务恢复只补缺项；观衡负责亿元展示及原指标派生，从同一 WT 快照核对六个字段的覆盖。WT 的原生日线及证券资料接口不表达这组外部报表金额，复用现有补充事实的归档、查询和恢复机制。

融资买入额历史缺口按最多 366 个自然日发起区间查询。WT 校验报表日期、分页和重复记录，仅接纳官方交易日历目标日，并归档区间原响应。尚未披露的行留缺口，可在后续任务重试。任务优先采集最新交易日。

常驻日更为所配置的融资、IPO、减持、回购、国债收益率及申万报表先开独立公开采集任务。该任务使用原公开采集配置和补充事实请求份额建立独立预算，与日更共用本轮绝对截止。它在原任务补充日志中记录已校验结果和报表阶段缺因。原数据线程在合并前等待唯一日志写者退出，用原行情绑定和统一发布校验生成完整目录。行情超时仍保留已采报表原件供原任务续跑。独立采集阶段不申请行情连接或发布租约。

`ipo_gross_proceeds` 的范围为 `CN.SH_SZ`。东方财富新股报表 `RPTA_APP_IPOAPPLY` 以实际上市日归集 `TOTAL_RAISE_FUNDS`，从亿元换算到人民币元。只接纳沪深 A 股。接口查询在已闭合交易日范围内，完整查询无沪深上市记录的交易日为已观察零。已有沪深上市记录但实际募资字段缺失时，该日留缺口。按区间归档原响应，历史首次可知时间保持未知。北交所另行核对来源覆盖和募资口径。

`shareholder_reduction_gross` 为 `CN.SH_SZ` 范围内的 Choice 已披露重要股东减持估算额。沿 `RPT_SHARE_HOLDER_INCREASE` 的二级市场和大宗交易范围，只累计减持方向的数量，按披露日归入当日或其后首个交易日。数量单位万股，优先使用报表成交均价，缺失时使用报表历史参考收盘价。所有原始分页经数量和复合身份核验后才接纳。交易日期晚于披露日或两类价格均缺失时，归属交易日保留缺口。完整报表无沪深减持的交易日记录零。历史当日收盘可得性未知，研究读回使用事后完整披露历史。

`buyback_execution_disclosed` 为 `CN.SH_SZ` 范围内的股份回购披露增量，来源 `CNINFO`。核准公告索引分页、发行人证券及相同方案引用。可识别证券简称省略、公告编码以及括号年份的单证券页眉，按同一编号身份核对有无分隔符，保留序号前导零。混列多只证券或执行公告引用自身为方案时仍保留缺口。较晚进展接续前序已核累计金额，首笔须有明确首次实施披露。累计金额回落、同日无法排序、前序不明及执行候选无法核准时，对应交易日保留缺口。同一截止日优先采用明确不含交易费用的累计成交金额。仅有含费金额时采用公告披露值，差分按同一回购方案执行，并在源证据中标注当前及前序金额的费用口径。累计回落或无法核对的冲突继续保留缺口。休市日披露计入下一交易日。完整候选索引未出现沪深执行公告的日期值为零，语义限于披露增量。成功行的直接父对象为定日公告证据索引，引用全部相关索引页与 PDF 原件，WT 读回核对两层对象。

执行公告引用方案标题和披露日期但省略编号时，按原证券与巨潮机构组合查询候选日，核标题与原方案 PDF 证券和公告编号，仅接纳唯一方案。证据索引包含补查的页面和方案 PDF。历次累计金额继续按同一方案计算，缺前序时留出独立原因。

回购历史补齐在已核 QMT 能力、当日其他补充事实和中证2000成交额之后，先查询尚未尝试过的最新交易日，再进入其他指标的历史补采。回购历史阶段优先覆盖尚未尝试的旧日，再复核已报缺口，同轮已尝试日期不重复采集。同一任务恢复沿本地持久进度，跨任务沿上一版已发布覆盖及可核验的未完成任务进度。最新日仍按原日更节拍建立；历史缺口与未尝试日期共享原请求预算，缺口保留供应商原因。

ETF份额标准单位为share，市场金额为CNY。官方成交额、双指数代理、指数成交额、指数自由流通市值、融资余额和融资买入额各有独立事实身份。源单位未知时保持unknown。

policy固定qmt_preferred。external_fallback为`SSE/SZSE/Eastmoney/BigQuant/CSI/CNINFO/ChinaBond`的显式子集。启用BigQuant时，`bigquant.bigquant_python`指定隔离解释器的绝对路径，`bigquant.timeout_seconds`指定1至60秒的单次查询截止。required为bool。required=true时缺事实在UPDATE固定前保持pending并保留原件/缺口，同任务恢复只补缺。required=false允许发布带gaps的不完整目录。已发布partial在下一个北京时间自然日09:00后最多创建一次同市场日修订，仍沿原INDEX/REQUEST及失败重试节拍。新的闭合交易日继续补既往要求窗口的缺项。

`government_bond_10y_yield/CN.GOV10Y` 读取中债历史收益率表的国债曲线 10 年期列。来源为 `ChinaBond`，单位为 `pct`，数值以百分数归档并保留原 HTML 摘要。WT 按同一任务的实际闭合交易日核对，缺日留在目录。观察侧仅消费同版本补充目录，并继续使用原股债差和债券仓位公式。

plan可选`max_requests`为1..512的整数，省略沿原公共总额度。该值分配本阶段单轮HTTP＋SDK份额，所有实际重试/请求仍从同一CollectionBudget扣账；进入阶段临时收紧max_requests，退出恢复原总上限，字节、总D、单请求D及取消保持。额度用尽登记gaps，required=false仍可发布已取得部分；它不取消后继轮次。原定日股票事实先取得，补充最新日优先，再用余量补较早缺口。正式有限日更可显式配置24次，历史补齐与来源资格分别登记。

采集复用原raw_store ContentStore和原Fetcher预算、一次总deadline/cancelled；新QMT请求复用原RetainedReadClient及持久slot。成功原件按SHA存证，任务先保存QMT准入与采集状态；失败原件和已成功任务保持，恢复不重新发未知QMT请求。按官方日历规划最多2000个交易日、60000个目标事实单元；采集串行、单轮公共请求及响应额度沿调用者预算。先复用上一成功目录，保留旧行原件和收到时刻，只取真实缺口。

每个target.from与本轮截止须落在同一官方日历coverage_start/end内，超界明确拒绝；开市日序列与覆盖日界一同固定在采集请求，避免早期整段裁剪后误报complete。覆盖日界中的周末/休市起点正常准入，实际单元仍按开市日生成。

HTTP远端响应协议中断由原Fetcher分类为source_remote_protocol，沿同预算交采集owner留缺口，协议失败不自动重试。COVERAGE先保留本轮成功/缺口，原取消及总截止随后优先决定终态；required等待不得覆盖停止/超时。

### 持续日更与跨日恢复

新增事实继续由当前统一日线owner串行执行，保留已发行的价格先行、原INDEX修订、旧请求/slot续核及北京时间15:30闭合窗口；09:00控制新目标首次建立及次自然日partial刷新，已登记的未完成任务仍沿原身份恢复。程序更新以已发行owner的接续行为为基线，补充目录与价格、日事实共同绑定快照。

新日先复用已发布补充目录及同owner此前未发布任务中已验证成功的行，保留原件SHA、received_at及available_at；未完成的QMT槽仍由原读取责任续核。只补要求窗口真实缺项，前日份额或融资晚到时可在新日要求窗口中补齐，缺失不前填、不写零。初始历史seed必须与本次ContentStore为同一原件库；新配置/新任务根的采用及数据迁移由运行方显式执行。

初始seed沿`template.supplement_facts={path,sha256}`原接缝，源目录raw_store须与daily.raw_store相同；已有CURRENT带补充目录后优先继承已发布版本。配置/任务根迁移时，`inputs.previous_requests`仅引用实际存在的完整REQUEST；可选`inputs.previous_inputs`为最多366个唯一固定`{path,sha256}`的旧INPUTS.json描述符，原input recovery从这些原根续核已尝试slot。完整REQUEST在输入准备结束后才物化，其缺失不代表未派发Source。旧INDEX未物化意向、旧原件及责任保留审计，不构造不存在的REQUEST，不借恢复补发原未尝试槽。

QMT双指数代理按实际缺失日期及现行profile的行数/自然日上限分块，首次请求前固定分块日期和参数。每块/证券拥有原持久slot；部分行落盘后恢复不得缩窄或改变已派发请求。上一日成功值已缓存时，新轮只请求新增缺日。metadata、未知请求和来源故障仍沿原状态，不将unknown归类为NotSupported。公共定日事实沿有限重试时间窗重新获得尝试资格，完整原回执保持；常驻owner的有限重试计数不得永久取消后续日更。

## MSF-03 事实目录与查询

目录schema=`guanheng.market-supplement-catalog.v1`，字段：

| 字段 | 合同 |
|---|---|
| schema | 固定目录协议 |
| raw_store | 原ContentStore本地绝对根；查询响应不输出此路径 |
| targets | 本轮metric/symbol/from要求，最多64项 |
| dates | 本轮显式交易日期，升序唯一，最多2000日 |
| policy | qmt_preferred |
| qmt_evidence | 已核当前binding/profile的原件SHA及事实接缝决策，凭据不入目录 |
| rows | 最多60000条标准事实，按date/metric/symbol唯一升序 |
| gaps | 未取得的目标单元及固定reason，不能补0/前填 |
| complete | 精确表示请求目标单元全部有值，不等于单位/PIT合格 |

每row包含`date/symbol/metric/value/unit/source/source_sha256/received_at/available_at`。value为有限非负十进制字符串，原精度与缩放明确；unit为share、CNY或unknown，source为固定来源标识（QMT/SSE/SZSE/SSE+SZSE/Eastmoney/BigQuant）。source_sha256绑定`guanheng.supplement-source-proof.v1`派生清单，包含该行date/symbol/metric/value/unit/source及1..4个parents原件SHA。官方两市合计保留两个原件；QMT双指数代理同样保留两份原回执。发布前验证整个目录的能力证据、逐行清单及浅层原件闭包，查询时再核当前页。received_at是本次实际取得UTC带时区时刻，available_at历史首次可知未知为null。每gap是`{date,symbol,metric,reason}`。目录文件最多32MiB，固定SHA，读取不触发采集。

东方财富原融资表的精确日期查询若返回已核空结果协议 `success=false, code=9201, result=null`，登记 `source_record_missing`；这表示该次查询没有目标日记录，不作为表结构损坏或零融资余额。未知错误码、缺字段和其它异常结构继续登记 `source_schema_invalid`。最新可见日期、当日未取得和网络失败分别保留；不根据请求日期前填发布值。

snapshot配置增加可选supplement_facts descriptor={path,sha256}；摘要进入provenance.supplement_facts_sha256并参与snapshot_id。源目录、目录内容、snapshot身份同时准入，未配置不改变旧身份。创建线程拥有store及关闭，不增加HTTP写入口。

快照查询采用显式投影协商：`market.source-snapshot-query` 的 request 为 `{date, include_supplement?: boolean}`。省略或 false 返回旧 v1 可见投影，只从 provenance 移除 `supplement_facts_sha256`，按该投影完整正文重新计算自己的合法 snapshot_id；磁盘完整快照与原完整 ID 保持。true 返回完整原快照，SDK 0.20 的 source_market_snapshot_query 默认发送 true。旧无补充快照两种请求原样返回原身份，未知字段及非 boolean 明确拒绝。

原日线、批读、定日事实和证券查询同时准入本代完整 ID 与旧投影 ID，响应 source_snapshot_id 精确回显请求 ID。原 generation 加载核验显式请求完整投影。独立补充查询只接受完整 ID；旧投影 ID 返回 Unavailable，外来 ID 返回 Conflict。同一旧投影在补充目录变动后可保持身份，它不指认任何补充事实；完整 ID 继续绑定补充目录，跨完整快照禁止混读。原服务默认 wire 对旧严格 SDK 保持兼容，无 token/消费者身份特判。

采用顺序为先发布支持投影协商的数据生产者，再采用默认显式完整投影的 SDK 0.20 消费者；旧数据服务的严格请求合同不认识新增字段。数据原件、生产者采用、SDK普通安装、真实消费链分别验收。

HTTP action=`market.source-supplement-query`，路径`/api/market/v1/source-supplement/query`。request固定`{snapshot_id,metric,symbols,from,to,offset,limit}`，symbols为1..64唯一升序，日期ISO、offset为0..60000、limit为1..2000。响应data包含`schema=guanheng.market-supplement-query.v1/source_snapshot_id/source_sha256/rows/gaps/selection/qmt_evidence`。selection为`{offset,limit,total,next_offset}`，total统计匹配rows+gaps，统一按date/metric/symbol分页，next_offset末页null。空匹配返回Ok空；未装配NotSupported、snapshot不符Conflict、原件损坏IoError。SDK与HTTP共用唯一validator。

## MSF-04 源口径与验证

SSE份额按STAT_DATE精确匹配、TOT_VOL万份×10000为份。请求第1页时，来源确认总记录、总页数均为0且结果为空，登记该日份额缺口为`source_record_missing`，保留原件；分页元数据与结果矛盾时保留分页错误。SZSE采用已实证可用的官方HTTP ShowReport XLSX，严格四表头日期/基金代码/基金简称/基金规模(份)，单位份直接保存。基金代码去掉首尾 ASCII 空格后，按六位数字、全表唯一和目标代码校验；日期沿原值精确核对。旧HTTPS JSON current_size万份合同保留在历史证据，生产不混用倍数。XLSX最多64成员、总解压16MiB、20000数据行；inline/shared及数字单元统一处理，拒绝公式、重复、错日、错单位、坏ZIP/XML/Deflate。多日归档导入按相同源合同及固定原件逐日校验，最多150自然日每块，精确目标日历集合准入。

融资默认复用原版RPTA_WEB_MARGIN_DAILYTRADE的FIN_BALANCE（发布方表头亿，转CNY），symbol固定CN.MARGIN_REPORT，报表市场覆盖尚待核；RPTA_RZRQ_LSHJ的RZYE是另一原表，不能混同或拼接。融资余额与总两融/买入额分别表达。官方成交额精确取SSE股票合计和SZSE HTTP 1803 JSON股票（含存托凭证），两市同日均成功才合并。双指数QMT amount代理单列，不填官方缺口。原项目算法/缺陷不复制到生产采集。源协议选择有实际成功和同刻失败对照，失败不扩大成未经实证的整源不可用结论。

主路径为原owner配置→QMT能力证据→缓存优先源采集→缺口计划/恢复→固定目录→同snapshot→实际HTTP/SDK查询，再补人工算式、错单位/错日/分页/重复、缺日、超时/取消/未知QMT恢复、原件损坏/跨快照、关闭及旧配置回归。构建登记新成员及SDK版本，普通安装验证。实际历史来源不齐时登记pending-verification，完整/合成/真实入口/生产资格分别说明。

## 导航

实现和真实证据沿[统一数据模块](../modules/unified-daily-data.md)、[研究指引](../research/resonance-research-guide.md)、[验证规范](../development/verification.md)登记。具体来源/回测及临时验证保留在Git忽略研究目录，公共源码与脱敏测试可追踪。
