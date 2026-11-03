# 原生回测操作员入口

类型：功能最终规格。状态：accepted。前缀：NBC。细化[NSH](native-strategy-host.md)的本机操作员调用；当前运行范围为唯一正式1.1.2，观衡沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)只读消费报告。

## NBC-R1 职责与准入

操作员通过已安装的`python -I -B -m guanheng_wt_runtime.backtest_cli`，显式提供受管安装manifest及SHA、预先建立的运行根、冻结会话JSON和回放起止时刻。复用WT-B01/B02原回放/撮合及NSH进程owner；CLI不创建原生上下文、不复制输入解析、资金或撮合逻辑，不接终端、账户、HTTP或共享内存。原观衡命名空间入口按历史制品保留追溯，当前安装边界按R5。

安装路径和摘要属于本机操作员的受管配置，不能出现在行情请求中。会话文件只能提供既有值契约，不能替换命令、模块、DLL或基础资料绑定。复用父宿主的本机固定盘、路径、重解析点、文件类型和有界文件读取检查；最多16MiB，不从stdin解释代码。缺参数、非法范围或不合格输入在启动原生前拒绝。

CLI与薄Porter共用纯时间窗口准入`validate_backtest_window(start,end)`，原解析/日历/顺序逻辑保持单一实现。CLI在读取会话和创建宿主前验证12位日期时分、真实日历及起止顺序；非法值不能进入runner或装载DLL后再拒绝。辅助函数不执行文件、原生或终端操作。

## NBC-R2 期限与取消

默认总期限沿NSH的1800秒，操作员可收紧到0.1秒；参数准入、文件读取和创建宿主从同一次monotonic起点计量，传给NSH的期限仅为剩余预算。剩余不足0.1秒时直接拒绝，不能重置完整预算。CLI没有重试、排队或自动建目录/清理历史行为。

SIGINT、SIGBREAK及可用SIGTERM只设置交给NSH的cancel事件，由原owner沿现有期限停止并回收。临时信号处理器在退出时恢复；信号不能跨线程直接触碰原生ctx或假报完成。父死亡回收资格继续由NSH负责。

## NBC-R3 结果与副作用

stdout只输出一条不超过8KiB的ASCII JSON回执，schema为`guanheng.backtest-cli.v1`，包括run_id、status、reason、请求和安装摘要、输出目录、pid、exit_code、forced、pid_reaped、pipes_joined、elapsed_ms和scope；完整业务报告保留在原宿主输出，回执不重复保存全历史。拒绝时输出明确中文原因及无成功状态，不回显输入内容、凭据或堆栈。

缺必填参数、未知参数、非法数值类型及业务准入失败均进入统一回执边界，stderr不输出argparse对原argv的回显。拒绝回执保留完整字段；不存在或未知的run/pid/退出/回收事实显式为null，不能因未得到HostResult就省略字段或声称已回收。scope区分准入前未启动与owner结果未知。显式`--help`/`-h`属于固定帮助模式，只输出不含原参数的说明，退出0且不创建宿主，不作为运行回执。

exit0仅对应NSH返回completed且非forced、exit_code=0、进程和管道均回收；busy退出3，其余失败退出2，已请求取消的不完整运行退出130。回执不授真实来源、实盘或生产资格，CLI不请求委托/撤单、不更改终端/权限，也不引入新数据库。

## NBC-R4 验证

覆盖参数/非法摘要、文件容量/路径/重解析点、读取耗时扣减、准入超期不启动、完整/不完整/繁忙/取消及信号恢复、输出预算和不伪报成功。独立安装后的真实原DLL命令须完整核回执、原始输出及进程回收；替身测试只授CLI路由和错误语义。产品、独立审查、整包和生产分别登记。

## NBC-R5 独立WT运行侧回测

状态：accepted / in-progress。按[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)将唯一正式1.1.2回放的Porter、事实投影、业务session、报告准入及原NSH父子owner迁到`guanheng_wt_runtime`。独立入口为`python -I -B -m guanheng_wt_runtime.backtest_cli`，参数和回执保持R1–R3；安装绑定显式使用`nsh-wt-install-v1`，固定runtime模块和唯一策略纯核/数量包，拒绝观衡/Web安装依赖及旧安装绑定。原`nsh-run-v1`请求及`guanheng.retained-replay-report.v1`报告语义保持，未安装观衡的全周期运行才授本项资格。

复用原WtBtPorter、ABI探针、基础资料检查、进程Job、同次绝对截止、零队列根租约和完整结果/原生输出身份校验。仅迁移现有唯一1.1.2链，旧策略族不进入运行发行；历史报告读取由观衡继续负责。独立包不引入持仓、资金、成本或撮合实现。原运行入口的兼容导出按文件owner集成，迁移的来源/目标文件和SHA明确登记，兼容接线完成与独立运行资格分别验收。

