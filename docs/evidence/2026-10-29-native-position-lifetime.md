# 模块B：原组合仓位条目增长时的内存生命期

类型：隔离诊断证据。结果：组件故障已复现，修复尚未实施；正式产品稳定性继续pending-verification。日期：2026-10-29。关联B-04/B-07及[NPO候选](../migration/native-position-ownership-proposal.md)。新增WT核心修改0、真实券商调用0、新增金融账本0。

2026-10-29用户决定：停止WT框架多线程相关调查和候选修改推进，转回主线开发；未来实际故障按当次现场处理。此前已完成的额外实验原件保留：`build/ms-upstream-position-003`中322个相关框架文件经Git blob原字节校验，64次派生类最小刺激含12次目标故障、50次正常返回和2次等待超时；`build/ms-upstream-cta-002`的32次原策略接口实验均正常返回。受控交错宿主仅完成构建、未运行。以上频次只描述实验；正式业务历史同次根因及调度影响没有由此取得结论。本记录保留历史事实，后续不将上述调查设为主线开发前置任务。

## 输入身份与原故障

C的原件为`build/configured-app-001/NATIVE-FAULT.json`：App托管与独立运行分别在原`GuanhengCtaRuntime.dll`的RVA`0x9cce5`和`0x9ccc0`访问冲突，原Runtime SHA为`73d3f64519f71360b12b3ec3cc8e0c856ae67d3caf9ddbda97d7183d6a4b3c04`。历史同次原生栈与寄存器缺失，原件保持。

