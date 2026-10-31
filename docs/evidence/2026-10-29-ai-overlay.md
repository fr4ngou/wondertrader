# AI叠加纯策略与独立安装

类型：开发验证记录。状态：done（NAI纯库、固定样本及独立安装限定切片）。范围沿[NAI-R1..R4](../specs/native-ai-overlay.md)，完整模块C和真实M1保持活动。

## 规则与职责

保留旧QMT固定提交6cf508a070392ff976b6b4d6b31b0e6219001e71的AI叠加数学与失败连续性，只抽取策略必要的冻结评分、批次完成回执和来源/时间事实。新纯库guanheng-strategy-ai不执行评分生产、研究任务或网络。基础目标、评分调整、最终信号目标和589680→589000执行选择分别返回。WT/NSQ仍拥有数量、持仓、撮合、费用与执行恢复。

五帧固定样本覆盖完整增配、失败、缺失、完整减配和等待证据。目标合计依次0.90、0.90、0.90、0.70、0.70；完整状态仅在真正完整评分后推进，失败保留上一完整目标，无完整值则保留基础目标。readiness与执行资格分开，真实来源/历史生产/执行qualified恒false。样本、公开JSON重建与分段状态续接位于apps/guanheng/strategy_ai/examples。

## 当前身份与验证

原件位于build/ai-overlay-001；原scripts/native.py::run创建隐藏Job、有限总截止及输出，负责完整树/EOF/join/资源收尾。旧工程仅两个静态Git对象，STATIC-MATH-001核5个数学/日历/失败延续函数和5个阈值的AST，移除合作式期限检查后与原对象一致。

最终候选wheel003版本0.1.0a1，SHA256为f00b828dc3d81e157a0260e21042f443f01b16b8e8ca8b31b7967ae9c107bf4c。普通runtime-venv-003安装AI/core a6/tzdata2026.3三个发行，663个带摘要RECORD成员、13个AI wheel实际成员逐项核验，pip check通过。INSTALLATION-003摘要8f3015af1542fdf26d8f700956a2da613c21a99dad1a87261ec40ed5beedb950，App锁保持原值。

实际-I主链、不同hash seed 1/7/42和公开JSON消费者全部输出相同规范bytes，文件SHA5733e4a512a2f5eea7fdc8f12043904985cab37f5d6c1aa1789e630426501abb。测试环境单独安装pytest8.4.2，最终31项安装回归通过，全部导入路径/摘要和9发行RECORD在INSTALLED-TESTS-004固定；运行三发行闭包独立保留。固定样本ZIP SHA c5a7de4b45e71e3e0a2118b38bf47fcdfee037e0daaf1d3ad1daf06974268526，实际解出五成员后在普通runtime003执行，完整结果与JSON续接相同。

SOURCE-SHA256-003固定16产品/规格/样本/测试输入，摘要59bd3245599bf631af181678b38c03eaa25d6db7a2c68ed7aa51d51d97573118；QA-SHA256-003固定11脚本，摘要bdd17ba7ad93ce435b8af18570ec159d79a1c57f7adeb098192f220484373ccd；EVIDENCE-SHA256-003固定114原件，摘要45d84d7786afff79f62ef4fb4a5107ce588b0295025896796c4ba0089d3cbcfd。三个集合均有独立只读镜像，core当前9个.py与批准a6 wheel逐字节一致。原001的16/11/76及旧候选保持冻结。

## 根因回归与审查

tests-002保留1ns预算漏拒：Python3.12/Windows的monotonic使用约15.6ms粒度GetTickCount64，短计算可在一次跳变内完成。改用同样单调的高精度perf_counter后，实际100次旧接受100/新接受0；确定性截止等号、数学中途超时及序列化期限另验。clock-base-001和CLOCK-RED-GREEN-001固定原触发。

早期wheel001的结果统计遗漏序列化收紧的标的/日历额度；补齐统一统计后，冻结同一测试在旧安装实际失败于max_symbols=1，wheel002通过。BUDGET-RED-CLEANUP-001核预期exit1的九项原资源收尾全true、清理错误0且无保留owner。所有旧语法失败及原件保留。

两个独立full审查定位集合宽度P2，规格另指出外部32条与聚合状态8192条的合同例外P3。003以同一_symbol_collection承担权重、评分及最终ID的准入/宽度统计，完整保留聚合证据，并明确资金预算与计算额度各自语义。三个独立宽度组合在旧002的两种序列化均放行，在新003均result_budget拒绝；实际生成超过32引用的完整状态续接通过，单事实33与状态8193拒绝。

最终SPEC-DELTA-003结论complete，原P2/P3均closed，SHA fad8a3ed2ad96b6b0f820d0a55fa05ea493a225bcab21d58d954356b2e05f765；STANDARDS-DELTA-003结论complete，无新增P级，SHA536dd0c17e0ebad3716e9df5d8278abecb10333f4fb721c4591faa6c031eb051。原full gap报告及全部旧失败保持。两轴核最终16/11/114、安装/回归和解包消费补件，资格限定纯业务库与普通安装。交接与完整后继见build/ai-overlay-001/HANDOFF.md、NEXT-CONTINUATION.md和最终DELIVERY.json。

## 未覆盖范围

真实评分生产者、全部策略版本、原生AI桥、真实M1的历史知晓模型及B Runtime稳定性、统一安装/升级回退、真实账户只读页面和观察完整来源/自然窗口分别继续。策略页面保持名称/简介/版本；本轮未修改页面、执行真实下撤单、发布或Git集成。
