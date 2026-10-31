# 交易owner执行时钟与原生元数据环境

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：ExecutionEnvironment实现、产品宿主SDK替身主链及安装消费通过；正式CTA策略入口继续。要求见[STQ-P15](../specs/native-qmt-standard-trader.md#stq-p15-交易owner的原生执行环境accepted开发中)，操作见[执行环境手册](../runbooks/qmt-standard-execution-host.md#执行时钟与元数据)。

## 问题与正确实现

此前产品宿主借用外层IExecuterStub，主链仍由手写HostStub提供固定日期。原CTA的get_real_time读取其_cur_date/_cur_raw_time/_cur_secs，原ticker在行情及计时路径推进这些字段；直接把引擎stub交另一交易线程不能作为已验证的线程隔离方案。本项补齐交易owner专用产品环境，不修改原引擎同步机制。

ExecutionEnvironment实现原IExecuterStub：实时缺省复用原TimeUtils::getLocalTimeNow的epoch毫秒，owner以Windows localtime_s取得本次自有tm，交易日直接调用原BaseDataMgr.calcTradingDate(reference_session,date,HHMM,true)。品种/时段继续由原CodeHelper及BaseDataMgr提供，HotMgr为可选借用。没有新增交易日历、金融账本、线程或CTA字段跨线程读取。模拟环境显式注入Clock，真实默认时钟与冻结模拟分别记录。

全部实例方法只由创建线程访问；元数据装载完成后稳定持有，生命周期覆盖原Local和Host。外部2/3段代码在传原解析器前验证非空段、复权尾标和原定长容量；未知品种返回空，查到品种不宣称合约存在。策略闭合分钟、执行epoch及请求steady截止保持不同职责。主机时区和交易日元数据的真实来源资格继续由部署验收承担。

## 实际产品调用链

将已有产品宿主探针的手写HostStub删除，改用本产品ExecutionEnvironment。主链仍为原WtExecuterMgr→跨线程目标/行情→StandardExecutionHost→原Local/MinImpact/Adapter→正式Standard→实际Host/Win32共享内存→独立SDK替身。原生探针先验证缺省系统时钟在实际前后epoch范围内，再显式注入2026-10-22 10:00用于委托替身主链；不把冻结执行冒充真实实时账户。

| 场景 | 四轮实际新增委托 | 来源持仓 | 来源余量 | SDK查询 | 退出 |
|---|---|---:|---:|---:|---|
| 完整空订单查询 | 1,0,0,0 | 100 | 0 | 8 | worker join/drain、API删除 |
| 活动订单查询 | 1,0,0,0 | 100 | 80 | 8 | worker join/drain、API删除 |

两案均核对产品环境读取的原品种/session指针；原周末规则从2026-10-24推进至2026-10-26；未知session、零epoch、未成形代码和未知品种拒绝。非owner环境observe与Host越线程入口拒绝，owner状态保持。原宿主配置拒绝、重复初始化拒绝、跨线程stop、重复close及关闭后迟到目标继续通过。真实下单/撤单0，每案SDK替身insert1/cancel0。原件：总体（外部历史/待归仓路径：`../../build/sp-007/environment-main-001/RESULT.json`）、空订单（外部历史/待归仓路径：`../../build/sp-007/environment-main-001/query_first/native-result.json`）、活动订单（外部历史/待归仓路径：`../../build/sp-007/environment-main-001/query_first-active-order/native-result.json`）。

## 构建、安装和审查

固定原上游加批准覆盖343份、自有257份全部SHA核对。自有CMake产品库增加ExecutionEnvironment.cpp，公开头安装并由实际消费端include。全新sp-007完整编译约153.85秒，随后两次增量分别约18.31秒/15.33秒（格式准入及探针品种语义修订），均exit0。最终安装install-003含7份自有公开头，实际header消费端仅从该安装include及原SDK/锁定依赖取得头，编译通过；同一身份的增量no-work结果按先前实际编译复用。安装provenance的owned-input摘要与最终来源一致。见编译（外部历史/待归仓路径：`../../build/sp-007/BUILD-RESULT.json`）、安装（外部历史/待归仓路径：`../../build/sp-007/INSTALL-RESULT.json`）。原库及SDK编译警告保留，含探针系统epoch比较的符号警告；未改WT消警。

独立full新模块/delta装配静态审查complete、无实质gap，实际8份自有/规格SHA匹配。审查者仅看最终规格、规则及源码，未读任务/历史/执行报告、未运行测试，见审查记录（外部历史/待归仓路径：`../../build/sp-007/REVIEW.json`）。Host生产h/cpp身份与前轮完全相同，生命周期静态资格按有效输入复用；本轮运行并不扩大其未验关闭组合。

python -B scripts/project.py check通过（本地文档导航及技能清单完整性）。本轮7个受控root与资源在POSTFLIGHT（外部历史/待归仓路径：`../../build/sp-007/POSTFLIGHT.json`）登记：原预算内exit0、未强杀、整树归零、双EOF、reader join及资源关闭。未创建可见控制台，未启停QMT策略、未调用真实账户或切生产。保留工作区9处未进入固定候选的差异（含一份当前缺失测试CMake），不声称整个工作区通过；旧QMT项目未执行或修改。WT核心两份TraderAdapter摘要与前轮已批准实现保持，框架新增修改0。

## 剩余主路径

本模块解决交易owner时钟/元数据实现及替身装配，正式CTA实例、原ticker/真实策略及两端整体生命周期仍未装配。原WtCtaEngine有公开addExecuter；WtRunner的engine为私有，受管入口要求空交易；WtRtRunner虽有getEngine，原release仅停止日志。接续须沿原公开引擎/上下文/生命周期组合或重整自有桥装配，保留既有限定入口，不能据此绕过关闭资格或修改框架。

在途stop/drain、回调重入关闭、未确认close截止及完整初始化失败收口动态组合仍未验。真实常驻两代、查询/回报与跨进程恢复、历史全库存/尾部、在线价格质量协议和观衡独立发行继续。整体目标active；当前无新增待批准框架项、无需用户操作。
