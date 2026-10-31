# 模块B：正式策略数量决策的原用户变量恢复

类型：开发验证证据。日期：2026-10-29。状态：R12-C1、C2四类拒绝、C3所列边界、C4所列应用异常及C5安装/包范围通过，完整R12和模块继续。规格：[NRT-R12](../specs/native-realtime-strategy.md#nrt-r12-原用户变量中的数量决策恢复)。新增WT核心修改0、额外停止保存0、真实券商调用0。

## 实现与调用链

自有ManagedStrategyBridge仅转接WT已有用户变量读写，每个原策略上下文使用固定键`guanheng.quantity.state.v1`。正式configured入口保存原NSQ的冻结StageState及观察序号，通过原dirty KV保存、原初始化加载；恢复时用原NSQ公开构造器、绑定身份及state_id校验后继续原advance。策略与组合金融状态仍由WT原文件承担。

独立审查REVIEW-001发现：自有INIT回调锁存失败后，原自有桥仍正常返回，宿主可能继续启动行情生产者并发布ready。现由自有Strategy::on_init在回调结束后立即传播已锁存错误，沿既有Session::start异常边界结束启动。修改位于`src/GuanhengRealtime/ManagedStrategyBridge.cpp`，原WT文件保持。

## 固定输入

根目录为`build/ms-configured-recovery-001`。`BUILD-004.json`绑定自有桥及三份App源码、已安装wheel、原Runtime和输入快照；SHA为`2d2ffb359c0721011614e16cc15cd9339d3ab80cc62a5e530a48a3796831d142`。沿P21原Runtime与原执行链，仅重编自有策略DLL。Python使用独立普通venv、22项固定依赖，App wheel沿BUILD-003，三份B源码与安装内容一致。

测试使用明确的合成证券、账户及SDK替身，经过实际安装Runtime、标准策略Factory、原CTA上下文、原Parser/Reader及Host/Journal。实际券商、QMT界面和生产配置均未操作。

## 实际结果

| 用例 | 观察 | 证明范围 |
|---|---|---|
| `configured-clean-005` | 正式configured模块实际启动两代；首代A700/B700、净买1400一次；两代24查询；第二代恢复相同state_id，观察序号接续，新增SDK0；两代正常关闭且recovery_ready=true | C1，同一安装、代码/输入与原状态根的正常恢复；本次未加载异常观察器 |
| `init-failure-001` | 原INIT已登记主K线后抛出ValueError；callbacks=1、setters=0、创建/销毁策略各2；四次初始化查询、SDK0；ready文件缺失、原closed失败且recovery_ready=false；自然退出、双EOF和reader join及Host资源关闭 | C4的INIT失败传播，失败不进入后续行情生产者启动调用或ready发布 |

两用例入口为`tests/integration/qmt_cta_product/run.py`，分别使用`--configured-python --configured-clean-resume`与`--python-callback --installed-python-api --callback-init-failure`。原件为各目录`RESULT.json`、`POSTFLIGHT.json`，以及`CONFIGURED-RECOVERY.json`或`callback-init-failure-proof.json`。正常返回由原native.run总预算/Job/pipe回收合同验收，产品子进程回收由POSTFLIGHT独立记录。

## 审查与未覆盖范围

REVIEW-001对旧BUILD-003的147项绑定确认C1，记录上述P2和C2–C5缺口；REVIEW-002已绑定193项关闭INIT传播P2，当前增量无新增P级问题，SHA为`4b4e5c3b3889b1336901fbe302610e25a414edda3d427007a1843df99abf1eb3`。既有失败实验保留原件，当前通过不覆盖其历史同次根因。

C4原向量第n项中途失败、实际KV登记/文件I/O失败仍待验；本次应用异常注入发生在完整setter或KV登记成功之后，投影异常发生在实际publish之前。上述范围分别登记。异常跨进程恢复、跨根交易责任、全部保留业务版本及真实账户/行情资格分别验收。本记录只授所列实际范围。

用户已决定停止WT框架多线程调查与候选核心修改；已有实验保留为历史记录，后续实际故障按现场处理，当前主线继续。

## 后继：恢复拒绝、兼容与部分副作用

后继生产输入继续使用BUILD-004，生产源码和运行DLL保持。测试入口增加显式测试参数，安装模块代码文件保持原字节；故障仅在测试子端内存注入，并继续调用正式模块main。

| 验收 | 原件 | 实际结果 |
|---|---|---|
| C2 | `reject-missing-001`、`reject-json-002`、`reject-binding-001`、`reject-invariant-001` | 首代通过原KV登记相应故障值或保留缺键，原产品生成clean证明；次代沿同一证明/原load及正式decoder拒绝，原金融文件21/23项前后完全一致、第二代setter及SDK增量均0，原clean已消费，失败不生成新clean |
| C3 | `state-api-001` | 32768字节完整往返，32769/空值/NUL/非ASCII及小读取缓冲拒绝；原INIT/SCHEDULE/其他事件阶段、跨OS线程、错误/过期epoch及复制所有权均验证；A/B原用户键独立，正常600+400买1000保持 |
| C3 | `legacy-fresh-001`、`legacy-recovery-002` | 冻结旧桥保持fresh买1000；显式恢复精确以state_capability拒绝，原配置/策略创建计数及查询均0。Runtime/旧桥DLL已装载，gh_cta_run尚未调用 |
| C4 | `partial-setter-002`、`partial-kv-001`、`partial-projection-001` | 原完整向量setter已进入8次后发生指定应用异常；保留原ValueError、health=-6及runtime失败阶段，SDK0、recovery_ready=false且无clean，策略创建/销毁各2，完整自然回收 |
| C5 | `headers-005/HEADERS.json` | 从安装目录编译C及C++消费者，实际加载固定DLL核7个原布局、state ABI1/MS ABI1及无借用拒绝 |

历史`actual_installed_runtime_dll`测试字段沿“原生运行入口实际调用”口径保留；新字段`native_runtime_entry_invoked`和`runtime_dll_load_confirmed`明确区分调用与装载，能力拒绝原件另有GetModuleHandleW及原计数证明。

`reject-json-001`首代出现访问冲突，退出码3221225477，原件保留且不计通过，未开展框架调查；002完成相应用例。`partial-setter-001`原测试误断阶段名，原health检查实际锁存runtime阶段；按源码修正断言后002通过，原件保持失败。

## 后继：独立安装与开发交付包

最终开发包为`build/ms-configured-recovery-001/GuanhengExecution-configured-recovery-dev-007.zip`，SHA `f9423d65eb4ebfe679a54533ad1dddbb060037d2f52bb95187dd0c1eb5917924`，55项约35MB，包含实际安装前缀、22项完整wheel/哈希锁、原生d1/HTTP Reader及WtDtHelper、许可证和操作说明。CPython3.12/Windows x64为显式外部前提；A的生产行情Parser和来源配置按统一集成提供，合成Parser/SDK夹具仅用于验证。

006包已在`build/ms-configured-relocated-006`全新根/普通venv完成无索引哈希锁安装、pip check及正式两代恢复；第二代新增SDK0，Host/源/进程/EOF/join均关闭。`AUDIT.json`将22个wheel的1904个内容成员与原/新安装逐字核对，22份RECORD按安装器正常重写单列。007只增加四份许可证及候选编号，installation/wheels/requirements-lock全部字节与已验证006相同，PACKAGE-007记录逐文件复用依据。

`MATRIX-007.json`绑定208项及最终包，SHA `0d54236106b0fb99f32d8b5300b8499be9f2d3c4cb3fb46117e4d00521d1c766`。它重新核当前生产源码、已安装DLL、原件、资源回收和文件摘要；最终测试定义与较早原件按实际影响复用，未声称所有较早进程执行了同一最终测试文件字节。最终独立审查及交接材料沿本构建根登记。

该包为模块B开发候选，App为隔离a10；C须在当前App保留三份B薄适配及原公共控制读取修正后重打统一候选。整体模块B、真实交易和生产切换均未完成或授权。
