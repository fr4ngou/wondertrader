# 历史行情公开ABI适配验收

类型：开发验证记录。状态：004独立full为request_changes；F001后继修复的12组验证及独立delta通过，开放发现0；未发布。要求见[NHA规格](../specs/native-history-public-abi.md)，职责见[文件适配模块](../modules/native-bar-file.md)。本记录承接[vendor资格更正](2026-10-22-native-history-vendor-inputs.md)，限定新的Windows历史profile。

独立full实际复现：持有最终文件句柄时，普通父目录重命名被拒绝，NTFS junction祖先可被换名并在原路径放入另一文件；WinAPI按路径重开读到替代内容，持有句柄仍读原内容。此机制影响原IRdm及私有Snapshot的路径重开，违反NHA-R2及R6；该次攻击探针没有直接调用原IRdm或C++析构，也未输入超大帧。004尚未取得开发审查通过资格，原004/source pack/report冻结保留；后继在自有边界修复并验证实际原生调用及析构。

## F001后继修复与实际验收

新证据根为`build/native/history-public-abi/repair-001/`，生产和测试候选为`build-002`，实际执行为`suite-002`。自有层把根路径交接为卷GUID，限定本地固定NTFS物理目录；逐层持有祖先租约并拒绝reparse。私有快照和待发布输出采用随机CREATE_NEW文件，清理绑定创建句柄；发布限定同一已保护父目录，保持原生公开解码/Reader能力及原DSB/sidecar协议。WT vendor原件保持。

主任务独立核313份vendor Git对象、唯一NRC overlay、全部35份编译源/头和12制品摘要；原build manifest的37份自有项包含2份README，后续文字澄清由documentation-only.json分开登记。959份此前跟踪核心当前摘要无变化，1002项实际执行输入无漂移。已直接回读各日志、结果JSON及38项XML，实际12组退出0：路径36、ABI50、Python4、行情38、NHQ21+34负例、NQW53+1+1、NHP8及HTTP1、NRC72、服务61、业务6、导入22通过/1既有symlink权限跳过。新junction专项实际执行，没有因该权限跳过。

路径36项包括原final-file-only机制可被替换的对照、既有junction路径在原调用前拒绝、实际原Helper/IRdm通过受保护物理路径读取、读取期间祖先改名/变junction失败、成功与异常析构的本次文件清理、外部marker保留及同父发布/跨父拒绝。ABI新增零/重复回调、嵌套/并行TLS和异常logger。此前abi-001的corrupt_writer使用fstream，新增身份租约使其没有实际写坏；后继故障注入改用明确共享删除的WinAPI并断言实际写入，原失败资料保留。没有为这个测试问题修改生产逻辑。

真实428两DSB已由主任务重新比较：当前原文件、旧004保留DSB、由旧冻结清单绑定的sidecar content_id三者相同；NHQ/NQW另有运行前后不变检查。新结果继续保持原量额精度和覆盖限制。根任务收据为root-build-002-verification.json与root-suite-002-verification.json。

| 新输入/回执 | SHA-256 |
|---|---|
| `final-002/validation.json` | `0ba79f6b13a2fba3b60ceeea83ec50799e805be8a1516251060309a92098f647` |
| `final-002/real428-identity.json` | `93941ed754dfa4e6458ce523823df4916decb24e2a402095180cb8c196cee6df` |
| `independent-delta-002/source-manifest.json` | `6c5239cc2b14c307c4b6eea94f507ba9803ea345b5faf06f8d99db0ff085ff29` |
| `independent-delta-002/metadata.json` | `da3c66b236dcf7d947473a3fe6ffaad047045949fb0106d6f20895457acc0c10` |

独立delta已通过上述新包：NHA-F001/P1关闭，新增finding为空，R1–R6在限定范围内complete。1300份冻结源前后无变化、35份编译源/头完整、313 Git对象及唯一NRC独立核验；11个保留测试体与before逐项一致。根任务回读JSON及正文并重算1300份清单，摘要无变化。报告为同目录review.json（SHA `c19765fe944a6c8b6a78879f2d9f8ebfd13e889c0701ca7578ef711fce08ee0f`）和review.md（SHA `d122f2cb04ef91d8edae75d50b4366ca8bbbb6db252c4bf7dee8b248ef20886f`）。001是计数/README信息补齐前的未审包，保留原件。盘符重映射、OOM、真实断电、全市场性能与完整发行包本轮未验，已有测试成功不授这些资格。

## 根因与实现

