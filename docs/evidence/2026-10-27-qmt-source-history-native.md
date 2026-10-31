# 源值历史：原生导出、DSB 与读取整链

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27。类型：开发验证；整体迁移 active。本页分列合成验证和真实两分钟样本；本轮真实下单、撤单、生产切换及新增 WT 核心修改为0。功能依据：[源值历史合同](../specs/qmt-source-history.md)。

## 实现与故障修复

QMI v2、format=2 sidecar 与 SourceHistoryBar/Metadata 已实现；与 v1 canonical 复用原 Helper/DSB/文件 ABI 和解析/写验逻辑。未知单位或区间如实保存，时间不平移，返回覆盖 unknown；旧canonical入口拒绝源值。导入CLI三个机器结果分支统一ASCII转义JSON，UTF-8解码恢复原Unicode。原 Windows GBK/UTF-8失败保留。

Python实际35通过/1既有symlink权限skip，含原Helper真实DSB往返和读取身份/非法数据/旧v1兼容；独立full及编码delta/有限动态审查通过。详见[四查询后继证据](2026-10-27-qmt-real-account-budget.md)及根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-PYTHON-ROOT-002.json`）。

## 新 C++ 构建及实际 CLI

固定上游323份文件，自有底座120份加本次显式覆盖构成130份，原Wrapper及适配器前缀保持。仅目标GuanhengQmtHistory，Helper/Reader三DLL原样引用repair-001/build-002。本次不纳入其他共享WT脏改动。

首001任务完整依赖审计通过后，CMake配置耗尽原235秒，未产生binary；root13756 exit2/235.149秒，outerexit1/nonforced/tree0/双EOF/join/closed。原失败保留。002仅修改自有driver准入240→600，在新独占目录和新原起点运行，outer600/child595/root620；依赖/工具/源码/资源上限保持，运行中未延长旧D。新根27672实际exit0/84.158秒，结果passed、无首因及次因、所有后验和资源关闭成立。新EXE6080d051…b87be，位于build/shc-002/cmake/bin；构建根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-CLI-BUILD-ROOT-002.json`）、旧失败（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-CLI-BUILD-RED-ROOT-001.json`）、独立预算delta（外部历史/待归仓路径：`../../build/qmt-source-history-cli-build-independent-001/revision002/REPORT.md`）。

profile实际12方法/46 CLI子进程全部通过，无skip/pending；新EXE前后SHA一致，默认/v2/v3读取选择、非法配置、未知源值/分数double/零量正额/左右标签不变、空页、原ID GET恢复及配置SHA拒绝均覆盖。根74128 exit0/8.355秒，outer150/root160原D，进程与双管道正常关闭。根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-CLI-PROFILE-ROOT-001.json`）。独立动态复核（外部历史/待归仓路径：`../../build/qmt-source-history-cli-build-independent-001/dynamic002/REPORT.md`）已完成，范围限具名输入与同机开发验证。

## 同机开发文件整链

源值：真实Windows SHM的10次合成来源调用→新C++ CLI fetch→原ID resume→QMI→原Helper/DSB→sourceReader，十行时间与OHLC量额逐值一致，unknown元数据和canonical隔离成立；恢复未重复来源调用。根62536 exit0/10.598秒，outer90/root100原D内且资源关闭。此路径不启动CTA。

旧v1：同一新CLI经原标准化文件链→真实WtBtPorter原C ABI回放，十行、预热2、闭合分钟7、前缀8且未来行排除通过。根29852 exit0/7.279秒，同样资源关闭。该结果覆盖合成文件消费者，不提升业务策略或真实来源资格。两链根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-FILE-CHAINS-ROOT-001.json`）。

这些入口在同机复制开发EXE/运行材料，不能称完整搬迁发行。继承flow内部相对timeout/capture_output及清理首因限制继续保留，外层Job收口和进程成功不能替它证明完整原D/首管道合同。新原生profile用例的ProcessJob资源证据仅属于其入口。

## 真实历史准备与剩余

当前QMT成功四查询的正文只有账户和快照两能力；历史三能力须新配对。离线prepare首001因安装源码nlink=2触发通用read的单链接限制而失败，根69668/.564秒，诊断73924/.302秒定位Sources→read；输出目录未创建，Host/SDK/终端正文均未变。修后仅固定SHA安装源码允许普通硬链接，私有材料默认仍严格单链接，保留reparse拒绝、容量、前后身份和同buffer执行。三个真实硬链接纯回归已根57576实际3/3通过、exit0/.381秒；修后prepare及实际QMT样本的成功后继见下。

新历史CLI薄owner六项纯回归根50928实际6/6、exit0/.336秒，涵盖首因、overflow、迟返回、关闭失败和unknown owner保留；它们使用替身，真实Host/App/Native资源仍须现场验证。九项纯回归收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-OWNER-PURE-ROOT-001.json`）。

