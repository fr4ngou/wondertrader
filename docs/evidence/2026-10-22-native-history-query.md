# 2026-10-22 原生历史查询接入

类型：代码及隔离验证记录。状态：限定开发验证及独立full/delta通过，开放发现0；生产与观衡用户入口尚未接线。要求见[NHQ规格](../specs/native-history-query.md)，能力依据见[原生数据能力](../modules/wondertrader-data-capabilities.md)。本轮跨北京时间午夜，原能力调查及CORE-008记录保留原日期。

## 实际行为与范围

原`history.query/read`和`NativeHistoryLoader`共用Store。显式`native_reader`配置后，Store校验来源/摘要/冻结/DSB帧及大小，公开IRdm工厂承担完整解码、索引和范围查询；查询退出Helper完整解码后遍历全量历史的旧路径。Helper继续承担发布、合并、恢复和测试oracle。未配置的开发候选兼容保留，原生失败明确返回错误。

Reader使用真实WTSBaseDataMgr加载显式基础资料，contract/product经原CodeHelper标准化，ETF不硬编码成股票商品。固定上游接口的输入前置条件在适配层验证：畸形JSON结构和超长原生标识先拒绝；DSB先核帧大小，再固定首条流式预读以防止晚于支持截止的数据进入原count索引。完整历史只由原Reader加载一次，不另建历史索引或行情库。

内容变化采用Reader换代，唯一后台线程通过公开delete工厂释放旧代际；查询不并发clearCache。缓存载荷计入在用及待释放代际，最多一个待释放实例；紧预算先背压、释放后重试可推进。借用切片及时释放，调用方持有复制结果。此路径限定独占历史根，出现`rt`目录即拒绝，未授DMB混读或通用热卸载资格。

本轮所有可用已跟踪src摘要959项与切片开始一致，334个原未落盘对象保持缺失：`build/native/native-query/boundary-check.json`的`changed=[]`。此前用户批准的CORE-008四行和其他冻结核心差异保持；本切片没有新增框架修改。QMT主工作树、数据库、真实终端及生产均未改动，测试仅使用独立生成目录和签名HTTP替身。

## 构建、输入与原生结果

MSVC x64、Release/C++17，正式构建目标为`GuanhengNativeHistoryQueryProbe/GuanhengMarketBridge/GuanhengmarketTests/GuanhengDataFixture`。最终构建日志：`build/native/native-query/build-final-inputs.log`，退出0。源码、规格、测试及二进制摘要固定于`test-inputs.json`，测试后回读输入漂移0；早期编译尝试日志保留为工作记录。

| 验证 | 实际结果 |
|---|---|
| 相关CTest | 32通过、0失败，86.12秒；含28项原市场测试、新NHQ、原行情服务、原导入fixture和原空计数回归 |
| 新NHQ原生检查 | 21通过、0失败；全字段、Loader、区间/空档/覆盖、追加/修订、结果副本、快速换代及容量恢复 |
| 配置负向子进程 | 30例全部正常拒绝并退出0；根标量/数组/null、危险嵌套、超长标识分别运行，断言/崩溃不能代替拒绝 |
| 有效摘要下的坏DSB | 4例全部正常拒绝；错误头/type、未知解压大小、非bar整数倍帧，sidecar先重新计算SHA，确实进入格式准入 |
| 原行情服务回归 | 44个Python测试通过，含5个新HTTP/from_env/ETF用例；补数后读取、离线缓存、空区间、损坏和同实例刷新 |
| 原空计数回归 | 72通过、0失败；本轮使用已批准修正的正式Storage，原先红例依据保留于NRC记录 |
| 真实已导入分钟 | 两证券428根逐字段与Helper独立读取一致，真实源目录前后SHA一致；使用显式合成基础配置，仅授数据读取开发资格 |

新NHQ详细结果：`build/native/cmake/test-work/native-history-query/run-334af69e16394e9da1519e86f299481b/result.json`；主进程和34个负向子进程均退出0。`real_source_unchanged=true`。证券为SZSE.300308和SSE.688076，分别239/189条，原来源覆盖限制保持，未宣称完整交易日或全市场验收。

本次合成修订查询7ms，关闭等待5007ms，快速下一代触发背压，紧预算退休后成功推进。数据量和机器限定使这些值只能证明本次行为；十年全市场吞吐、RSS与硬实时截止均未测。关闭使用原检查线程join，实际调度不能保证严格5秒。

CTest原始输出固定于`build/native/native-query/final-last-test.log`，摘要和JUnit为`final-ctest.log/xml`。JUnit会截断单测试stdout，44项Python及5个新服务用例的完整输出以固定原始日志为准。

测试后仅澄清规格中的既有时间预算：`history.read`在本地读取后检查剩余截止，`history.query`只提供大小限制，客户端超时不表示原生调用被取消。实现和测试未变；测试时规格摘要保留，后续文档差异独立记录于`build/native/native-query/documentation-clarification.json`，不伪造为测试时输入。

关键二进制SHA-256：

- GuanhengMarketBridge.dll：`b3428246127dabf000682bb394d8bf52e96edc54fe73eb8b3a4ae72d0952d60e`
- GuanhengNativeHistoryQueryProbe.exe：`2991e9d79ffa1375f132ced3cbbe76a68261892777618b81bc3fab97dae9e334`
- WtDataStorage.dll：`f467d34a1291a10042ea6d9d8cb30b471e128c7b943cd622aed14669e36d7294`

## 审查与剩余资格

首次独立full覆盖接口、缓存代际、线程/释放、来源边界与规范：`build/native/native-query/independent-full-review.md`。审查发现的首次未来数据前置条件、配置根类型及后续标识长度问题均已在适配层修正，并加入对应真实DLL子进程负例；最终delta报告`build/native/native-query/independent-delta-review.md`已逐项关闭，开放发现0，SHA-256为`1a97fdc4e7662cf22d73fdeb1bfcf5d3624b0be103c9112fc8e714d2953692a6`。报告绑定当前规格及实际测试输入，文档预算澄清单独登记。

尚待：原DataFactory全字段、多时段和修订资格；图表/研究用户入口；原CTA多证券闭合/预热/恢复接线；QMT真实主动1m补齐和来源最终性；交易接入及独立业务发布。策略ticker不使用本同步磁盘/HTTP补数链。当前固定Reader的停止标志仍为普通bool，本次未声称整个上游无数据竞争。

未制作新的完整开发包；此前完整包资格只覆盖原输入，本轮DLL与测试记录不扩授旧包或生产资格。
