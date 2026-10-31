# 观衡永久源码与独立读取发行

类型：接口规格。状态：accepted。前缀OSB。依据Root对App71/004永久源码归仓的明确委派，沿[独立部署](../architecture/adr/0016-independent-wt-runtime-and-observer.md)及[离线制品](observer-runtime-package.md)，不改变运行或交易职责。

OSB-R1：App唯一长期入口为apps/guanheng；四个读取变体分别位于packages/observer-read-side的strategy_core、strategy_native、strategy_v1、wt_runtime，与WT执行发行分别维护。永久归仓基线为0.1.0a72+source.1。用户要求修复报告503的纯标量转换后继为App 0.1.0a74+scalar.1、Native读取0.1.0a1+read2，沿[BRP](backtest-report-read-performance.md)限定成功纯值复用；原a73读池实验保留失败资格，读池及JSON守卫已恢复原实现。保留a71标准Selector、当前C70运行故障说明/五个前端后继、Core/read2、V1/a7和WT/read4。部署locator继续独立，不覆盖B/Host/WT框架。

OSB-R2：构建声明使用仓库相对永久项目、前端文件和第三方hash锁。薄入口只组织已有Flit构建、角色锁/验包、角色compose及观衡制品；account_runtime_install.prepare的文本精确版本约束保持。逐项目调用固定Flit，角色通过普通PEP440依赖与精确wheel锁安装，原有读取/执行版本各自成立。

OSB-R3：构建解释器、Flit wheel、第三方wheel目录、Node/npm和npm离线缓存均显式提供，记录实际工具SHA。纯离线、全新输出目录；不读取旧QMT、Codex可变缓存解释器、历史build源码或旧venv。第三方输入按永久hash锁验证；私有wheel只从本次永久源码生成。前端在新目录按永久声明文件执行npm ci --offline与原npm run build，静态资产对应其实际源码、命令及编译结果。

OSB-R4：源清单包含项目元数据、全部包成员/许可证、实际前端构建输入、工具及配置；构建前后重新核精确文件集与SHA。所有外部命令沿native.run隐藏创建期Job、有限总截止和输出上限，失败保留现场并返回非零；最终构建收据在完整检查成功后发布。外部缓存只供固定第三方内容，记录不提升其为产品源码。

OSB-R5：角色沿qar.role-artifacts.v1，真实来源标识为本次source-build，不伪称安装；保留App30发行、所选extra、精确requirements和永久local-projects。现有compose/安装器保持唯一实现，独立包沿guanheng.observer-runtime.v1及其原verify/install。安装不启动WT、采集或交易，个人数据和实际市场观察根在包外配置。

OSB-R6：先从全新目录、仅永久声明源和显式依赖实际构建，核未变payload与选中004/App71，C70差异明确单列。随后普通离线安装、公开App入口、账户/分钟/报告/观察及正常关闭；已验真实004只读结果和不变算法/异常回归按精确身份复用，不重发QMT或全池查询。必要构建/身份回归、两轴独审及project.py check通过后交付源码、入口、角色、独立包/安装和完整结果。整系统组合、locator、原生Reader、生产及Git集成由Root/相应owner继续。