继续完成只读三能力实际配对、QMT 2021-11-01两分钟样本、真实QMI→DSB→sourceReader，再按库存/证券日期覆盖推进全量历史。策略元数据接线、实时分钟/补齐、查询优先交易完整重启恢复、观衡保留业务及独立发行仍未完成。当前没有需要用户决定或操作的事项。

## 真实来源小样本闭环

修后live003离线prepare根69852 exit0/5.912秒，原45/40/50预算、正常资源闭合。实际固定70份安装源码、45模块加载，旧pair未改；PREPARED SHA072e6c82…1581，完整create/verify和实际pythonw身份通过。准备收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-PREPARE-ROOT-003.json`）、独立动态复核（外部历史/待归仓路径：`../../build/qmt-history-source-real-prepare-dynamic-review-003/REPORT.md`）。

同一生成正文在国信Python3.6.8上初始化/单代/停止通过，root25328 exit0/.832秒、文件/网络/SDK入口计数全0。该探针在策略执行前由外部工具读入正文，只证明内存运行部分；实际QMT资格由随后现场另验。目标探针（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-TARGET-ROOT-003.json`）。

根私有逐字备份旧正文74f4bc16…f46b，再将新三能力正文写入现有GH_WT_MEMORY_VERIFY；安装根17988 exit0/1.191秒，新terminal SHA4034e03e…d09d（新pair正文02d4efca…b7a6、CRLF及额外两LF），没有新建策略名或改其他策略。安装收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-TERMINAL-INSTALL-ROOT-003.json`）。原验证策略保持只读，生成manifest/order_ready=false，生产资格未改。

新live driver仅在自有测试工具修复Host启动错误被诊断/包装错误覆盖的首因问题，四个历史候选均保留；最终004统一固定最早本地error/stage、有限补记首因后才记次因，原对象与owner/两pipe保持。根40604实际16/16纯回归exit0/.384秒，独立004delta关闭原P2。纯测收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-LIVE-OWNER-ROOT-004.json`）、独立delta（外部历史/待归仓路径：`../../build/qmt-history-source-live-driver-independent-001/revision004/REPORT.md`）。

实际App管理独立Host18024，root自行启动GHWT，真实认证并取得新鲜tick后运行新C++一次fetch和同root原ID resume，读取000001.SZ在2021-11-01 14:50/14:51两条原值记录。真实SDK源请求为market.history_1m，none/fillfalse/subscribefalse由原响应校验；恢复沿原ID读取，source trace一个POST。root自行停止GHWT并写stop确认；Host1/Native2全部自然exit0、树0/双EOF/join/资源闭，App shutdown/observer join通过。根45332实际exit0/121.813秒，原outer240/child235/root260内，无guard/forced；总耗时包含UI协调，不当作SDK耗时。父66模块、Host49模块分别验证，order/cancel请求均0。真实根收据（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-REAL-LIVE-ROOT-004.json`）。QMT保持打开，本次策略已停止；原18017及TRIN编辑器保持。

随后独立读取上述同一QMI清单，原Helper导入新私有WT DSB，再用sourceReader并绑定新导入收据SHA回读；两条时间和open/high/low/close/volume/amount逐值等于已校验CSV，source单位/边界unknown与coverageunknown保持，canonical入口明确拒绝源值。根68072 exit0/.457秒，原outer60/root70正常闭合，本阶段新SDK调用0。真实回读收据及oracle源码（外部历史/待归仓路径：`../../build/qmt-native-followup-20261027-002/HISTORY-REAL-ROUNDTRIP-ROOT-001.json`）、有限独立动态审查（外部历史/待归仓路径：`../../build/qmt-history-source-live-driver-independent-001/dynamic004/REPORT.md`）。审查用公开安全投影的实际SHA绑定私存result/ready，不读取金融正文；数值oracle范围是已校验QMI CSV→原Helper→SourceReader，不额外宣称独立SDK金融原文核验。

本结果覆盖同机真实两分钟的小样本；源量额单位、分钟区间、完整日历覆盖、长窗口吞吐、全市场/ETF库存、策略元数据接线、实际两代连接恢复、完整交易恢复和发行仍须各自验收。当前全量接入的硬上限已核：Python _history_limits与C++QmtBoundReadCore以及CLI每窗限制5日/2000行；当前普通协议max_result<=2MiB。批量规划在继续，避免机械放大为百万次小请求；任何新bulk能力保持显式选择与旧默认兼容。目标盘E当前可用3334GiB，单次容量观察不替代全量规划。无需用户当前决策或操作。

全量接入后继方案已写入[批量导入方案](../migration/qmt-bulk-history-export-plan.md)，状态proposed；重点先解决长窗、逐页调度、Frame所有权及跨批数据根/恢复身份，当前额度和运行配置保持。
