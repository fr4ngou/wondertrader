# 当前库存的新运行基准与原生两代

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B NRT-R30实现检查点。状态：in-progress。用户决定沿[唯一初始库存方案](../migration/retained-strategy-takeover-proposal.md)，入口见[运行手册](../runbooks/initial-inventory.md)。旧开仓历史工作已取消；本项新增WT/策略核数学/金融账本和真实交易均0。

## 实现与实际复用

新增自有initial_inventory.py：验证当次有身份与有限有效窗的当前库存、可卖及标价；用启用时点生成明确initial-inventory管理周期，清空旧退出初值。原行情、复权、配置和NSQ policy保持。调用C原PositionCycle/唯一纯核，再生成原RetainedRuntimeInput和P23初值协议，无需改变C算法或WT核心。原P23继续核券商当前数量/可卖和未决责任，加载原持仓、组合和KV；本次标价为原WT新运行成本基准，历史收益/费用0。

公开准备CLI只独占创建输入与最后收据，不启动Runtime或交易。其源、普通安装与内部原协议可分别核对。准备收据明确origin、baseline_at、输入/源SHA、history_imported=false及runtime_started=false。CLI及恢复操作沿运行手册。

## 先跑通的实际主链

values001与values-installed001均使用原A401日窗口及原唯一核：旧模板510050开仓2024-04-10会报opening_history_missing；准备后持200/可卖100及另一库存数量保持，旧退出为空，新管理周期年龄0、参考价未形成，原市场值完全保持。空库存沿原fresh路径；7项错时间/量/可卖/重复证券/旧字段/缺标价拒绝。两次均实际调用公开准备CLI并核PREPARED全部文件SHA，未调用账户。原Job分别41584/75656，exit0、树零、EOF、读线程join和资源关闭通过。

独立安装冻结原R7源及原七依赖，仅加入initial_inventory.py和开发本地版本0.1.0a11+initialinventory.1，避免混入并行A的a12/Reader等待或未交付的报告源码。7发行761条带摘要RECORD全部通过，源码与wheel及安装逐项相同，uv依赖检查通过；新环境没有App/Web。安装根build/ms-initial-inventory-install-001，外层及四次构建/安装子作业正常回收。此为固定B开发候选，统一候选版本由A集成。

native002以原SCMR批准制品的安装目录、普通新WT环境及当前冻结SDK替身，经原配置/Factory/CTA/NSQ/原执行器/标准Trader/真实WinSHM完成两代：第一次持仓加载、两次正式策略计算、零SDK下单；正常停止后同金融根恢复，序号与周期延续、初始化收据保持，第二代零新增SDK。原生动态损益为0，新周期前缀和新起点被原KV保存，当前成交为空。原同版核心文件与测试输入前后无漂移；外层Job56532 exit0，44.727秒，原树零/EOF/join/资源关闭，内部公开关闭按原POSTFLIGHT逐项核对。该情景模型已有库存与原NSQ目标相符，含1只沪深300，非沪深300与可卖受限的主链后继继续。

native001选到已有测试行情子目录的main009安装副本，测试准备阶段mkdir失败；原件保留，账户/策略尚未开始。后继改用正式干净SCMR安装，不修改生产逻辑来绕过目录冲突。两次使用的Runtime/股票执行器相同，标准Trader不同版本分别由原安装绑定保留，不能把001或旧main009整体当作002输入身份。

## 非沪深300库存、可卖限制及首次调度前恢复

native005使用同一普通候选、原标准现金ETF session和原库存加载，初始化两只库存，其中510050总量200/可卖100，原持仓冻结量100。首代和次代均在尚无市场调度时正常关闭；原策略fund收益/动态收益/费用0，明细标价、数量和冻结量正确。原KV逐字保持，周期来源为本次initial-inventory，旧开仓和交易记录没有进入输入；重启无再次清零。两代原Native closed.v2均ok/recovery_ready/exit0/resources_closed，WRI/Host/Source/Agent/server/proxy均正常关闭，12次SDK替身查询、下单0。外层Job41040 exit0，20.721秒，树零/EOF/join/资源关闭通过。

该项证明库存/可卖初始化和首次计算前的原状态恢复，未授可卖受限后的NSQ调度/等待或真实日历资格。此前native003在实际盘后使用同日10点模型行情，原策略未产生调度后测试超时，4查询/0SDK，物理回收完成；native004把QA会话扩大到24小时以试验当前分钟，原现金ETF精确session准入拒绝，0查询/0SDK。两失败均属未成立的输入/测试范围，原件保留；24小时试验已退出，产品及原DAY会话保持。

## 最终回读修正与同版重验

协议full审查001发现P2：最初版本在PREPARED写入/fsync后直接返回prepared=true，缺最后同D回读。旧普通安装的receipt-old001确实在真实句柄写入坏首字节后仍返回成功，另一个回读失败入口未被调用；负例按预期红，外层Job8320 exit1且完整回收。责任层将收据固定编码为bytes，关闭写句柄后沿原D回读核同一bytes，失败保留原件且不启动运行。source001及普通receipt-installed001两例均正确拒绝，分别保留CtaBridgeError和原OSError；损坏原件及Runtime输入保留。

