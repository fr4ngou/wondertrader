# 原生CTA与查询优先执行宿主装配

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：自有C++装配、原ticker策略主链、配置拒绝和安装头消费已取得限定证据；实际业务策略、真实连续来源、完整异常/恢复与发行继续。要求见[STQ-P16](../specs/native-qmt-standard-trader.md#stq-p16-原生cta与执行宿主装配accepted开发中)。

## 实现与复用

新增CtaExecutionSession通过公开接口组合原WtCtaEngine、WtDtMgr、ParserAdapterMgr、CtaStraContext与原策略工厂，并挂接已Ready的StandardExecutionHost.command。原引擎继续拥有ticker、理论部位、策略上下文、过滤和目标汇总；原MinImpact/Local/Adapter继续执行目标，券商查询继续拥有实际持仓和订单。自有装配提供控制线程生命周期和跨线程停止请求，没有新增金融账本、日历或调度算法。

现金股票的原sub_tick也要求HotMgr；初次装配漏传导致访问异常，现构造接口必需IHotMgr引用并提供原WTSHotMgr空规则实例。原目录getter缓存进程路径，生成根由外层在首次WT插件初始化前独占创建，Session核同一目录和空CTA状态。配置公共类型与所有活动Parser先统一检查，再原engine/data/parser初始化；原后台任务失败沿task_failure观察、关闭准入且不重放。

close按停止准入、ticker请求、Parser停止确认、原ticker/pool/tasks join、Reader停止确认、原工厂删除策略、上下文及插件释放、执行宿主关闭推进。策略删除false/throw锁存尝试并保留Impl；局部timeout不替代原进程截止，未确认依赖保留到进程结束。原Runner默认入口和受管空交易配置限制保持。

## 实际主链

最终矩阵（外部历史/待归仓路径：`../../build/sp-008/configuration-matrix-002/RESULT.json`）包含18个实际Ready宿主的无效配置拒绝及1条完整正向。正向为原Factory/Context→原ticker闭合→原目标汇总/有界桥→原MinImpact/Adapter→实际Host/Win32 SHM→明确SDK替身，未手调schedule。策略初始化与原闭合调度各1次，同一目标200股在券商查询100股基础上只产生1次100股SDK替身提交，8次实际查询，最终观察P=100、未成交=0；未将替身提交解释成实际成交。

最终正向原生结果（外部历史/待归仓路径：`../../build/sp-008/configuration-matrix-002/positive/main/native-result.json`）还核非owner调用拒绝、跨线程request_stop关闭新准入、Parser在途0、Reader分钟1/删除1、策略删除1和Standard API查找为空。夹具独立核SDK/账户查询由原Agent owner线程调用；19案Host/Agent/HTTP/代理及原生子进程均确认关闭，真实券商调用0。最终矩阵根约57.48秒正常exit0。

确定性行情自然日2026-10-28，执行/SDK模拟账户日2026-10-22，均明确记录；原ticker用实际等待闭合，Clock冻结只供组合验证。该结果不授真实交易日一致性、T+1、真实连续行情或业务策略唯一核资格。

## 配置与根因回归

修前Ready反例（外部历史/待归仓路径：`../../build/sp-008/ready-config-red-001/main/native-result.json`）中riskmon.active={}被错误接纳，拒绝断言失败，退出仍确认关闭；原Boolean实现假定标量，必须由自有边界先核类型。修正后18例覆盖Boolean的Object/Array、pool/product/store/session/module/id错误类型，以及缺省后没有活动Parser的情形，均在行情DLL装载前按Configuration拒绝，4查询、0提交并删除策略/API。

原JSON加载器省略null字段。正向另核三个null可选字段确实省略且读取为缺省false；没有将被省略的null当作可识别的独立类型。当前装配要求带类型WTSVariant，原YAML标量String未取得该入口资格。插件私有字段仍归插件验证。

## 来源、构建与安装

固定上游08b230dd05facf6d650d949bfe51054115a2ecb1加既有批准查询及14份NCS覆盖，净346份固定输入、263份自有输入，共609份；完整来源审计（外部历史/待归仓路径：`../../build/sp-008/APPROVED-SOURCE-AUDIT.json`）逐字节匹配，新增WT核心修改0。编译调用方沿既验CMake政策及Windows系统头顺序，不改上游源码。原算法工厂在同一固定输入中编译，最终测试不借用前轮二进制。

GH_STANDARD_CTA产品库与GH_STANDARD_CTA_MAIN测试驱动分开显式选择；实际构建图（外部历史/待归仓路径：`../../build/sp-008/BUILD-GRAPH-RESULT.json`）核缺省无CTA库、显式仅库有CTA库，两者均不含确定性插件/主链驱动。原默认行为保持。

最终安装（外部历史/待归仓路径：`../../build/sp-008/INSTALL-RESULT.json`）在新install-002目录生成13文件，包括8份公共头、两个自有静态库和Standard DLL；仅以实际安装自有头和原SDK编译消费端通过。该物料仍需匹配原WT库/SDK和ABI，不是完整独立发行包。

## 审查与资源

独立full及两次配置/来源语义delta已完成，原类型gap已关闭，无剩余实质静态gap；见源码身份及范围（外部历史/待归仓路径：`../../build/sp-008/REVIEW.json`）。审查只读最终规格、规则、源码，未运行测试或读任务/历史/执行报告。静态审查与上文运行结果分别成立。

临时验证记录（外部历史/待归仓路径：`../../build/sp-008/DEVELOPMENT-NOTES.md`）保留全部初始失败及后继结果；收尾审计（外部历史/待归仓路径：`../../build/sp-008/POSTFLIGHT.json`）记录实际根/整树、EOF、reader join、资源及文件身份。运行采用隐藏受控进程，无QMT策略启停、真实下撤单或生产切换，旧QMT项目保持只读。

## 剩余范围

本切片确认初始单策略、poolsize=0、新生成根、确定性Parser/Reader的主路径。Parser/Reader pending及删除异常、在途停止/重入、原任务故障动态注入仍待验；策略原回调异常和插件热卸载未取得资格。实际业务策略同核、真实行情/账户连续运行、两代常驻重连、完整交易恢复、历史全库存/尾部/在线质量及统一独立发行继续，整体目标active。当前无新增用户批准项或必需手工操作。
