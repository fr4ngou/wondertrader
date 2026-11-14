# IPO、股东减持与股份回购来源核查

类型：来源研究与样本证据。核查日期：2026-11-14。适用范围：观衡「IPO减持供给压强与科创50折价」。状态：验证了无需账号的单项样本、回购计划关联和公告分页。沪深北历史覆盖和日更资格待验。

## 三项数据的来源与口径

| 输入 | 可复用来源和处理 | 本次验证 |
| --- | --- | --- |
| IPO 募资总额 | 东方财富公开新股报表 `RPTA_APP_IPOAPPLY` 的 `TOTAL_RAISE_FUNDS` 单位为亿元。使用 A 股 IPO 募集总额，按上市日归集。BigQuant `cn_stock_new_share_TS_raw` 和 Tushare `new_share` 可使用 `funds`（亿元）及 `issue_date`（上市日）。`ipo_date` 表示网上发行日。 | 东方财富 688827.SH 返回上市日 2026-11-10、募集总额 7.771246 亿元，与发行人上市公告书中的 77,712.46 万元相同。公告另列扣除发行费后的净额 68,236.18 万元。[东方财富新股数据](https://data.eastmoney.com/xg/xg/default.html) · [发行人上市公告书](https://static.cninfo.com.cn/finalpage/2026-11-09/1225662726.PDF) · [上交所上市日公告](https://www.sse.com.cn/disclosure/announcement/listing/ipo/c/c_20261109_10837163.shtml) · [BigQuant IPO 表](https://bigquant.com/data/datasources/cn_stock_new_share_TS_raw) · [Tushare IPO 文档](https://tushare.pro/document/2?doc_id=123) |
| 重要股东减持金额 | 复用观衡已有的东方财富 Choice `RPT_SHARE_HOLDER_INCREASE` 事件准入、公告日、价格来源和修订。按事件方向累计减持毛额，沿现有规则保留估算、无价、时点冲突和已核除事件。原周图 `shareholder.net.ashare` 发布的是增减持净值，毛额需从同一批已准入明细计算。 | 九州一轨 688485 样本在 2026-08-15 返回一条减持，`CHANGE_NUM=309.9473` 万股、`TRADE_AVERAGE_PRICE=57.4364` 元，折算 178,022,571.0172 元。发行人减持结果公布 3,099,473 股、178,022,551.40 元，19.6172 元差异与平均价舍入一致。Tushare `stk_holdertrade` 提供减持方向、数量、平均价、公告日和进程，可做旁证。[股东原公告](https://static.cninfo.com.cn/finalpage/2026-08-15/1225475327.PDF) · [现行观衡规格](../specs/independent-market-observation.md#obi9-重要股东增减持历史) · [Tushare 股东增减持](https://tushare.pro/document/2?doc_id=175) |
| 上市公司回购金额 | 发行人公告提供按计划的已成交累计额及其截止日。巨潮资讯可公开查询公告记录并下载原公告。东方财富的 `REPURCODE` 可用于交叉核验计划身份和最新金额。 | 呈和科技同一计划的四份相邻执行披露可关联计划号 `688625.SH:2026-036`，总额和差额复核见下文。按公告日形成的是已披露执行额时间序列。月报区间内的实际逐日成交不可由累计额反推。[巨潮资讯公告查询](https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search) · [东方财富回购列表](https://data.eastmoney.com/gphg/hglist.html?market=sh) |

三项汇总统一转换为人民币亿元后计算 20 个交易日均值，分母的 `max(..., 1)` 即采用 1 亿元下限。此单位选择属于观衡口径，EasyK 截图没有披露原底层单位。真正无事件日仅在来源完整查询和分类通过后记零。源缺失、金额口径不明或计划关联有歧义时保留缺口。交易日图可将非交易日公告计入下一交易日，保留原披露日及可核实的发布时刻。公告呈现时点和收盘前可得性分别判断。[EasyK 官方相关回顾](https://easyk.work/articles/weekly-review-2026-03-22#case-title-c6b57a079ef7b072adb3af42)

2025-11-14 至 2026-11-13 的东方财富报表原始响应有 159 条，其中沪深 84 条均有实际募资总额，北交所 75 条的该字段全部为空。WT 首次接入范围为沪深。隔离快照成功读回 2026-10-13 至 2026-11-13 的 24 个交易日、5 个正值和 0 个缺口。2026-11-10 读回 777,124,600 元，只有北交所记录的 2026-11-06 对沪深事实读回 0 元。

同区间的沪深减持估算额通过隔离 WT 接口读回 21 个交易日，11 月 2 日、6 日和 13 日存在价格资格缺口。11 月 9 日读回 600,552,366.8 元，包含 11 月 7 日披露并计入首个后续交易日的记录。隔离接入使用 Choice 报表内的均价或历史参考收盘价，后续可补经 WT 核实的历史行情及公司公告更正。

## 回购计划及历次累计金额实测

沪深交易所规则规定集中竞价股份回购的首次、月度及一定比例变化等进展披露，公告包括已回购股数、最高和最低价格、实际支付金额。源文件具有公告编号及回购方案引用，可用「证券市场代码＋原始方案公告号」关联同计划。方案调整、价格上限变化和延长实施期沿明确原计划引用处理。公告平台 `announcementId` 标识单份文件，不能替代计划身份。同公司有多个计划、一个公告引用多个计划或原编号无法确认时，按具体语段核验，无法唯一归属则单列待核。区间差额按同计划累计额计算，重复金额贡献零，回落须核实更正或身份错误。同公司并行启动方案已有 [三环集团 2026 年员工持股计划披露](https://static.cninfo.com.cn/finalpage/2026-08-28/1225530757.PDF) 实例，同一方案调整已有 [威迈斯公告](https://static.cninfo.com.cn/finalpage/2026-09-08/1225551697.PDF) 实例。[上交所第 7 号指引](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/mainipo/c/c_20250516_10779134.shtml) · [深交所第 9 号指引](https://docs.static.szse.cn/www/lawrules/rule/stock/W020250327585488391328.pdf)

呈和科技原方案于 2026-07-21 披露，原公告 `2026-036`，拟用资金 1.00–1.50 亿元。下表四份公告引用同一计划。金额采用正文精确到分的实际成交金额，均不含费用。四笔公开披露的差额合计 120,019,984.92 元，与完成公告相等。直接累加四份公告的累计金额会得到 271,676,535.82 元。[原方案](https://static.cninfo.com.cn/finalpage/2026-07-21/1225433672.PDF)

| 公告日与原件 | 截止日 | 累计回购金额（元） | 相邻披露增量（元） |
| --- | --- | ---: | ---: |
| [2026-07-23 首次，2026-040](https://static.cninfo.com.cn/finalpage/2026-07-23/1225437350.PDF) | 2026-07-22 | 6,539,005.94 | 6,539,005.94 |
| [2026-08-04 进展，2026-043](https://static.cninfo.com.cn/finalpage/2026-08-04/1225454859.PDF) | 2026-07-31 | 48,226,931.38 | 41,687,925.44 |
| [2026-09-02 进展，2026-049](https://static.cninfo.com.cn/finalpage/2026-09-02/1225541704.PDF) | 2026-08-31 | 96,890,613.58 | 48,663,682.20 |
| [2026-09-09 完成，2026-052](https://static.cninfo.com.cn/finalpage/2026-09-09/1225554444.PDF) | 2026-09-07 | 120,019,984.92 | 23,129,371.34 |

### 无需账号的复查方法

- 巨潮资讯页面使用 `POST /new/hisAnnouncement/query` 读取公告索引。表单含 `pageNum=1&pageSize=30&column=sse&tabName=fulltext&stock=688625,gfbj0838731&seDate=2026-07-20~2026-09-10`。使用公告搜索页 Referer 和 `X-Requested-With: XMLHttpRequest`。结果含 `secCode`、`orgId`、`announcementId`、`announcementTitle`、`announcementTime` 和 `adjunctUrl`。按 `https://static.cninfo.com.cn/` 解析附件相对路径。公告索引没有结构化计划号与金额，从原件识别。8 月 4 日附件本次直接读取 HTTP 200，正文金额也可核对发行人在 [上海证券报刊登的原公告](https://paper.cnstock.com/html/2026-08/04/content_2251641.htm)。
- 全市场候选用同一公告查询，留空 `stock` 并设 `searchkey=回购`、`seDate=2026-11-02~2026-11-02`。实测页长 30 的四页分别返回 30、30、30、11 条，`hasMore` 在第 4 页为假，去重后共有 101 个公告 ID，与 `totalAnnouncement=101` 相等。该接口返回的 `totalpages` 是 3，`column=sse` 和 `column=szse` 均含沪深记录。枚举依赖实际页内容、`hasMore` 和总数校核，市场范围另按证券身份校验。文本筛选需要核除限制性股票回购注销、非市场过户、贷款承诺和仅陈述预算的公告。
- 东方财富 [回购列表脚本](https://data.eastmoney.com/newstatic/js/gphg/hglist.js) 使用 `RPTA_WEB_GETHGLIST_NEW`。公开 GET `/api/data/v1/get` 以 `(SECUCODE="688625.SH")` 查询，实测两个计划 `10754` 和 `16230`。`(REPURCODE="16230")` 只有一条，`DIM_DATE=2026-07-21`、`NOTICEDATE=2026-09-09`、`REPURAMOUNT=120019984.92`。追加 `(NOTICEDATE<='2026-09-01')` 返回空，尽管 7 月 23 日、8 月 4 日已有正式披露。这个接口已证实可用于该计划最新状态校验，历次回购增量依靠公告原件重建。持续采集的后续快照可辅助核验，在采集前已经被覆盖的状态仍需从公告补齐。[东财源页](https://data.eastmoney.com/gphg/hglist.html?market=sh)

## BigQuant 回购与公告表的资格

- [股票回购 `cn_stock_repurchase_te_raw`](https://bigquant.com/data/datasources/cn_stock_repurchase_te_raw) 的公开字段是 `instrument`、`ann_date`、`end_date`、`exp_date`、`proc`、`vol`、`amount`、`high_limit`、`low_limit`。目录列出的最近更新时间为 2024-08-02，公开字段无计划键，金额只描述为「回购金额」，缺少计划金额和实际累计额的区分。Tushare [`repurchase`](https://tushare.pro/document/2?doc_id=124) 的公开字段也缺少计划键。两表可作候选线索，按股票代码或截止日直接累计会把进展和结束公告重复计入，也可能错并两项计划。
- [股东增减持与解禁公告 `cn_announcement_share_supply`](https://bigquant.com/data/datasources/cn_announcement_share_supply) 公开结构含 `title`、`publish_date`、`content`、`date`、`instrument`。`content` 是 PDF 解析块，页面提示可能有同一公告重复和漏解析，所列起始日期与正文覆盖说明不一致。该主题表适合辅助找减持原文，回购计划键或结构化累计金额需自行提取。其文档指向 `cn_company_announcement_content` 母表，本次未获得该表的公开字段契约并未用账号查询确认。`cn_stock_shareholder_change` 提供股东户数及户均数据，数据粒度与股东实际减持不同。[股东变化表](https://bigquant.com/data/datasources/cn_stock_shareholder_change) · [既有 BigQuant SDK 实测](2026-11-09-bigquant-data-source.md)

当前可重复证据支持从公告构造计划身份和累计差额。采用前还需核验历史窗口计划链覆盖、沪深北各交易所真实样本、并行计划与更正分类，以及发行人公告和供应商表的覆盖边界。已披露增量和真实逐日成交是两个不同序列。

补采重放确认，广东明珠和广深铁路的公告同时披露月内金额及截至具体日期的累计金额。解析按明确截止日选择累计实付额，复核分别为 65,216,277.12 元及 89,993,363 元，并识别真兰仪表和派能科技正文的未执行零额。永茂泰与华源控股原件也通过金额提取，出售库存回购股份的公告从执行候选中排除。同一截止日金额冲突仍保留缺口，零额转首次实际回购沿同计划差分。以修正后的 WT 接口重查 11 月 6 日至 13 日，六个交易日仍均有缺口，五日缺已确认的原方案身份，一日存在执行公告歧义。回购曲线仍需完整日覆盖。隔离回读见 `build/observation-buyback-refs-v2-qa/history-cumulative-results.json`。

后续重放核实四个原方案或报告书编号：金诚信 `2026-086`、涛涛车业 `2026-050`、锋龙股份 `2026-071` 和星辉环材 `2026-051`。其中金诚信的索引和 PDF 分别使用证券简称及公司全称，锋龙股份将多个标题和等量公告编号顺序列在一起。WT 将同一证券、同日索引与原 PDF 的方案标题核对后取文件编号。标题和编号的并列关系缺项时保留不确定性。按新版重查同一六日，仍无完整市场汇总，三日方案身份待核，三日执行公告有歧义。结果见 `build/observation-buyback-refs-v2-qa/history-proposal-final-results.json`。

公告内的方案与报告书可以指向同一计划。按同一证券、同一语句中唯一且明确的并列引用归并后，再对累计实付额差分。锋龙股份、华源控股、广深铁路和真兰仪表四份公告原件确认了对应关系。测试覆盖仅引用报告书的前序公告和后续方案公告连续差分，以及一份报告书关联多方案时保留缺口。市场补充数据集成测试 93 项通过。隔离 WT 六日重跑仍有三日方案身份待核、三日执行公告有歧义，见 `build/observation-buyback-refs-v2-qa/history-plan-alias-results.json`。

逐件追踪失败原件后，WT 增加以完整执行区间截止日识别累计额、排除明确含交易费用的金额、换算万元小数至分，以及在正文缺实付额时读取结果表。华润双鹤的合作方药品权益回购从股票回购索引候选排除。金诚信、申科股份、四川双马、豫园股份等五份原件金额复核通过。隔离 WT 通过补充事实接口首次读回 11 月 10 日的完整沪深日汇总 312,573,654.36 元，六日范围其余五日仍有缺口。市场补充数据集成测试 94 项通过。回读见 `build/observation-buyback-refs-v2-qa/history-execution-results.json`。

对引用正文日期的回购公告，WT 优先查同日索引，未匹配时核验下一日的同证券原件。按标题核对后优先采用原方案；只给出期号时，核对明确引用日及原件同年同期标识。弘信电子补得原方案后，WT 快照读回 11 月 13 日沪深已披露执行增量 434,321,493.36 元。11 月 10 日原汇总保持一致，11 月 6、9、11、12 日仍有缺口。三环集团原件确认第四期方案编号为 `2026-72`，同日汇总仍存在执行公告歧义。95 项市场补充数据集成测试通过。隔离回读见 `build/observation-buyback-refs-v2-qa/history-phase-final-results.json`。[三环集团第四期方案](https://static.cninfo.com.cn/finalpage/2026-11-05/1225658392.PDF)

公告引用语句含报纸刊名时，保留同句的发行人披露日供原件核验。明确尚未进入执行期且未回购的披露识别为零。四川双马在同份公告并列本次、前次及两次回购合计，按「本次首次回购至」后的日期选取本次累计实付额。以真实公告补采后，WT 接口新增 11 月 6 日 588,428,185.49 元、11 月 9 日 516,243,256.43 元及 11 月 12 日 29,473,541.99 元。六日覆盖达到五日。11 月 11 日的联合动力首笔公告只给出含交易费用的金额，当前仍保留歧义。98 项市场补充数据集成测试通过。隔离回读见 `build/observation-buyback-refs-v2-qa/history-current-plan-results.json`。

将补采扩大到 10 月 19 日至 11 月 13 日的 20 个交易日。第一批实际读取 379 次，已核五日，另外 15 日分为三日公告识别缺口和十二日超出本轮采集预算。范围及逐日原因见 `build/observation-buyback-refs-v2-qa/history-20-sessions-results.json`。另外独立跑 11 月 11 日的原公告，WT 缺口确认为 `buyback_execution_net_amount_missing`。联合动力公告披露含费总额 5,308,047.97 元，缺同次不含费金额或费用明细，原净成交额口径继续保留。99 项市场补充数据集成测试通过。[联合动力首次回购公告](https://static.cninfo.com.cn/finalpage/2026-11-11/1225667044.PDF)

第二轮续采再次在 11 月 3 日触及采集预算。WT 现保存已经发出请求的预算中断日期，下一轮先访问尚未尝试的日期。同一回购计划的首次公告和进展公告如果同日披露相同累计金额，按一笔核算并保留两份原件；金额冲突仍保留缺口。科大讯飞两份 9 月 1 日原件的累计金额均为 30,021,592 元，重放后 11 月 5 日剩余缺口变为另一公告的原方案引用。集成测试 101 项通过。

结构化来源的下一轮准入应核对同一计划的多次历史进展能否一起返回，以及金额是否累计、是否含费。Tushare `repurchase` 实际查询两个 2026 年区间均返回 `40203`，BigQuant `cn_stock_repurchase_te_raw` 实际查询返回表权限拒绝。米筐 `get_buy_back` 文档列有回购总金额和进程变动日期，富途有 A 股事件进程及回购金额，二者尚缺同一计划历次报告的实测样本。[Tushare 股票回购](https://tushare.pro/document/2?doc_id=124) · [BigQuant 股票回购](https://bigquant.com/data/datasources/cn_stock_repurchase_te_raw) · [米筐股票数据](https://pypi.ricequant.com/doc/rqdata/python/stock-mod) · [富途回购接口](https://openapi.futunn.com/futu-api-doc/quote/get-corporate-actions-buybacks.html)

## 结构化历史样本交叉验证

EasyK 公开回顾确认「IPO减持回购失衡且科创转弱」观察 IPO 与减持供给相对回购对冲，并列科创50表现。公开页面给出事件日期与价格曲线，未列回购输入字段的数据供应商、金额单位、公告归属日或可导出的原始序列。[EasyK 回顾案例](https://easyk.work/articles/weekly-review-2026-03-22#case-title-c6b57a079ef7b072adb3af42)

实际读取五份同花顺金融研究中心以 iFinD 数据发布的历史表，保留 HTML 摘要及提取行。呈和科技 9 月 2 日及 3 日均为 9689.06 万元，9 月 9 日完成为 1.2 亿元，对应发行人原累计额分别为 96,890,613.58 元与 120,019,984.92 元。9 月 2 日和 3 日对应同一次累计披露。金诚信在 10 月 29 日显示 3925.02 万元，11 月 13 日显示 4 亿元，发行人原件分别披露 39,250,230 元和 399,880,100 元的不含费累计额。公开表能找到相邻状态和候选个股，表头没有原计划或公告编号，展示金额经过舍入，当前作为核对线索。原件及五行证据位于 `build/observation-buyback-structured-qa/ifind-public-comparison.json` 同目录。[9 月 2 日表](https://news.10jqka.com.cn/20260902/c679505951.shtml) · [9 月 3 日表](https://news.10jqka.com.cn/20260903/c679542952.shtml) · [9 月 9 日表](https://news.10jqka.com.cn/20260909/c679717866.shtml) · [10 月 29 日表](https://news.10jqka.com.cn/20261029/c681213067.shtml) · [11 月 13 日表](https://news.10jqka.com.cn/20261113/c681774265.shtml)

九章量化文档提供按公告日和市场分区的本地 Parquet 回购公告表，文档主键 `row_hash` 标识单条记录，仍需用样本验证同一方案的关联及金额口径。iFinD 的下一项验证是用授权的终端导出或 API 读回上述证券完整记录，确认是否具备单次公告原始金额和可关联的计划身份。公开日报的证据不足以采用为 WT 主来源。[九章数据文档](https://www.jiuzhangquant.com/support/data-docs) · [iFinD 接口取数说明](https://quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/deploy.html)

进一步实读东方财富 Choice 公共接口六次。金诚信计划 `16731` 的两列 `REPURAMOUNT` 和 `ZJJE` 均为 399,998,500 元，恰为公告含费总额，原公告另列不含费累计成交额 399,880,100 元。联合动力计划 `16727` 两列均为原公告披露的含费总额 5,308,047.97 元。把金诚信的筛选日回拨至完成公告前一日，2026 年该计划整体消失，只剩 2019 年旧计划。呈和科技回拨也出现同一现象。由此确认公开表可用作计划身份及最新披露金额的对照，缺历史版本且金额费用口径随公告。原始响应、请求与摘要存于 `build/observation-buyback-structured-qa/eastmoney-progress-comparison.json` 同目录。[东方财富回购数据](https://data.eastmoney.com/gphg/hglist.html) · [金诚信完成公告](https://static.cninfo.com.cn/finalpage/2026-11-13/1225668201.PDF) · [联合动力首次回购公告](https://static.cninfo.com.cn/finalpage/2026-11-11/1225667044.PDF)

证监会统计指引另有「上市公司股份回购金额」，取实施结果公告日确认整笔完成额。它可以作为独立的研究口径，和本看板按各次披露计执行增量的日期分布不同。EasyK 公开页未交代使用何种日期口径，不能由指标名称推定。[证券期货业统计指标标准指引](https://www.szse.cn/www/lawrules/csrcrules/notice/P020250519343090326948.pdf)

第三轮续采以原任务进度恢复，从 2026-10-19 至 11-13 的 20 个交易日经隔离 WT HTTP 核回五个有效金额和十五个缺口。此前 11 个“预算或来源缺口”均已取得具体核验结果。当前十四日存在执行标题、金额、方案身份或披露顺序歧义，11 月 3 日仍触及字节预算。已接纳五日的金额保持一致。采集现在也在确实发出请求后保存超时日期，后继优先核对从未尝试日期。102 项 WT 补充事实测试通过。回读文件 `build/observation-buyback-refs-v2-qa/history-20-sessions-batch3-results.json` 的 SHA256 为 `591ba77b3f8318a805b785e5ad42b2689633cd79ef9297f2a8f596fbc991491f`。

单独重查 11 月 5 日时，49 次读取获得 32 份可解析执行公告及 4 份待核公告（含前序基线）。申通快递与唐源电气的定日累计执行段分别使用「回购总金额」和「资金发生总额」。扩展定日执行段金额识别后，两份原件分别读回不含费累计额 338,696,500 元和 13,406,996 元，原计划编号分别为 `2026-057` 和 `2026-043`。定日文字须先给出实际回购股数，拟回购金额和含费金额仍不纳入。两个单项累计额还需经各自计划差分和全市场覆盖校验才能进入日汇总。[申通快递进展公告](https://static.cninfo.com.cn/finalpage/2026-11-05/1225657466.PDF) · [唐源电气进展公告](https://static.cninfo.com.cn/finalpage/2026-11-03/1225655411.PDF)

米筐公开范例以首次信息发布日期为索引，同一证券同日返回协议回购和集中竞价两条已完成事件，说明证券加日期不足以唯一关联计划。公开字段有进程变动日、公告时间戳和回购总金额，范例尚无同一计划历次执行进展。富途 A 股字段有预案公告日、股份变动日、支付日和回购金额，逐日回购示例仅覆盖港股。两者在拿到覆盖期内同计划多期原始明细并核对费用口径后，方可验证为 WT 备用来源。[米筐回购文档](https://www.ricequant.com/doc/rqdata/python/stock-mod.html#get-buy-back-%E8%8E%B7%E5%8F%96%E5%9B%9E%E8%B4%AD%E6%95%B0%E6%8D%AE) · [富途回购文档](https://openapi.futunn.com/futu-api-doc/quote/get-corporate-actions-buybacks.html)
