# 上游共振原版独立还原

类型：功能规格。状态：accepted / pending-verification（离线实现及算法对照通过，完整历史数据待验）。前缀 ORR。范围：用户2026-11-06授权核对并还原 OrangesHuang/Resonance，现有策略保持独立。

## ORR-01 固定原版与隔离

原版指所给仓库 main 的固定提交 `351f9d58152e10efd2447c997b8ee4db66b5ac6a`，算法版本采用其 `stable` 路由；最早提交、beta、band分别是其他身份。独立研究策略标识为 `resonance-original-351f9d5-stable`。计算实现位于 `apps/guanheng/strategy_original/`，提供离线冻结与回放，输出保持 `execution_qualified=false`；后继只读页面接入沿ORR-06。现用策略、配置、默认选择、服务及账户保持各自身份。

直接校验并运行用户给定上游的纯计算源码，避免再次翻译复杂状态机造成漂移。来源文件逐一绑定SHA-256，在独立临时目录复制后由隔离子进程装载；完整原件保留本地研究目录，发行包保存自有接缝和来源清单。上游未声明许可证，当前范围为本地核对与运行，尚未形成上游源码再发行制品。

## ORR-02 数据冻结与准入

支持显式原SQLite路径只读事务导出 `etf_daily/market_turnover/margin_trading/trade_calendar` 的业务字段，或读取同schema冻结JSON。实际发布时刻、复权来源和版本若原库缺失，输出记录未知；数据库更新时间不能代替历史首次可知时间。输入包含来源、数据性质和单位声明，数值有限、日期严格升序且唯一，证券使用原六位代码；589680与589000保持不同证券身份。

输入上限32MiB、60000条记录、17只证券；计算由一次有界子进程完成，超时终止并返回失败。输入按完整历史预热，回测日期裁剪用于最终信号/估值；任何数据缺失、日期缺口、预热不足和未覆盖派生核对在报告明示。禁止把缺份额填零或以其他ETF替代。

## ORR-03 原算法与组合

复用上游 `router.compute_trades(version='stable')`、情绪 `enrich_turnover/percentile_series`、五灯 `compute_resonance` 和 `simulator.simulate`。默认九标的沿上游 `portfolio/api.py::ALL_CODES`，588200引用588000、159352引用510300；选择其他原监控证券需要显式代码。五灯与交易状态机分别输出。

原组合按下一交易日收盘成交、新BUY触发全部在仓等权满仓、SELL释放现金且其余仓位保持，原浮点份额和零费用模型保持。原策略统计中的信号收盘收益与组合成交收益分别标识。现有WT回测入口使用不同策略/数量/成交合同；本次离线原版结果与其报告族保持分离。若继续做可交易改进，WT-S01/S05/S06和WT-B01/B02负责调度、状态及撮合，不增加第二套实盘执行或账户账本。

## ORR-04 算法与数据检查

逐字段检查派生价格位置、量比/量概率、份额概率及重算后的方向/综合分数；只在已具备所需历史与输入时比较。原seed与后继recalc语义差异分别报告，不自动覆盖存量事实。上游自身缺陷和回填修订按原行为保存并披露。算法一致性、数据完整性、严格逐时点资格和收益有效性各自说明。

主路径先跑冻结输入→原路由→原组合→独立JSON报告，再覆盖人工可算的边界、原入口差分、源码篡改、未来/重复/错序/非有限输入、缺参考证券、空结果、失败和超时。原始测试、合成数据和真实来源分别记录；没有原作者完整数据库时，原作者收益复现保留为待验。

## ORR-05 QMT/WT真实数据研究输入

用户2026-11-06追加授权核查并获取实际来源后重跑。行情优先WT已发布日线及既有QMT历史读取/准备通道；必要补齐只涉及来源缓存与独立研究目录，活动策略、服务配置和发布CURRENT保持。保留原请求身份、实际回读与原件内容摘要；缓存准备调用返回和实际数据覆盖分别证明。

原价、供应商前复权和复权事件分别保留；指标按交易日期精确匹配ETF与沪深300参考。来源price/volume/amount单位、供应商分析基准日或历史首次可知仍未知时，在研究输入source显式登记假设及未合格状态，目标协议units不单独提升来源资格。已取得的价格预热日期上的份额参与后继第一条派生日的份额计算；未知日期不能补零、前填或用当前总份额代替。

历史ETF份额与市场融资/成交额属于补充事实，现有WT价格bar及股票daily_facts不包含这些业务字段。本次以独立研究适配器连接已核公开来源；生产WT事实接口和持续采集发布属于后继范围。官方股票成交额、原版使用的双指数amount代理各有完整独立身份；缺失官方日期不会由代理隐式补齐。缺份额的九证券实验和份额完整的七证券子集分别记录，证券集合改变不当作同条件绩效比较。

完整回放保持原组合初始现金及持仓推进；2026年或6—11月结果从同次全程净值按前一日权益截取，不重新启动模型/组合。评价起点前若已有原模型持仓而组合从现金开始，报告明确其数量及原API语义。结果沿原次日收盘、零费用模型，继续保持研究诊断及逐时点未合格。

## ORR-06 观衡只读目录与报告导入

用户2026-11-06授权将独立原版策略及已冻结报告接入观衡，并指定正式回测使用WT框架。目录保留master现有WT公开结果动态身份及版本（未知保持None），随后新增 `resonance-original-wt-351f9d5-stable@0.1.0a1`（共振原版·WT回测）和 `resonance-original-351f9d5-stable@0.1.0a1`（共振原版·原组合对照）；当前已核WT发布版本为1.2.2，App不硬编码该版本。两者保留独立身份、报告族和模型；账户、运行状态、配置保存及交易权限继续归现有执行链。

