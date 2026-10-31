# 源值按需历史服务的真实QMT主链

类型：真实来源、隔离安装接线证据。日期：2026-10-29。状态：真实缓存补入、普通App及独立安装主链通过；真实补齐命令已调用，早期窗口仍为空。完整C/B统一组合、市场覆盖与生产发布未验。

## 输入与调用链

候选为build/source-history-demand-001/package-007/installed，INSTALLATION SHA256为766560851d835467f0cda0d3fe8046f83421e8ba9d46b3042d57aa2c24b85e1e。13项交付源码、158个安装清单成员逐项摘要一致。依赖冻结HPR e（INSTALLATION SHA256为5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3）及既有安装Appa13进程管理模块。原生框架未重编。

复用已运行GH_WT_MEMORY_VERIFY090及原v6配对参数；Host与服务均在新私有目录受管启动。采用原335store旧配置build/source-market-real-main-021/source.json作为显式旧库存，其中510300尾部为2026-10-26 11:30。原数据根保持，补入结果在新workspace发布。源码/配对凭据仅在受控材料中，正文不复制。外部Host使用loopback HTTP，QMT正文继续通过命名共享内存通信。

## 实际结果

- build/qmt-source-preparing-real-180及控制181：588000和510300在2026-10-28 14:51..14:55各5根，经正式SDK→已安装服务→已安装Host→实际QMT缓存→原Importer/Helper/DSB→原Reader→同一SDK返回Ok。源端六字段和分钟标签共10根逐值完全一致，单位与覆盖仍unknown/Unknown。
- 两窗口在QMT缓存已有数据，各只执行一次market.history_1m；无需history_prepare。重复SDK查询结果完全相同，窗口收据字节保持，原Host read_operations只读核查为2项terminal，新增补齐0。
- build/qmt-source-preparing-real-182及控制183：588000在2021-11-01 10:01..10:05读前0根，原history_prepare实际调用一次，终态ok且effect=call_returned，SDK执行16ms；读后仍0根。公开结果保持Pending/来源覆盖未知，未生成空DSB。三次同窗调用共2项history_1m、1项history_prepare，均terminal，无重复下载。函数返回只证明调用结束，真实数据补齐成功尚无证据。
- 180主链7.375秒，181原外层9.547秒exit0；182观察7.703秒，183外层9.782秒exit2（所需数据为空，资格未通过）。两次Host/服务均closed、forced=false、pending=false；原Job树为0、两管道EOF、reader join与资源关闭确认。

首179在创建受管进程前因验证宿主缺quote_collection_process导入退出，该次QMT源调用0。失败目录保留；后继复用既有安装Appa13的进程管理模块，生产代码保持，原未知请求身份保留。

## 运行边界与后继

实际QMT策略正文SHA保持6be3b6e5d9b41fc6861b40972192e31d7aae72bc73933ca65bddad7ed0a9b89b，本轮未重启/编辑策略。采集137/140未切换；10:38:56的LIVE显示已处理8099628条、源时间约10:38:55.777、溢出0；同轮CIM确认采集69928及父App54752存在。这是瞬时运行观察，不授全天/逐证券时效和收盘归档资格。

FINAL-AUDIT.json区分成功缓存补入与早期空窗口，原始RESULT/响应/收据及独占Journal分别保留。真实下单0、撤单0、生产切换0。下一步连接观衡普通App的同服务入口，继续已获数据的策略消费和收盘归档；早期窗口真实数据可得性及当天补齐协议分别保留未完成，整体目标active。

用户已明确停止WT框架潜在多线程问题调查，四核心待议修改不实施；该调查已从当前主线前置任务撤下，历史证据保留。

## 普通 App 主入口差分与盘中采集后继

同一固定 Appa17 wheel（SHA256 7b6a51eaa266d48a887a1fdb38a0a2037e4d046127b65841c633c24645cc5c5e）与 SPA011（SHA256 025ebd950cd1f0b471b9804b5ff1c446688e89a24883460d0022f1b8584503ed），使用普通 ConsoleSettings/create_app/lifespan，无替换客户端工厂。88个App发行成员和18个SPA文件逐项核验。

