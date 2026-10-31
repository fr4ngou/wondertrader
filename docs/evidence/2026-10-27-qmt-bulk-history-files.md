# 2026-10-27 Host 分页文件与原生 DSB 验证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：partial；BF1–BF4/HP1实现及合成文件链通过，实际运输/Journal最终确认/真实长窗继续。关联[批量历史规格](../specs/qmt-bulk-history.md)与[完整方案](../migration/qmt-bulk-history-export-plan.md)。

## 实现与复用

Host 新增 BulkHistoryFiles：单domain线程、单证券新根、固定来源/窗口/原D与页/行/文件/累计字节额度；每页直接写七列CSV，重放必须核实际文件身份/SHA。非空最终页封原QMI v2 chunks，随后可交已有import_dataset/原WtDtHelper/DSB/sourceReader；没有新增拼接器、数据库或WT核心修改。空结果保empty，不伪造可导入清单。

私有文件新增显式 write_private_durable_new，复用原CREATE_NEW、创建期protected DACL、SecurityResources及唯一内部写入：完整WriteFile→FlushFileBuffers→实际关闭→同原D后验才成功。原write_private_new默认仍不flush，六项原caller清理和八项原安全资源兼容回归通过。文件flush不承诺目录断电事务；同步WinAPI不可抢占。

中间页只有CSV持久并读回核验后ack_eligible=true；最终页即使清单封口也仍ack_eligible=false/requires_terminal_commit=true，外层原Host Journal提交成功后才可最终ACK。本模块不自己ACK或操作Journal，现有运行器尚未调度该能力。

失败按事实归属处理：纯解码/验证/编码只锁固定码，防止异常栈挂整页；真实IO失败保原异常及资源。读取首因与close错误分别保留，未确认stream/SecurityResources沿私有owner继续持有。自有函数finally清行页/CSV缓冲，源数据、原期限和失败材料不被覆盖或重试。

## 固定输入

- collector生产004 SHA068892dd7fc6bf9d9ba549e1e416a961b8e1779d1fc0291043cb2ca423c4fdca；writer SHA8943c52dc3a51507fa654d113f9397cd1e5513e858280edc7e5c662f0cb6cc65。
- 最终collector测试005 SHA17ea237d89a12032d12803bf4b0681aefcbf1f326abc6f22a271840357b8822d；原生文件链测试bb058fa20c039b6854e089f0066ab0a9843c650eb7a1bfa4971d0eac08e70fc9。
- PINS-FULL-002（外部历史/待归仓路径：`../../build/qmt-bulk-host-validation-001/PINS-FULL-002.json`） SHA c6786e6a2c0288d727deb8751fc8f9a207ff52d83df15fe3989263763f18601e，固定78生产模块/5测试/3 DLL，业务与测试从已核同一buffer编译加载；前后无漂移。
- 既有独立安装依赖经清单（外部历史/待归仓路径：`../../build/qmt-bulk-host-validation-001/DEPENDENCIES-001.json`）固定974文件/10,659,390字节，SHA ddf78514582544176972d6a5a7163324e8cad7216489b5df2400a68b6893cc7c；前后逐SHA核同，无新下载/安装。
- runner（外部历史/待归仓路径：`../../build/qmt-bulk-host-validation-001/run-003.py`） SHA9605ba0e5216b63bf347fa7ab395a3b6e92bc4006decd0fb6e389302e8509e9f，-I -S -B，Python3.12.14。禁止未固定业务依赖；没有SDK/旧QMT工程导入、终端或网络启动。

## 实际结果

统一FULL-002（外部历史/待归仓路径：`../../build/qmt-bulk-host-validation-001/FULL-002.json`）实际57个唯一方法全部通过，0失败/错误/skip：collector28、durable writer12、真实DLL文件链3、原安全资源8、原配对清理6。完成时新增存活线程0；三DLL及源码/依赖前后同。

真实文件链为合成五行三页：BS原值页→真实私有CSV/QMI→原import_dataset/WtDtHelper→DSB→sourceReader，六个double和源时间逐值相同；分数量、零量正额、跨页时间缺口及unknown单位/分钟边界/coverage保留。重复中间/最终页不增文件或字节；empty/错SHA不调用Importer；canonical入口拒source。测试始终不确认最终页，源snapshot在断言时保持awaiting_ack，不冒充Journal已完成。

root39056自然exit0/2.287655秒；原90秒外Job、85秒传入wall/mono D、100秒rootguard。控制器child57588 exit0、2.172秒，member_before_resume=true/own_console=false/forced=false/tree0/双EOF/join/资源关闭。2GiB进程树预算、双路64KiB捕获；协调器无控制台，子进程采用隐藏创建。root句柄及失败保留见ROOT-HANDLES-002（外部历史/待归仓路径：`../../build/qmt-bulk-host-validation-001/ROOT-HANDLES-002.json`），SHA a0666ca4ea169912c4e1d432b0e05077684bce2c4ef59c95978b1b900b9d15d2。

## 原失败与独立审查

首writer001因隔离runner缺已有Pydantic依赖而在测试导入前失败，产品方法未运行；显式固定既有安装依赖后writer002实际12/12通过、root52240 exit0/1.291857秒。FULL001实际54通过/3失败，三者因unittest.assertRaises清除了需要核验的public traceback。测试005改真实except取证并遍历retained_cleanup_error，checked>0和所有大局部None断言保持，生产004逐字不变；同57方法FULL002全部通过。两个RED原件保持，不回写成功。

本轮并发/持久化/资源规则触发独立full及delta。final005报告（外部历史/待归仓路径：`../../build/qmt-bulk-history-files-independent-001/final005/REPORT.md`） SHA5e6429d824c6fa4887d2ff0eed87e94a787fa88aea3d72ca5ae7c0f077834e1c；manifest7452f114cd19d95738b9dd22d6e1696d49e6953b0e54ea1be2fb19bedc534f16，43份原字节回读核同，最终规格56aeb133855586d6733936231ec8bdcd1334ef560a24d8a53638891ea1352e47。必要P1/P2为0。原full004及各修订材料保持；根句柄事实与独审未另取OS父关系的边界分别说明。

## 未验范围与下一步

该组件还未接实际bulk profile、ControlPeer页请求/退休确认、Host域调度、原Journal terminal、签名HTTP/C++ artifact。下一步沿现有通道接入，不新建通信系统；完成提交后最终ACK和同代/跨代恢复，再对比真实小窗、测月窗及完整证券历史/ETF范围。原Importer仍物化有限单证券数组，QMT SDK/Frame内部峰值与不可抢占耗时、全市场吞吐及完整覆盖尚未验证。

常驻Host实际晚于60秒首次连接和两代重连、查询优先完整交易恢复、策略/观衡保留业务及独立发行仍保留在完整目标中。本轮没有改动/运行旧QMT项目，没有启动/停止终端策略、真实下单/撤单或生产切换；两份获批TraderAdapter和终端正文摘要保持，当前无需用户决策或操作。