正式WT回测使用 `guanheng.original-native-replay-input.v1 / guanheng.original-native-replay-report.v1`，信号算法仍绑定固定原stable，模型采用原日线OHLC、D日信号后下一交易日首tick、100万元和100份整手。具体执行与数量/费用按[WT模型独立规格](original-native-backtest.md)及每份原件声明，原版组合的次日收盘浮点结果继续作为ORR对照。WT原版validator由 `guanheng_wt_runtime.original_native_contracts` 唯一拥有，App薄适配并复用既有nsh父回收证明、nbw完成归档与CNY绩效/CSV投影；现有retained各族准入及诊断保持。configuration详情仅新族新增original_native元数据（信号算法、来源摘要、执行与历史模型、三项资格），既有native响应保持原合同。WT报告展示继续保留来源、PIT与执行未合格标记，实盘权限单列。

维护CLI `python -m guanheng_app.original_report_import --manifest <manifest> --archive-root <existing-root>` 显式导入，HTTP只读。manifest schema为 `guanheng.original-report-import.v1`，固定字段 `schema,run_id,label,report_path,input_path,source_manifest_path,report_sha256,input_file_sha256,source_manifest_file_sha256`；三个路径均为绝对普通文件。报告/input/算法清单原字节分别核摘要，报告内部input和source_manifest摘要按原canonical JSON核对；固定算法清单语义SHA为 `5c85a8ee3838d3cbcc83158986b223ed3943640cb0b62cb250faded78ca8ad11`。导入复制原件到同一归档owner的独立32位hex运行目录，以 `completed-archive.json` 最后发布，完成证明schema为 `orr-completed-archive-v1`。既有run拒绝覆盖；失败目录保留为未完成，不作为有效报告列入。该完成证明证明已导入原件一致性，不伪造进程、WT安装或原生撮合凭据。

既有 `/v1/ui/backtest/archive` 及 `/archive-summaries` 返回原版条目 `report_family=resonance-original`，通用字段 `run_id,record_count,report_sha256,configuration,scope,receipt_sha256`；原版没有Host命令的owner_id/request_id。configuration沿通用 `label,name,start,end,session_sha256,max_seconds`（原输入摘要、日期窗口首日00:00至尾日23:59、读取上限30秒），不表示可发起回测的配置。原版summary为 `strategy:{id,version},initial_equity:1,unit:normalized-equity,report_family:resonance-original`。

同一run既有configuration/performance/visuals/ledger/records路由按完成证明的原生family分流，原版投影分别使用 `orr-archive-configuration-v1 / orr-performance-v1 / orr-visuals-v1 / orr-ledger-v1 / orr-records-v1 / orr-day-v1`，native既有schema与严格准入保持。每次详情读取复核完成证明、三份原件及内容绑定；读取额度、路径防链接、截止及分页沿归档owner合同。归一化权益不标记人民币，价格单位声明沿原输入并明确来源资格，浮点份额来源为原trade_log的amount/price；TRIM在卖出侧统计且保留action。原trade_log缺逐日完整持仓快照，ledger明确 `positions_available=false,positions=[]`。不从原信号trades_by_code伪造成交。

performance包含固定strategy/algorithm、input与source_manifest摘要、unit、model、data_kind及false资格，metrics为 `initial_equity,last_equity,total_return_pct,observed_max_drawdown_pct,fees`；points为 `[YYYYMMDD,equity]`。收益和回撤按原报告舍入后的每日equity派生，指标含义为观测序列值，原报告汇总继续保存在原件。visuals沿六元 `[date,daily_return_pct,negative_drawdown_pct,buy_count,sell_count,unknown_count]`。ledger按原trade_log顺序，单页至多50，date筛选与offset支持分页；交易字段为 `index,date,signal_date,symbol,side,action,price,quantity,amount,weight_pct,fee,reason`，reason缺失返回空字符串。records按history日期分页，单日返回equity/invested/position_pct及对应原模型交易。原版与native比较返回422，原版同族比较仅按原版归一化合同。

`/archive/{run_id}/signals` 提供独立 `orr-signals-v1`，参数同ledger的 `receipt_sha256,day,offset,limit`。响应字段 `run_id,receipt_sha256,report_sha256,schema,date,total,offset,signals,scope`；signals每项为 `index,date,symbol,action,price,reason`，action仅原BUY/SELL，价格为信号价。按日期、原六位代码、同证券原序号排序后赋全局index；单页50。单日records响应的signals为同schema分页对象，不能以当天组合REFILL/TRIM替代原信号。未知报告族读取该入口返回422。

公开source仅投影描述、对齐、成交额模型、复权基础、historical_available_at与units_qualified，不公开本地source_path或原始输入文件内容；配置详情投影有界数据诊断摘要，完整诊断继续保留原件。报告展示资格不等同完整历史、PIT或执行资格。验证使用已有真实来源冻结报告完成CLI→目录→HTTP→详情/曲线/交易分页主链，再覆盖摘要冲突、损坏、错误family、原件路径及native回归。

## 导航

运行入口和数据格式见[独立包说明](../../apps/guanheng/strategy_original/README.md)，研究记录沿[研究指引](../research/resonance-research-guide.md)，适用[验证规范](../development/verification.md)。具体来源摘录、冻结输入和诊断结果保存在Git忽略的 `research/resonance-20261105/`。