安装侧调用`backtest_installation.write_binding(output, python=..., native_root=..., abi_probe=..., basefiles=..., seconds=60)`，以安装后的明确路径复用同一运行期验证器，完整核site/native库存、解释器、原DLL、ABI及五类基础资料后独占写入新manifest并返回原InstallationBinding。总期限0.1至120秒，已有文件保持；不自动建目录或启动进程。普通安装采用无隐式启动钩子的标准环境，`.pth`/字节码和观衡/Web目录仍在原生启动前拒绝。

本策略环境的发行闭包固定为`guanheng-wt-runtime`、`guanheng-market-client`、`guanheng-strategy-core`、`guanheng-strategy-native`、`guanheng-strategy-v1`和`tzdata`，对应顶层包及唯一dist-info/METADATA名称、版本保持一致。额外发行、旧策略族、顶层启动文件及缺包由同一安装验证器拒绝。通信Host使用其独立角色环境；本绑定不把Host或观衡的依赖并入策略执行环境。

R5-C1：普通新环境仅WT运行及现有六发行依赖，使用A真实冻结全历史输入，经安装CLI→原父owner→原runner→原WtBtPorter，完成全部闭合日期、唯一核/NSQ、原持仓/费用/userdata及完整报告，进程/Job/管道关闭；同版安装仍能加载已有RT入口。R5-C2：旧绑定/错包/错输入族、错误摘要、错窗口、取消/超期、繁忙及报告/原生输出身份失败按原边界拒绝，既有有效测试复用前核输入。R5-C3：原生BT和RT共用同一纯核、数量核及业务接缝，全周期可见前缀/目标与成交模型逐项比较；单日flat目标比较不代替全周期。安装制品、独审、兼容接线和统一候选分别登记，真实交易及新增框架行为沿原授权边界。

## NBC-R6 逐日基准的配置入口

状态：accepted / in-progress。细化 NRT-R28-C4，复用 WT-B01/B02 的原 Porter、原 RetainedPerDateBacktestSession、NSH 和本 CLI。逐日原价、因子与分析窗口归 A 的 ReplayCatalog，B 只接配置、输入和结果身份。默认最终批次输入、绑定和报告沿原路径。

新的纯值输入 `guanheng.retained-per-date-replay-input.v1` 精确包含 `schema`、`session`、`source`：session 是原 `guanheng.retained-replay-input.v1`，source 是 R28 原 `guanheng.retained-per-date-source.v1`（manifest_sha256 和有序 windows 日期/SHA 映射）。完整输入仍限16MiB，日期1..4096且为递增有效ISO日期。会话不含代码、DLL或市场目录路径。

本机部署调用原 write_binding 时可显式给 `replay_catalog={path,manifest_sha256}`；目录为绝对受管只读数据路径，manifest摘要为小写SHA256。由此生成绑定的 report_schema 为原逐日报告族，附同一 replay_catalog 字段。省略该配置保持原绑定。绑定与会话的manifest必须相同。逐日角色在原六发行之上精确增加 `guanheng-native-analysis-core`，由其提供 `integrations.guanheng` 原API和 `guanheng_market_client.qmt_native_replay` 公开重导出；原market-client 0.15.0 wheel及其已有成员保持原身份。部署绑定覆盖七发行及B原逐日session的全部安装字节。默认最终批次角色继续原六发行。CLI参数与回执保持R1–R3。

Runner在原受管Job内，通过固定安装import调用 `ReplayCatalog.open(path,manifest_sha256)`，不导入行情目录内代码。此API的 .dates/.window 和原来源字节校验继续由A实现，B保持每轮原窗口SHA/日期/原生raw配对检查。SDK公开导出由A集成并交付固定core后继wheel；B消费该原制品，公共生产文件保持A所有。早期B六发行API装配副本仅保留为准备记录，正式逐日入口使用A交付的七发行角色。所有读取、准入、回放和回收沿原同一次截止，原JSON、文件和Job容量保持。

父端接受两种明确报告族，按本次绑定选择唯一一种；逐日报告必须有本次source绑定、historical_model=null、原session规范编码摘要与source组合摘要、完整原生会话/配置/策略资本和输出身份、完整闭合日期。逐日模型不改变来源接收/可知时间，历史15:00假设与真实RT差别沿R28保留。报告继续由原validator与投影接口消费。

