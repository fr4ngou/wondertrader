# 全库存历史分钟线导入进展

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：运行验证记录。日期：2026-10-27。状态：running，整库最终验收待完成。

## 任务与当前结果

用户要求将国信已下载的2021-11-01起历史分钟数据实际迁入WT。此前只完成分批样本和三证券价格质量验证，整库尚未执行；本轮改为优先执行全库存。

本地D:/software/guoxin/datadir的沪深60目录共5342份DAT，约82.58GiB。启动前E盘可用约3.25TiB；本作业启动预留800GiB、逐批保留400GiB。使用冻结的既有六模块及指定WtDtHelper，分批16证券直接执行离线convert；无新下载、SDK采集、QMT策略操作或数据库。

快照2026-10-27T10:31:13.783Z：控制进程48460句柄仍存活，driver 24908，已完成432证券、121436440根分钟，空0、拒绝0、剩余4910。这是进行中快照，后续进度见输出根progress.json，进程存活另查原控制句柄。见有界快照（外部历史/待归仓路径：`../../build/qmt-full-history-001/SNAPSHOT-001.json`）。

实际输出根为E:/workspace/wondertrader-data/qmt-history-20261027-002。每个batch目录保留QMI/CSV、原Importer成功收据及store/his/min1的DSB与metadata。原Helper写入后逐字段回读全部WTSBar；成功后才登记catalog-items.jsonl，并按SHA核对复制至native/his/min1/SSE或SZSE。catalog记录逐证券来源SHA、条数、真实起止日期、原store及成功收据SHA。源文件只读，source异常价格原值保持及质量计数。

扁平native目录当前为未启用的离线物料，尚无合并QMI收据；按source Reader读取须沿catalog使用各batch store。运行策略、行情HTTP和观衡入口均未切换整库输出。整库处理结束后才生成FINAL.json/catalog.json，进一步完成统一读取、总量、覆盖和最终验收；当前不授完整数据集或生产可用资格。

## 依赖、失败与后继

首轮冻结包遗漏native_history/dependencies/models导致启动失败，未完成任何证券；失败根qmt-history-20261027-001及控制记录保留。补齐六份冻结依赖后运行002，原Helper SHA为59696d42d8985ca09ddacf0e583525d025dba91ff66ffaa296cec8f6174cc45a。见六源码身份（外部历史/待归仓路径：`../../build/qmt-full-history-001/INPUTS-002.json`）、作业要求（外部历史/待归仓路径：`../../build/qmt-full-history-001/RUN-SPEC.md`）。

独立静态审查确认冻结源码身份、原Importer/完整回读、只读来源及离线目录边界；同时发现临时运行器两处失败路径问题：exit1未区分数据拒绝与依赖/native失败；completed_with_failures的预期exit1又被BaseException捕获导致progress终态冲突。run-003已修正这两项，原函数/控制流的替身回归先复现原两反例，再验证12个类别与清理失败；新终态三处均为completed_with_failures。首次回归脚本定位到新增resume状态更新，修正工具终态选择后全部通过；失败记录保留。见回归（外部历史/待归仓路径：`../../build/qmt-full-history-001/RUNNER-REGRESSION-003.json`）及独立delta（外部历史/待归仓路径：`../../build/qmt-full-history-001/REVIEW-003.md`）。

单次原始总截止8小时，子批最多420秒。进程树归外层2GiB Job及原native.run管理，隐藏启动，退出须分别核对tree zero、EOF、reader join及资源关闭；本轮长作业仍存活，尚无最终收尾结论。首次失败进程已完整收尾见审计（外部历史/待归仓路径：`../../build/qmt-price-adjustment-001/PROCESS-AUDIT.json`）。

剩余事项：处理全清单、汇总各证券覆盖与缺失尾段、原生统一读取/策略与观衡消费、最终终态/来源SHA及资源核验。用户设定起日不代表各缓存均覆盖该区间；已知多数股票尾部为2026-10-21，之后需补齐。价格复权调查见[后继证据](2026-10-27-qmt-price-adjustment-investigation.md)，不以该问题阻塞全库存原值保存。无新增WT核心修改、真实下撤单0，当前无用户必需操作或待批准项。

## 运行器003后继

旧driver在累计560证券后受控停止，按实际镜像、创建时间及本次PID核实归属。原控制器exit2对应业务driver人为exit90；tree zero、双EOF、reader join和资源关闭全成立。首次停止工具以虚拟环境启动器路径检查实际解释器而拒绝动作，按pyvenv.cfg和只读镜像核对后才执行；未操作QMT或其他进程。旧002根、部分批次及原日志完整保留，旧progress是当时快照。

新控制器63920使用run-003.py在独占E:/workspace/wondertrader-data/qmt-history-20261027-003根接续。逐成功证券核对原batch收据和两个原生文件SHA后硬链接，保留原store来源；处理尚未登记证券。原wall deadline=1793124019.0146115、monotonic deadline=1194801.437原样传递，新外层预算也约束在原剩余范围；未重置整次8小时截止。见owner交接（外部历史/待归仓路径：`../../build/qmt-full-history-001/OWNER-HANDOFF-003.json`）。新作业的活跃状态、接续总量及最终结果另按最新快照核实。

接续实测：原560证券/146763509根全部收据与文件SHA通过；新003 progress为adopted=560、completed=576、rows=151201270、remaining=4766、failed=0。控制进程63920实际句柄仍存活，driver 67948。见新运行快照（外部历史/待归仓路径：`../../build/qmt-full-history-001/SNAPSHOT-003.json`）。
