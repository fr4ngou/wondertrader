# 独立市场观察安装与真实归档读取

类型：开发验证记录。状态：done（本机独立安装的冻结读取切片，两轴独立审查complete）。完整F18/COP-A7和模块C保持in-progress，未发布。

## 根因与实现

原保留ObservationShell尚未装配到主App，独立观察后端依赖旧研究包与PG/MinIO部署。依据[OBI规格](../specs/independent-market-observation.md)和[ADR-0015](../architecture/adr/0015-observation-snapshot-owner.md)，将原合同、纯计算、日终PCR、完整历史预热与固定快照读取迁入`guanheng_app/observation`；WT行情重合能力继续由A拥有。SQLite事务拥有manifest/current/成功receipt，另库写事务拥有采集lease；显式离线采用/恢复核全部对象并执行CAS。HTTP/导出沿App已有有界读池，前端沿原观察Shell、日终PCR和原页面功能接线，策略资料页保持用户要求的简介版本列表。

小对象读取最初错误地按256MiB上限分配缓冲区。20,001字节对象5次读实测约0.328秒；改成按已打开文件实际大小加一字节读取，增长/容量/SHA校验保持，实测低于计时分辨率。对应内存回归限制小对象读取峰值低于1MiB。早期截止、归档附带manifest及缺父对象的失败原件保留在独占build目录，失败期间current保持空。

## 实际来源与身份

输入为旧独立观察的受控冻结归档`E:/workspace/qmt-storage/generated/observation-evidence/observation-remote-20261020/{admitted-data.tar.gz,snapshot.json}`，归档SHA256 `0d1a0639b32a2adf53b4d24ba117ea727aa300b29700b921b7f8e7b672a1697a`。snapshot保持`18cf046f58fc17c357d0e3179ab79b60f6a8fc613e2ca92279c1811f6d596280`，原发布时间和历史覆盖保持原样。此数据不代表10-29最新披露。

原包有14,824个内容对象、768,975,793字节及一份同身份目录；15,835项资产登记包含历史/去重引用。完整校验发现债券旧指标一项父对象未随原包导出，从只读`shared-data/market-observation`库补得264字节，内容SHA为`0e84e65e53fd390046dd5b62ec263c70842a2d58098481845bdbb2b081278f51`。没有修改manifest或删减谱系。完整14,825个引用对象、48数据集54,280指标行、10股票标准分区4,946,119行通过校验后，在新数据根原子采用。最终采用重用已复制对象，全量重读及校验58.704秒；不将此时间写成首次空目录复制用时。

Appa10普通wheel SHA `2ffa18b88c9d94213df599b30c38f15d316344b976e6267b622916a841f3e097`，PyArrow26.0.0与uv.lock公包hash安装、六份既有私包精确SHA安装，新Python3.12.14环境22发行pip check通过。生产SPA004按当前manifest只冻结17文件，ZIP SHA `4b25b58b1cfe93e2f96abbdc3c32939baae1faa7a4c7f999d17c2febc2577c3e`。新进程再次完整采用同一真实快照通过，并核62个App安装成员与wheel逐字节一致、22发行1967个RECORD摘要匹配。旧App/Host安装及旧BT profile保持各自资格。

## 主链与验证

原件在`build/observation-app-001`，每阶段沿`validate.py`调用原native.run：隐藏Job、一次总D、有限输出和树/EOF/join收束。生产App从安装site-packages导入，数据只读自本仓新根；旧QMT仅作只读来源和原纯计算oracle，不进入产品运行依赖。

