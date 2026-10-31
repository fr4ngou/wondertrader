# 完整App与异步来源的四代候选切换

类型：开发集成验证记录。状态：pass（ACU运行与双轴审查范围），完整模块C/M1继续in-progress。关联[ACU-R1..R3](../specs/app-candidate-upgrade.md)和[COP-A1/A2/A8](../specs/guanheng-operator-platform.md)。

## 接线差额与实际实现

A已交最终RS14异步补齐组件，原组合使用旧App代码的31发行数据消费切片；C完整业务App有35发行及新的来源范围界面。此前缺少这两个独立候选对同一任务、偏好和补齐结果的跨代证据。本轮保留两个实际安装、同一最终RS14/HPR e与原数据/状态根，依次验证旧App/SPA→完整C→旧App/SPA回退→完整C恢复。

生产代码沿精确[HCO003](2026-10-29-source-history-chart-observation.md)及A最终RS14复用，新增内容仅为规格、隔离验收与运维说明。App/SPA回退保留RS14作为原v2任务owner，旧RS13没有新v2收据的降级读取资格。两个App均标记a18，明确为两个开发构建，以wheel/安装/SPA SHA和独立Python入口区分；没有同版本覆盖式正式发行。

## 固定输入

QA根为`build/app-candidate-upgrade-001`。SOURCE/QA/RAW及frozen-*镜像共15来源、22 QA、201原件；REVIEW-INPUTS、CANDIDATES、SCREENSHOTS和CONTROLLED-INPUTS绑定完整身份。私有配置、认证及准备原收据仅留原ACL根，公开镜像不复制private正文。

| 输入 | 固定身份 |
|---|---|
| 基线App/安装 | A的metadata-only a18，wheel `44a29f4980ccd522b396b497ae1352404927be980c37ac2ef018603b85294c7b`；`build/source-history-followup-001/app-runtime`，31发行/4743 hashed RECORD/7私包，SPA011 |
| 完整C App/安装 | a18 wheel `04a7abb8d8e684b2d99660d81c68c91ae46acd895bb019d7bf9de0e3ff5842fa`；`build/source-selection-display-001/runtime-venv-001`，35发行/4787 hashed RECORD/11私包，SPA003 ZIP `cdf772c2b21ece9b0673d5b288ee572cead43fb30db673418c1dc4df0cfe00ae` |
| 最终RS14 | `build/source-history-followup-001/package-005/installed`，160成员逐文件SHA一致，INSTALLATION `48e907ccfca84d6eb65eb07cdaacb1ee876dc19fdb80a4380228735826ddaf73` |
| HPR e | INSTALLATION `5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3`，592成员逐文件SHA一致 |
| SDK0.15 | 基线wheel `34579862be4dc777bf2f10cceff64d0df2a242a7ee78f368c06e9a4c744287ab`；C wheel `33bf4675a063c0cd46d6a510d582d7c2f4f9755b9e3b46d4e3a69cc121cdc335`。17非RECORD成员仅__init__.py物理换行CRLF/LF不同，文本归一后逐字一致，其余16成员字节相同；每环境均按自己wheel原字节核对 |
| 最终来源/QA/原件清单 | SOURCE `c0af4c888006123153ed1faf922244b02c77649151aad02d71ebba3abfc79769`；QA `bf12db531f52ad9945a7941cc3e4bae70158f4f67f3b17af4652c3be80357f18`；RAW `3f664e093955189bc0a05c6bbe92329d8271afc1ab5d1c7e9d389dd18a928455` |

完整C新增AI/risk/rules/V1四个发行，signals a3→a4、V2 a2→a3，原公共依赖版本保持。此处证明共同安装与应用兼容，不增加各算法的原生执行资格。B后继执行源仍按HCO已记录的漂移独立处理，本轮执行入口未配置。

## 四代主链

全部运行经原`native.run`、创建期隐藏Job、有限总截止和输出。最终`run.py main 003`外层33.813秒成功退出；每代使用实际安装Python、正式ConsoleSettings/lifespan/SDK/SourceMarket/HPR，未注入App工厂。SDK替身仅在真实3.6.8解释器和原SHM/Journal上运行，有限六根来自已有离线原值，原根所有已绑定文件SHA前后保持。

| 代际 | 实际结果 |
|---|---|
| baseline | 旧App/SPA以source-store读归档5根，Journal0。实际页面添加510300.SH个人观察，一次PUT后版本2，保存watchlist_id/symbols/updated_at及文档SHA；正常关闭 |
| upgrade | C完整App/SPA显式启用RS14 follow_up。补齐函数返回后缓存仍空，实际GUI为Partial5/2000、窗口读回0；父先从原v2收据保存UUID/prepareSHA/原跟踪截止，与HTTP原ID一致，再放行源owner的缓存回调。手动重读得到6根、窗口2根、原分段4+2及三单位，替身download仅一次；正常关闭 |
| rollback | 旧App/SPA在同一RS14/工作区/Journal读取同6根；旧界面保留自身展示能力，未冒充有HCO说明。个人观察与原数据结果保持，原通信记录没有增加；正常关闭 |
| restored | C App/SPA恢复后完整图表DTO与升级后逐字段相同，原UUID/准备正文SHA/原D保持；个人观察GET与文件字节保持。Journal总5条不增加，download1/cache_callback1；最终正常关闭 |

