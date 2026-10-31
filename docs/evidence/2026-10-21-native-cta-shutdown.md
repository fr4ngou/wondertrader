# 2026-10-21 原生 CTA 退出复查与修复

类型：验证记录。状态：开发隔离验收完成；生产未发布。规格：[NCS](../specs/native-cta-shutdown.md)。用户授权与既有冻结边界见[当前决策](../migration/current-approval.md)。

## 复查与根因

再次查询官方仓库HEAD，固定上游仍为 `08b230dd05facf6d650d949bfe51054115a2ecb1`。原始源码已有CTA ticker.stop、HFT析构stop、parser/trader manager.release及pool等待；WtRunner只公开init/config/run，退出轮询结束后直接返回，CTA析构直接删除ticker；实时Porter.release只停日志，回测stop_backtest属于另一套replayer/worker。

独立Astra源码复核保存于 `build/native/existing-shutdown-recheck/astra-report.md`，81项输入摘要随报告保存。结论为局部方法存在、当前实时Runner缺少完整可达接线。停止路径由原所有者补齐，保留原分钟调度，采用明确启用的受管模式。

本轮再次执行修复前二进制（SHA-256 `5c53211523f8252b9bcce420ba957ad83c1e39f5081699467a025a3f60a06316`）的原入口负例：`build/native/existing-shutdown-recheck/red-before-fix/observations.json`。Pending calculate=0、同实例恢复2根历史保持；信号返回后exit=3221226505（0xC0000409），无watchdog kill。旧脚本只记录observed，正常退出断言为失败；新测试严格要求exit=0及停止/析构顺序。

该二进制来自工作区构建，包含此前冻结的差异；Runner/CTA/ticker相关原样身份及匹配MAP定位见[原退出提案](../migration/native-cta-stop-proposal.md)。没有把工作区二进制称为纯净上游发行版。

## 实现与审查范围

14个核心文件：Runner三、CTA/ticker四、base两、parser两、DtMgr两，以及CtaStrategyMgr.h。后者增加显式释放策略的入口，保持策略先于context销毁。复用ticker.stop/pool.wait及QNP/NHR已有stop导出；任务队列同锁准入/关闭、排空本地与共享批次，异常保留首错和未执行数量；运行器通过stop_requested观察失败并以非零退出。配置/连接失败经同一清理链处理。

配置启用前要求CTA、内嵌parser列表、空traders/executers、risk monitor/notifier关闭，stop/deleter在创建插件之前核验。普通信号仅写lock-free原子标志；控制线程执行join。stop未确认时保留对象与依赖。插件模块保留到进程末端，整体严格截止与热卸载分别保留其资格边界。

首次独立full识别3项P1：配置异常/策略init失败、parser连接失败未传播、task异常未触发控制侧停止。相应实现与新回归已补，源码及最终运行证据已关闭上述3项。首轮完整回归132/133通过，integration.managed_runtime揭示ParserAdapter.run默认返回语义扩大；已恢复默认语义，仅受管Runner显式启用严格连接结果，并保留同一不可用端点的双模式回归。失败证据保存在build/native/cta-shutdown-pre-compatibility；修正后定向运行时7场景通过。第二轮完整回归132/133通过，唯一失败为新增manager负向测试仍用默认run；已改为run(true)与正式受管调用一致，生产逻辑未再改变。第二轮证据保存在build/native/cta-shutdown-compatibility-test-adjustment，第三轮完整流水线23阶段全部通过。审查原始输入/报告位于 `build/native/reviews/cta-shutdown-full/`。

## 验证登记

| 验证 | 当前观察 | 证明范围 |
|---|---|---|
| 修复前真实Runner负例 | 0xC0000409，无kill | 原触发条件仍存在 |
| 首轮原生构建 | pass | 首轮源码可链接；后续异常修复须重编 |
| 首轮22项退出回归 | 22 passed，15.90秒，`cta-shutdown-first.xml` | pool0/2正常、阻塞回调、HTTP在途/idle；4配置拒绝；task与插件生命周期 |
| 最终新增异常、并发及回调请求 | 41项新增CTest通过（13原生、28进程场景） | 配置false/throw、connect失败、task异常无外部信号、双stop及重复stop、回调请求、never-run和默认兼容 |
| 完整流水线 | 23阶段通过；133启用CTest通过、1既有disabled；32工具链测试通过 | 编译、SDK、回测、原生与业务适配、安装及搬迁链 |
| 二进制包退出 | 4场景通过，exit=0、无kill | pool0/2正常、pool2阻塞回调、pool0休市等待；包内Runner/QNP/NHR与构建摘要一致 |
| 独立full/delta | NCS-R1..6完成，开放发现0；42审查输入匹配 | 原始XML、28份完整进程记录与输入摘要独立核验 |

首次证据只对应首轮源码。最终源码哈希、原始XML、流水线receipt和日志保存在 `build/native/cta-shutdown-final-evidence/`，包退出原始UUID记录位于 `build/native/cta-shutdown-package/`。最终编译输入SHA-256为 `3272f49b1f4db7d46212183c112c096275819e3e8655735f839191f761fc36c6`。CTest自身日志339.85秒，流水线阶段计时340.075秒，二者口径分别保留。

制品：`dev-20261021T130655Z-8dec7ed3.zip`，6,240,975字节，SHA-256 `dff27429fad37c226cb6f400daaebefea499db3e4b0ba477e61e28535d52ed80`。`summary.json`登记包、三项运行二进制和4份搬迁场景摘要。该包为开发验收制品；未部署、未切换正在运行的QMT/观衡服务。

## 范围与后继

Windows隔离进程使用本机随机端口合成来源，无真实下单、撤单、终端重启或生产发布。保留原有Pending与补齐恢复语义；不据此宣称实时Porter、HFT/SEL、交易/执行器、主动风控或notifier已具备完整受管退出资格。任意回调无限阻塞时仍须外部监督；本轮证明释放顺序和正常排空，不承诺全局严格时限。

此前冻结12项摘要中，ParserAdapter属于本次批准覆盖；其余11项保持原摘要。整体观衡接入目标继续active，行情来源和业务接线后续验收独立推进。
