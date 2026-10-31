# 午后采集观察与Writer生命周期实施

时间：2026-10-28。类型：进行中的现场与隔离验收记录。生产切换、真实下单和撤单均为0。

## 已确认的业务结果

原SHM全推进入原生DataKit，旧隔离存储实际有6922份一分钟DMB（SSE3254、SZSE3668）。三个样本600000、000001、510300回读标签13:01—13:16，各16根；该计数含当时未结束的最后一分钟，完整分钟及量额资格另验。样本见build/qmt-live-afternoon-observation-001/SAMPLES.json。

旧采集状态实际停在14:02:45，旧原生消费者停在14:02:34，登记子进程已不存在且缺少最终控制器receipt。14:41读取旧状态不能证明仍在运行。中断恰邻Node诊断运行时重置，直接退出原因尚无句柄/终态证据，保留原目录，不授正常关闭。

已从独立隐藏控制器恢复原始记录及隔离原生消费：build/qmt-live-quote-capture-20261028-recovery-001 与 build/qmt-native-live-20261028-recovery-001；限定原始截止分别15:31:45、15:28:52，结束与数据结果仍待实际receipt。原采集策略正文及其他运行策略保持。恢复并非全天完整资格。

15:19:29的新原始状态接收812574条、6925个证券，connected=true；最大源时间13:31:43.395。15:19:24原生计数809636，Writer处理同数。源时间持续推进但大幅滞后，实际实时性未通过。原生界面个股成交更新至14:08/14:24，官方说明个股行情与全推所依赖的中心不同，不能据界面更新认定全推缓存新鲜。

## 诊断及清理

原内置get_full_tick对照探针两次等待未绑定，业务POST均0，外层Host/App/进程树已正常回收；中间一次准备文件缺失失败单独保留。外部quoter仅返回10月23日缓存；纯内存测量量化了重复profile验证开销，均不足以确定90分钟源延迟根因。详见build/qmt-live-afternoon-diagnosis-001/REPORT.md。

界面连续两次无法激活后停止自动输入；用户确认停止SHM_READ_PROBE。其正文已逐字恢复，SHA35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae，恢复收据build/qmt-live-full-tick-compare-001/RESTORED.json。此探针与继续运行的GH_WT_MEMORY_VERIFY分别管理。

## Writer开发和当前资格

用户“你改吧”已批准L+M两文件范围，仅隔离开发/验收。固定上游08b230dd，统一源码差异位于integrations/wondertrader_lifecycle/writer-lifecycle.patch；受控构建生成候选，工作树旧CORE005冻结差异保持。

自有Session固定writer.module选择，缺省/原模块维持WtDataStorage，显式WtDataStorageLifecycle选择候选；新增archive_and_close先原生归档后排空收束，实际持久数据用Helper核验。close/marker不能替代完整回读。

第一候选实际完成401证券及6982证券（27928合成tick→6982DSB）主链、两个样本两分钟原值、关闭后新实例重开、12秒观察。主链线程观察区分固定MSVC Writer入口与其他进程线程；原生公开接口另核sync/async/idle线程实际HANDLE退出，async积压512项排空。相关完整规模full-001/002最初因将ntdll其他线程归作Writer而失败，记录保留；修正观察归属后的full-003通过。此证据属于旧候选003。

审查提出初始化/扩容/归档I/O返回检查，第二候选004已编译成功（外层exit0、非强制、树0、EOF/join/资源关闭）。最新patch0bd88ea7bc98d382f65cf35baf5de59255f9491e6616c6fbba8d99c0f4cac227，候选DLL e6b85c26d793114f436eeff6bc70181d9a065107b2c2022e6a3e88be1c622ee2。读取侧同类失败保护仍在补齐，最终独审及新身份运行未结束。默认原DLL、原分钟算法、10秒检查/600秒过期和DMB/DSB格式保持。

## 下一步及剩余风险

完成最终读取失败保护→新候选编译→全市场主链及原阈值实际过期、dumper、重入、初始化/存储失败回归→独立delta审查；获取恢复采集的实际归档/关闭及Helper数据收据。源延迟根因、真实量额/完整分钟与全天覆盖仍未通过。原StateMonitor非allday模式的生命周期另需资格核实，本项不扩改其他框架文件。当前无需用户新增决策或操作。

## 后继：恢复采集实际关闭与最终候选主链

恢复隔离原生消费者已正常归档并返回close；外层qmt-native-live-recovery-20261028-001实际exit0、非强制、进程树0、EOF/读取线程/资源关闭，2069.454秒。实际6925份DSB；原Helper回读600000、000001、510300各10根，标签13:25—13:34，交易日20261028且顺序有效。该输入仍是严重滞后行情，首累计快照及最后未结束分钟不授完整量额/当天资格。原生实例使用候选003，独立新构建不热换运行DLL。回读收据build/qmt-native-live-20261028-recovery-001/READBACK.json及只读Job均通过。

