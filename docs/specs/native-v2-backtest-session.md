# V2原生隔离回测首纵切片

类型：功能最终规格。状态：accepted。前缀：NVB。依据已核的V2原生接线PLAN/CONTRACT/ADDENDUM及NSB/NSH/NSQ/NVT；只扩展本仓既有原生回测owner。全部策略版本继续保留，真实来源、RT、实盘及生产资格另验。

## NVB-R1 身份及复用

同一StrategyBacktestSession复用原Porter/CtaMocker公开ABI、loader、完整前缀核对、coherent capture、NSQ、完整setter和释放；同一StrategyHost/runner/ProcessJob负责进程。禁止复制算法、撮合、资金/持仓或任务账本，WT、NSQ及各纯包数学保持；core/SST/NVT公开接口和发行身份同步沿SCW及NVB-R5登记。configured原输入、普通结果及nsb-report-v2保持兼容。

V2输入独立schema=nsb-v2-input-v1，strategy_id=resonance-regime-v2、version=0.1.0，算法身份为no-cycle/native-cash-etf-replay-v1；所有算法/来源常量由模块拥有。首原生信号profile固定legacy-backtest-evaluation-range-v1、数据profile=native-frozen-causal-v1、target_admission_policy=reject-overweight-v1，不包装成configured1.2.0。V2没有原实际成交周期注入，不把1.1.2的fill年龄/峰值规则迁入。

## NVB-R2 输入、截止及计算

显式history_start/evaluation_start/evaluation_end、pre_risk_capacity、八signal→execution一对一映射、原生映射及完整读取并集raw日线。history_start等于实际信号首日；完整八证券日期相同；execution原价并集完整且逐日核原值。首域逐日Shanghai收盘须与现原生UTC+8时钟相等，其他历史时区明确不适用。run起始日等于evaluation_start、结束为evaluation_end15:00，起始分钟沿原Porter纯窗口准入。

原生前准入完整配置/市场辅助/原生资料/资本/显式费用来源；回调不联网补数。每次读取原Porter实际完整前缀，逐字段核来源后按(date,symbol)附回因果metadata。每次调用实际NVT evaluate_v2_history，以全history计算features后把固定evaluation_start..native当日送机器，禁止first_ready或截已算decisions。typed/JSON均严格重审、只接固定分支，无动态模块/loader。

稳定配置身份含算法/profile、history origin、固定最终范围、capacity、执行映射和准入policy。daily cutoff/input/trace/pipeline SHA、价格/NAV/capture序号不进入经济配置或代际；source/factor修订须新会话。每日业务求值/投影/保留用同一剩余5秒协作窗口，父Job单一总截止继续覆盖原生/整个进程，不逐阶段重置。

当日协作截止在Session回调入口建立，覆盖原生完整前缀读取、逐行核对、因果子集构造、求值、采集、数量推进、报告及setter前检查。单步读取不可抢占；该步返回后若已到期，停止继续读取及提交。Session在公开构造入口完整快照并重验SessionLimits，调用方后续改动原预算对象不能改变本次准入值。

## NVB-R3 raw、数量及资格

保存NVT真实完整raw与trace，显式pre_risk_capacity只按原算法约束升级，不归一化底仓1.125。最后真实NFA event日期进入EconomicTarget，完整execution向量由显式映射形成；无event为initializing/None日期，不提交清仓；dated zero为真实零目标；无新event不伪造新日期。

EconomicTarget继续由NSQ构造准入；精确总和>1明确blocked_raw_total，零新增setter，保留实际pending及旧阶段，不假取消或用旧目标冒充新结果。下一合格目标仍按原advance核旧阶段。其他数量错误不冒充超额。原数量/现金/费用/T+1/卖后重算及incomplete语义继续沿NSB/NSQ。

短且因果的八证券合成数据可以形成原生模型数量/实际回测CSV；native_input_ready与旧legacy_offline_ready、source_qualified/historically_produced分别表达。旧360..720自然日、benchmark through-start100及辅助coverage是旧dataset门槛，不暗加成新native条件；缺辅助继续原分支并公开缺项。新原生模型成功不授旧PnL、lot1/成本/缩权等价或完整V2/真实策略资格。原runtime全prefix启动承接和旧比例cap留作明确后继政策。

## NVB-R4 有界共享报告

V2报告schema=nsb-v2-report-v1，configured nsb-report-v2及其完整重建保持。V2每证券完整decision序列及allocation_events只保留一份，逐日压缩保存完整非增长header、末特征、capture/NSQ/提交/回读和共享引用边界。旧共享前缀修改即失败。完整重建同时还原原NVT.to_dict与原SST.to_dict，不截证据或丢trace。

唯一公开validate_report_dict、reconstruct_session_record/reconstruct_prefix_result和有界project_session_record负责两个封闭schema。普通构造也走同版准入且深不可变；dict/类型标签不能绕过。共享八组/行数/单条/字段/边界/累计展开均审入，check贯穿增长循环及解压/展开；输出没有调用者别名。

check的截止/取消属于调用方控制事实；各公开入口在解压、编码和字段校验阶段均保留其原异常对象及原因码，不因它与业务错误使用同类异常而重新分类。业务数据错误继续由报告层提供固定原因。

现硬预算继续成立：4096记录、8MiB完整报告、256KiB单条展开、64MiB累计展开；V2最多32768条decision、4096allocation events、每decision17×256证据。联合容量先到即拒绝，setter前为完整当轮共享增量、压缩上界和回读预留；禁止仅抬高上限或逐日重存累计结果。公开完整重建/summary各受check和有限输出约束。

pipeline与signal_trace组合后的单份完整prefix同样最多8MiB；每日保留前先计量该组合，避免保存可准入而不可完整重建的结果。树复制、分块编码及共享增长沿本次剩余截止；有界stdlib单步属于协作检查间隔，父Job负责进程总截止。

## NVB-R5 受管安装及验收

发行profile由`guanheng_app/v2_package_profiles.json`唯一固定，Python报告准入与SPA共同消费。当前运行仅允许core a6/SST a3/NVT a2/NFA a3/NSQ a1/tzdata2026.3，core实际wheel摘要为012d2d2fb456159781028ef01f12cf6a78d3b40aded02af40a824bf3f9c30312。算法仍为原V2 0.1.0。已归档报告另保留core a5原5397695c…/SST a2/NVT a1的完整组读取资格。core版本、真实wheel摘要及dependencies必须整组匹配，同一会话跨日绑定相同完整profile；混组、未知摘要及跨日改组拒绝。此兼容只允许读取已准入旧原件，不能在新运行中选旧组或扩大来源/执行资格。

原NSH单值manifest.report_schema明确选择configured或V2；父/子/结果按固定映射核输入种类、schema、安装、request/run及原生输出，未知组合拒绝。仍只有固定runner、独占UUID根、Job预绑定、单一期限、有限管道和nonforced/exit0/wait/pipes/有效完整结果完成门槛。

测试安装显式非editable绑定当前完整profile及全部site、原DLL/probe；统一app发行/锁/HTTP/页面由模块C组合接线。先实际NVT→原CtaMocker/NSH的≤1合成成交，再取得真实原始history producer→1.125拒绝，不能用手造decision替代后者。正负、同代/切代、费用/T+1、全向量、报告全部prefix保真、容量setter前拒绝、configured兼容及安装后生命周期均需验证。冻结后交其他作者独立审查，本实现不自行授通过。