- 自动补齐模式：build/qmt-source-demand-app-real-185/APP-RESULT.json、APP-CHART-UTF8.json及控制188。App自动启动Host和行情服务后，正常GET请求510300.SH、1m、limit=5、before=2026-10-26T11:30:00+08:00，返回data_available=false、0根，原Host read_operations为0。App按原接口发送长期from到截止时刻的查询，007提前把整个查询跨度作为单次补数范围校验，导致旧库存已有数据也被拒绝。该失败归属新增源服务准入与选取逻辑，后继修正进行中。
- 原库存模式：build/qmt-source-demand-app-baseline-191/APP-RESULT.json、APP-CHART.json及控制193。采用同一旧335store根，保持相同App/SPA/正常GET，仅选择source-stores并禁用HPR，实际返回data_available=true、5根。无QMT请求。控制3.766秒exit0；App关闭完整、HTTP线程结束、Reader线程0、来源子进程closed/forced=false，外层树0、EOF/join及资源关闭确认。
- build/qmt-intraday-minute-189/SUMMARY.json及控制190：10:52:36北京时间，以稳定副本经原Helper读取仍运行的137/storage；510300、600000、000001各83根，09:31至10:52共82根已闭合，10:53一根形成中。该结果证明三个样本持续落盘，全市场完整性和收盘归档仍待；采集实例未停止或重启。

后继先完成同一普通App查询下已有库存与预算内尾部补齐的统一返回，再消费策略主链。潜在WT并发问题研究保持停止，本轮框架源码修改0、真实下撤单0、生产切换0。

## 原早期窗口延后回读

继182/183原history_prepare调用后，195/196以新独占Host只执行一次market.history_1m，回读相同588000.SH、2021-11-01 10:01..10:05。原下载记录和收据摘要保持；未重发原补齐，也未新发下载。实际请求ok=true、error_code=null、rows=0，原Journal只有一项history_1m terminal。该观察说明延后回读仍未取得数据，空窗口来源与下载效果继续未验证，不能把函数调用成功报告为已补齐。

195/AUDIT.json分别记录通信成功与data_available=false。内部3.156秒，196外层5.360秒exit0仅授只读通信/正常关闭；Host closed/forced=false/pending=false，外层树0、双EOF、reader join及资源关闭。QMT正文摘要保持、采集137/140未切换。常驻操作手册已统一系统管理Host的启动顺序，旧单连接期限单独标识；默认框架行为与真实下撤单边界保持。

## 真实App增量与分段来源

后继RS13开发候选package-002（build/source-history-selection-001/package-002/installed），INSTALLATION SHA256为81cd8b878bf5f50f1788c37af437cca0272273ccd7cf118c53072d5e59f3429b，159项清单核验。消费固定Appa17原wheel及SPA011，App源码/路由保持；新SDK工程wheel SHA256为014d0c407ab413b2d6c62105a71a4a4472a13f45f3dfd57ac0150e2780954feb。该SDK工程候选仍沿0.14元数据，正式SDK版本/依赖集成由根后继处理，不能据相同版本号替换已交付旧wheel。

- 198/200：同一普通GET读取原335store旧尾5根，data_available=true，最后2026-10-26 11:30。原Host Journal操作0，修正前185的同形失败已消除。200外层6.062秒exit0，正常关闭。
- 201/203：App原lifespan自动管理真实HPR e Host与源服务，现有GH090保持。四次普通GET分别读取旧尾5根、昨日14:51..14:55新尾5根、最近10根及相同10根重复；均可用，最后新标签为2026-10-28 14:55，重复图表完全一致。随后同服务原SDK查询保留两段provenance，前5根为原DAT归档、后5根为实际SHM缓存来源，各段原source/session/generation保持；集合不伪造共同捕获身份。
- 201/AUDIT.json核对实际认证SHM回复的5根与SDK尾部的OHLC/volume/amount六字段及分钟标签完全一致，原库存图表5根与合并前缀完全一致。原Journal只1项market.history_1m terminal；无history_prepare，重复及合并未新增源请求。新DSB与原根分离，原Helper/Reader复用，WT框架本轮修改0。
- 203外层6.953秒exit0，App shutdown_complete、HTTP join、Reader线程0，Host/源服务closed且forced=false/pending=false；原Job树0、双EOF、reader join和资源关闭。198/201原件、私有配对、来源回复及收据分别保留，秘密不复制到文档。

