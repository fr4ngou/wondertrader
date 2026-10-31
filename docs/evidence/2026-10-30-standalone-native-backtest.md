# 独立WT唯一策略全周期原生回测

类型：模块B开发证据。状态：独立回测与限定同安装RT切片通过，完整模块继续。要求：[NBC-R5](../specs/native-backtest-cli.md#nbc-r5-独立wt运行侧回测)、[RR112-R5/R6](../specs/retained-resonance.md)及[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。原件根`build/ms-retained-backtest-001`，全部新增写入、安装、临时目录与缓存位于E盘。

## 职责与实现

原回放能运行固定WtBtPorter，但其父宿主、runner、Porter、事实投影及报告校验仍位于观衡包。B把唯一正式1.1.2链迁入独立WT包，现有纯策略核、NSQ、WT持仓/费用/撮合/userdata继续拥有原行为；新增WT源码修改0。Porter、回放session、事实投影三模块与冻结C原件AST完全相同。报告JSON辅助函数沿原实现抽出，去掉旧策略DTO分支；原取消异常对象、有限快照、冻结与投影保持。

运行入口为已安装的`guanheng_wt_runtime.backtest_cli`，安装绑定为`nsh-wt-install-v1`。原根租约、零队列、父子同次绝对截止、预绑定Job、管道排空及完整报告/输出摘要校验保持。安装writer复用同一个运行验证器，固定六发行及顶层/唯一dist-info/METADATA集合，完整校验后独占写入新清单；写入后再次核同一D，晚D保留实际文件并返回失败。

C拥有的原文件保持。`migration-source`冻结原9模块；`MIGRATION-MAP-002.json`逐文件登记来源、目标及语义变化。`compatibility-proposal`提供五个原路径别名候选，未应用。旧App生命周期入口、历史报告兼容及新WT报告只读消费由C按文件owner接线，不能将候选别名计为已合入。

## 安装与输入身份

最终普通安装`INSTALLATION-004.json` SHA `14ff0cc9c165b55bd5728633112a400660a866129dd4c6bdb24a1a0c5018d766`：六发行/731条hashed RECORD，独立WT、SDK、core、native数量包、V1a7与tzdata，无观衡/Web；规则版本1.1.2。原`strategy_job`和`thread_owner`来自A冻结快照。最终10个新增模块的当前源、冻结源及实际site逐项匹配；版本相同的开发wheel使用各自SHA区分，统一发行版本由A集成。

绑定004 SHA `72164b163ead7b7ff76baca03e4a5a2c6221db5bf45fe0eb3dcfb371692b2aa2`由实际安装writer生成；固定WtBtPorter SHA `4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`，ABI探针SHA `a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6`。完整site/native库存、实际解释器运行库及五类基础资料均纳入原绑定校验。

`SESSION.json` SHA `c2296c1072a78823c23054b072f2d0dde20979f080334a9cd04a5acabcdd49e0`沿C原真实窗口输入，401日/八证券3208原价及分析行；末日比较实际核其history/analysis与A最终窗口进入RT的原值完全相同。来源为A `main006/ANALYSIS-WINDOW.json` SHA `a38386d74bda91da91cc9669ffde734cb69ba50f4d06427fe27038e0ff857859`。显式最终批次历史模型、实际实收及原单位保持；资本120000、费用与撮合为明确历史模拟，真实账户/实时可知资格保持false。

## 实际验收

| 项目 | 原件与实际结果 | 资格 |
|---|---|---|
| R5-C1最终普通安装CLI主链 | main004→原Host/runner→原WtBtPorter，2025-03-06至2026-10-28共400次闭合；98预热、77初始化、10 buying、26 selling、189 converged，12原生输出/原userdata及完整报告通过 | CLI与runner exit0、非forced，151031ms；内外进程/Job/管道回收通过 |
| 当前安装生成绑定 | 实际`prepare_standalone_backtest.py`调用安装writer，最终binding004由运行前同一验证器通过 | 六发行/完整库存及无隐式启动钩子通过 |
| R5-C2边界 | qa-boundaries002：CLI准入/回执/信号、子代监控、未知关闭责任、thread owner、原回放/报告及新writer回归89项通过；一个C App-only绩效输入比较明确deselect | 原生事实/线程替身按测试声明保留范围；实际Job和DLL由C1证明 |
| 两项审查问题的原触发 | red-installation001对旧安装003运行同一额外退役包及真实文件写后跨D回归，均出现预期DID NOT RAISE；最终004对应回归通过 | 旧缺口复现、根因修正闭合 |
| 同安装RT入口 | rt-main002使用最终六发行/731 RECORD，原WRI/Factory/CTA/NSQ/执行器/WinSHM完成四次SDK替身买入、四个周期并收敛，29查询 | 业务通过；关闭c0005，运行根exit2、外层wrapper exit1；外部六清理及Job回收通过，完整RT关闭失败 |
| 同安装BT/RT比较 | last-day-comparison001：同一元数据/费用/资本及完整history/analysis，末日flat单次原BT与RT的14完整非来源字段、经济目标、八数量一致 | 单时点比较通过；全周期BT/RT比较仍gap |

main002及003分别保留安装002/003的400次完整回放，最终资格以上述004为准。`RUN-SUMMARIES-001.json`逐运行关联原回执、结果/原生输出SHA、清理与异常，不把RT失败归并为BT失败或完整模块成功。

## 失败尝试与交付边界

安装001使用uv默认venv，其`.pth`钩子被原校验在原生启动前拒绝；后继采用标准无pip venv安装相同wheel，校验保持。首轮边界QA中的旧host空JSON没有进入唯一族准入，以及一个App-only绩效模块不在迁移范围，导致17失败/73通过；后继只修正夹具的当前输入/选择器并明确排除C-only用例，生产准入没有放宽。

独立审查发现并修正：额外旧策略包可被writer登记、writer写入返回后缺少原D复核。唯一verifier收敛包集合，写后沿原D报告结果；当前原策略/原生事实和绩效没有新增实现。

独立审查、开发归档及最终安装/文件身份沿本根`REVIEW-001.json`、`DELIVERY-002.json`和`FINAL-POSTFLIGHT-001.json`。归档001在交付检查中发现包含QA临时安装，保持为拒绝原件；最终归档002只保留冻结QA源码与回执，排除临时安装、通信私有配置、完整RT POSTFLIGHT和内存转储，保留允许输出的摘要及原件SHA。完整RT稳定关闭/两代恢复、动态真实输入、全周期BT/RT对照、T+1与完整资金/费用/未知责任矩阵、C兼容/只读接线和统一候选继续；本轮没有真实下撤单、生产切换或新增WT核心行为。
