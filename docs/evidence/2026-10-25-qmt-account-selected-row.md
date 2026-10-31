# 完整原查询的单行金融映射验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。范围：accepted SEV-R5d-A 的唯一金融mapper选行、Shm metadata共用及既有链兼容。当前新探针、原金融/匹配/回收与Common19/Standard31/Retry9全部实跑通过，独立动态复核已通过。完整补查、P8双来源、启动/重连交接和生产发行继续待验。

## 根因与实现

纯匹配可以在完整查询中找到目标原行，同时排除定位明确不同的缺字段行；原全批金融转换仍会因该无关缺字段行失败。新入口直接借用完整原数组的选中行，沿原唯一循环完成解码、WT构造、视图和规范输出；完整查询原文及来源保持。包装分别持原下标/总数和单行输出本地0。机械选择与完整查询唯一匹配的职责由公开接口注释明确区分。

Shm入口共用拥有data Document和metadata的准入helper，返回值独立持有来源与WT数组，旧全批/事件入口的金融规则和错误次序保持。[权威规格](../specs/native-qmt-standard-events.md)与[模块边界](../modules/qmt-shm-connector.md)为当前正文。

产品只修改AccountMapping.h/.cpp、ShmAccountMapping.h/.cpp；P8、Common客户端、Standard产品和WT框架未新增修改，无第二份金融账本或人工交易资格。

## 固定编译及静态审查

最终候选为固定003构建（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-selected-row-fixed-003/result.json`）：158份自有输入、323份原上游输入，commit 08b230dd05facf6d650d949bfe51054115a2ecb1。12个显式目标实际编译；原上游取Git原blob，本地既有框架差异未进入此编译。原生依赖沿已缓存锁定输入，不下载新SDK。

full独审（外部历史/待归仓路径：`../../build/qmt-account-selected-row-independent-full-001/REPORT.md`）发现缺少多行合法全批对照的测试定义；003 delta（外部历史/待归仓路径：`../../build/qmt-account-selected-row-independent-delta-003/REPORT.md`）确认已关闭：ORDER/DEAL各三条合法且可区分原行，按source_to_output取得原WT对象，对照真实getter、规范记录和只归一本地index的视图。两报告及126份raw由根逐SHA复核，见复核记录（外部历史/待归仓路径：`../../build/qmt-account-selected-row-work-001/STATIC-REVIEW-VERIFIED.json`）。

001首编译失败保留：新probe动态JSON key表达式与Windows small宏冲突；修正仅在测试代码。002编译通过后，按独审补全合法多行回归并重新冻结/完整编译003。001/002原件保持，当前运行资格只绑定003。

## 实际原生运行

四探针结果及控制器链接（外部历史/待归仓路径：`../../build/qmt-account-selected-row-work-001/PURE-RESULTS.json`）保存本次实际stdout。

| 入口 | 实际结果 |
|---|---|
| 新selected-row | 五组，1768次显式检查通过 |
| 新选行分配失败 | mapper ORDER60/DEAL70，Shm ORDER732/DEAL730，共1592点逐一注入，通过旧输出保持与本轮临时new分配归零检查 |
| 原金融/规范/事件/inspection | 128/115/31/142通过 |
| 原matcher | 72通过 |
| 原append资源转交 | 4通过 |

分配注入包含真实WTSArray/vector路径；其中392次沿原Common profile validator把bad_alloc翻译为Backpressure，再由原Shm边界转换为固定异常，单列计数。注入只覆盖本线程global-new及其数组/aligned/nothrow形式；RapidJSON malloc/realloc、CNG内部资源与物理OOM保持未覆盖。固定槽为8192，各路径观测点数上限1024；没有新增产品故障钩子。

四个controller分别耗时0.687/0.344/0.344/0.359秒；均无控制台、创建期Job成员、exit0、forced=false、tree0、双EOF、读线程join与resources_closed。有限逻辑预算与这些结果不构成整个进程物理内存上限。

## 当前金融mapper整链兼容

使用最终003编译的八个实际制品与同一CMake tree的追加核对收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-selected-row-compat-append-003/result.json`）。当前166份Python运行输入重新冻结，只有未被方法导入的build.py相对前轮变化；原59方法集合保持。

| 批次 | 当前状态 |
|---|---|
| Common | 19/19通过（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-selected-row-common-003/result.json`），无失败/错误/跳过 |
| Standard/WinSHM组合 | 31/31通过（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-selected-row-standard-003/result.json`），严格原19事件场景，无失败/错误/跳过 |
| 事件读取恢复 | 9/9通过（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-selected-row-retry-003/result.json`），无失败/错误/跳过 |

三批均核原166份运行源码、158/323固定输入、cache和八份实际制品；耗时18.938/37.922/51.969秒。均exit0、forced=false、无控制台、创建期Job成员、tree0、双EOF、读线程join和resources_closed，见三批汇总与控制器（外部历史/待归仓路径：`../../build/qmt-account-selected-row-work-001/COMPAT-RESULTS.json`）。最终独立动态报告（外部历史/待归仓路径：`../../build/qmt-account-selected-row-dynamic-independent-003/REPORT.md`）确认本范围complete，无新增P1/P2；1356份原件约20.65MB、12制品、55份case复制DLL、9控制器及62原生子进程逐项核实。根逐份重核源/raw字节及SHA，见动态复核收据（外部历史/待归仓路径：`../../build/qmt-account-selected-row-work-001/DYNAMIC-VERIFIED.json`）与最终收尾（外部历史/待归仓路径：`../../build/qmt-account-selected-row-work-001/VERIFIED.json`）。原001编译失败和002历史范围保持。

## 未覆盖及下一步

合成DTO只验证metadata接缝；近期这组运行真实券商SDK调用0，不连接终端、不下单撤单、不切换生产Factory。A的canonical输出额度不替代后继全阶段来源/HTTP/候选并存预算。下一步按同一原任务截止接通真实补查、完整查询与原事件双来源P8、既有身份/去重与锁外SPI；首次/重连覆盖事实仍须真实来源依据。完整历史、连续实时/T+1、保留业务和独立发行继续属于整体未完范围。