最终普通候选为build/ms-initial-inventory-install-002，版本0.1.0a11+initialinventory.2，仍仅覆盖原R7的新增入口及开发版本，七发行761条RECORD相同范围通过。values-installed003补验已有准备目录不覆盖和错源SHA在创建输出前拒绝，原行情/数量/可卖/清旧状态及CLI全部通过，Job48228 exit0/5.788秒/全回收。receipt-installed001 Job22760 exit0/3.016秒/全回收；安装外层Job65892正常退出。原.1证据及带问题安装保持原件。

该最终候选的native007完整两代正式计算通过47.305秒/Job6900 exit0，native008无调度的两库存200/可卖100初始化恢复通过19.687秒/Job64960 exit0。各12查询、SDK0；两组Native/WRI及运输全部正常关闭，外层树零/EOF/join/资源关闭。007中原NSQ seq2→3、周期元数据、NAV/现金及原状态保持；008原收益/费用0、数量和冻结量及KV逐字保持。两组实际运行的8份QA字节分别固定在各自qa/，与运行前INPUTS和运行后SOURCE-POSTFLIGHT相符；005/006同样已按原SHA补固实际8份字节。002原阶段仍保留其当时哈希绑定范围。

当前最终限定交付以.2、values003、receipt-installed001、native007/008及后继独审为准；007与008分别证明计算后和首次调度前恢复，不将008提升为可卖受限的NSQ等待验证。

当前完成新准备入口及限定安装、原生两代库存模型主链和非沪深300/200可卖100的首次调度前恢复；可卖受限的后继调度、启用后实际差额、新日线推进、完整边界、独审和最终增量包继续。真实当前只读事实生产者自动装配、最终A/B/C同版组合、跨日及未知责任解除仍各自待验，完整B目标保持。冻结证据和新目录全部位于E盘，当前真实账户与生产配置保持。

## 已接受WT12上的单模块组合与搬迁

按根集成要求，以root-published-reader-refresh-001已接受的a12 wheel为唯一运行包基线，逐字保留全部原包成员，只增加最终initial_inventory.py；依赖元数据、公开入口及原execution_market_window等待行为保持。候选为0.1.0a12+initialinventory.1，固定安装在build/ms-initial-inventory-wt12-install-002。此基线本来不含R7的backtest_completion.py和retained_per_date_replay.py，本增量不扩张基线；R7/R28原封存资格另列，最终统一版本由根集成。首次构建驱动的字符串语法错误及基线文件集合断言失败保留在job001/002，均在构建/运行前退出并完整回收；后继job003成功，不将准备失败归因于产品。

新候选普通公开API/CLI与最终收据故障两例均通过，values001 Job1692/5.112秒、receipt001 Job72336/2.726秒，exit0且全回收。该组合的native001完成原Factory/CTA/NSQ/Trader/WinSHM模型两代及正式计算，12查询/SDK0，Job75956/40.374秒；native002完成两库存、200可卖100、首次调度前同根两代，12查询/SDK0，Job64400/20.623秒。两组原关闭与八份QA原字节及运行前后摘要均保留在各自独占根，不提升受限可卖调度或真实来源资格。

build/ms-initial-inventory-wt12-package-001固定七wheel、SHA requirements、唯一新增源码及运行说明，并生成B-INITIAL-INVENTORY-WT12-001.zip。实际解压到新E前缀、require-hashes/offline/no-deps安装、全部带摘要RECORD/原成员字节检查，以及安装环境公开CLI/API和收据故障通过；外层Job20496 exit0/13.623秒/完整回收。该搬迁验证依然显式使用原冻结测试市场模板，未启动搬迁前缀的完整原生运行。包身份、精确计数及最终两轴delta审查沿INTERFACE-002及SOURCES-003；当前事实自动装配、后继成交周期、可卖受限调度和整套候选继续。

最终SOURCES003的130项原件在封存前0漂移。协议003与执行002各自核对195/182项绑定，开放P1/P2为0，复用未变初始模块原full审查。组合的34个A12原成员逐字相同，唯一新增初始库存模块；七发行普通759条与搬迁752条的差恰为7个direct_url记录，安装器生成元数据/启动器有各自路径身份，产品源码保持。ZIP14成员/561735字节，SHA bfe62b812efca650a144aff582124fa319672d13b30d25a6c18d8fc92d43d4b1。最终交接为HANDOFF-003（外部历史/待归仓路径：`../../build/ms-initial-inventory-delivery-001/HANDOFF-003.json`），其生成外层Job65424 exit0且完整回收；文档检查通过。封存以frozen-003文档及各审查原件为准，本段和后续自动启动规格属于封存后的活动文档后继。

当前转入WT执行启动的自动事实生产者：复用原账户扫描及行情SDK，取得当次数量/可卖/资金/委托和标价，生成原输入、调用原P23后运行唯一策略。该条自动主路径完成前，当前封存材料继续明确为准备入口及隔离库存模型，不报告为系统自动启动可用。
