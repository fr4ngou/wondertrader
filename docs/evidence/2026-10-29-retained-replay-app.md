# 唯一1.1.2策略的App回测任务与可读报告

类型：模块C验证记录。状态：限定合成历史切片已完成双轴修正复审与精确交付；完整真实M1继续。关联[RR112-R7](../specs/retained-resonance.md#rr112-r7-app任务与报告)、[NBW](../specs/native-backtest-workspace.md)、[BPC](../specs/backtest-performance-comparison.md)。整个模块与真实M1继续in-progress。

当前后继为Appa23/runtime-005，原a22保留审查缺口与固定镜像。最终资格沿文末修正后继及002复审，a22候选不作为最终交付。

## 根因与实现

上一轮唯一1.1.2原生回放尚未接入App固定runner与旧报告消费者。新增backtest_reports统一选择新输入及报告族，retained_report持有有界校验和深不可变值；任务、归档、逐日记录、绩效和比较消费同一投影。报告绑定完整规范输入、配置、策略理论本金、历史假设、原生观察和输出。修正顶层模型时间与逐日摘要分别使用+00:00/Z造成父端拒绝的根因，报告生产者统一采用领域canonical_bytes。旧报告继续只读，新运行在创建runner前只接受唯一正式1.1.2输入。

用户页面仅显示名称/版本、回测时间、模拟绩效、持仓/调仓数量和简短说明。原始JSON、算法过程、哈希、请求/运行/进程身份和资格明细退出页面；API及内部原件保留完整事实。目录页面继续名称、简介、唯一最新版本。报告与比较按原React Query身份保存同查询成功结果及原读取时间；首次失败重读，成功空目录替换原目录。归档详情与绩效独立读取，取消原只为显示内部配置而设的请求前置依赖。

## 固定候选与输入

原件根build/retained-replay-app-001。当前普通runtime-004/wheels-004为App0.1.0a22、corea8/V1a6/nativea1及A当前SDK0.15.0，29发行、4729项哈希RECORD、5私wheel；pip check及wheel每成员/安装成员一致，无旧策略发行依赖、pth或pyc。SDK来自A统一原件build/native-quote-parser-v6-scope-001/unified/relocated-001/components/sdk，公共依赖沿既有24项精确hash。共享uv.lock由A集成，本轮没有修改。

输入沿上一轮SYNTHETIC-REPLAY-INPUT-008，125合成交易日、八证券1000行，显式最终批次前复权和历史收盘可知假设；保持来源/实时/券商/生产未授资格。原DLL4726…33b2e及ABI探针a7fd…b71b6保持；没有读取旧QMT、操作QMT界面、发真实来源/账户请求、真实下撤单或切换生产。

## 实际调用链与观察

- main-004：普通安装→固定StrategyHost/runner→原DLL→新报告validator→父端完成确认，124条原计算，非forced、exit0、pid_reaped/pipes_joined均true。
- http-003：实际回环Uvicorn/HTTP启动两次新回测；逐日、归档配置、绩效、两报告比较均读取原输出。停止并重启同App后只读同两份归档，无新运行，两个App/线程/端口正常关闭。
- 外部可视化根retained-replay-app-001/ui-002及spa-002：当前Appa22与生产SPA，页面再次启动一份原生回测，124条记录及末日结果可读；重启App读取三份原归档。1440×1000、390×844与LA浏览器时区下北京时间、无横向溢出、无原始JSON/内部身份、无框架错误层。比较GET503时保留同对结果，手动重读恢复；成功空目录替换旧内容，再从实际HTTP恢复。各代console仅一条主动注入503错误，warning0。Browser plugin not available，使用既有Playwright/Edge。
- http-bad-001：观察原ProcessJob.start返回的实际pid、poll=None、active_processes=1，再经真实HTTP取消；父端确认不完整、forced及reap/join，原请求重复认领没有第二次执行，未完成报告与归档不开放。旧版本输入pid=None且没有创建run目录。自有归档副本的result和原funds.csv分别改动后拒绝读取，恢复原字节后重新可读，最终保留owner0。
- 172后端回归覆盖唯一纯核/回放/报告准入、领域冻结、错资金/持仓/价格/读回、模型时间/配置/输出身份、空记录、截止、原工作区失败与恢复；120前端回归覆盖实际合成新报告、旧归档可读业务投影、错误/身份边界、比较刷新保留及成功空指标。TypeScript、正式编译及分块检查通过。

所有外层调用沿原scripts/native.py独占Job和有限总期限，成功tree/EOF/join完成。失败main-001、package-003及tests-001的九项清理状态均true、errors空且owner_retained=false。原App shutdown_complete、线程join及端口关闭另有实际收据。

## 失败原件与后继

main-001原生exit0但父端因顶层/逐日模型时间编码不同拒绝，诊断记录精确定位该条件；由生产者规范编码修正后，main-002及最终004通过。package-003的QA全局替换误改共享纯包路径，wheel数量断言失败；保留该根，004从原配方明确保持纯包来源后通过。tests-001缺少旧测试同目录import路径而收集失败，002加QA搜索路径后172通过。未为这些QA错误加入产品特判。

普通安装与HTTP/浏览器均使用合成历史，真实前复权因子、实际持仓周期、B同核实时/接管、真实隔离委托撤单M1、全模块安装/升级回退仍待组合。独立审查结果与精确文件/制品SHA在本根后继清单登记；当前切片通过不表示模块完成或生产已部署。

## a23独审根因修正与复验

001 full规格审查gap/一项P2，规范审查gap/三项P2，原报告及38源镜像review-source-001均按原SHA保留。已独立证明a22报告在摘要全零但NSQ仍正权重、冻结basis时点未来、execution_policy异值时被父Host._result接受；比较输入未包含前复权analysis/current_view/model；旧V2 codec仍导入已退役variants包。这些均为有效缺口，原正常主链资格保持其限定范围。

a23在retained_evaluation抽取唯一目标转换及原NSQ前代交接/推进，生产回放与validator共用。validator从初始空状态逐日复演原数量推进，比较完整Outcome和previous_status；合法前代未收敛保持原逻辑。比较源摘要覆盖原值历史、前复权分析/因子、当前实收版本与历史模型。旧V2只读codec固定原版本协议身份，去除对已退役计算发行的运行依赖，旧新运行继续拒绝。

普通runtime-005/wheels-005仍为29发行4729 RECORD/五wheel，Appa23。main-005新原DLL124条完成；VERIFY-005从最终安装读取原a22有效124条，并在父Host._result拒绝三个原触发变体；8个封存V2 header及三份实际configured/旧V2/当前V2归档的绩效与末日均通过。176源码后端回归包含新增冲突及分析/因子比较差异。tests-003因QA在runtime-005安装完成前启动而缺少纯包，原件及九项回收均保留；004使用已完成且同版纯包环境通过。

http-004再次完成实际HTTP两次新回测、报告/归档/绩效/比较及两代重启；http-bad-002复验真实回测Job取消、原请求不重复、旧输入零runner和原件损坏恢复。当前a23/spa-002的ui-003完成页面第三次新回测、124条/末日、两代归档读取、宽窄屏/LA时区、比较失败保留/恢复、成功空目录/恢复及无技术身份渲染。main-cli-002安装CLI也新完成124条。全部App/线程/端口及外层Job正常关闭；此处“取消”为隔离回测进程取消，真实券商下撤单0。

前端源/SPA与120项已通过输入未变，a23浏览器组合实测另行确认。普通ZIP搬迁安装已验证a22候选的29发行/五wheel/自身site导入及CLI入口，a23最终ZIP和复审、完整M1及整体升级回退分别记录。

## 002复审与精确交付

002规格与规范delta均complete，原报告关联、比较身份、退役依赖三项P2全部关闭；001 gap保留。规范审查保留一项非阻断P3建议：model_states为有界诊断JSON，当前不作为NSQ执行状态或页面业务渲染输入，后继可收紧其诊断结构。完整纯核结果沿冻结输入复现，部分摘要不授完整数学重演资格。

冻结002为39源/800原件，SHA d03c0f7a7bcc5fe085430a1bf225131828de3685db77f6eaf95c456d8695c56c。规格002 SHA ce61522e8937fceb9df6033b3bc8dd765ea132e0b649f8870511156790eadf7b，规范002 SHA 0d744eead171e10427d41d335da3b22ded8f56754e0348c8f5c3138134f733d0。两轴分别独立验证原父端冲突拒绝、合法前代未收敛、四类来源比较、旧归档以及最终安装；所有审查命令终态。规范工具一次逐文件resolve超30秒，原九项清理均true且无保留owner；仅缓存同目录resolve后在原30秒预算通过，原失败保留。

最终开发ZIP为guanheng-retained-replay-development-002.zip，28成员，SHA 8e46710f11dc27cb4ef0380b7dbc8908b81fb890ab9e81197d49be0e1b82bbcd。relocated-002从ZIP解压在全新venv按随包hash清单实际安装、pip check、自身site导入/create_app/CLI help及SPA逐字一致通过。原URL安装29发行4729哈希RECORD；find-links搬迁29发行4724项，少五个安装来源direct_url附加记录，五wheel137个非RECORD成员仍逐字相同。未把搬迁记录数冒充4729。最终源、原件、四审查、ZIP/成员及作者状态文档分别固定在DELIVERY-003.json，A唯一集成提交，C未暂存/提交或部署。

A后继已交八只ETF实机复权事件，FACTOR-INPUTS.json SHA 2f0d60e4c3b751434db4e9ba98377a7cc85494f86bc91fa843ba1f7ec0d13cce；当前仅事件序列，analysis_ready=false。逐日同基准倍率与带日期原值配对仍归A，空事件表保持原空，不合成全1，丢日期的早期日线不授绑定资格。下一主线继续消费A完整分析输入与B实际周期/唯一核CTA候选，闭合真实1.1.2的BT→RT目标→隔离委托撤单→页面链；共享uv.lock更新、完整模块与升级回退继续。整个goal保持active。

最终作者状态同步时保留共享文档中新插入的A复权进度与空行，独占段落已按实际锚点完成更新。DELIVERY-002为作者同步前快照，最终DELIVERY-003沿同一产品/39源镜像/800原件/四审查和ZIP，另绑定最新状态文档；产品代码与制品保持原字节。