旧历史实验调用未批准新增的Helper limited接口，其构建还含冻结的通用头、Helper及Writer差异。新profile从固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`提取原源码，只叠加批准的NRC空历史count修正及中文注释；Windows头顺序用构建参数处理。原工作树其他vendor差异保持原样，未参与该历史profile。

自有`NativeBarFile`在解压前验证V2头、类型、单帧、已知解压长度和容量；用不可变私有快照调用原`read_dsb_bars`，完整解码由原Helper承担，索引及派生周期由原IRdm/DataFactory承担。Python显式加载自有`GuanhengNativeBarFile.dll`，核版本/布局/摘要，保留1m/5m/1d。原Helper无limited导出，不改其公开ABI。

原store每次写入新身份，成功资格由完整回读和内容核对确定。校验后持续持有输出句柄，并经同一句柄发布。实际Windows实验发现：目标被拒删除的只读租约占用时，rename返回5，非修改DELETE权限探测返回32；只读文件属性限制下rename同为5，DELETE打开可成功。因此仅实际共享/锁冲突转Backpressure，原队列保留暂存，释放后不重新获取即可发布；真正写入限制继续Io并保留旧数据。原DSB/sidecar单写者及摘要恢复协议继续使用，没有新增共同事务或数据库。

## 实际输入与结果

此前证据根：`build/native/history-public-abi/run-20261022-a1/`。该轮候选为`build-004`；`suite-004`十一组命令退出0、执行输入漂移0。原失败候选及诊断资料分别保留，不授后继候选资格。主任务重算313份vendor Git对象、唯一NRC overlay、964份冻结源和11个二进制摘要；959份此前可用跟踪核心文件无新变化。

| 验证 | 实际结果 |
|---|---|
| 自有文件边界 | 42检查通过；包含帧/预算、原生调用前拒绝、回调完整性/TLS恢复、短写/旧材料、并发写删、目标占用重试及真实权限失败 |
| Python真实DLL入口 | 4项通过，覆盖1m/5m/1d、原Helper缺少limited及错误后恢复 |
| 原完整行情组 | 38项通过；原13项中两项实验断言迁到自有边界，其余11项保留，连同原25项完整执行 |
| NHQ查询 | 21主检查及34配置/帧负向子进程通过，真实两证券428条与原Helper oracle一致，来源目录摘要不变 |
| NQW周期/窗口 | 53主检查、特殊时段1项、首次并发1项通过；真实428输入及周期预期一致，来源目录摘要不变 |
| NHP分片 | 8项原生及1项公共HTTP链通过 |
| NRC空历史 | 同一新profile的原72场景全部通过 |
| 服务与业务 | 61服务、6个NativeHistory业务用例通过；导入22通过/1跳过，跳过为`InputTests.test_symbolic_link_is_rejected`，原因是宿主缺少符号链接权限 |

服务fixture原5秒join恰与上游Reader的5秒checker休眠边界相撞。测试等待调整为有界10秒并加中文说明，线程存活/error硬断言及查询小于2秒断言保持；生产退出预算和框架实现未改。

## 身份与复用

| 制品/清单 | SHA-256 |
|---|---|
| `final-004/validation.json` | `d20e3b49cf860d96c45276b4d9b386d17d66b1b13bd02c81cec326295fae2b24` |
| 自有文件DLL | `e72c232f732ae681d75dbdf03154ba1604b1a68c9563ae6505703934c9f5d741` |
| 原Helper DLL | `79db55eae0e52e0ec4c6716743db0e512c02b43978d021e6b4936880161f464b` |
| 原Storage加NRC DLL | `4ac992f9a4f25f0855f3f81b58be85fedaf53675dbaaf28b46a9c1e4e11d71b3` |
| `market-supplement-001/final-delta.json` | `6696e2ead7a7d1539838cbe86efedba265050ae6f6fcb8312464962b5758c286` |
| 完整38项测试exe | `f8c5e2c3541a272933cb5ebca94cb0a2ab9fcff371ca44bc6647597a53584da6` |

38项补充仅迁移测试与登记，复用004完全相同的实现静态库、原测试对象、importlib和DLL，均绑定摘要。004原整链结果保持原输入，不重标成后来重编译的DLL；新增exe另有源/编译/链接/38项XML证据。测试builder已恢复完整38项登记。

独立审查包`independent-full-001/review-pack.md`，摘要`75b248ec2e10196c67987de762cdc4d52889c68570fdfbd8850201d9491b156a`；1294份冻结源清单摘要`0f08c785a32859086c3a2dde988e0d3c665321c56843647737cf105a04967079`。独立报告为同目录`review.json/review.md`，原313 Git对象/唯一NRC及1294源前后完整性独立核验，结论request_changes、NHA-F001未关闭；原成功回执不替代该缺口修复。

## 资格边界

本次限定Windows历史开发链。真实428样本保持原量额精度及不完整覆盖限制；没有执行真实QMT请求、下载、订阅、账户或交易操作，没有数据库及生产改动。实际保留策略BtPorter回放、完整发行包、生产切换、跨平台及全市场性能继续单独验收。原Reader已有线程机制的全局无数据竞争结论未在本切片取得；自有文件保护与历史-only输入资格分别说明，不扩大为实时Writer资格。
