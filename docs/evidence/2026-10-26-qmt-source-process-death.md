# QMT共享内存源进程异常退出：PD01

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：隔离故障验证证据。日期：2026-10-26。状态：一案实际通过并经动态独立复核；完整故障矩阵及生产资格保持待验。

## 场景与职责

实际使用正常Standard TraderQMT DLL及其Factory/ITraderApi/SPI、原Host/通信Journal、Windows命名共享内存与真实RestrictedTradingAgent。源载体为本测试创建的独立Python进程，券商API全部替身；不操作正在运行的QMT终端或真实账户。Native以同TU复用原standard_probe辅助，未另编金融替身或改WT框架。

唯一insert经真实HTTP/HMAC→Host持久dispatching→SHM→原源owner进入SDK替身，返回门保持关闭。确认原UUID/bodySHA/dispatch绑定、SDK进入1/返回0、Native仍活着后，只终止本次Source Job；该计划故障与后续Native/Host正常关闭分别记账。之后仅GET原UUID核查，不重发POST；第二次新委托在本地拒绝，撤单0。

## 编译及运行结果

固定原版08b230dd构建NqpSourceDeathProbe通过，65.953秒；根核181本仓/323上游快照，EXE ac4116b1fb0fc676822734fc7e781079f9db79b5f9502327c119a9c04e5e6743。复用正常DLL61c9f81e2094dedae1c05bddbf364af1888f3a424faa779985afefb21f4d1980，未修改产品或框架。见集成与编译（外部历史/待归仓路径：`../../build/qmt-source-death-integration-001/BUILD-ROOT-VERIFIED.json`）。

首运行在Host导入FastAPI前失败，Source/Native尚未创建；原件保留。修订仅让Host协调器使用现有venv依赖，Frozen.imports精确保留该解释器的purelib/platlib路径，业务模块仍须来自冻结目录；Source仍直接固定base Pythonw。没有安装全局依赖，CPP保持原样；环境修订审查（外部历史/待归仓路径：`../../build/qmt-standard-source-death-independent-002/environment-delta002/REPORT.md`）与最终运行包审查（外部历史/待归仓路径：`../../build/qmt-standard-source-death-independent-002/runtime-delta003/REPORT.md`）分别绑定实际输入。

后继PD01实际1/1，unittest6.573秒，控制器7.703秒；Node原45000ms监督从启动前一次冻结，实际7807.061ms退出0，guard未触发。controller根PID28328匹配Node句柄；其child69040仅表示venv启动器，Host正文自报PID36704，GetModuleFileNameW实际image为固定base Pythonw且SHA4726f719ee509ee0728bbddce04d110f1b65df5f75c2bebd35b916ed0262bf60。Source正文PID52564精确等其Source Job PID，SDK在源原线程进入，返回/退出门始终未放。

| 观察 | 实际结果 |
|---|---|
| 源故障 | 唯一计划终止，Source树0、双EOF、reader join、句柄回收；不宣称源业务关闭确认 |
| Native | SubmissionUnknown，Pending1、writes_blocked；第二写负返-2，原ID保持；成功委托回调0 |
| Native关闭 | 自然exit0，Closed/join/drain、Factory delete及registry移除；先于Host.close |
| Host关闭后 | 原SQLite owner已关，再以mode=ro查原行，unknown/interrupted、source_result空；原body/hash/绑定/过期事实不变 |
| 外层资源 | 无额外forced，Job树0、双EOF/join/资源关闭；Host/server/proxy关闭、cleanup为空 |

173 frozen源前后身份、实际Host与Source模块来源均由测试校验，资格字段immediate_disconnect_persistence_verified、automatic_parent_death_verified和real_broker_qualification保持false。根实际句柄、原D和业务核查见运行根结果（外部历史/待归仓路径：`../../build/qmt-source-death-integration-001/RUNTIME-002-ROOT-VERIFIED.json`），首环境失败见失败原件（外部历史/待归仓路径：`../../build/qmt-source-death-integration-001/RUNTIME-001-FAILED.json`）。原生64位线程标识按原始JSON十进制字符串保存，避免JavaScript Number精度往返。

## 限制与后续

该案验证源突死后不重发原委托、保留未知责任，以及正常Native关闭后Host能持久原未知状态。它没有运行原TraderAdapter金融查询，没有验证真实券商结果或父进程死亡自动回收，也不证明Host在仍存活且未外部close时立即持久中断。后者已有[独立根因反证](2026-10-26-qmt-host-interruption.md)，修复沿三个自有Host文件推进；完整首次/重连恢复、父死亡及故障矩阵继续。


独立动态复核（外部历史/待归仓路径：`../../build/qmt-standard-source-death-dynamic-independent-001/REPORT.md`）已通过，根核348份原件。29组交叉检查确认77跳HTTP中仅1 POST及64次原ID GET，173源和130模块身份保持；64次GET仍为dispatching，Native在writeD之前692ms沿有限GET链转Unknown。最终unknown来自原Host.close后只读SQL，本次不授关闭前即时持久化。


## Host收尾修复后的同案复验（2026-10-26）

三个自有Host文件修复后，原PD01测试/fixture、EXE和正常DLL保持，173项输入仅3 Host及2受影响单元来源更新。同案1/1通过，unittest6.646秒；Node/controller67732实际exit0，controller7.828秒，无额外forced，tree0/EOF/join/资源关闭。venv启动器68660与实际Host20276分别记录，Source10732和Native10608均来自各自真实Job。

本轮仍唯一POST/SDK进入1返回0；64次原UUID GET首1条dispatching/202、后63条unknown/200。Native保Unknown/Pending1/禁新写、自然Closed/delete；Host.close后mode=ro确认原unknown/interrupted及原字段/B/期限。原PD01没有首次interrupt D测点，immediate、自动父死亡与真实券商资格字段仍false；首次D内落盘由[两条独立runtime根因回归](2026-10-26-qmt-host-interruption.md#修复实施与同断言后继2026-10-26)承担。见根核（外部历史/待归仓路径：`../../build/qmt-host-fix-continue-001/PD-ROOT-VERIFIED.json`）和动态独审（外部历史/待归仓路径：`../../build/qmt-host-fix-runtime-independent-001/dynamic002-pd/REPORT.md`），172份原件根核通过。
