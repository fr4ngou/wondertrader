# 观察服务自然09点窗口验证

类型：模块C独立观察服务实际运行证据。日期：2026-10-31。当前状态：pending-verification，原自然09实例已正常关闭，实际窗口未形成完成回执；原等待及失败证据保持，预算责任层修正另验。原件：`build/observer-natural09-003`；QA：E盘同名wondertrader-qa目录下的natural09_003.py。

## 当前运行

使用已验App a63新离线安装及原observation_supervisor→ObservationCollectionProcess→observation_service→scheduler入口。原25路sources003保持，只将本次隔离配置的schedule.start_date设为2026-10-31，避免启动时补跑前日窗口；时间仍为北京时间09:00，轮询2秒，单批原600秒。正式CLI使用真实系统UTC，没有注入时钟或提前触发窗口。

修订后的固定观察快照f2ce4de9…b43f3通过不可变对象复制及catalog/collection两个SQLite在线备份进入独立根，备份完整性检查通过。原观察数据根及18126保持。所有GUANHENG连接环境清空，不加载现场连接或凭据；WT行情在本次隔离采集中保留未配置状态，来源与窗口完成资格分别记录。

2026-10-31 04:13后原监督ready绑定实际PID40840、子服务PID56188及原控制UUID。QA持有原Job，通过实际进程句柄及IsProcessInJob核监督PID归属；venv启动器PID24832单独记录。exec会话38145已实际轮询保持运行，PROGRESS显示独立心跳、phase=waiting及窗口前attempts=0/new_runs=0。此证据只授就绪等待，natural09_qualified仍为false。

监督命令有有限总预算，父验证最晚09:25结束；实际窗口完成后按原stop收据正常关闭，再在同一根重启，验证完成窗口及原尝试/快照不变、来源请求零重复。若来源部分失败，保留原失败与旧值，不改写为全成功。后继结果依RUN、RESULT及两代正常关闭证据登记。

## 原失败与修正

natural001在准备副本时直接复制活跃SQLite目录，枚举出的WAL/SHM在读连接退出后消失，复制失败；尚未创建调度服务。natural002改为SQLite在线备份并通过完整性检查，原服务已ready；QA将venv启动器PID与实际Python PID直接比较而失败。原正常stop及exit0、tree0、双EOF、读线程和句柄关闭保持。后继按原产品已有的进程句柄/Job归属语义核身份；未改产品或放宽配置/来源验证。三个尝试原目录、日志与失败关闭分别保留。

## 剩余

实际09:00启动时点、完整25路请求/发布及部分失败结果、完成窗口和重启去重仍待本实例实跑。自然窗口通过后也分别保留回购403、股票日线超时、WT连接及T2108/完整市场覆盖缺口；整个C及统一系统继续active。固定源码/SPA与定义修订沿[当前交接](2026-10-31-observer-source-update.md)，真实账户、交易及生产仍归根授权和验真。

## 实际窗口后继：未完成及根因

同一原实例在北京时间09:00:01.782462真实触发第一次尝试，09:10:05.006355开始第二次。原QA在09:12未取得窗口回执而断言失败，随后沿原stop正常关闭监督与子服务；原first-CLOSURE为exit0/nonforced、tree0、双EOF、join及资源关闭。外层CLOSURE保存QA失败和完整回收，未启动替代调度实例。

`FAILURE-RESULT-001.json`在原停止后经原a63安装只读核实：两次尝试已持久，窗口完成为false，窗口运行回执为0，原62项快照f2ce4de9…b43f3保持，调度状态stopped。全部原输入摘要保持；本诊断无来源请求。正常重启去重未执行，自然09资格保持false。

根因位于单一collection owner：外部采集与finally保存source_manifest及后续发布共用完全相同的已耗尽截止。来源占满采集时间后，finally的BoundedContentStore.put再抛collection_timeout，退出到scheduler.tick；该轮缺少持久run，随后按原attempt/backoff政策再试。a65原离线安装同触发条件的两项回归均在该finally路径失败，见`build/observer-finalization-budget-001/RED-002.log`；首次RED-001输出上限失败也保留。