混合最近10根明确observation=Partial、coverage=Unknown：有限5分钟尾窗被读回，但旧归档至该尾窗之间仍有未核区间。最近N根可读、新尾缓存补入、密集范围完整和真实下载成功分别成立或待验，不能互相替代。实际QMT文件/策略未重启，盘中采集137/140保持，真实下撤单和生产切换均0。模块最终异常/审查/固定发行、真实下载效果、当日补齐及统一B/C安装仍继续，整体目标active。

## SDK0.15与Appa18独立安装后继

build/qmt-sdk-app-version-205以冻结的SDK工程wheel及Appa17制品准备独立源目录，通过原锁定flit_core 3.12.0后端构建明确版本。SDK0.15.0 wheel SHA256为33bf4675a063c0cd46d6a510d582d7c2f4f9755b9e3b46d4e3a69cc121cdc335；App0.1.0a18 wheel SHA256为44a29f4980ccd522b396b497ae1352404927be980c37ac2ef018603b85294c7b。SDK模块范围14项，变更__init__中的版本；App85项包内源码/资源字节与原a17完全一致，依赖元数据明确绑定SDK0.15.0。共享活动源码、WT框架和C在研文件保持。

205/runtime为新普通安装目录，沿固定公共requirements SHA256 96a40a8280225a486052960f8bb480c4d0c1bfa0732fd0b75a5f62d23303947b及7个固定私有wheel安装；无依赖冲突。原207的30秒全RECORD校验超时，失败与正常回收原件保留；同一已安装输入的210独立回读在16.625秒exit0，31发行的4743个有hash RECORD条目逐项字节/大小匹配。INSTALLATION.json SHA256为a8b330036ce3bd0d3941ade1b72da2a0d6545948ca4e52e31623a43506eac8e1；该证明范围是所列安装项，没有授额外未声明文件的完整目录资格。

208/211从上述新解释器正常创建App/SPA及两个受管owner，复用实际GH090、package002和新的独占pair/Journal。旧尾5、新尾5、混合10及重复10的原GET均通过，同SDK保留2段来源；实际SHM缓存的5根六字段/标签与输出完全一致，原Journal只1项history_1m terminal、history_prepare为0。211在9.375秒exit0，App shutdown_complete、HTTP join、Reader0，Host/服务closed且forced/pending=false，外层Job树0、双EOF/join和资源关闭。208/AUDIT.json绑定本安装身份，observation仍Partial、coverage仍Unknown。

此候选证明明确版本和独立安装下的真实只读历史主链。A最终模块交付及其最新源身份仍在收口，公共源码版本/锁片段、C活动业务/B运行组合与最终统一发行后继集成；不把205临时源目录视为已合入主干，不切生产，不做真实下撤单。

## 最终005源码与共享SDK版本整合

根逐项复核RS13最终005的17项声明源码与159项安装成员，全部摘要一致。相对此前实际运行002，仅source_history_preparation.py改变；005已完成的离线主链/恢复与两轴审查按其固定输入复用，真实运行不冒名改标。

共享SDK __version__已改为0.15.0，当前C的完整Appa18依赖只调整guanheng-market-client==0.15.0；新增V1/AI/risk/rules等C依赖全部保留。215沿当前项目执行uv lock --check --offline通过，uv.lock保持4b7357d9a0e90e233f854ef33349bb1da95d9c6a04332882b31abbcaad594477。这里只授共享元数据与锁的一致性；完整C Appa18仍由C交付。

从005冻结Python闭包复制到独立输入218，仅替换上述SDK版本文件，原生二进制与其余成员全部保持。原打包器输出218行情组件，159成员，INSTALLATION SHA256 fb0c6d6b3e2d4e5fb81794d148de4423279ef9e90cce22768c9b15a8d7570eae，ZIP SHA256 d22fbaf58b97672a3d3fdc32bb2c518bb8143ea6a36231ef836ee1c34f8a852d；SDK216 wheel SHA256 34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab。217构建2.297秒exit0，未重编原生、未改变WT框架。

220为第二个新普通数据消费环境，沿相同24公共依赖和7私有wheel安装，31发行/4743有hash RECORD核验及依赖检查通过；221外层46.141秒exit0，资源完整关闭。消费App仍为冻结a17业务代码的metadata-only a18制品，不替代C当前完整a18的新增功能。

