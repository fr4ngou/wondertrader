# 固定来源只读插件原生构建与开发包

类型：验证记录。状态：本地固定来源开发包隔离验收通过，最终独立 full 审查待完成。依据：[NQP规格](../specs/native-readonly-package.md)。本记录只覆盖显式 `qmt-readonly-fixed` profile；真实终端、生产运行和交易副作用分别验收。

## 输入与责任

WT 固定对象为 `08b230dd05facf6d650d949bfe51054115a2ecb1`，受控 QMT 固定对象为 `34777db5eab144d6fe8a2f259b9f2c0de167435a`。原 `native.py` 继续拥有工具链、依赖、受管子进程、阶段收据、CTest、安装与归档；固定输入、配置和阶段组装位于自有 `native_support`，没有第二个发布 CLI。当前脏框架源码及历史 original-build 库不作为本 profile 编译输入。

普通插件仍编译四个自有生产 TU；宿主从固定原库及四个原 Adapter TU fresh 构建。普通与门控 DLL 分开工作目录，测试参数显式绑定探针、库、CWD、自有测试快照和受控来源。私有 QMT 源只在生成目录作临时 Journal/loopback 合成验证，不进入 WT ZIP。

## 当前已取得的证据

- `formal-001` 锁定依赖 audit 通过；快照期间自有输入变化被正确拒绝。`formal-002` fresh 177 个编译/链接步骤通过，后继 Ninja 相对依赖审计明确失败；路径已锚定实际 CMake 目录，并加入当前脏头逃逸拒绝回归。
- `formal-003` fresh 构建通过，6/8 CTest 通过；HTTP/drain 在深层输出复制固定来源时触发 Windows 路径限制。显式固定来源改为就地验证，副本保持不可变。
- `nqp-004` fresh 177 步、8/8 非空 CTest、59 项流水线回归及 ZIP 归档验证通过；包级二进制验证受到本机 Python `.pth` 自动启动和受限 PATH 冲突而明确失败。其 ZIP、manifest、收据和失败日志均保留；此包没有取得完整开发包资格。
- `nqp-005` fresh 构建通过，6/8 CTest 通过；HTTP/drain 在 `-S` 隔离下暴露通用 helper 的未使用 DTO 导入依赖。原通用 HTTP 默认继续加载原 DTO；NQH 显式关闭未实际参与其响应验证的 DTO 导入，仍执行真实固定 HMAC/Core/Queue/Journal 和原 32 字段/自身映射断言。包级子进程统一使用 `-S -B`，资格边界明确登记。
- 当前 15 项 profile 编排回归实际通过，包含默认入口兼容、跨 profile/cache 拒绝、verify 无构建工具、缺明确外源提前失败、依赖审计、包内容规则、不可变来源和有界宿主预算。当前完整集合62/62实际通过；最终冻结候选仍须按自己的快照重跑。
- `nqp-eng-010` 使用 005 生产 DLL 和独立编译的新测试宿主，delete-ready 及两项映射截止门控实际通过；功能用例采用显式 5s request/30s round，宿主覆盖 round+close+10s，设置 60s 测试上限。专门截止用例保留各自预算；这项调整不授生产 SLA。旧 006/007 的来源排队超时原件保留。
- `nqp-eng-010` 的 read-request-timeout 在 5s owner 下实际成功完成四查询。原 POST 结果未知后沿原 ID 认领属于现有传输设计；HTTP 100ms 配置与 slow_post800ms 不足以保证最终失败。严格原因/阶段断言拒绝该用例，当前未授其超时资格。
- 隔离诊断 `nqp-eng-015` 通过强制 202、慢 GET 认领8s，在 owner5s 前 observed4016ms 得到 `qmt_http_exchange_failed` / `IoError`；实际 POST1、同ID GET1、原生查询1、投递0。原 QRT 异步 REQUEST_ERROR 分支统一归为 IoError，当前未读取原始异步错误码，因而此证据覆盖传输失败，不覆盖 Timeout 分类。生产实现未变；后继已明确更名 `read-get-transport-failure`，精确验证实际 GET 传输失败/IoError；原始异步错误分类缺口单独保留，工程017已完成targeted4/4、搬迁binary3/ABI19/no-connect3、外部固定原Core HTTP86/86及drain4/4，全部通过；生产DLL来自005、宿主为独立测试构建，因此仅授工程接线资格。