诊断固定使用`build/ms-business-001`已安装Runtime及既有`WtCore.lib`（SHA `f4fde931bad833b34cbe61a71ea5093f043a28137a77b47eea600abf97046286`）。该库包含已批准NCS生命周期差异；“本轮核心修改0”描述此次诊断行为，纯上游运行故障仍未知。当前四核心文件与该构建的composed副本相同；固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`的`WtEngine.cpp`已含相同`find→PosInfoPtr&→对象锁`源码，静态所有权缺口早于NCS。

`build/ms-runtime-fault-001/RESULT.json`将旧对象/库重链接并生成MAP。原函数完整320字节与原Runtime相同，SHA为`5049586113ad7785e48d9973cd5a530689ef4fa1374074dcf0f586dd51efd9e8`，起点`0x9cc60`，两故障为函数内`+0x60/+0x85`。整个.text另有321字节差异，不能声称整个重链接DLL等同原DLL。

## 复现与观察

| 原件/步骤 | 实际结果 | 证明范围 |
|---|---|---|
| `ms-runtime-fault-003/LOOP.json`正式配置10次 | 9次主链通过；1次测试直接读取strategies.json发生PermissionError，原生exit0；均无捕获AV | 失效实验保持失败；连续通过未关闭历史故障 |
| `ms-runtime-fault-007`最小组件 | 1024条目正常完成2048任务；8192条目时在原任务+0x85捕获RAX0/read0 | 缩小到原基类任务与容器增长 |
| `ms-runtime-fault-008/REPEAT.json` | 先以原tick启动worker，Sleep2ms，再创建8个零仓位并投递原tick；12进程中2次AV/10次完成18任务 | 两次分别+0x85/RAX0/read0、+0x60/RBX18/write18；旧RDI均在观察到的当前vector外 |
| `ms-runtime-fault-009`早期持久化driver | 第16进程在+0x60捕获非零非法指针；driver仅接受null形态而失败，未形成完成收据 | 原件保留，推动判据按失效引用而非null特例识别 |
| `ms-runtime-fault-010/REGRESSION.json`当前命令 | 64进程中14次同指令AV（+0x60为11次、+0x85为3次）；50次18任务全部完成/正常停止；14次错误清理字段全true | 更强组件负例；10次故障地址为非零非法值，旧slot可能被重用 |

已实际执行的持久化命令（仓库根、Python3.10+、Windows x64）：

```text
python -B tests/integration/qmt_cta_product/diagnostics/position_growth.py --component build/ms-runtime-fault-008 --output build/ms-runtime-fault-010 --expect existing-fault --runs 64
```

该命令退出0表示捕获并识别预期的既有故障，修复状态仍为未实施。`--expect clean`要求全部进程正常完成；编译器/符号身份准入与正式产品回归仍须在实际修复构建后核验。输出目录必须新建，重复运行使用新的独占根。

诊断组件源已原字节保留为`tests/integration/qmt_cta_product/diagnostics/position_growth.cpp`；观察器为同目录`exception_probe.cpp`。组件只调用原`do_set_position`和原`WtEngine::on_tick`，使用零仓位和隔离目录，无策略、ticker、真实行情、Trader或券商。没有复制PnL算法。观察器记录固定字段/最多16展开帧后返回`EXCEPTION_CONTINUE_SEARCH`，原异常继续终止进程。

`WtEngine::_pos_map`采用vector-backed unordered_dense；新增条目可能搬动其中的`shared_ptr`slot。后台任务持有slot引用，原对象锁覆盖对象内容，无法保持旧slot有效。组件当前MAP函数起点`0x55ee0`：`0x55f40`的`xchg [rbx],al`对应+0x60，`0x55f65`的`movsd xmm0,[rax]`对应+0x85；与C原两处偏移对应。每个捕获组件保留同次CPU寄存器及6帧栈，实际调用链为原lambda→task_loop→thread invoke。

## 证据边界、资源与身份

CPU寄存器及ExceptionInformation属于故障时刻；观察器随后读取的slot/vector仍可受其他线程影响。`warm-8-01`读取的旧slot为double10位模式，不能由事后值推回故障时slot内容。显式bind-vector模式中`old_runtime_layout_read`表示成功读取绑定vector头，`engine=0`是未使用的旧字段，不表示真实engine为空。独立审查逐项核对这些限制。

错误进程的原native.run收据确认root_reaped、job_tree_zero_observed、reader_join_confirmed、pipe_eof和resource_closure_confirmed均true。成功进程由原native.run成功合同及原任务计数证明关闭；成功case没有独立的显式清理字段收据，不能把null写成一组实测true。所有目录均为独占诊断根，固定原DLL、静态库、配置及金融文件原件保持。

| 身份 | SHA256 |
|---|---|
| 008复现原件REPEAT.json | `d84e04a5c18faa9d487dc8e50918090460c77e6895a578a1a4d46a0490183587` |
| 010当前REGRESSION.json | `73001891a8e16006dcbb4ae35dff01ac5403abd273ffa9d9351c5b09e6b9aeb6` |
| 诊断组件源码 | `969c99b8b1ce030a0b12a780ecb79e11adef81630b6eb9814c5d71b2f2fed600` |
| 观察器源码 | `c44ce7b4a84efdd4810a0670fb0e96fcba4184110f52c3f4823e29a33191f01e` |
| 当前持久化driver | `7e1687b34e8f46047b6215af7a880ae2cda3e0d5322ffe4a0f4765486ecda479` |
| 008诊断EXE | `8227388a284a5b3cfa587f590ca454bef77cf9dda709f645093bffae834e0ea0` |
| 005/008观察器DLL | `ef66499980429d298b64c5305fc9ee1ab99f72db5e6ed8cead307d9548dba1fb` |
| 007独立REVIEW.json | `033ab1d1c7cb6c933f4d01bd0aa0549aed31838cf3b2bfd349a54713dc4bdc0c` |

独立审查确认同容器的CTA/SEL创建/遍历需共同覆盖；指出只复制shared_ptr仍缺同步，以及append_signal前必须释放对象锁。该审查支持收敛四核心文件的内存所有权候选，完整修复、修复后正式产品稳定性及模块B完整资格继续待验。当前未申请或取得真实交易/发布权限。
