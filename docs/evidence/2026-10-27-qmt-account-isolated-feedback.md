# QMT账户隔离反馈与历史只读准备

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-27。类型：开发验证记录。整体目标 active；本轮真实SDK、委托、撤单和QMT界面输入均为0。

## 账户隔离反馈

保留真实现场“Host POSITION终态成功、Native单项截止”的[前序观察](2026-10-27-qmt-resident-followup.md)。本轮没有修改原Native EXE/DLL及其4秒单项预算；封版002使用当前App/Host/Agent源、Windows命名共享内存、签名HTTP和独立新Journal，唯一实验变量为主线程tick节拍2ms与1s。账户政策对齐公开现场queue20秒/total30秒。

独立full与002 delta（外部历史/待归仓路径：`../../build/qmt-account-deadline-feedback-review-001/revision002/REPORT.md`）已关闭旁路记录可能覆盖原Native失败首因的必要P2；001原件保留，002先锁存原Native错误再写trace。根执行前核108封件与4项外部pins，MANIFEST SHA caaf20b6b133bb749a00731f97a251282758272698cdb30e79867b36f57dc34a。

实际L01/L02均通过原成功oracle：每案持仓、订单、成交、账户四批完成，11项独立合成金融值匹配，四次SDK替身/四唯一POST及四条Journal成功终态；Native exit0、队列0、worker已退出、join/关闭完整。L01 tick107次、L02 tick7次，实际SDK仅为合成fixture。两个case均未出现目标超时RED，真实现场根因继续待定位。见结果（外部历史/待归仓路径：`../../build/guanheng-workspace/account-deadline-loop-002/result.json`）、L01（外部历史/待归仓路径：`../../build/guanheng-workspace/account-deadline-loop-002/L01.json`）和L02（外部历史/待归仓路径：`../../build/guanheng-workspace/account-deadline-loop-002/L02.json`）。

根PID6700实际exit0/15.818秒；外层240秒Job创建期绑定/2GiB、child25548 exit0/15.156秒，tree0、双EOF、readers join及资源关闭，forced=false、own_console=false。根260秒保护未触发。原外层收据（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-account-deadline-loop-control-002/build-qmt-account-deadline-loop-control-002/result.json`）和根实际句柄（外部历史/待归仓路径：`../../build/qmt-account-followup-20261027-002/LOOP-ROOT.json`）。上述通过只证明这两组合成条件成功，未覆盖真实QMT延迟、Python3.6.8实际SDK或全部第三方退出故障。

字段语义更正：前序把execution_ms=14称为SDK耗时，现已按[原Agent代码](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/restricted.py)核实，它覆盖成功ACCOUNT请求的执行校验、SDK及投影、to_json_value到最终封装前这一整段；单独SDK耗时仍未知。completed_at同样早于最终封装、共享内存返回和Host持久化，不能据此判断Native原4秒内已经可读。前序观察原件保持。

## 历史三能力离线准备

已生成新的resident-read只读配对，显式包含账户、full_tick及history_1m；order_ready=false。完整verify通过，目标国信Python3.6.8正文初始化/tick/主动停止通过，文件及网络入口调用计数均0，SDK0；单代测试未启动Host。原GHWT正文SHA74f4bc1604cff343aed66dca580a16cfd9894ca6e36243acba8e5cbb6587f46b保持，本轮没有替换终端正文。新端口18020与历史Journal仅为准备配置，服务未启动，Journal尚未创建。

有限独立准备审查（外部历史/待归仓路径：`../../build/qmt-resident-history-preparation-review-001/REPORT.md`）与根补充（外部历史/待归仓路径：`../../build/qmt-resident-history-preparation-review-001/ROOT-ADDENDUM.md`）无必要P1/P2；准备摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-resident-history-prepare-001/PREPARED.json`）仅含安全字段。根40780 exit0/2.708秒、目标探针根31684 exit0/0.493秒，根准备（外部历史/待归仓路径：`../../build/qmt-account-followup-20261027-002/HISTORY-PREPARE-ROOT.json`）及根目标探针（外部历史/待归仓路径：`../../build/qmt-account-followup-20261027-002/HISTORY-TARGET-ROOT.json`）均未触发外保护。

已另准备单窗口600000.SH、2021-11-01 09:31至09:32小样本输入，max_rows3、最多预期2行。分钟边界、量额单位、来源许可保持unknown，输出限定raw-only；CLI未执行、真实分钟未读取、真实DSB和全量历史未导入。样本安全摘要（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-resident-history-prepare-001/SAMPLE-PREPARED.json`）与限定静态审查（外部历史/待归仓路径：`../../build/qmt-history-sample-preparation-review-001/REPORT.md`）已核对，无必要P1/P2；真实端点/策略就绪和实际CLI读取仍待验。

## 当前开发与边界

查询优先提交空窗的自有层分组合同（外部历史/待归仓路径：`../../build/qmt-order-gap-group-contract-001/CONTRACT.md`）已接受，正在Standard插件和自有执行上下文接线及补真实运输合成回归。原默认native路径保持；此次不修改WT框架，未完成编译/独立审查/运行验收。完整重启恢复、单写入者、原HostJournal恢复库存及真实终态包含关系继续保留为未完成范围。

QMT界面工具此前连续failed to activate captured window，能读取画面，输入未可靠执行；具体系统原因仍unknown。用户已确认GHWT停止，本轮无需用户重复操作。下一步根据真实现场与成功合成的差异收窄原单次请求的返回链观察，然后验证真实账户和历史小样本；2021-11-01起全量历史、完整交易恢复、策略与保留观衡业务及独立发行继续。无新增WT框架审批或用户待决策项。

文档导航检查通过：根10544实际exit0/6.744秒，外Job tree0/双EOF/join/关闭、forced=false，按规定命令python -B scripts/project.py check执行。后补的既有源码及审查链接均已核实存在；此检查只授文档导航一致性。