| 范围 | 实际结果及原件 |
|---|---|
| 完整冻结导入 | stage.json：原目录SHA、原分区、全部资产/父对象/股票字符串分区校验后采用；此前失败未切指针 |
| 48指标真实HTTP | http.json：54,280行逐值匹配原Parquet和原纯计算，日终PCR/通道/期限曲线保持原口径；48份JSON导出同snapshot逐值一致 |
| 生产SPA | browser.json：1440×1000与390×844；真实PB图、PCR成交口径、数据资产/搜索、四品种8图及其历史503、原图503、更新回执503、未来空日期、catalog503隐藏和手动恢复；单观察侧栏，产品请求全GET，未预期运行错误0 |
| 后端回归 | 31通过，含原App启动5项；完整历史预热/缺口/空值、CSV/JSON/JSONL、旧版本固定、坏query/只读、损坏拒绝/恢复、事务中断/CAS竞争、跨进程lease与崩溃释放、绝对截止、小对象内存及plain/dictionary高压缩Parquet解码前拒绝 |
| 公共回归 | app_console/operations_workspace共124通过、1原有skip；原skip的用例名/原因见regression-skip.json，未据skip授资格 |
| 前端回归 | 62通过，含原观察页面和IndependentApp；分页身份/循环游标/同一15秒截止、22项突发限2并发/排队取消/原截止、延迟timer时排队不发请求及晚JSON拒绝；TypeScript、生产构建及五工作区分块通过 |
| 资源 | 最终15.625秒，main.json及native-result.json：App shutdown_complete、两个读池线程0、HTTP线程join和监听关闭；原Job/整树/EOF/join完成 |

截图位于本会话visualizations的`observation-app-001`目录，已人工核宽屏和390px真实图表。Browser plugin not available，使用现有Playwright/Edge；没有调用QMT界面、真实交易、生产或供应商采集。

## 独立审查修正

首次32输入full审查两轴均发现采用准入和子读取错误门控问题，规格轴另发现已有历史目录损坏时INSERT OR IGNORE仍能切向坏行。已在唯一发布owner修正完整结构/指标父对象闭包，在同一事务核已存版本原字节；拒绝时current/receipt集合保持原值。新增缺失/损坏父对象、缺boards/preferences/published_at、已有坏目录正确外部导入的回归通过。模型只验证原manifest，不重编码或改写原身份。

Reference、Futures及Quality按各自依赖成组成功状态门控，失败隐藏旧图/结论/回执并支持手动恢复；DataAssets补重读入口和真实空目录提示。观察查询统一关闭库的自动重试，防止跨轮续期；日期/分页一轮仍15秒。指标100000行与股票65536批/单分区2000000行/当前总20000000行/128登记版本分别约束，股票逐批沿原采用截止。完整真实快照在新wheel再次采用通过，原5M字符串及目录SHA保持。生产浏览器额外验证四品种8图，以及原图/更新回执/期权历史的先成功、单子接口503、旧值隐藏及手动恢复；全部请求GET，零未预期运行错误。

股票原始归档进一步在解码前核全部row-group未压缩字节总量≤256MiB，按字典保留重复字符串，依据字典值掩码和indices核身份，避免按行展开；单批Arrow字节≤256MiB。两个真实zstd编码回归验证原口径正常、压缩体积小于预算而解压超额时不进入iter_batches；完整原4946119行重新采用通过。

生产复跑还捕获四品种重连的一批额外503；原App固定2worker/4队列，客户端同时发起多项读取且没有并发准入。客户端观察API统一2并发/32等待，排队和分页共用原15秒截止，取消/超期出队，完整响应解析后归还名额。获得名额和JSON完成后显式核原截止，覆盖主线程忙时timer尚未调度的窗口。matrix-burst-failure-*保留原失败，修复后的SPA004正常8图及单组失败隐藏/恢复通过，零未预期运行错误。

初次被审候选wheel65041e和SPA原件保存在initial-reviewed-artifacts及原独立目录，bd4/SPA003后继保存在pre-byte-budget-artifacts；最终输入按review-sources-final-002.json的56项重新冻结，SHA `03f1cd695097921d0bd536339a718b2f31eb09df3075d94917956942477a6581`。规格与规范两名独立审查者分别核56项零漂移、64构建文件/62安装成员、31/62回归及实际完整采用/HTTP/生产SPA/资源原件，最终delta与全部受影响闭包均complete，无剩余P级问题。报告归档reviews.json，精确交接见DELIVERY.json；首次full及各后继gap保留原身份，不挪用资格。

## 资格与后继

本轮授予本机独立安装的冻结观察读取/图表/导出及目录事务开发资格。完整provider迁入、模块A替换重合行情、09:00正式调度与窗口完成/更新恢复、镜像备份、统一安装搬迁/升级回退、真实策略M1及完整模块C继续。自动更新状态明确未配置。历史公开观察、当时可得/最新性及可执行行情资格分别保持，不授交易资格。
