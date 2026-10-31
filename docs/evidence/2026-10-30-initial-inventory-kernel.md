# 初始库存的唯一纯策略核

类型：模块C纯算法合同及独立安装证据。状态：纯核限定验收完成；B最终组合消费及完整系统pending-verification。要求沿[RR112-R8](../specs/retained-resonance.md#rr112-r8-显式初始库存)；当前账户与原生初始化归[B的初始库存证据](2026-10-30-initial-inventory-baseline.md)。

## 根因与实现

原PositionCycle只表达flat/held，held要求实际opened_at。用户取消旧开仓记录、历史交易及旧周期迁移恢复后，当前持仓需要独立的新运行起点。唯一核增加initial_inventory及baseline_at；旧实际开仓时间为空。B持久拥有基准、数量、当前订单责任及新运行状态。C保持纯同步计算，无账户、文件或网络读取，无新增金融账本。

首次严格晚于基准的合格分析收盘形成新参考，精确相等收盘继续等待。此前年龄0、参考峰值空；首参考日年龄0，其后复用原七角色的年龄、峰值及退出规则，沪深300保持原模型分档。新基准前的行情继续用于模型预热，旧周期状态不进入实际止损。基准早于新窗口时明确返回initial_inventory_history_missing，运行侧保留基准并补齐新运行行情。新字段共同计入输入身份和原容量/5秒计算期限。flat/held省略新增空字段，旧规范输入和完整结果保持。

## 主路径与独立安装

固定原行情为build/ms-per-date-replay-001/candidate-003/SESSION.json的401共同日、3208行，配两证券各200股的明确合成初始库存。无旧开仓时间、无旧流水、无旧退出。源码原入口产生完整八目标，模型状态、分配及权重与同一行情flat对照一致，实际年龄0、峰值与退出空，JSON往返完整结果相同。原5秒内约0.5秒完成；该样本不声明真实账户资格。

build/initial-inventory-kernel-001/PACKAGE-001.json固定独立stage，V1 0.1.0a8、共享数学core 0.1.0a8及tzdata 2026.3。使用原flit构建脚本、离线精确哈希安装到全新纯包环境；3个分发、4个V1包成员与源码及wheel逐字一致。原App a57和WT安装未修改。INSTALLED-MAIN-001以普通已安装包处理同一冻结输入，完整结果逐值一致，耗时0.469秒。

原输入拒绝新增字段的red-001保留；源码93项受影响回归通过。独立纯包40项覆盖新基准、严格收盘边界、年龄/峰值/退出、新系统同基准重启、加仓不重置、旧退出拒绝、缺新运行窗口、坏时间/混用/不同批次、输入身份、零文件IO及原容量边界；旧实际held及历史模型保持。测试框架取开发环境，业务模块全部来自全新三包安装，输入前后摘要一致。

LEGACY-PARITY-002及LEGACY-INSTALLED-001加载冻结a7原latest.py，通过公开JSON边界比较九组旧flat/held输入及完整输出字节；含113/120/200/400日人工可核形态及原401日行情。首轮legacy-parity-001的第九组沿旧捕获时间触发原时间准入，原失败与正常关闭保留；后继明确刷新合成周期捕获/决策时间，原行情接收身份保持，旧新使用同一请求。原结果一致的结论只对应后继有效输入。

## 范围与剩余工作

91份冻结输入已完成独立Spec/Standards full审查，开放发现均0，前后摘要一致。Spec报告SHA5e7a60f0ed355d6c560e544c6b2c74fc7bdf288825f7491eea5409c599245c5a，Standards报告SHA6a8191b48effa1ed8327a9b19fd063d4c91a896bafc40fbb41170f5dcafe8781。冻结报告保留原输入时点，后继公开样本CLI还实际读取新安装，current/historical两个原样本输出与TARGET.json逐字相同；该附加运行未冒充91件原审查输入。

最终合同为build/initial-inventory-kernel-001/INTEGRATION-HANDOFF-001.json，SHA0f1f090bf755f01e1f5705cec6be8688e6c3f69befd5680cc1d47a6b44c64ef8；V1 a8 wheel SHA3ad9a9de4c7605c1528fdc64b8ed927cf6fafc782542bfb69f746e907e67896e。原生接管准备的前代开发候选仍把启用基准编码为held/opened_at，最终B候选需要采用显式status/baseline_at、精确升级依赖并验证原Configured/P23及新运行状态持久恢复。C没有修改B自有准备入口或其固定安装。

两份C自有发行元数据已按构建前摘要CAS核对后提升到a8，根十份包文件与冻结已审stage逐字一致；App/WT已有安装和依赖锁保持原候选。METADATA-PROMOTION-001保存前后摘要，用户18126未切换。project.py check后继已通过当前文档静态检查，旧UI阶段的他方未索引失败原件保留。

全部原生驱动使用独立有限Job、隐藏控制台、原日志额度；source/main/package/installed/legacy各有闭合原件。当前真实查询、委托、撤单均0，WT框架改动0，用户18126与生产未切换。独立审查已绑定最终固定stage；B沿真实Configured/P23/原WT账簿消费、首次加载、当前责任核查及新系统两代恢复另验。纯核合同通过不授完整C、连续系统或生产资格。
