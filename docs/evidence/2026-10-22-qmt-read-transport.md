# QMT共用只读传输开发验证

类型：开发验证记录。状态：隔离开发验证及独立delta通过，首次full两个并发/容量缺口关闭。范围：QRT自有Common传输、旧Market兼容包装器及原实际消费者。最终要求见[QRT规格](../specs/qmt-shared-read-transport.md)，接口/所有权见[模块正文](../modules/qmt-read-transport.md)。

## 行为与原生边界

原数据专用客户端的签名、有限WinHTTP、会话筛选、单次POST和原ID认领、回调排空收敛到Common，旧QmtHttpClient保持Market薄层。新增Account域只准入已声明qmt.account-query.v1的stock四查询；不承接金融字段验证或原生Trader初始化资格。原bounded body、请求ID和HTTP状态得到保留，明确终态与源会话/成功data的不同资格。已收到成功头但已知长度正文截断时，只GET原ID，不重新POST。

构建vendor为固定08b230dd05facf6d650d949bfe51054115a2ecb1加唯一已批准NRC；其他核心源码保持。ReaderGuanheng使用独立ReaderHttpClient，仅共享未修改的WinHttpSessionDrain；本次没有重跑该Reader关闭组。ParserQMT和MarketBridge实际重新链接本次Common；原冻结NHA制品和原证据保持。

## 实际构建与调用链

最终输入`build/native/qmt-read-transport/final-004`，构建`build-003`、执行`suite-003`；冻结后主任务逐一回读2773个清单文件、2429个实际非系统编译输入、160个已生成对象、15个链接库及18个产物，差异0。313 vendor对象、唯一NRC和44个自有快照分别核对。959个跟踪核心与既有基线无新漂移。

| 验证 | 实际结果及范围 |
|---|---|
| 共用Market/Account域、capability、完整body/错误、原ID、截止 | 15项通过，含多个参数子场景，无skip |
| 原Market真实WinHTTP/HMAC/DTO链 | 15项通过，无skip |
| 真实回调排空及卸载 | 6个独立子进程通过；生产无测试导出。qnp在connected之前停止，证明关闭屏障，正常连接行情资格另验 |
| 原公开长历史分片入口 | 1项通过，无skip |
| 回环HTTP→新MarketBridge→原DSB→独立服务→实际安装SDK0.12.0 | 合成3根数据及量额一致，认证负向与无交易能力通过 |

最终validation SHA-256 `634cf8c40b0883219c0ae4690bc246249c108f2d59534d8d005d91901579ead1`，freeze-receipt SHA-256 `fe2e77f9807ffda1eeb84e0f266c5b8083de835ff3742e07b98216e4d842fb4f`，源码清单SHA-256 `d718cf75c2bb664acffa7a81810e247017b1eec135c4fc8cec2c148d68bf5223`。编译依赖生成期的相对路径索引已在冻结前修正；final-003及初始0项中间核查保留，最终资格以final-004和后继根核查为准。

## 独立审查与剩余资格

首次公共接口/并发重构触发full审查。根已按最终输入组`review/full-001`，metadata SHA-256 `e6ea978bb0a9dfc5a04fb992cd8be9ab10794fc8a1c4af00e423b2f422b3b0eb`；独立Reviewer只收到最终规格/规范、冻结源码和验证身份。正式结论为request_changes：QRT-R1–R3 complete，R4/R5 gap。QRT-F1要求在prepare完成后的实际POST/GET读取窗口验证晚回调排空，QRT-F2要求同一owner满64个session、第65拒绝及部分释放恢复。两项为P2验证缺口，静态审查未确认生产实现故障。报告SHA-256 `1cdb3f9c65923412552b4cc785ba8b6d24a810873ffefb53eeeeb3dd5b7e84d5`，位于`review/full-001/review.json`；后继只补对应测试/fixture并独立delta复核，原正式报告及final-004保持冻结。

上述Account测试使用合成版本化回环源。源端执行上下文在独立QMT工作树实现，206项定向及独立delta通过，见[来源候选证据](2026-10-22-qmt-source-build-review.md)，尚未安装；QRT与该源的原生Trader四查询整链、金融归一、真实账户、持续push/恢复、跨进程ticket及生产发布均继续分别验收。没有真实下单/撤单、主动下载/订阅、账户变更、数据库部署或生产切换。

## F1/F2后继验证

后继冻结输入为`repair-001/final-008`，实际构建`build-006`、执行`suite-008`。新增读取/容量6个独立子进程，加原drain6项、共用read15项、原market15项，共42项通过，0失败、0跳过。F1覆盖两域prepare成功后的POST读取及202后原ID GET读取：部分正文、200状态、原请求ID保留，API约185–190毫秒超时返回时回调仍在途，真实body/closing线程均异于owner；原ID仅认领一次，无重复POST；Pending/Timeout、释放、完整排空、后续读取与实际DLL卸载均被断言。该时间为合成回环观察值，不是生产延迟承诺。

F2以测试宏延后关闭64个真实WinHTTP session，使原UNLOAD_NOTIFY_EVENT保留；第65次准入按原容量拒绝，额外HTTP为0。释放8项后保留56项，读取恢复，最终全部关闭、排空并卸载。此场景验证真实session延后关闭，F1另验真实HANDLE_CLOSING晚回调；不把两种门控描述为同一系统调度条件。测试条件块在最外层回调原锁析构后等待，保持生产锁、取消、状态及关闭顺序；生产有效正文一致，实际编译无测试宏，DLL无fixture导出。前三次fixture调度失败保留在suite-004/005/006，未计为生产故障或成功资格。

主任务逐项回读2939冻结文件、313固定Git vendor及唯一NRC、44自有源码、236测试输入、2427实际非系统编译输入、159个TU/object、15个链接库、5个新产物和959跟踪core，差异0。freeze SHA-256为`dda179b09b5b4de8484fc0c2ce241031e874726251fce4bc0b297d57550e1a28`，validation为`cf99c97196d8a8e82de99d1502aecee6ca4e702bb5c7a3b66e74828c771c54a2`，文件清单为`c9fad98b25a0dbe1469b5103406e6cf5443fecd544017db499d8b8dbec3e9aba`。独立delta包`review/delta-001`，metadata SHA-256为`48d74d1628082f484d8637157c16a4a3ad2a87a216f3b9cc7895a0afd153dd28`，复核中。原full报告、final-004及Reader/服务/SDK未变输入的原资格保持；本轮没有重授真实来源、金融、交易或发布资格。

后继独立delta已完成：approve，QRT-F1/F2均closed，QRT-R1–R5均complete，新增发现0。Reviewer独立核验2939冻结文件、生产有效C++ token一致、测试宏编译隔离与实际断言/回执。报告`review/delta-001/review.json` SHA-256为`293d5cf4725be0ab9f7e751a50b6b2beaaa6905eaed833799beac29e9c6a235f`，主任务已实际回读匹配。该确认授本次开发资格，后继继续来源字段与上下文的实际组合、原生Trader领域映射和各自运行验收。