R6-C1：七发行逐日角色普通安装，实际CLI→原NSH/runner→原ReplayCatalog→原逐日session/Porter，401日期400计算及400报告投影，内外完整回收；原六发行最终批次CLI回归。R6-C2：源/安装/报告族失配、坏日期/窗口/原价/单位、超期/取消及结果身份失败沿原owner拒绝，新增原生/来源副作用逐层核实。R6-C3：精确源码/SDK候选及安装SHA、报告/输出、独审、离线搬迁、C归档消费与统一候选分别验收，完整400期RT/BT继续独立完成。

## NBC-R7 WT父责任层发布原完成证明

状态：accepted / in-progress。沿ADR-0012和NBW-R6，将独立运行后的完成证明接到WT操作员入口。原WT-B01/B02继续保存报告、资金/持仓、费用和原生输出；本项只保存父端已核实的退出/回收事实及原件摘要。当前stdout完成回执在CLI退出后缺少稳定文件供只读观衡消费；原子发布原NBW证明补齐该调用链。

操作员显式使用`--archive-label LABEL`启用发布；LABEL为1..100个无控制字符的展示文字。省略参数保持原CLI参数、回执和输出行为。持有最终原HostResult的CLI在completed、nonforced、exit0、reaped、joined且原报告准入成立时，调用WT自有`backtest_completion.publish_completed(result, work_root, label=..., max_seconds=..., deadline=...)`。截止沿CLI原总D，发布失败保留真实执行完成事实和所有原件，不重跑、不扫描旧目录补造成功、不另起完整预算。

复用`completed-archive.json`和`nbw-completed-archive-v1`原合同及16KiB上界，原run_id作为CLI本次owner_id/request_id；这两个字段仅标识该次独立CLI调用，不授已退出进程的控制权。配置保留标签、原请求backtest参数、Host已准入并规范编码的运行会话SHA及原总期限。configuration.session_sha256必须与原request.session_sha256相等，由发布者从已核原请求唯一派生；调用者不另传该身份。操作员输入文件可包含等价时区写法、空白和省略的可选字段，其原字节SHA沿来源/输入CAS单独保存，不能替代规范运行身份。请求/安装/结果/报告、五类原基础资料及原生输出按原摘要绑定；策略报告scope保持原族，旧NBW receipt.scope沿原隔离BT资格字符串供既有读取器兼容。观衡直接使用原BacktestArchive只读校验与投影，无需接管WT进程或重新计算金融事实。

发布沿本机固定盘/无重解析路径与类型/链接准入，先独占写临时文件、flush/fsync、回读，再Windows不覆盖rename与最终回读；既有相同证明可确认，冲突和未知状态保留原件。请求发布的CLI回执增加一个有界archive对象，字段为status（available/unknown/not-applicable）、receipt_sha256和reason。available仅在回读确认后成立；执行完成而发布失败时status保持completed、archive为unknown、CLI exit2。未完成/取消/busy保持原退出语义，archive为not-applicable。默认未请求发布时无archive字段。

R7-C1：普通新安装的实际逐日400期CLI→最终父HostResult→原完成证明，再由独立观衡读取同根配置、全部400记录与原绩效；固定批次兼容和实际HTTP/页面分别验收。R7-C2：未完成/reap/join不全、原件漂移、同身份重复/冲突、坏路径/类型/硬链接、容量/期限、临时写入/rename/回读失败保留原件且新Native执行0；默认CLI回执保持。R7-C3：冻结源码/安装/包/证明身份、实际退出清理、独立审查及C只读交接分别登记。旧R6目录保持未归档，不补写；完整RT/BT和模块B继续独立验收。

## NBC-R8 原报告读取的字节预算与消费性能

状态：accepted / in-progress。细化R7-C1和RR112-R7。自有report_values的JSON快照继续先复制有限树、逐节点核类型/深度/数量及截止，之后由原唯一报告validator核领域事实，并沿原深不可变冻结及按需投影消费。8MiB字节额度按标准JSON的ensure_ascii、紧凑分隔和有限数编码精确计算，恰额度接受、超过一字节拒绝；键、引号、转义、标点、负数、指数和非BMP字符全部计入。替换通用逐值编码的实现须与标准编码字节边界等价，保持每128节点及最终检查、原控制异常对象和调用者数据隔离。

R8-C1：原两份各400期的不同完成目录独立准入，原5秒HTTP比较、坏证明409及同身份恢复结果相同；来源/原生输出仍每次核验，读取不运行新回测或创建交易owner。原版和后继的耗时分别实测，偶发成功不能消除既有超时证据；候选性能和普通安装/HTTP资格按实际输入、版本与负载登记。R8-C2：标准JSON精确字节、有限类型、节点/深度、复制/冻结/投影隔离、原取消/截止异常及既有报告族回归。R8-C3：固定源码/原依赖的独立安装、制品摘要、双轴审查和C/A接线交付；C页面及统一候选由相应owner另验。
