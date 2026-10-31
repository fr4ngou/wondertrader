# 独立WT执行包迁移与关闭证明

类型：开发验证及接口交接。状态：in-progress / pending-verification。要求：[模块B](../migration/module-b-delivery.md)、[NRT-R19](../specs/native-realtime-strategy.md#nrt-r19-独立wt执行装配)、[STQ-P24](../specs/native-qmt-standard-trader.md)、[WRI](../specs/independent-wt-runtime.md)。真实下撤单、生产切换与新增WT源码行为均未执行。

## 已确认问题与实现

观衡生命周期中的执行装配已按ADR-0016迁至独立WT包。五个模块为execution_process、execution_strategy、execution_configured、execution_facts、retained_evaluation；只移植唯一正式1.1.2运行闭包，业务数学、NSQ、持仓和绩效沿原owner。固定工厂读取绑定descriptor，返回原start/status/request_close/close协议，构造阶段没有进程或金融文件写入。descriptor字段和身份要求以NRT-R19为唯一正文。

原main-010真实资料隔离运行已完成后继P发布：券商观察revision2包含四证券，与四笔SDK替身买入一致；策略进入waiting_actual_cycle。该次原生进程后来exit2，而旧v1闭合证明已写，暴露出“子进程尚未最终退出即自行确认退出成功”的边界错误。修正在自有证明发布owner：native005只写prepared，父监督者实际观察exit0并完成Job/管道/句柄回收后发布最终closed.v2与clean.v2。非零退出不发布完整成功组合。金融文件内容与WT保存入口保持。

main-010已从临时C目录迁至`build/ms-real-retained-001/main-010`：89文件逐项SHA一致、原专用目录已删除，收据为`MAIN-010-RELOCATION-001.json`，SHA `f3dcefbfe3b4b2264e836b4edf5dadb1a93a07968aea10fb186ff4c8e9183251`。原件内历史绝对路径保留其原字节，定位使用迁移收据；后续项目临时文件、缓存和制品均在E盘。

## 固定安装与证据

路径均相对仓库根；冻结原件保持原内容。

| 材料 | 实际身份及范围 |
|---|---|
| 源迁移清单 | `build/ms-standalone-execution-001/MIGRATION-001.json`，登记原/目标全部SHA及四个抽取函数身份 |
| 独立源码快照及wheel | 同根`source/`及`wheels/`；完整清单在INSTALLATION-002 |
| 普通独立安装 | 同根`INSTALLATION-002.json`，SHA `bade14387de216c31ccd51fd2c5a665d8102c1ad11e5f8cee2220651268e776e`，六发行/720带摘要RECORD全部匹配且single-link |
| 独立解释器 | 同根`runtime-002/Scripts/python.exe`；App、FastAPI、Starlette、Uvicorn均不可导入 |
| 原生运行库 | `build/ms-retained-runtime-001/native-005/BUILD.json`，SHA `0a37f6f9e9fcd60aa42b9733d2f187906901a733e33d5773ce632d1273c77e7d`；运行DLL SHA `ec7e363283bce510735bebe3bb2d245cb31b4e5a03fef8273f2da00db1f8de38` |
| 关闭组件 | 独立根`close-component-003/RESULT.json`，真实文件系统七案通过；进程退出事实由fixture提供，不能代替实际恢复 |
| 先前实际正常候选失败 | `build/ms-close-confirmation-001/normal-001`，运行中plugin_error10、host_fault3、exit1，prepared失败、最终closed/clean均未发布；外层NORMAL-OUTER-CLOSE-001核实际Job/管道回收 |
| 独立实际启动失败 | 独立根`retained-004`，trader阶段plugin_error10/exit1；target控制者无App/Web、原生reaped/EOF、失败prepared、无最终closed；源proxy实际2秒HTTP超时，完整正常业务资格未通过 |
| 独立实际业务链 | 同根`retained-006`与`retained-008`，唯一1.1.2实际卖200及后继converged；完整股票退出仍失败 |
| 实际异常恢复拒绝 | 同根`unclean-001/RESULT.json`及`UNCLEAN-PROOF.json`，实际异常5份金融文件复制后Ready前拒绝，4查询/新SDK0，源与副本SHA保持；外层与目标owner完整回收 |
| 工厂实际准入 | 同根`descriptor-001/RESULT.json`，普通安装工厂完成9项坏输入拒绝及native/Python两种合法构造；构造没有创建进程，金融和控制文件摘要不变 |
| 最终独立审查 | 同根`REVIEW-001.json`，full/delta核输入；原QA P2关闭，新增P1/P2为0，正常退出/两代及系统整链仍gap |
| 适用静态检查 | 同根`CHECKS-001.json`及PROJECT-CHECK-001.log，十个Python源码语法/五个已安装B模块身份一致，文档导航检查通过；不授运行资格 |

首次独立普通安装的uv默认hardlink使包文件nlink=2，被既有输入身份准入拒绝。INSTALLATION-002使用相同六wheel、`uv pip install --link-mode copy`生成新根，全部720摘要记录nlink=1；没有放宽准入。第一安装保留为历史失败输入。后继retained-005按显式来源排队5000ms、执行1000ms及同一原总截止运行；QA代理与Trader HTTP预算均为8000ms，覆盖已选来源预算，生产实现保持。

retained-005仍在首查询失败；原通信Journal为terminal、error_code=qmt_call_failed，SDK明细查询及订单均0。沿夹具数据流发现初始化循环将保存各证券可卖量的sellable字典覆盖为单个整数，detail(position)调用其get方法抛AttributeError。已改临时变量为initial_sellable。`QUERY-FIXTURE-REGRESSION-001.json`重建旧QA原字节并与RUN-INPUTS-005摘要核同，直接执行原Fixture.detail AST：旧路径AttributeError且查询0，新路径返回持仓/可卖各200且查询1，SDK0。该证据定位自有夹具错误，与WT线程无关；retained-004另有2秒代理超时，保留其独立范围。

retained-006修正后在实际无App/Web目标环境ready，唯一1.1.2完成selling→converged，sh50_trailing_exit目标经原Factory/NSQ/股票单元及真实WinSHM运输执行替身卖200。13次SDK替身查询、1次替身委托，源/代理无首错，Host/源/HTTP均完整关闭。原生随后exit2，stderr仅表明OSError；目标父owner核reaped/双EOF且未生成最终closed/clean或prepared恢复标记。外部控制者exit0、其Job树0/reader join/EOF/句柄回收均有outer原件。业务片已运行，完整正常退出仍失败，故未生成整体成功RESULT。

retained-007尝试附加时，QA控制投影仍用不可变文件读取器，实际遇到Windows共享冲突32，未取得异常调试资格。QA读取已统一复用market-client的read_status/CollectionStatusPending，允许同句柄旧快照并沿原D轮询；控制者同时传递原startup及stop绝对截止。后继retained-008成功附加本次目标PID，捕获关闭期间c0000005，访问类型8（执行），dump SHA `596ce688bff70c8d512b3677d1472c60d1c931d93ac58127b6e6327974deb4f5`。原debugger附加/分离/join均成功、无错误、controlled_schedule为空。栈扫描slot0候选返回地址为WtExeFact.dll+0x1baff，与既有固定原股票商品release位置及独立引用缺额证据对应；扫描结果保持候选范围，未声称完整栈展开。源/目标及外层回收保持，WT源码改动0。

unclean-001将retained-008的5份原金融文件复制到新根，以同一独立安装调用正式工厂。原resume_clean在Ready前拒绝，4次查询、新SDK0、无最终closed/clean/consumed，失败prepared与failure的控制ID/配置SHA/PID匹配；原件和副本10份摘要相同，目标原生reaped/双EOF且无forced/pending，源/Host/HTTP关闭六项均通过。`UNCLEAN-OUTER-CLOSE-001.json`记录QA根exit0、Job树0及全部资源回收；目标控制者自己的outer也全部通过。该用例只证明缺完整证明时拒绝恢复，正常两代与异常责任继续运行尚待验。

## 接口交接与待完成项

运行组件工厂为`guanheng_wt_runtime.execution_process.create_process(descriptor_path, expected_sha256)`。共享runtime.py已使用该接缝；A保持公共运行/installer所有权。安装执行闭包见`apps/wt_runtime/execution-requirements.txt`：runtime a1、market-client0.15.0、core a8、native a1、v1 a6、tzdata2026.3。本片锁定迁移前已验的策略包字节，C当前后继版本须另按其最终交付重新绑定，不能静默替换。

C需将BT对retained_evaluation的消费统一至独立包，并把strategy_replay_facts的SessionError、_native_json、_decimal、admit_native_files改为从execution_facts导出，删除旧位置相同实现。B保持C文件原状，四函数源片段摘要已交；该迁移尚未完成，暂存两侧胶水不具有最终唯一owner资格。原App三执行入口的兼容退出需随C依赖/入口迁移处理，冻结历史制品不改写。

QA将Host/HTTP运输替身放在外部测试解释器，独立WT解释器实际调用正式工厂，再启动绑定策略子进程；目标进程内检查无App/Web。共享QA原件保持，专用快照仅迁移ThreadOwner/ProcessJob导入及显式HTTP预算，逐份源/快照SHA写入SOURCES.json。来源、SDK替身及清理断言保持原实现。该范围与完整统一运行实例分别验收。

独立full审查已核源码迁移、构造、恢复与六发行身份；发现异常恢复QA仍读旧closed路径，已改为读取失败prepared并断言无最终closed/clean，实际拒绝用例及最终delta复核通过，新增P1/P2为0。审查保持整体pending-verification及正常退出根因unknown边界。目标控制者在start前保存原输出buffer引用，关闭后按该引用采证，避免基类回收重置成员后丢失stderr。

执行安装需消费完整requirements文件及固定六wheel；uv路径显式指定`--offline --link-mode copy --python <独立解释器> --find-links <固定wheel目录> -r <execution-requirements.txt>`。运行组合仍使用WRI原CLI及已绑定配置，不从QA输出复制账户或权限配置。普通pip复制安装方式另按其实际安装验收；本片实际命令及日志在E盘独占根。最终开发归档、SHA及可复核源/证据清单由该根DELIVERY-001.json登记，资格为部分开发片，不能替代完整B模块或生产部署。

正常独立主链、最终同根两代、实际异常恢复拒绝、真实新开仓周期来源、完整资金/T+1/费用、同输入全周期BT/RT、WRI完整组合及观衡断开后的持续运行仍未授资格。股票组件既有提案保持原审批状态，任何异常按同次现场归因，不推定为WT线程故障。