修正沿[OBI7原预算](../specs/independent-market-observation.md#obi7-用户入口与验收)划分来源与收尾阶段，保持原总截止。新a66从已审a65的197源输入构建，161模块中仅collection.py变化；原自然实例、a65制品及用户18126保持。修正后的普通/离线安装、公开手动25路主链、部分/全失败回执与完成窗口重启去重分别验收；手动或固定时钟回归不提升今天自然窗口资格。

## a66修正后的实际主链

原a65离线安装的两项红例在finally存证路径失败后，a66普通安装执行观察模块全部359项通过，含相同真实单调时钟超时、部分成功发布、全失败回执、完成窗口持久化及新reader重启零重复；原总截止和取消门禁保持。`build/observer-finalization-budget-001`固定197源、30依赖和161安装模块，其余160模块及18SPA与a65相同。新离线ZIP为`d4ab6c89c9562f7f641289b3c8d729fd72865a104d1f763a3d46eaa8578bcc72`，普通/离线payload逐文件相同。

`main-002`在原失败自然根的独立SQLite备份和不可变对象硬链接上运行原公开refresh CLI，原根保持。先沿原完整计算配置加入既有真实8股票点，再执行原25路手动来源更新：329请求、18成功、4仅检查披露、3失败，278.406秒正常完成并发布63项/54773查询行。最终快照`43d617a508a129576740c5cb9af0208269e62cd64bfe1bbc2d0c4f94ca6aad37`。回购拒绝访问、逐股PB请求超时和WT未配置分别保留旧值；该隔离验证清空现场连接环境，未启动来源/Host/WT/QMT，未操作账户或交易。原自然窗口仍为两次尝试、完成false，调度保持stopped。

`main-001`误用单指标models={}配置到组合62归档而publication_failed，原失败及完整回收保留；002保留组合模型及原日历配置，未据此修改产品。局部合并的来源到最终完成约51秒，原总预算内最多60秒的收尾余量实际可用；整个来源批次仍按600秒原上限执行。

最终离线a66原App CLI的`http-001`已读取全部63项/54773行，HTTP、CSV逐值相等，并核对每个CSV完整投影字段及固定快照。PCR默认口径使用查询投影schema；headers001将原始定义直接当导出schema而失败，002沿同App实际投影核全63项通过，产品未改。真实T2108 CSV全部19字段及字节与原8样本相同。CUA临时页64核1440/390、无页面横向溢出；25%紧邻8/5576、缺5568和完整市场待补齐，更新页明确手动部分成功和三项中文原因，页首显示原服务已停止。质量页可见文本未出现64位摘要，控制台warn/error为空。临时页关闭、视口恢复；App正常exit0/nonforced、树零、双EOF/join/句柄关闭，原Job回收通过。

该轮仍保留原四项沪深广度归档：breadth、RANA、TRIN和换手大于5%各13个交易日、截至2026-10-29；本轮逐股来源超时使其日期保持。完整沪深北/最新截面与A新来源的单位、参考价、流通分母和复权资格沿各自原件核对。

新267件冻结输入的两轴已完成、无新增P项：Spec SHA `3013e9502b8533b231532b24b6cfe0ac26b3a7daec4a67053e445e1af97e3d61`，Standards SHA `ccf5fd84ad7087573f1c439055dd324ad1caa2e9fe3439ae99ebcc85db46346b`。上述实际手动/最终HTTP/UI终态另作固定补件；新自然09窗口、运行中WT连续性、全市场及完整系统和生产继续pending-verification，未新增调度实例或切换18126。

409件运行补件已独立两轴通过，Spec SHA `0f9097636c9a21b10e763729c7b2724c4f5c98bce1db15c3df2b1ccb343548fb`，Standards SHA `4b292207b074caa5baf7b43b4deb73530a8ae9715759d0f38f7a06e7e9280d5c`；父267件和当前补件摘要前后相同，无新增P项，手动25路及最终离线HTTP/CSV/实际页面缺项闭合，原自然窗口资格保持false。

当前a66独立更新回退也已另行实跑：`upgrade-001`使用原a65→同一d4ab最终a66 ZIP新目录安装→原a65，旧App PID35748在安装期间保持存活并于安装后读取原值。三阶段各63项54773查询行、两份400点报告共800点、原持仓/可卖/资金/时点及同一个人自选ID、版本、顺序、保存时间和字节均一致；三代App正常关闭，298输入前后不变。新旧均161模块/18SPA逐SHA相同于各自封存身份。三个切换阶段的UI按相同18SPA/read160、相同闭合SDK来源和本轮实际a66桌面手机复用，未宣称三次新浏览器验证；活WT连续性仍待根组合验收。

361件升级补件两轴无新增P项：Spec SHA `78078f8e014a8a9c3c0f16cd8c137f3cd7315b05368ea6c0b9812f400bbee95e`，Standards SHA `0e66a2efe7b4aa0d13a4a7ca9c996d24e1b2de0e85b5ac984b169e1c54a97a9f`；父267/409及本361摘要相同，仅闭合独立a66软件升级。最终唯一后继交接位于`build/observer-finalization-budget-001/FINAL-INTERFACE-001.json`及`INTEGRATION-HANDOFF-001.json`，精确继承原a65接口，不改原包/原失败/旧审查。整仓文档检查已通过，运行和完整系统资格分别保持上述边界。

## 实际三市场原件后继

根交接的`build/root-mdp-real-six-source-002/root-partial-audit001/INTERFACE-001.json`（SHA `b8caca803ca88bab82dcd032c3eb99a7d73d3b8279b06abd6d69775758e44752`）与原ZIP `3e7059b6e3a7c14a165539fe17f00f07f78bed020cb280cf75ec079482f94123`，包含上游真实QMT缓存准备后的三个市场切片。000001.SZ、600000.SH、920000.BJ各有82根原值及82根前复权日线，尾日均为20261030；原六成员、两批请求/结果摘要、绑定、实收时钟和consumed身份保持。因子未请求，复权、闭合日与跨市场共同基准资格均为false。上游临时QST接收端关闭超时，正常WT关闭仍缺证，原whole_run_passed=false保持；本消费者关闭资格归自身运行。

`actual-successor-002`使用最终离线a66公开refresh CLI，在正式main-002根的独立SQLite备份/不可变对象副本读取492行、2952浮点事实，4.187秒返回`t2108_no_qualified_observations`并持久化失败回执。原63项head `43d617a508a129576740c5cb9af0208269e62cd64bfe1bbc2d0c4f94ca6aad37`、全部分区、真实8样本及原来源时间保持。预期业务拒绝及外层Job均记录完整回收；此轮SDK/来源调用、Source/Host/WT/QMT启动及账户交易操作均为0。既有HTTP/CSV/桌面手机验证按同软件、同快照复用。

38件补审两轴无新增P项：Spec SHA `87b44c7af4e2ab8292425c37397185a40a1e53869d6a82dd3071212ec70c36fe`，Standards SHA `fc13be4033a0c48bebe7c1b7278cebfdfcccc177aeabaca6c35b97f56f48dcc1`。另经上游原安装的`guanheng_qmt_shm.analysis_batch_source.read_capture`纯文件入口校验同批原件，2批/3证券与全部输入SHA保持，原单调截止内正常退出；此入口只解码本地原件，未创建来源连接。其记录位于`OWNER-READ-CAPTURE.json`及对应关闭文件，另有14件固定补件核实该入口和驱动边界。

当前交接使用`build/observer-finalization-budget-001/FINAL-INTERFACE-002.json`及`INTEGRATION-HANDOFF-002.json`，001作为不可变前件保留。新原件仅补充实际消费证据；T2108仍为8/5576、样本25%、缺5568，市场值为空。新的真实自然09窗口与重启去重、真实全池与因子/基准、最新完整沪深北广度、运行中WT组合及生产验收继续pending-verification，用户18126保持。

14件纯文件入口补审已完成，无新增P项：Spec SHA `27afeedd5731bfe33f9ebb5ff5df0a27a573d2c991290a14fcafe8b9338f10c1`，Standards SHA `67e5adbd57f23b7fe618a2a5c6bc43a34ce15d7fc0262947eab46db20dec66f4`。同批原件及父38件摘要保持，未增加市场或上游整体关闭资格。
