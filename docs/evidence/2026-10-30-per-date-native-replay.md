# 八ETF逐日基准的原生回放及报告消费

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发证据。结果：partial，完整模块继续in-progress。规格：[NRT-R28](../specs/native-realtime-strategy.md#nrt-r28-逐日基准的原生回放与完整比较)。新增安装、运行、临时文件、缓存及制品全部写入E盘。原WT框架修改、真实券商调用和新金融账本均为0。

## 实现及输入身份

A原ReplayCatalog拥有原价、复权分析值及因子；B消费固定401日/13组、644808对raw/analysis，保持manifest、逐窗摘要及实际接收时间。来源为qmt-native-replay-001主交接（外部历史/待归仓路径：`../../build/qmt-native-replay-001/MAINPATH-HANDOFF-001.json`），manifest SHA256 `328978f0eee0d0ad1b65cab7ee5fd6073158efecab6af3d63ae580260325f6bf`。B原安装类型解码及13份原件绑定沿INTAKE-001（外部历史/待归仓路径：`../../build/ms-native-replay-consumer-001/INTAKE-001.json`）。金额unknown/unused，历史首次可知及修订unknown；历史15:00可用为显式回测模型。

原RetainedBacktestSession提取市场请求接缝，保留唯一Porter/CtaMocker、财务capture、周期/退出userdata、NSQ和目标提交逻辑。新增RetainedPerDateBacktestSession逐次选择A日基准，绑定已有RetainedHistoricalModel；初始完整市场输入须匹配目录末窗，本轮窗口raw的symbol/date/OHLC/volume/amount须与实际原生撮合前缀相等，lot声明须匹配。B没有重算复权OHLC。

新报告族为guanheng.retained-per-date-replay-report.v1。原backtest_reports按明确schema选择准入；逐日manifest/窗口/factor/时刻与各决策模型核验后，共用原财务、原NSQ状态转换和原生输出校验。显式旧validator保留原报告族。公开读取与逐条投影是本次交付范围，产品配置CLI和观衡页面接线分别保持待验。

固定原WtBtPorter DLL SHA256 `4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`，原ABI探针SHA256 `a7fdb6ecd763ebdd395d4b0d11d78a1f6d30bbb57f23a63630c2410c243b71b6`。最新python-003安装（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/python-003/INSTALLATION-001.json`）包含六发行、737条带摘要RECORD和36份运行源，保持A的开发版本0.1.0a4，以wheel SHA区分；统一版本由A集成登记。无App/Web。

## 实际验证

| 验收 | 入口与原件 | 结果及范围 |
|---|---|---|
| R28-C1 | 原A目录→B原RR112类型 | 401日/644808对完整解码、逐窗SHA固定；输入接收资格 |
| R28-C2 | python002直接API→原Porter，main-002 | 400 calculate/3200 bar；98 warming_up、77 initializing、11 buying、194 converged、20 selling；原7份财务/用户输出逐项SHA匹配 |
| R28-C3原路径 | 同python002/原最终批次compat-001 | 400 calculate/3200 bar；98 warming_up、77 initializing、10 buying、189 converged、26 selling；原validator通过 |
| R28-C3守卫 | 旧red001、green001；最终冻结green002 | 旧版4案中raw前缀和单位2案失败；当前4案通过，错误raw在setter/userdata写入前拒绝。green002当次冻结6输入、源码副本和实际回收，旧原件保持其原溯源限制 |
| R28-C4报告消费 | python003安装→reports-001 | 两种各400期原生报告通过；18类模型/来源/财务失配拒绝、独立投影、跨schema拒绝及原取消异常对象保持通过 |

逐日主报告SHA256为`f08392e3a5cb9dbc6000aa74a18e024e608dcf38b80aef96537b206e54f9a27d`，原路径报告SHA256为`c71296105a60251f985c4cb35360d842b777b36ad2702fae1bf86703673eeb24`。原生主案沿MAIN-RUN-002（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/MAIN-RUN-002.json`）和COMPAT-RUN-001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/COMPAT-RUN-001.json`），受管启动根PID31220/50316实际exit0、root回收、tree0、EOF、join和资源关闭均成立。venv解释器根与实际装载DLL的子解释器身份分开，未额外采集的子PID及独立OS码保持unknown。原Porter.release正常返回与外层进程树关闭分别记录。

报告读取收据（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/reports-001/RESULT.json`）绑定QA、原报告及实际安装两模块，受管根PID72948 exit0、完整回收；最终守卫收据（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/boundary-inputs-002/RESULT.json`）绑定运行前冻结的6输入，根PID10208 exit0、完整回收。上述进程原件位于各自PROCESSES.json。

搬迁后的relocated-001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/relocated-001/RESULT.json`）从独立candidate-001目录内六wheel、原A目录、原DLL/ABI、五基础资料和固定会话运行。实际新venv以requirements的--require-hashes离线安装，731条带摘要RECORD及36源相符；相对直接wheel安装少六条direct_url来源元数据，产品内容相同。包内全部文件在运行前后摘要一致。原Porter再次完成400回调及7份原生输出，正式读取接口核全部400投影，阶段计数与main002相同。主报告SHA256 `d0930ac7093a3130c6a79264b4bf2e3379d9c0ef151e9879e47e483193c8f9a7`，安装/依赖/主路四个受管启动根15296/11620/65196/73840均exit0及完整回收；实际DLL装载子PID的独立OS码仍未另采集。该入口为显式开发API验真脚本，产品配置CLI继续待接线。

后继独审发现搬迁QA在导入A模块前只核已登记SHA，未拒绝目录内未登记文件；001当次实际目录无额外文件，其400期事实保持，通用目录准入资格转为待修。当前统一verify_package对解析后的包内树在导入前/结束后核精确文件集合、普通文件类型及重解析点，发现目录先核总量4096再入队，文件/总字节同样有界。shadow003（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/package-boundaries-003/RESULT.json`）实际重现旧版进入已知合成dataclasses并报固定标记，新版在来源API导入前拒绝；两案Native/券商0、预期OS1且完整回收。capacity001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/package-capacity-001/RESULT.json`）用受限目录枚举替身重现旧先超边界再检查、新即时报目录容量；该项为纯值回归，未授真实大目录压力资格。

最终candidate003/relocated003（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/relocated-003/RESULT.json`）以当前QA重新独立安装并完成原生400期及正式报告400条投影，阶段与main002一致；731 RECORD、36源和包全部文件前后匹配。主报告SHA256 `d4541aa26958f4ea9910d777ac05df1e03738c6ddcf3370453b5f2e144be5f65`，四个受管根36904/70960/39748/69124均OS0及完整回收。中间candidate002/relocated002保留其400期及当时目录容量检查范围，最终目录准入以003与两类定向回归为准。

## 两种回测模型的差异

MODEL-COMPARISON-001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/MODEL-COMPARISON-001.json`）和MODEL-DIAGNOSTIC-001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/MODEL-DIAGNOSTIC-001.json`）比较逐日基准BT与固定最终基准BT，范围内没有RT。400期模型状态类别全部相同；39日权重存在最大`2.7755575615628914e-17`差异，首次2025-11-21。原经济目标使用精确权重，102日期的经济代际不同；137日期数量目标、15日期阶段和185日期财务事实存在差异。所有原数值保留，未通过舍入、更改策略或调整账本强制相等。后续数量/财务差异的完整执行因果仍需逐日对应，不能仅凭首个浮点差异归因全部后果。

## 独立审查及剩余工作

执行审查（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/REVIEW-EXECUTION-001.json`）与协议审查（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/REVIEW-PROTOCOL-001.json`）核C1–C3、源码/安装/原生输出及回收。raw前缀P2已以同触发条件修正；报告执行delta（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/REVIEW-REPORTS-EXECUTION-001.json`）与报告协议delta（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/REVIEW-REPORTS-PROTOCOL-001.json`）核python003、报告读取及最终守卫原件。各报告新增开放P1/P2为0，范围及输入SHA由原报告拥有。

R28-C4的产品配置CLI、A固定安装目录API的部署接线、C观衡报告/绩效消费、R28-C5完整400期RT/BT继续。当前RT正式入口使用真实接收/当前UTC决策及原CTA ticker，逐日历史回放使用显式历史时钟；完整比较须保留这一差别并核相同日基准/原生状态和成交模型，末日flat比较、两种BT或重复纯核均不替代完整RT证据。正式WRI跨日恢复、unknown解除及统一新候选亦继续沿模块B验收。

开发API制品、冻结源码、接口交接及独立审查索引沿DELIVERY-001（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/DELIVERY-001.json`），制品为B-PER-DATE-NATIVE-API-001.zip（外部历史/待归仓路径：`../../build/ms-per-date-replay-001/B-PER-DATE-NATIVE-API-001.zip`）。该制品复现上述直接API及报告读取，完整模块保持in-progress。
