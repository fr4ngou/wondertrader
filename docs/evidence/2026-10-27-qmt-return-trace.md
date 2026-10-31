# QMT返回链与提交组验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27。类型：开发后继记录。整体active。下方准备阶段观察保留原时点；最新现场和构建结果见“实际验证后继”。真实下单、撤单及生产切换均未进行。

## 准备阶段已完成

[前序隔离反馈](2026-10-27-qmt-account-isolated-feedback.md)两案通过，原C++客户端在2ms/1s节拍均完成四查询、11项合成金融值及原资源关闭；独立动态复核（外部历史/待归仓路径：`../../build/qmt-account-deadline-feedback-dynamic-review-001/REPORT.md`）无新增必要P1/P2。这个结果没有复现真实超时。

本轮重新选择QMT主窗口，activate_window实际成功，焦点为GH_WT_MEMORY_VERIFY编辑器；原窗口激活故障本次未出现。仅激活及读取窗口树，未关闭/修改编辑器，未运行/停止策略。终端磁盘正文SHA仍为74f4bc1604cff343aed66dca580a16cfd9894ca6e36243acba8e5cbb6587f46b。界面事实（外部历史/待归仓路径：`../../build/qmt-return-trace-followup-20261027-001/UI-ACTIVATION.json`）不授后续点击必然成功或编辑器缓冲已核资格。

## 准备阶段实施范围

按最小接线合同（外部历史/待归仓路径：`../../build/qmt-resident-return-trace-plan-001/CONTRACT.md`），仅在独立诊断fixture的原App job_factory边界改接同一Host解释器启动入口；在新Host子进程构造阶段组合service.request及ASGI send透明观察。原App/ProcessJob/Host服务生命周期、PID核验、请求数和超时保持。Host子进程自行核来源，不用父加载器替代；不修改WT、产品、安装包或QMT正文。

先封实现并独立审查，再由根执行代理异常回归及实际App→独立Host→WindowsSHM合成四查询，验证真实PID、原响应与异常透传、旁路容量/发布失败及资源关闭，之后再进行真实只读单轮。原Native每类最多一次POST，首次失败按原行为停止；不增加诊断GET、并行扫描或重试。

自有交易适配的提交分组与拆单/Unknown/DefinitelyNotCalled回归在开发中，尚未冻结、编译或授运行资格。历史三能力配对及小样本材料仍为离线准备，真实历史与2021-11-01起全量导入继续。TraderAdapter.h/.cpp的根复核SHA分别f95bdb95aba5838c81a2722198d7c59cd16f717fa58d045b2d5b3ca3079ca90c、c9585665af66b5aea909b03bbb1b44644aad965ca71e811f939737f5d4ebfa35，保持前序批准状态。

当前无新增用户决策或需用户处理事项。剩余技术工作为真实返回链分段定位、历史导入、完整交易恢复、策略与保留业务及独立发行。


## 实际验证后继

### 返回观察器与真实只读现场

003诊断候选经过完整及增量审查，16项纯回归、真实Host解释器离线prepare、实际App→独立Host→Windows共享内存→原EXE/DLL四查询合成链通过。合成四类各一次、11项金融值断言通过，根35492自然exit0/8.995秒，Job整树、双EOF、reader join及资源关闭成立；联合动态审查（外部历史/待归仓路径：`../../build/qmt-resident-return-trace-dynamic-review-001/REPORT.md`）限定该正常路径。002离线prepare误拒安装目录普通硬链接的失败保留，003只修诊断公开源读取器，未改产品、WT或QMT正文。

根本轮已自行关闭GH_WT_MEMORY_VERIFY编辑器、启动该只读策略、确认认证及两次新鲜回调，扫描结束后自行停止同一策略并写stop.request。界面激活故障未重现；其他策略与原18017保持，终端正文SHA未变。实际只提交一次POSITION，后续三类未发；四组unavailable表示本轮未交付账户数据。根41588自然exit2/78.768秒，Native exit3、Host exit0；无forced，App/Host/Native/外Job的整树、双EOF、join及资源均已确认关闭。根收据（外部历史/待归仓路径：`../../build/qmt-return-trace-followup-20261027-001/LIVE-001-ROOT.json`）、单轮复核（外部历史/待归仓路径：`../../build/qmt-resident-return-trace-live-review-001/REPORT.md`）。

安全返回trace记录唯一提交202，Host时轴27422ms，唯一终态200在31422ms；终态HTTP状态本身不授业务成功。对已有私密原件做只读投影后，按本轮完整来源绑定关联到唯一POSITION通信记录：terminal_ok=true、请求timeout3997ms；原生扫描4025ms触发code=-6“单项查询截止时间耗尽”。原生尚未发布请求UUID，因此关联范围为“本轮来源绑定唯一记录+单POST”，保留该区别。安全分类（外部历史/待归仓路径：`../../build/qmt-return-trace-followup-20261027-001/LIVE-CLASSIFICATION-003.json`）、分类动态复核（外部历史/待归仓路径：`../../build/qmt-resident-return-trace-live-review-001/classification-dynamic-003/REPORT.md`）。

Host排队→开始887.663ms、Agent完成字段−Host排队2887.655ms属于wall-clock字段差；Agent完成字段不等于Journal提交时点，六项零值timing是默认值，不能解释成SDK或传递耗时为零。已确认券商查询成功和原生owner单项截止的边界；HTTP客户端返回、worker发布/owner取结果和共享内存响应各段仍待定位，当前没有据此修改WT框架或延长预算。

### 提交组构建及纯状态回归

提交组、SDKReturned责任保留、Unknown与DefinitelyNotCalled处理已在自有扩展实现并完成静态审查；未增加本轮WT框架差异。首次sg-001构建在原240秒预算内未进入编译，失败材料保留。独立准入分相单次在同240/235秒预算内40.828秒完成，完整来源/依赖/三快照前后校验均通过；这次时序不能反推首次慢因。准入复核（外部历史/待归仓路径：`../../build/qmt-order-gap-group-admission-perf-live-review-001/REPORT.md`）。

原冻结构建入口在新sg-002中完成八目标、九制品，根52404自然exit0/210.342秒，来源/owned/依赖/工具四后验成立，完整资源正常关闭。使用固定原版WT与已批准TraderAdapter两文件覆盖，未带入其他dirty框架差异。构建收据（外部历史/待归仓路径：`../../build/qmt-return-trace-followup-20261027-001/GROUP-BUILD-002-ROOT.json`）、独立动态复核（外部历史/待归仓路径：`../../build/qmt-order-gap-group-build-live-review-002/REPORT.md`）。

同批实际制品运行：NqpCState通过33场景/378断言（含实际layout、64MiB完整配置拒绝）；NqpUnknownCancelStateProbe通过49场景/2126断言；新增NqpSubmissionState在前三场景通过后第四场景失败。三个外Job均自然归零/EOF/join/资源关闭，失败未被标为通过。纯状态原件收据（外部历史/待归仓路径：`../../build/qmt-return-trace-followup-20261027-001/PURE-STATE-ROOT.json`）。正在区分产品实现与第四场景fixture/oracle；28项默认兼容和新运输方法尚未执行。

### 当前剩余与决策

当前无需用户启停策略或决定新方案。技术工作为真实返回阶段根因、新增提交组第四场景失败、后续运输与恢复回归、真实历史小样本及2021-11-01起1分钟全量导入、策略/保留业务与独立发行。历史三能力配对仍为离线材料；真实账户四查询和完整迁移尚未完成。
