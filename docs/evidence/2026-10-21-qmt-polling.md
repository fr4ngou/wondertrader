# QMT 持续行情插件验证

类型：候选验证记录。日期：2026-10-21。状态：QNP隔离开发验收通过；真实收盘后只读接入通过，生产常驻与完整WtRunner资格pending-verification。规格：[QNP](../specs/qmt-native-parser.md)、[HTTP](../specs/qmt-http-market.md)。

## 触发条件与修正职责

默认ParserQMT工厂此前创建未配置端点的MarketParser，标准加载后缺少持续轮询。自有QmtPollingParser读取受管配置，在worker内拥有签名HTTP客户端、端点和通用parser，并在投递前处理重复快照与订阅边界。

原10项并发/配置单测通过；真实签名HTTP替身→默认DLL→原ParserAdapter→原CTA公开on_tick的8场景运行曾通过，重复测试则在adapter停止后清理阶段出现 `0xc0000005`。隔离回归 `qmt_polling.retained_tick_survives_worker_and_parser_destruction` 在未修复二进制中明确失败。原因是原WT线程池对象超出其分配线程生命周期仍被缓存持有；原WTSObject源码已说明此约束。修正归于自有QNP投递边界，以独立堆对象保持原API/retain/release语义，原框架保持冻结。

独立full指出另两项缺口：HTTP请求结束后仍有系统关闭回调，worker结束不足以证明DLL可卸载；临时订阅集合应在逐项准入时即受容量约束。当前候选已实现逐项容量、独立tick和HTTP系统回调排空。三项分别保留P1/P2/P1的原full记录，未用单次通过覆盖退出失败。

## 原始证据

- `build/native/reviews/qnp-full-87dca177-32e2-4464-9697-0873fab0e74d/`：首次full报告、最终规格和当时源码摘要。
- `build/native/qnp-retained-tick-red.json`：旧二进制红例输出；编译源码与取证时已改源码分别登记。
- `build/native/qnp-ctest.xml`：首轮10项通过、HTTP宿主退出失败，属于修复前记录。
- `build/native/runner-audit/ticker-662012fae5b24cdcbfef15ffe817196c/summary.json`：独立原ticker普通异常/stop后析构/运行中析构三组控制；范围限自持ticker，完整WtRunner仍待验。

## 验收范围

生产框架没有新增修改；12个既有框架文件与冻结摘要一致。QMT主工作树只读，现场服务、账户及交易状态保持。HTTP替身验收包含原HMAC/DTO oracle；真实终端和最终制品结果见下方，资格分别登记。

完整WtRunner/ticker的就绪、分钟调度及退出继续独立验收，详见[运行器审计](../migration/native-runner-boundary.md)。ReaderHttpClient使用另一套WinHTTP实现，尚需独立补齐回调排空；本轮QMT客户端修正不授予Reader DLL卸载资格。存量MarketBridge void销毁不提供有界确认，新关闭接口与消费者适配作为后续工作。

## 最终修复复验

统一命令：`python -B scripts/native.py all --offline --qmt-source D:/workspace/qmt --calendar-owner-source E:/workspace/qmt-worktrees/wondertrader-service-adapters`。原始日志 `build/native/qnp-final-all.log`；CTest `build/native/ctest.xml` 共86项、85启用通过、1原有禁用、0失败；32项流水线测试通过。QNP原生12项含retain→worker退出→parser销毁→继续读取/release，以及10000代码超额批次的原子性和停止可达性。

真实WinHTTP门闩四组通过并显式卸载DLL：独立session辅助层在回调未返回时Pending/Timeout；正常client实际同步关闭，超时client实际请求已返回而关闭回调仍在执行；QNP准备阶段取消时stop(700ms)/destroy(0)保留依赖和Close=0，放行后stop成功、Close=1、删除和卸载成功。测试宏仅专用fixture，无持有tick场景下的卸载结论不授予仍持有tick的宿主。

默认DLL→原ParserAdapter→原CTA公开on_tick的8场景通过，pool0/2、重复快照、新时间、来源变化、冲突、倒序、错误配置/认证和超时均覆盖；搬迁包同8场景通过。原ticker与完整WtRunner未在此探针启动。

## 实际18010只读接入

同一最终ParserQMT DLL SHA `c80623759421fbe017060546413b4c69555f8911c427604a71d13b3315f886e7`。10秒请求预算下，默认工厂取得单证券快照，12秒轮询观察窗仍connected，重复收盘快照去重为1次投递；外部stop成功、Close一次、进程退出0。脱敏记录 `build/native/live-source-probe/polling-6100f67f2dc24050b9ef2d2acd2e777b/acceptance.json`。此观察发生于收盘后，未证明盘中持续更新或生产长时间稳定性。

初始3秒探针三次中1次通过、2次在连接后无quote关闭；不以重跑覆盖失败。独立客户端预算对照：3秒read返回Timeout/qmt_http_deadline（含prepare总5080ms），10秒read成功（总6963ms），记录 `polling-budget-diagnosis.json`。10秒是本次探针配置，生产默认保持原规格。队列等待与实际取数耗时仍需拆解；长期运行资格pending-verification。

## 评审及最终制品

延迟只读调查另存 `build/native/live-source-probe/latency-audit.md`：三次空闲health GET为415/1012/999ms，prepare与read至少六次HTTP且各有预算。安装策略每秒调度、每轮一项operation、完成后留下一轮响应投递，相关逻辑与当前源码一致。总耗时不能直接当作原生取数耗时；后续须结合现有request_admission/queue_wait/execution/response计时分段定位。终端及调度配置保持原状。

独立full的F1/F2/F3已由delta关闭，开放实现问题0。报告 `build/native/reviews/qnp-delta-d50182d4-2a19-4d3e-aeef-5d50799fff06/` 绑定最终源码、原始测试和构建输入，摘要不匹配0；系统事件创建失败/64槽耗尽未作故障注入，保留验证范围限制。

完整22阶段全部通过。开发包 `build/native/packages/dev-20261021T110015Z-b2d60cbb.zip`，6,220,695字节，SHA256 `7d8b27988ce3773039559b141630b648896d7a12cf853cdac66ba214724dc726`。最终receipt的源码身份与当前输入相同；原框架12个冻结文件摘要一致。本包未部署，未连接真实交易。
