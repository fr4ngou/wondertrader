# 原生回测绩效与比较

类型：功能规格。状态：accepted。前缀：BPC。范围：COP-R4，沿[NBW已完成归档](native-backtest-workspace.md#nbw-r6-已完成回测只读归档)提供派生展示，原生金融事实继续归WT。

## BPC-R1 来源与身份

只消费同一显式work_root内带完成receipt的归档。复用BacktestArchive的原request/installation/result/native outputs摘要核验及报告族唯一validator，不引数据库、复制资金账本或重跑回测。请求固定run_id及receipt_sha256，配置、报告、session输入、安装、策略/模型身份完整返回；原件变化、未完成或身份失配明确拒绝。configuration.session_sha256保留原会话文件摘要，顶层session_sha256保留规范化请求会话摘要，两者分别核实。单份报告与比较共用既有backtest_reader及一次绝对读取截止，串行读取第二份不重置预算。

## BPC-R2 指标与数据边界

初始本金取本次已准入session.policy.initial_capital_cny，原生报告capture.basis.nav_cny表示该本金加WT净损益；capture.funds的net/realized/dynamic/fees保留原生累计语义。每条记录经唯一公开project_session_record读取；null capture保留未知点，不补零或前值。

收益率=(末个合格日末模型净值/初始本金−1)×100；回撤从显式初始本金和已观察日末净值的历史峰值计算，展示名称为“已观察日末最大回撤”，不推导盘中风险；原生累计费用取末个合格capture.funds.fees，不累加每日累计值。计算沿有限精确有理值，最终有限数值/十进制字符串投影；派生不可表示时明确不可用，不返回NaN/Infinity或伪造零。

报告零记录或没有资金观察时保留内部身份和明确空指标；唯一1.1.2报告预热日已有资金capture时仍可展示日末净值，策略信号继续标预热。部分capture缺失保留总记录数、观察数、缺失数与末合格交易日，界面说明指标仅覆盖合格观察。最多4096个日期/净值点，响应沿512KiB上限，单份与比较均不截断冒充完整。收益不年化，不提供样本不足的夏普或未来收益承诺。V1/V2两类报告按其真实schema/输入身份消费，新增族仍须明确适配。

金额与净值使用最多512字符的非指数十进制字符串，显示数值超出有限范围或非零值下溢时整份拒绝；百分比派生不可表示时返回null。输入身份包含规范化history、policy、strategy-or-config的SHA256，保留market_manifest_source、capital_source和费用来源。比较中的model差异由report_schema、algorithm_id及policy_sha256表达，费用比较采用预留及来源。各曲线注明自身净值范围及分别缩放，精确原值保留在日期表。

唯一1.1.2报告的history_sha256绑定原值历史、analysis前复权来源/因子/数据、current_view实际版本与historical_model的完整规范对象；其中任一改变进入input比较差异。其他已封存报告族的原字段语义保持。

## BPC-R3 HTTP与比较

新增GET /v1/ui/backtest/archive/{run_id}/performance?receipt_sha256=... 返回nbw-performance-v1；新增GET /v1/ui/backtest/comparison?left_run_id=...&left_receipt_sha256=...&right_run_id=...&right_receipt_sha256=... 返回nbw-comparison-v1。只读，无query以外body；额外/重复参数、非法身份及选择同一运行拒绝。比较结果包含两份完整身份/指标及条件差异，展示窗口、初始本金、输入、策略版本/配置、模型和费用差异；差异保留解释，不自动把异窗口/异输入当成同条件优劣。同一固定报告对刷新或失败时保留上次成功结果及原读取时间；首次读取失败显示重试。切换报告对使用自己的查询结果。成功空结果替换旧结果。schema、输入/字段、中文错误及容量封闭校验。

## BPC-R4 页面与验收

原回测与报告tab保留启动/取消/逐日记录/归档；在已确认归档内展示单份绩效、净值日期表/曲线，选择第二份归档进行并排比较。正常/空/加载/失败/重读及窄屏可用，读取中和失败时保留同查询结果与原时间。页面呈现名称、版本、绩效、曲线、日期和数量等业务结果，内部SHA/算法/请求/实例身份及完整JSON保留在API与诊断资料，页面直接停止渲染。策略目录继续只读名称、简介和版本。当前新运行仅唯一1.1.2；新报告族及模型范围沿[RR112-R7](retained-resonance.md#rr112-r7-app任务与报告)。已封存报告仍按其原schema校验，只呈现业务结果。

主链采用实际原生归档，从固定安装App/生产SPA读取单份及两份报告，与原record/资金字段逐值复算；覆盖两族报告、空/缺失观察、身份变化/原件损坏、超时/容量、错误恢复和资源关闭。独立审查核对数学口径、完成证明、版本与模型差异；源数据、RT/真实券商/生产及完整模块继续各自资格。
