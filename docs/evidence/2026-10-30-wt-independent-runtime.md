# 独立WT运行包与安装后数据主链

类型：隔离开发验证。状态：独立数据运行包主链、必要故障及独立双轴审查通过；完整WRI组合资格尚未取得。要求：[WRI](../specs/independent-wt-runtime.md)，长期职责：[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。

## 根因及实现

原运行装配在观衡Web生命周期内构造Host、历史、采集及执行owner，导致观衡承担WT运行责任。本轮新增独立`guanheng-wt-runtime` wheel及安装后CLI，按配置组合原组件，把进程生命周期归WT。原生行情、仓位、委托及执行算法新增修改0。

原八个组件文件迁入`apps/wt_runtime/guanheng_wt_runtime`，原输入及目标SHA见`build/wt-independent-runtime-001/MIGRATION-INPUTS-001.json`。原观衡路径的退出由主集成/C处理，冻结原制品继续保存其当时身份；本轮验收的产品进程只导入新安装包。`runtime.py`及`__main__.py`负责固定工厂、共享启动/关闭截止、配置身份、OS实例锁及安全状态；原ProcessJob和各组件收据/未知结果责任保持。

## 固定输入

所有路径以仓库根为基准：

| 输入 | 原件与SHA256 |
|---|---|
| 产品源码清单 | `build/wt-independent-runtime-001/SOURCE-001.json`，`8f089030d87a07a91c3c928f7e8119ef1cdb33ec6b4e91afa70afcafadcebd98` |
| 本轮wheel | `build/wt-independent-runtime-001/dist002/guanheng_wt_runtime-0.1.0a1-py3-none-any.whl`，`ed1817655967b44a2d9491d7d4ef4b2ee23ee60a59771ab96348d7218d5b767a` |
| 源码/依赖/安装成员/QA与证据 | `build/wt-independent-runtime-001/QUALIFIED-INPUTS-001.json`，`724e51489f1ebd35b0c26e5ac6e7e2d15d6bb15e515466624ce0dc407c35df4c` |
| 主链业务结果 | `build/wt-independent-runtime-001/main003/RESULT.json`，`6ebd9a8ec34903a77552444e50389dbf93357a8936d31d4fbf1f4a8f6381d4b7` |
| 主链外层控制 | `build/wt-independent-runtime-001/control-main003/build-wt-independent-main003/result.json`，`c0ca5615b1c062640e8d2c42ad887958182dbc6ecce75840d1fbf668d00c93ac` |
| 必要故障结果 | `build/wt-independent-runtime-001/failures001/RESULT.json`，`99dcaafc861fa7f7271aff3cf85a73867aa39910524334b039d2d1e48ee5fa21` |
| 故障外层控制 | `build/wt-independent-runtime-001/control-failures001/build-wt-independent-failures001/result.json`，`c43e381ba5728be430844b7cb41929cbc9ad95c36ba4f998a3c95dffe6c9863d` |
| 最终输入绑定 | `build/wt-independent-runtime-001/QUALIFIED-INPUTS-002.json`，`c28dd26b6bc199fa7e787fa3d7c175ce86bab9df7221170f1988a88902f8457e` |
| 最终主链业务结果 | `build/wt-independent-runtime-001/main004/RESULT.json`，`c74f1f81d52a1f92c1475596b52277faf5d3015eb20e9bf07009e403ab19c189` |
| 最终主链外层控制 | `build/wt-independent-runtime-001/control-main004/build-wt-independent-main004/result.json`，`3a171a8c0e1e519fa5c9a4e06acebd8e320a558129c7d90eaa224b36371a2305` |
| 独立双轴审查 | `build/wt-independent-runtime-001/review/REVIEW-001.json`，`ec5d8812b0df16877eee96baf7325b718d1b2dde9448e32bd3bf505db3e48b27` |

普通离线环境为`build/wt-independent-runtime-001/installed`，CPython3.14.6；只安装`guanheng-wt-runtime==0.1.0a1`和`guanheng-market-client==0.15.0`，31个非RECORD wheel成员与安装文件逐字相等，查找`guanheng_app/FastAPI/uvicorn`均缺席。Host继续使用其已验独立环境，WT父进程不导入Host包。真实历史由固定R7组件的原Reader服务读取已完成历史目录；现场跨夜目录及活动Writer不在本轮输入中。

## 真实公开入口主链

测试入口为`tests/integration/wt_runtime/main_installed.py`。隐藏创建期Job实际调用安装后`pythonw -I -B -m guanheng_wt_runtime`，配置声明原只读Host、原Reader历史服务及原采集Process协议替身。外层总预算600秒，实际87.247秒，exit0、无强制退出、整树0、双管道EOF、读线程join及资源释放全部通过。

- 真实WT运行PID为22760，Host/历史/采集替身PID分别为44268/68720/65652；ready PID经真实进程句柄核本Job成员，允许venv launcher与实际解释器PID不同。
- 超过旧60秒窗口持续等待，最后一次等待观察为64.539秒；期间Host不退出、历史查询可用，来源binding保持未就绪。
- 两代CPython3.6.8内存策略SDK替身各完成持仓、账户、委托、成交和行情五个请求。SDK均在原来源线程运行，受限文件/网络尝试0；两代认证摘要不同，Host PID不变，旧结果逐字保留200，旧绑定再次提交409，不自动重放。
- 原Reader实际读取510300.SH五根已完成1分钟线，完整SDK响应与此前原生固定收据相等，包括时间、OHLC、成交量/额及来源元数据。此项是单证券真实样本，不授全库存或缺口完整性资格。
- 独立只读消费者正常退出、随后另一消费者`os._exit(7)`后，WT及三个子PID保持；历史查询相等，采集替身计数继续增长。这证明运行owner与独立消费者进程隔离，观衡本体的全部入口与故障资格由C及主组合验收另证。
- 正常停止后所有组件`closed`、`pending=false/forced=false`，WT最终`closed.json`及exit0一致；所有测试来源线程、进程树和句柄回收。

`main003`源码快照在`qa-source-main003`；随后当前QA的通过条件增加`wait_seconds>=60`断言。该QA增量沿原记录独立可核，原实测64.539秒满足，未把修改后的QA字节声称为原运行输入。

最终`main004`在相同产品源码/wheel下重复实际公开入口，新增完整QA依赖身份的调用前后观察，并实际运行超60秒断言。1038项工具、原Host安装wheel/成员、原Reader制品、335个历史来源收据、分钟样本及原基线的摘要前后逐字相等；外部已冻结输入与原`QA-INPUTS-002`、Host安装收据、原组件INSTALLATION及来源自有摘要匹配。`INPUTS-BEFORE.json`和`INPUTS-AFTER.json`均为`2769519e5d130562a48c05fe2f3b41e26800591faabecb7f0ca3e2843b252ea4`。最终90.343秒exit0，最后等待观察64.732秒，WT/Host/历史/采集替身PID分别为76208/68768/39548/648，两代各五请求和独立消费者正常/异常退出后持续运行均通过；最终全owner实际关闭、无forced、树0/EOF/join及句柄释放保持。该后继补齐main003当时未保存完整外部依赖前后观察的证据缺口，主链资格以main004为准。

`SOURCE-001`及dist002界定本轮数据运行包的12项产品输入。开发者1后续在同包加入的执行模块源码属于后继组合输入，当前安装和本轮审查不自动授其资格；统一发行需重新构建完整包并绑定新身份。

## 必要故障及状态责任

`failures_installed.py`通过三个真实CLI场景，外层总预算180秒，实际2.665秒exit0，隐藏Job/树0/EOF/join及资源释放均正常：

1. 同控制根及实例UUID的第二个owner返回2，其控制目录未创建，原实例及其组件持续；原实例随后正常关闭。
2. 原采集owner的协议替身ready后真实退出7，WT返回2并写failure、不写closed；原组件故障保留，pending最终false。启动marker仅一条，自动重启及业务重放0。
3. 配置声明execution而执行接缝或descriptor不可用时，在任何组件启动前返回2，控制根没有组件ready，避免忽略执行或启动半套服务。

纯装配回归六项覆盖启动/关闭依赖顺序、只读status无副作用、共享绝对预算、失效执行准入、启动失败清理及关闭失败继续收口；结果见`unit-tests-001.txt`。

独立Reviewer按规范和规格双轴完成full审查，产品静态未见P1/P2；发现的外部QA输入绑定缺项S-F1通过main004原触发条件复验及1038项独立重算关闭，delta见`review/DELTA-001.json`。最终审查范围开放P1/P2为0，规格整体仍partial；表中未完成项保持独立资格边界。

## 要求状态与后继

| 要求 | 本轮资格 |
|---|---|
| WRI-R1 | 数据主链可独立安装/运行；唯一1.1.2策略及原执行owner接缝待B交付和组合 |
| WRI-R2/R3 | 独立只读消费者正常/异常退出隔离已验；观衡Web全部入口及同实例策略推进待C/主组合 |
| WRI-R4 | 超60秒晚到、两代认证、旧结果保留及旧绑定拒绝已验 |
| WRI-R5 | 原Host/Reader/Process owner及真实历史样本相等；本轮采集为协议替身，原Writer和完整执行另证 |
| WRI-R6 | 已声明三个组件真实关闭与failure责任已验；执行未知责任沿B原协议组合验收 |
| WRI-R7 | 无Web普通wheel安装、原公开CLI、配置/状态/中文手册已实现；统一发行及两侧升级组合继续 |

本轮真实QMT调用、真实账户查询、下单、撤单、下载、现场实例切换、数据删除及WT核心修改均为0。开发安装及合成来源结果不授生产、真实模拟盘或完整系统资格。