最终读取失败保护补齐，差异patch e4a6301b1b6713987862ab792735738117f210d6bd7bfba8b5ebb2f2978aa64c，候选cpp970a12c216d3dc673a0d9e9cb50a690a0c31141aa6f921aa75099501ff4bf84b、h3f1d94eda6e487567dbf6cfb63b9c6bc6d27210e4fa4bca4682e68cf035dc417。独立delta2确认原2P1/1P2及读取侧缺口均在源码闭合，无新增P1/P2；运行资格另核。

最终候选005实际235.515秒编译通过，输入清单d2fb9721ad94ae2d31ce617bb1f4113329ed45e7d6d2f07312056533f9d2e32d，适配DLL4b489ae4f503ee97a51dbdd7529795241df45bea8d8dc54b1e8783e11c077d9c。新候选全市场主链full-004实际通过：6982证券/27928合成tick/6982DSB，原Helper样本回读、关闭和新实例重开、关闭后12秒线程观察，外层90.656秒exit0/非强制/树0/EOF/join/资源关闭。原阈值过期及其他错误/重入模式仍在本次独立隔离目录运行，以实际终态补充。

最终候选005的sync/async/idle/reentrant/dumper/init_failure/storage_error/read_error八模式已全部通过，103.141秒，外层exit0/非强制/树0/EOF/join/资源关闭。合成数据经原Helper验证：正常及重入两证券各两分钟；写出/历史读取失败时000001的一根实时DMB原值保留，故障DSB三字节cut逐字保持；dumper接到四根拥有副本且原DSB不重复写。异步积压512项排空、同步一次重入总513项、初始化失败及重复release均沿公开接口核实线程HANDLE退出。收据build/qmt-writer-lifecycle-native-cases-002/VERIFIED.json。原600秒过期单独进行，结果尚待记录。

原始记录接收器亦按原截止结束：15:31:10 receiver_closed=true，原外层实际exit0/非强制/树0/EOF/join/资源关闭，2907.218秒。最终1101608条/6925证券，最后源时13:34:28.338；57个清单成员未收到有效快照，原因待核。两恢复进程此时均已关闭，QMT原全推策略继续运行，但当前没有活跃终端外持久采集实例。此有限观察结束不授长期受管采集、自启或完整收盘资格。

## 后继：真实原阈值测试失败与可用当日分钟入口

expiry-001外层603.765秒exit1，完整回收。probe实际通过原600秒后至少两条过期日志、后续写入/归档和release；失败在observed_thread_handles：观察3条/signaled2/timeout1。旧探针把进程所有新增线程计为Writer，且未保存起始模块/线程id；当前无法确定第三条身份，也不据此宣称Writer漏join或测试已经通过。正在补齐固定MSVC线程归因及逐条等待事实，然后以相同生产阈值复验；生产代码不因这条未定位的观察失败改变。

15:38一次独立厂商API只读查询get_market_data(close,三样本,period=1m,count=1)取得Panel，三证券尾均20261028 15:00:00，外层4.531秒exit0/树0/EOF/join/资源关闭。它与旧tick/quoter缓存入口不同，为自动取得当天分钟数据提供可继续验证的路径；当前仅close尾部，不授完整OHLC/量额/全天/全市场资格。输入/结果build/qmt-live-afternoon-diagnosis-001/{external-minute-cache-probe.py,MINUTE-CACHE.json}，正在准备三样本完整字段与既有Importer/Helper实链。

## 最终隔离验收汇总

最终生产候选仍为005/e4a630源码，无新增核心修改。全市场full-004、八短模式native-cases-004及真实原阈值expiry-002均通过。expiry-002实际603.391秒，原600秒后两条expiry日志，后续两证券各两根经原Helper核对，两个ucrtbase实际HANDLE均signaled；另一ntdll线程wait258单独记录，外层exit0/树0/EOF/join/资源关闭。此项使用冻结probe be2e0fb/run_native ca635，结果具该输入身份的有效性。

短模式003在storage_error归档任务过快结束、尚未捕获proc HANDLE时失败（只捕获checker1，expected2）；测试已用首个公开归档查询回调的有界门闩建立观察时序，不放宽count。新probe76dab39d324c846db00e44b8be78863217531e9fe4e5c404d75787914f31165c/run_native a66da4ee3458021a86df58bd85d9129fa9ff104985d05d55396dab4dba32d43b实际八模式004通过，101.578秒，非async首归档门闩进入且超时0，所有Writer精确数量/HANDLE退出、数据和失败保留断言通过。独立最终测试delta静态无新增P1/P2。最终测试门闩改动未再重复600秒场景；核心/600秒语义和旧expiry有效证据保持，运行身份分别登记。

生命周期适配的该配置/范围已具隔离验收证据；默认原库保持，原非allday StateMonitor、六类映射全覆盖、跨进程写者、强制I/O截止、生产安装/切流及全天采集仍各自未授资格。当天ETF239根已沿现有Importer/Helper/策略Reader实际通过，股票当天仍为空，详见[当天分钟证据](2026-10-28-qmt-current-day-minute.md)。