222/224用220普通安装、最终218服务、原HPR e及实际GH090再跑旧5/新5/混合10/重复10与SDK分段来源。5根真实缓存的六字段/标签逐值一致，原Journal仅1项history_1m terminal，下载0，observation Partial/coverage Unknown；224在7.640秒exit0，App/Host/服务及原外层Job、EOF、reader均正常关闭。完整清单及各身份绑定在build/qmt-data-components-delivery-225/DELIVERY.json，实际值审计为222/AUDIT.json。

下一完整A模块为异步补齐后续回读：原下载只一次，缓存后到时在明确有限跟踪预算内回读并发布，当前固定空观察仍保持旧事实。该模块继续开发；当日补齐、完整市场/全天归档、App部分范围展示、当前C/B统一安装及生产资格继续未完。旧项目、实际QMT正文/策略和137/140保持，真实下撤单与生产切换0，完整goal active。


## 最终RS14与根已安装消费端组合

2026-10-29，根核12项最终源码/规格/QA及34份交付原件摘要，采用最终source-history-followup-001/package-005/installed（160成员，INSTALLATION SHA48e907ccfca84d6eb65eb07cdaacb1ee876dc19fdb80a4380228735826ddaf73），与根220普通安装的SDK0.15/Appa18数据消费切片组合；App/SDK wheel及公共锁依赖与交付相同。此App仍为冻结a17业务代码的元数据升级，不覆盖C完整a18。

236/main沿同一正常GET/lifespan、HPR e、真实认证SHM和Python3.6.8完整内存正文的SDK替身：先5根Partial，download立即返回而after为空，原owner稍后cache_callback出现数据后返回6根；原下载一次，6条通信记录，旧根不变。App与两个owner、源、全部线程/句柄/EOF关闭通过；237外层9.906秒exit0、tree_zero/EOF/join/resources全部正常，无强制关闭。实际QMT下载0、真实交易0。

根原件在build/qmt-rs14-root-236，INPUTS/SUMMARY和main结果绑定根220安装身份；最终模块完整细节见build/source-history-followup-001/HANDOFF.md及DELIVERY.json。原Unknown/整App重启续接、次数/期限耗尽及76回归沿相同最终输入复用其有效证据。真实QMT异步效果和旧182/218的v1空收据接续未授；旧原任务不得换ID重发下载。原137/140采集保持，NMR原生分钟受管接线继续，完整目标active。


## RS14最终包的真实QMT既有缓存链

2026-10-29，239材料将最终RS14包005与根220普通安装App/SDK组合，显式follow_up开启；沿原GH090完整内存正文与新认证配对，未部署新正文、未启停137采集。244准备阶段不启动进程/请求，随后248实际App正常GET先读旧5根、读取昨日新尾5根、混合最近10根及重复10根，六字段/标签与唯一QMT history_1m终态结果逐值一致；全部10根也与此前固定真实值一致。两段原provenance保留，observation为Partial、coverage为Unknown，原新尾窗202610281451..1455、preparation_state=NotNeeded。

Host Journal只有1项market.history_1m terminal/ok，history_prepare为0，未发生真实下载、下单或撤单。实际源文件SHA6be3b6e5…a9b89b保持，读到既有缓存不表示真实异步下载已验证。248外层10.218秒exit0、无强制关闭，tree_zero/EOF/join/resources全部通过；App shutdown_complete=true、reader_threads=0及正常owner关闭。采集69928/54752保持。原件和字段级AUDIT/DELIVERY在build/qmt-rs14-real-239，成功App输出在retry-246；同一私有配置/Journal正常续接，未换任务身份下载。

初次245只取得旧库存5根，尾部期望未满足，正常退出并保留material/APP-RESULT及图表原件；当时before捕获尚未规划、观察Journal为空。248以相同配置重新启动后通过；未凭旧5根宣称补齐成功，首次状态缺少独立连接事件快照，其具体就绪原因保持未定。准备243的诊断脚本inspect.py与标准库同名导致导入失败，重命名保存后244正常准备；该失败未启动Host/QMT请求。

此节新增真实缓存读取和最终包兼容资格；真实异步数据晚到、旧v1空任务接续、全天覆盖及统一策略主链继续，完整目标active。
