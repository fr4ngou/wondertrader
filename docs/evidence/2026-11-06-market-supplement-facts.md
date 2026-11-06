# WT市场补充事实与原版融资来源验证

类型：验收证据。状态：生产代码主路径、隔离真实来源与HTTP/SDK查询已验证；整角色安装、完整历史及生产采用待验。范围沿[MSF规格](../specs/market-supplement-facts.md)，操作沿[统一数据手册](../runbooks/unified-daily-data.md#市场补充事实和历史补齐)。

## 根因和实现

原WT bar与定日股票八字段事实缺少ETF每日总份额及市场融资。补充目录由原daily owner采集、持久续补和同快照发布；QMT当前绑定先核能力，外部源按显式准入补充。缺口、未知单位及历史首次可知时间分别表达。QMT代理请求范围由固定任务定义，恢复只投影缺行；发布前及snapshot阶段恢复均核原件闭包，总截止/取消贯穿新增遍历。

要求起点与截止同时核原官方日历覆盖范围，超界拒绝；首个开市日前的覆盖内周末正常准入。该修复避免静默裁剪早期要求窗口后误报完整，日界和开市日一并持久固定。

融资来源核查追到原版RPTA_WEB_MARGIN_DAILYTRADE/FIN_BALANCE，单位亿转CNY；此前RPTA_RZRQ_LSHJ/RZYE是另一张表，两者不逐值相等。原表市场覆盖未知，symbol为CN.MARGIN_REPORT。原值、原fetch四位处理、暖机、重新回放及差异以本地研究13b登记，旧输出保留。

## 真实链路和安装范围

2026-11-05单日实际取得三项：SSE.510300份额46491787700 share、融资2278513909140 CNY、QMT双指数amount代理2117950073861.0 unknown。目录SHA为15c380c699c74f151a76b68f3eacd7caea54dddc6b5ecb5195b4f7e73ecc819f。重复采集外部HTTP为0，原received_at保持；这三项单日完整与九ETF全历史完整分别判定。

最终日历修复后按新任务再次实采三项，数值和单位一致，新目录SHA f18f2c6227e2b032d5865fd4833aff51ccd03d4665fb0b00178a076c20e24f23；首次HTTP2，恢复HTTP/SDK均0。两次研究任务身份和原回执分别保留。

该真实目录经过隔离snapshot及实际HTTP，由普通wheel安装SDK0.19.0消费，逐值/单位/来源核同；旧ID冲突、未配置、分页边界及目录/proof/父原件/能力原件副本损坏与恢复通过。实际native base为已发布source-catalog叶子338 stores，未mock factory；候选旧解析器尚不兼容当前归档包装及security_reference，验证明确省略该两部分，完整价格组合待验。生产CURRENT、源目录和原件闭包保持原样。

SDK wheel SHA为db2270b38936d994e3caeb51cd8d727c3fe1528887b290d73fd4e21a4e9000bf，module.__file__已核安装目录。Core候选0.1.0a1+unified.2登记本任务11成员；完整构建在source_inputs被五个已有QMT源码与永久声明摘要不符阻断，原声明保持，待对应来源资格确认后重建。该SDK安装证明与整Core安装、生产采用分别记录。

## 回归和剩余范围

独立回归覆盖validate_configuration→prepare_update的required等待/同任务补齐→UPDATE→run_update→GenerationPublisher/CURRENT→实际HTTP/SDK查询；股票公共输入和原生日线DLL使用明确替身。QMT代理走真实RetainedReadClient、票据与slot，失回执查原ID、部分行落盘后退出恢复保持SDK调用身份；损坏闭包、取消、单位、范围及旧身份同时检查。

28项采集、owner接入和查询回归通过，两份独立审查的必须项已关闭；原HTTP服务16项（含1项平台跳过）及旧日线7项回归通过。原版融资历史为609行（525要求日＋84预热），要求区间缺日0；三组新名称回放逐日净值、信号和成交与旧结果相同。来源更正与策略收益资格分别表达。

最终源码摘要、命令/退出码和两份独立审查保留在被Git忽略的`research/resonance-20261105/msf-development/FINAL-VERIFICATION.json`；真实原件和查询回执在同目录MAIN/MAIN-HTTP，具体研究入口见[研究指引](../research/resonance-research-guide.md)。

两只SZSE ETF份额、官方成交额缺日、QMT代理单位和历史PIT仍待补证。更广source_market_app测试因既有固定策略依赖未安装在收集阶段失败；旧超大security错误码断言的失败已用前任务SDK复现。本轮文档静态检查仍为30项已有未索引文档，新增文档已纳入导航。

## 2026-11-06实际历史纳入与原版请求再核

用户追加授权实际补齐并指定继续主目录。现有七ETF份额3557、原版融资525、QMT代理525、两市官方58，共4665项纳入WT标准补充目录；目标6158，标准缺口1493。原59日官方原值均保留，其中07-01缺真实接收收据而未纳入标准目录，源缺日466与该1项资格缺口分别记录。两只深市份额按上市日窗口仍缺1026项。

真实目录通过逐原字节独立重算/完整来源闭包及普通安装SDK的实际HTTP全6页读回。实际补缺任务保留pending与COVERAGE，原成功行/收到时刻保持，完整目录未固定；正式生产CURRENT和策略保持。原生base验证范围沿此前叶子目录限定，整Core安装/生产采用待验。

重新核上游main仍351f9d5；AkShare深市实际XLSX完整请求分别默认代理/直连失败。管理人真实接口和东方财富数据仅有季度规模或PCF篮子，日频总份额继续缺失。详情和具体源码/原件身份沿[研究指引](../research/resonance-research-guide.md)中的14专题读取。

实采触发HTTP RemoteProtocolError未归类，已在原Fetcher层修正为固定来源错误，保存缺口并保持预算；required等待的停止/截止优先级同步修正。新增真实TCP及原collector续补回归、独立红绿和最终源码身份保留在本地HTTP-FAILURE-REVIEW/BACKFILL-FINAL记录。静态文档和原角色构建的既有阻断范围保持单列。

## 用户服务器对照与HTTP路径修复后继

只读用户提供的Resonance实例，冻结九ETF、日历和市场辅助序列后，由原版独立入口本机重放：2021-01-04至2026-11-06全部1415净值、260调仓、137信号与远端逐字段相同，收益164.25%、回撤20.88%。这证明同冻结输入的算法一致性；独立QMT数据同窗口仍有价格与存量指数字段差异，保持另一报告身份。

本机同刻单变量对照实证HTTPS导出响应头前断连、HTTP官方XLSX导出200且无重定向。生产来源改用已核HTTP导出及按份单位，标准库有界解析；原HTTPS JSON仅作历史记录。两深市ETF官方份额全部新增1026行（525＋501），补含A500上市初19日。新标准目录v2共5750项、余408官方成交额缺口；既有目录保持不改，新目录实际HTTP/安装SDK全6页逐对象核同。QMT完整份额回放4412消费行无份额缺失。

新旧来源红绿、坏Deflate异常收敛、真实Fetcher→collector恢复及原查询合计60项通过，独立审读必须项0。源连接/长期限流、当前旧QMT绑定的完整现时采集、整Core安装及正式采用各自未授资格。当前unified.21未配置/安装MSF，所以新增数据尚未每天自动更新；观衡目录也尚无原版研究条目与原版归档。具体一手证据、输入/报告/源码摘要沿[研究指引](../research/resonance-research-guide.md)第15专题及FINAL-VERIFICATION读取。

## 同日线owner的持续日更增量

以正式master `46c42ba1edf103f584cff9bdc56703efaf9afa8b` / unified.21 `008492d921c65675109c6f41cd9da1184a623fe5`为行为基线，保留原price-first、原INDEX修订和Source读取责任。新增MSF接缝合入同一数据线程；最新事实先取，旧缺口使用剩余原预算；可选max_requests分配阶段份额并继续扣原CollectionBudget总账。源单位/PIT和HTTP传输资格保持原声明。

required=false允许partial发布，次北京时间自然日09:00后最多创建一次同市场日修订，失败沿原节拍恢复；同日partial成功不因历史gaps空转。旧未发布任务已成功事实经proof闭包核对后进入新日，收到时刻和原件保持。QMT代理仅请求真实缺失日，按现行profile行数/自然日分块并首次固定参数/slot；unknown不归NotSupported。配置迁移可用固定previous_inputs保留外层REQUEST尚未物化时已经存在的输入及原读槽。

实际执行 `.venv/Scripts/python.exe -B -m pytest -q tests/integration/market_supplement tests/integration/service/test_market_supplement.py`：72项通过。原prepare→五组目标→UPDATE→run_update→CURRENT→实际回环HTTP/SDK完整调用链通过；Source/Native边界为明确替身。覆盖跨日、次日09:00、额度恢复、公共预算超时partial发布、price-first成功后来源失败保CURRENT、原未知请求、损坏闭包、分块及取消/总D优先。恢复的Host inspect_saved_result文件SHA为29315bc0907e41e3812839ad27b88d0827607a557a913d30e3e0cf2c46ddd542，与master及实际unified.21安装字节相同；所需security_price_roles及price阶段名称同样恢复发行基线。

最终源码、原基线恢复/字节摘要、命令与结果在Git忽略的daily-auto-development/SOURCE-FREEZE、BASELINE-RESTORE、TEST-RESULT及HANDOFF登记。后继配置和迁移收据只在受控数据根准备，旧运行配置/INDEX/CURRENT保持；真正新角色普通安装、独立审查与正式采用仍由Root分别验收。主目录project.py check仍列30项既有未索引文档，新增MSF正文沿既有导航到达。
