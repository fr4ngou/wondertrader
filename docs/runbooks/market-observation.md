# 独立市场观察操作

“市场广度”中的“40期均线上方比例 · A股T2108方法”按含当期的40个实际收盘参考计算。主比例使用合格样本为分母，旁边显示合格数/股票池总数、覆盖率及缺失、过期、不足40期和复权待核；完整市场占比在覆盖不足时留空。“怎么算”给公式，“原始数据”和CSV保留同一版本的数量。合格只表示本指标当前收盘参考核对通过，历史当时可得时间及原来源整体资格按原证据分别阅读。

该指标的采集使用显式`qmt_t2108`来源，指定绝对`input_manifest`和精确`input_sha256`，datasets固定为`t2108.ashare`，tables固定为`source.t2108_ashare_universe`。v1读原单证券QAS资料，v2读原QAB批次；格式、原件和有限参考核验资料沿[唯一输入规格](../specs/independent-market-observation.md#obi9-r4-t2108原qas回包消费)。仅使用本地已公开原件时allowed_hosts可为空。更新继续原refresh、09点窗口、lease及CAS，观衡不启动Host、调用SDK或补QMT缓存。固定索引只负责所声明批次，未来自动来源发布需维护者提供新的原件身份和对应来源配置；单次导入通过与持续每日来源分别登记。

页面刷新中或失败时，已读图表、数据和说明继续显示，并标注上次读取时间和重试入口。历史导航、原图或期权等子项异常只影响对应部分；当前日期图表仍有数据时可继续查看。切换日期、指标或参数后按新条件读取，成功的空结果显示该范围暂无观察。页首心跳和更新回执表示其记录时间的观察，刷新失败时按提示核查当前运行情况。

类型：中文操作手册。适用：本机独立App，业务范围见[OBI规格](../specs/independent-market-observation.md)。采集/调度接线已进入安装验收，完整来源与最终发行资格按对应证据核实。

## 准备与启动

使用已安装App的Python3.12，固定依赖包含PyArrow26.0.0（Apache-2.0；原生Parquet codec随wheel分发，版本与uv.lock一致）。公开第三方依赖及本仓SDK/纯策略包分别按安装清单校验；旧QMT工程不进入应用导入路径。

在安装目录之外准备本地观察数据根。空`GUANHENG_OBSERVATION_ROOT`关闭观察读取，其他工作区保持原能力。数据根包含`objects/sha256/<前两位>/<完整SHA>`和目录数据库；它与账户、委托及策略配置分别拥有。历史归档的日期与来源说明保持原样。

先通过受控文件传输准备完整冻结内容对象与manifest，保留原SHA清单。只向新数据根复制，旧QMT及原归档保持只读。然后使用安装后的解释器执行：

```powershell
& $AppPython -I -B -m guanheng_app.observation initialize --root $ObservationRoot
& $AppPython -I -B -m guanheng_app.observation import-frozen --root $ObservationRoot --manifest $ManifestFile --snapshot $SnapshotSha --seconds 600
$env:GUANHENG_OBSERVATION_ROOT = $ObservationRoot
& $AppPython -I -B -m guanheng_app --static-directory $ProductionSpa
```

以上变量由本机安装记录给定。首次导入的expected-current为空；已有版本时追加`--expected-current <当前SHA>`，版本变化会停止采用。先验证全部对象、资产大小与分区，再在同一事务采用目录及成功记录。未采用对象可留待下一次核查，原current保持可用。CLI写只改变观察目录。

## 页面使用

打开本机App的`/observation`。选择指标及日期，窗口与通道使用完整归档历史预热；日终PCR可切换持仓/成交口径。原始数据、怎么算、来源与质量、原图对照分别展示实际定义。“指标说明”提供中文名称、来源、覆盖、字段含义、公式和读法。

CSV/JSON导出链接包含页面snapshot_id，和表格/图表保持同版本。机器读取前缀为`/v1/market-observation`，浏览器投影为`/v1/ui/market-observation`；分页继续携带原snapshot及cursor。原件下载仅机器前缀提供，按已登记资产ID读取。独立App CLI仅监听回环地址；远程共享及访问控制另行部署验收。

“尚未配置”需要补显式数据根；“尚未接纳”需要完成离线导入；内容校验失败需要从受控原归档恢复对应SHA对象后重新验证。查询忙或超时支持重读，超容量时缩短日期或选择字段。空值和缺披露日期保持空白；0保持真实零值。页面显示更新未配置表示本候选没有运行自动采集，不代表历史数据已经更新。

## 校验与恢复

```powershell
& $AppPython -I -B -m guanheng_app.observation verify --root $ObservationRoot --snapshot $SnapshotSha --seconds 600
& $AppPython -I -B -m guanheng_app.observation restore --root $ObservationRoot --snapshot $PreviousSha --expected-current $CurrentSha --seconds 600
```

恢复重新核全部引用对象，保留每份冻结版本，仅通过CAS切current，回退记录与新指针同一事务。其他采集或发布者持有lease时，写操作明确返回正在运行，操作员保留原记录后核查；不依据锁文件存在删除状态。应用停止沿统一关闭入口等待读取线程，`shutdown_complete`为关闭总结果。

快照恢复与App程序版本回退分别执行；原归档不因程序升级覆盖。完整统一安装、实际来源/自然09:00窗口及组合升级回退继续按模块C验收，读取页面通过仅覆盖相应链路。

## 显式采集与每日09:00

### 广度、阿姆氏、RANA与换手率

开发候选的“市场广度”提供上涨范围、阿姆氏TRIN和RANA，“换手活跃度”提供换手率严格大于5%的已确认市场占比。范围为沪深A股；缺行和缺值数随原始数据表显示。主图下界与完整市场占比、有效样本占比分别命名，完整率缺失时保持空。最终安装与部署资格沿[本轮证据](../evidence/2026-10-30-observation-crosssection.md)；财务、高管、T2108和北交所继续补齐。

现有股票日终来源在原`baostock`配置中保留`pb_shsz_daily`，datasets追加`breadth.shsz`、`trin.shsz`、`rana.shsz`、`turnover.gt5.shsz`，tables保留`source.cn_calendar`并追加`source.shsz_universe`。同一连接、证券表和日线生成全部输出。原请求和批次截止继续有效，大表来源的请求预算按实际网络容量核实，分块抵达不续期。

已保存的原始股票日线可以直接补算，避免重复采集。维护人员固定来源快照、日期与目标当前版本后执行：

```powershell
& $AppPython -I -B -m guanheng_app.observation derive-breadth `
  --root $ObservationRoot --source-root $ExistingObservationRoot `
  --source-snapshot $FixedSourceSnapshot --start $StartDate --as-of $ObservationDate `
  --expected-current $CurrentSnapshot --seconds 600
```

新目标根先initialize，首次采用省略expected-current。来源根只读，目标沿原采集排他和CAS；版本冲突先核当前目录，来源歧义先核证券表及同日原件。每批最多366天且受原对象和父对象容量约束，超过时分期核验。PB/PE历史中缺价格、成交量与换手的日期保持缺口；该命令只生成四项日终观察，40日均线上方比例仍按独立输入资格核实。

### 原采集与调度

采集安装额外使用发行清单固定的`observation-collection`依赖闭包，包含HTTPX、Baostock及其精确依赖；普通只读App保持基础安装。先接纳完整历史快照，再核实来源配置原字节SHA、公开host、日期窗口、请求/字节/时间预算及A统一行情连接。来源文件禁止嵌入凭据。大陆行情通过A的已配置查询服务取得；其他来源失败时保留原数据并记录原因。

央行大型银行PDF需要采集闭包中的固定pypdf；页面只读安装保持零PDF依赖。原件取得后核文档页/字节与文本容量、年份、亿元单位和逐月列，失败保留原值及原件，维护人员核对最新官方表而非手工平移月份。HTTP未显式提供SSL_CERT_FILE/SSL_CERT_DIR时使用系统默认可信CA；显式提供时沿原配置核证书链。证书与主机名验证持续启用，网络错误及官方资料变更分别处理。

股票PB适配使用固定Baostock0.9.4协议常量与独占匿名公共连接，服务地址public-api.baostock.com:10030；该连接独立于HTTP代理。客户端版本与服务器响应版本分别登记。行内原始字符串保持，协议列头的排版空白单独规范。HTTP和协议消息各有原请求绝对截止，分块抵达不续期；来源timeout_seconds可以进一步收紧全局请求时限，所有工作仍服从批次seconds及停止信号。请求超时、容量或格式失败保留该来源原数据；维护人员先核固定错误码及原件，不修改旧快照原值。

requests为HTTP请求与实际PB协议发送数之和，http_requests/sdk_requests分别给出口径，含分页和正常登录/注销；它们表示消息发送次数。captured_bytes为HTTP传输正文与PB线上字节，decoded_bytes为HTTP压缩层输出与PB展开量。单响应、每层展开、规范表和两类总量分别受来源预算限制。HTTP保留http_wire与有父SHA的http_body两类原件；声明gzip/deflate，未知或损坏编码固定失败。连接池在响应头及每次网络读取前后核当前请求D，保持环境代理、NO_PROXY、证书校验和TLS。依赖升级需复核固定HTTPX/httpcore接缝、池复用及关闭。完整新候选的真实来源、全模型和安装资格按[输入预算证据](../evidence/2026-10-29-observation-input-budget.md)核实。

一次更新使用已安装解释器：

```powershell
$SourcesSha = (Get-FileHash -LiteralPath $SourcesFile -Algorithm SHA256).Hash.ToLowerInvariant()
& $AppPython -I -B -m guanheng_app.observation refresh --root $ObservationRoot --config $SourcesFile --config-sha256 $SourcesSha --as-of $ObservationDate --seconds 600
```

`ObservationDate`为本次截止自然日，来源实际休市和披露日期保持原样。单来源失败保留该来源旧数据；存在成功来源可发布明确的部分成功版本，全部失败或完整校验失败保持原current。公开观察数据继续仅供观察。

“盈利与回报”沿同一更新命令读取年报。维护配置显式加入`financial_annual`来源，URL为公开财务数据接口，`reports`指定1至5个连续年度；`window_mode=report_latest`、`max_pages=16`，数据集为`earnings.eps.shsz`和`earnings.roe.shsz`，来源表为`source.financial_shsz_universe`。声明`minimum_universe`、原总请求/字节/时间预算，并使用包含observation-collection依赖的App安装。跨年时维护者按实际已完成报告年度更新列表和配置摘要；当前批次仍只请求明示年度。来源身份可使用`eastmoney.annual`，页面显示“年报盈利与回报”。

财务页面默认显示全部实际年度，上图为有效样本平均EPS或平均ROE，下图为五年历史分位。“原始数据”可核有效数和尚缺数；完整股票池均值在样本不足时为空。负ROE继续保留。范围、公司去重、币种、报告修订及日精度按[唯一财务定义](../specs/independent-market-observation.md#obi9-年报盈利与回报接线)阅读；当前沪深结果和北交所覆盖分别验收，[实际证据](../evidence/2026-10-30-observation-annual-financials.md)记录安装及来源资格。

沪深北候选使用同一financial_annual来源，显式scope=ashare及earnings.eps.ashare/earnings.roe.ashare、source.financial_ashare_universe，并把www.bse.cn加入来源主机。minimum_bse_universe约束实际名单下限，bse_history配置持有市场启用日期、资料核验截止日和已核退出区间/原公告SHA，具体字段沿[唯一规格](../specs/independent-market-observation.md#obi9-北交所股票池接线)。超过资料核验日期时来源停止采用新结果，原图表和数据继续可读；维护者补齐上市/退出资料、核原公告后更新配置摘要。当前普通安装/真实来源到页面的资格沿[主链证据](../evidence/2026-10-30-bse-financial-pipeline.md)，最终发行与自然09仍分别验收。

独立观察服务需要监督部署与子服务配置两份原字节文件。子配置只有`schema=guanheng.observation-scheduler-service.v1`、`root`、`sources_file`、`sources_sha256`。监督部署使用`schema=guanheng.observation-process.v1`，字段为`pythonw/pythonw_sha256`、已安装的`observation_service.py`及`entry_sha256`、子配置`configuration/configuration_sha256`、受保护本地绝对路径`control_root`、`startup_seconds`、`stop_seconds`、`max_output_bytes`。各文件及解释器/入口摘要来自当前安装清单；数据根须与Web读取根一致。更新服务使用含observation-collection闭包的独立安装，凭据由维护环境注入。

```powershell
$ObservationControlId = [guid]::NewGuid().ToString()
$ObservationControl = Join-Path $ObservationControlParent $ObservationControlId
$ObservationDeploymentSha = (Get-FileHash -LiteralPath $ObservationDeployment -Algorithm SHA256).Hash.ToLowerInvariant()
& $CollectorPython -I -B -m guanheng_app.observation_supervisor `
  --deployment $ObservationDeployment --deployment-sha256 $ObservationDeploymentSha `
  --control-directory $ObservationControl --control-id $ObservationControlId
```

调度保留北京时间每日09:00，可在同一`schedule.times`配置至多三个16:30以后的盘后窗口，例如`["09:00","17:30","21:00"]`。启用`schedule.date_policy="source-aware-v1"`时，每源声明`date_policy`：沪深行情用`cn-closed-day`、香港行情用`hk-closed-day`、披露和报告用`calendar-day`；前两者按原官方日历取窗口时点已结束交易日，后者保留自然查询截止及实际报告期。周一早上回看前一交易日；高管资料按股份变动日回溯已披露记录。旧09:00配置省略date_policy时沿前一自然日兼容口径。每次只扫描昨日和今日已到期窗口，`schedule.start_date`可登记首次投用日期。网络请求前持久登记尝试编号；失败沿同一窗口按有限退避继续。完成窗口、新快照及成功/部分成功回执共同提交；重启后已完成窗口零采集。手动更新与计划更新争用同一采集lease。

同一观察数据根只允许一个存续中的调度实例。第二个独立更新服务启动同根时，子端返回`scheduler_already_running`，原实例继续工作。页面的“自动更新”读取数据根最近心跳和窗口回执，并说明由独立观察服务更新。Web App只配置`GUANHENG_OBSERVATION_ROOT`，其启动、停止和升级保持观察服务继续；旧App托管环境项已退出。正常关闭或进程退出由SQLite连接和操作系统释放调度租约，维护人员沿原监督及子端关闭结果确认资源后再启动；保留协调文件，避免破坏在途锁。

隐藏维护使用发行包的`observation-update-owner.py`模板及该部署的`PREPARED.json`；部署记录给出实际安装副本和稳定定位。核解释器、维护入口、部署和来源配置摘要后，执行`python -I -B <维护入口> status|stop|start`。status同时核原控制身份、进程创建时间、子进程和最近心跳；outcome=observed只表示状态查询完成，需继续读取alive及实际来源回执。stop取得同代closed及资源退出证明后再启动下一代，未知时查询原代，不重发启动或移除协调状态。更新角色与Web使用独立维护定位，版本可以分别升级，数据根保持同一已提交目录；当前实例及回退范围由[发布记录](../releases/README.md)维护。

日终更新只复用同一数据根当前已提交快照的未变化内容资格；来源新增值、新引用、指标字段合同变化及股票分区登记变化继续完整核验。更新回执的`validation`给出前代snapshot、实际读取对象数、复用集合摘要、复用指标及PB历史版本/行数。首次导入、显式verify和恢复继续全量校验，查询仍逐次核摘要。后继安装同时接收App状态读取与独立更新角色，合并唯一来源配置；保留原数据目录、窗口和尝试记录，候选目录的验证完成索引不迁入现场。

发布准备、写锁等待和提交准入共用原批次截止与停止信号。提交前超时或停止时，当前版本、成功回执和完成窗口共同保持；已登记尝试仍保留。持久提交后的确认超时返回`publication_unknown`，保留原候选SHA和窗口身份。下一次检查先核完成窗口与当前快照，已经完成时跳过采集；维护人员用`verify`核原候选并读取更新记录。核查前保留该结果，防止把未知提交当成确定失败重复发布或回退。

前台维护入口使用Ctrl+C请求正常停止；受管维护环境沿本实例控制目录写原`guanheng.observation-stop.v1`停止收据，包含匹配control_id及同机单调时钟的有限deadline。监督进程先关闭原采集owner，再join自己的停止监视线程，写closed或failure；完整关闭同时证明子进程、Job整树及管道已回收。可选`--seconds`限制包括启动和关闭的总运行时间，用于有限验收；长期维护环境省略该项并持有监督进程。截止到达由原Job收尾，强制回收作为失败。中断保留原版本与尝试，下一次启动先核原窗口状态。心跳表示最近检查；来源可用和数据覆盖沿每路回执核实，Web继续读取此前合格版本。

沪深北高管候选在executive_changes中显式选择scope=ashare，登记executive.net.ashare、executive.ratio.ashare、executive.companies.ashare及source.executive_ashare_universe，并提供同一bse_history、minimum_bse_universe和www.bse.cn来源主机。股票池、规范代码与公司分母共用原BSE资料；缺身份仍留空，图表标注已披露范围。原shsz来源保持可选。配置字段和失败保旧沿[唯一规格](../specs/independent-market-observation.md#obi9-高管披露接线)，实际来源/页面与安装资格沿[本轮证据](../evidence/2026-10-31-bse-executive-observation.md)。

## 沪深北固定日终原件

配置`ashare_snapshot`来源时，显式绑定原件清单绝对路径及SHA256；清单交易日须与本次`refresh --as-of`一致。原件包包含同日普通A股股票池、沪深日线、北交所行情及股份资料，并保留各自实收时刻。沿原独立采集入口发布，四项`.ashare`指标与已有`.shsz`历史分别展示。

固定包提供对应交易日的可核验观察；每日取得新原件和配置身份更新由持续来源负责。更新失败保留原成功快照，界面继续显示其实际日期及原因。完整合同和验收范围见[日终规格](../specs/observer-ashare-day.md)。