HTTP 日期与 metadata 负向用例必须到达精确原因、查询数、投递位图及原 SPI 阶段，早期超时不能替代命名故障。旧 repair 失败原件和 SHA 继续保存。新功能预算只处理测试自身目标竞争，不宣称修复生产超时。

## 最终 fresh 候选 nqp-018

生成根：`E:/workspace/wondertrader/build/native/nqp-018`。原 `native.py all --profile qmt-readonly-fixed --qmt-source <受控固定源> --jobs 4 --offline` 返回0，`receipt.json` 状态 passed。开始前冻结 OWN72，缓存只复制经原 owner 复核的依赖源码/下载及锁定 backend wheel，生成目录当时没有 CMake、对象或 `.lib`。

| 阶段 | 实际结果 |
|---|---|
| 固定输入 | WT323 / OWN72 / QMT1526；与预冻结摘要匹配；生产源与005相同 |
| fresh 编译 | 177步，66.101s；配置179TU，实际生成对象对应159TU；未构建配置项为13个Boost宽序列化与7个spdlog源 |
| 实际依赖与链接 | 2520条去重头/源依赖、18条链接命令；对象162含3个CMake探测；库14含DLL导入库、exe6含工具链探测、DLL2 |
| CTest | 8/8非空、无失败/跳过；总191.51s。fixture68、根因60、补充8、HTTP86、drain4、ABI19、未connect3、CNG3按各组登记，部分断言跨组复用 |
| 原流水线 | 当前快照62/62通过；原锁定 backend fixture真实构建，无wheel安装/分发资格扩授 |
| 安装与归档 | 普通DLL、三普通探针、CRT、验证闭包、许可与来源；78个manifest清单文件，ZIP 2,942,319字节；门控/CNG/private QMT源未入包 |
| 包级搬迁 | binary正常/空/失败3、ABI19、no-connect3通过；显式外部固定Core HTTP86/86通过（162.411s），原HMAC/Core/Journal真实模块摘要匹配 |
| 普通/门控PE | 普通8导出，门控14导出；动态依赖为CRT/WinHTTP/bcrypt/系统库，无WT/Boost/spdlog动态库 |
| 末尾稳定性 | 原owner与独立复核均确认OWN/三个固定快照/对象库DLL保持各自摘要 |

ZIP：`packages/dev-qmt-readonly-20261022T024355Z-d8335df3.zip`，SHA256 `0440632b81cfeb7463b3d8a3bd070f432f2b6b9217a7b9cd2bc93fde1805c7f6`。普通 DLL SHA256 `48222d95f214ab443ea822845c91f744d609fe27b876d5718aa2c3cd7f7094cf`。交接文件 `handoff-manifest.json` SHA256 `1ecc800e7d15ee978ab6cb094674e790f8cc155960f9983c568a0793d1b04440` 绑定正式收据、CTest、固定输入、实际编译/链接、PE/包审计、关键故障原因及独立verify。

另一次原入口 `verify` 在 `E:/workspace/wondertrader/build/native/nqp-018-independent/new location` 通过；该路径含空格，外层和验证子进程使用 `-S -B`，PATH只含Windows/System32与Windows，清除QMT、编译器和库环境，不提供QMT源。实际归档+binary3/ABI19/no-connect3通过。机器本身仍安装构建工具；本证据证明运行无需发现/执行这些工具，第二台机器尚未验收。

## 尚待范围

独立 full 审查、第二台Windows主机、真实QMT终端、生产发布及真实委托各自尚未验收。QRT异步REQUEST_ERROR的具体 `dwError` 分类信息缺口独立保留；本轮仅验证原实际IoError契约，HTTP100ms精度和独立Timeout分类不在当前资格内。

所有工程与开发包验证使用隔离合成QMT；当前真实数据开发/验收仅以QMT为来源。既有失败、快照、ZIP和收据保持原样；017工程证据与018 fresh资格分别登记。历史缺字段诊断不计当前资格。

CI 已配置显式 profile 与受控只读来源输入；固定 34777 对象属于原源分支，squash 到主干不会自动使它成为主干祖先。目前未推送本候选、未配置该读取 secret、未验证受控远端可 checkout 此对象，也未实际执行托管 job。缺源时明确失败，保持托管资格未验；入口不会回落到远端 master。

运行方法见[构建手册](../runbooks/build.md)、[测试手册](../runbooks/testing.md)和[原生部署手册](../runbooks/native-deployment.md)。目前没有生产安装、终端重启、账户变更或真实委托。