同一HTTP端口56705四次正常绑定/释放；每代HTTP线程join、两个读取池线程0、SourceMarket/HPR closed、forced=false、pending=false，Job/进程句柄/双管道EOF/reader/monitor均完整关闭。共享源替身始终在自己的原owner线程，最后unsubscribe/资源关闭，forbidden_attempts0。真实QMT、真实download、真实账户/委托/撤单均0，137/140和WT核心未操作。

Browser plugin not available，使用现有Playwright/Edge。实际`http://127.0.0.1:56705/market`（现已关闭）、1440×1000与390×844、LA浏览器时区，四代标题/主体/无框架覆盖/图表/上海标签/观察列表/详情/重读及横向溢出均通过；console error/warning均0。四代浏览器共9图在visualizations当前线程根下`app-candidate-upgrade-001/main-003`，SCREENSHOTS逐张SHA绑定；已人工查看空缓存5根桌面图与恢复6根分段手机图。唯一写请求是基线一次个人观察PUT，其他请求均GET。

## 异常与恢复

| 最终入口/原件 | 观察 |
|---|---|
| install_probe-final.py | 使用原30秒每环境预算，基线/完整C实际各1.188/1.234秒，31/4743及35/4787全部RECORD路径/大小/SHA、7/11全部私wheel非RECORD成员通过；SDK-COMPATIBILITY-004绑定精确差额与两个原Job关闭 |
| unknown003 | 源SDK阻塞5.3秒形成Unknown；先保存真实空after、原UUID/prepareSHA/D，正常关闭整个首代App/两个owner再启动第二代，随后原源owner缓存回调发布6根。最终C HTTP1.7保持Unknown与原ID，未把读回成功改报准备成功；Journal5，下载1，两个App完整关闭，外层19.875秒 |
| attempts001 | 两次后续观测耗尽，返回旧5根Partial、窗口0、原CallReturned/RID，重复不新增源任务；SDK原因与原receipt保留耗尽事实，App按原有限字段显示，不从自由文本推导新状态。Journal5，下载1；外层20.719秒及完整关闭 |
| total001 | 原总跟踪期限耗尽，返回旧5根Partial/CallReturned，重复不延长期限、不新增源任务；Journal3，下载1，完整关闭；外层17.547秒 |

HCO003未变的正常/空/503/恢复/实际停止和Unknown中文映射回归继续按原源身份复用。上述异常分支新增实际C公开HTTP证明，未逐分支重跑浏览器，也未把组件回归冒充真实窗口的UI操作。

## 保留的验收失败

- 两次父脚本解析错误在业务启动前退出；main001原native子端解析错误已完整清理，未创建业务案例目录。源码生成器后继先AST解析再启动。
- 首个安装探针30秒超时，九清理标记全true、cleanup_errors空、owner_retained=false。根因是对每个RECORD条目重复解析同一目录；改为每目录解析一次，仍逐文件准入最终路径/大小/摘要并拒文件符号链接。最终恢复原30秒预算实跑通过；初次失败和中间50秒探针结果保留。
- SDK完全字节相等的初始假设失败。静态比对定位唯一入口文件换行差额，最终只允许该特定文件的CRLF/LF差额，所有其他成员仍严格逐字比较；没有把代码差异放宽为任意同版本兼容。
- unknown001中缓存回调抢在初始SDK断言前到达，产品已返回6根；未知任务重启验收未完成，原失败保留。后继门控源替身回调，先保存空缓存/原ID再重启，未改变产品逻辑。
- unknown002已完成产品两代与最终Unknown6根，但QA尾部引用另一函数局部counts导致UnboundLocalError。unknown003在最终HTTP读取前保存本层计数并核无新增，最终通过。前两轮App/源及外层清理证据均保留，九项标记全true，后继成功没有改写前轮状态。

最终门首轮在文档check发现并发新增MRC规格尚未索引，未进入finalize、未创建交付快照；原失败九项清理全true/errors空/owner未保留。补入该已存在规格的索引链接后沿相同门复验，原失败保留为FINALIZATION-FAILURE.json.initial与check-final.log.initial。

## 范围与下一步

以上完成当前App/SPA候选与A最终异步来源的限定组合、同状态回退与恢复。它没有授予数据组件RS13读取RS14 v2状态、真实异步下载、当前B完整候选、所有策略M1或生产发布资格。当前NSB仍要求明确amount=CNY和逐时点可知数据，而真实交付127的amount单位/历史首次可知未知；后继历史日末模型准入需分别保存真实实收与模型假设，不能把来源日期标签直接改报历史可知事实。

独立规格轴及规范轴均complete，新增P级发现0。报告位于本根REVIEW-SPEC.md（SHA256 `7602da7ad64e7c5b8672c014486809d92e345d88ef80e8cef03246eff4cfb91e`）及REVIEW-STANDARDS.md（`7889ebe7e0f1499e3bfb1bd2e1a4e80c358f2ca33cd770e9722ca544ae9c29e0`）；两者分别核当前15/22/201、全部安装/制品及实际恢复。最终原native门依次执行project.py check与finalize，检查当前输入后保存八文档快照及DELIVERY；门实际结果和闭合耗时由同根FINALIZATION.json及其日志拥有。完整模块goal active。后继优先闭合上述真实历史/原生模型与B稳定候选的M1差额，所有保留策略、整模块升级/回退及中文运维材料继续。
