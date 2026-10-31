# AI叠加纯策略事实与冻结回放

类型：功能规格。状态：accepted / in-progress。前缀：NAI。依据[保留策略](native-strategy-kernel.md)、[COP-R2/A6](guanheng-operator-platform.md)及[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)。

## NAI-R1 单一业务职责

`apps/guanheng/strategy_ai`独立发行纯库`guanheng-strategy-ai`。固定旧QMT提交6cf508a070392ff976b6b4d6b31b0e6219001e71的AI overlay.py/strategy.py是数学与替换映射来源。保留0.1.0的方向×置信度×0.03、绝对调整合计0.10、单证券0.28、组合至多0.95和正向调整可用预算缩放；减少仓位先释放预算。基础V1目标、评分调整、最终信号目标和明确执行替换分开。

只剥离策略需要的外部评分事实/批次完成回执。新模型不包含研究编排、生成模型、采集器、证据任务、数据库、网络或页面。WT-S/WT-B/NSQ继续拥有运行时钟、理论持仓、数量、费用、撮合及恢复；原StrategyIntent和通用worker退出。本库不生成评分，缺合格事实时评分层明确不可用，执行资格恒false。

## NAI-R2 窄事实合同

公开不可变领域值为ScoreBatch、ScoreFact、OverlayFrame、CompleteTarget、OverlayBudget。批次只含完成状态、run/bundle/content身份、最终scorecard IDs、完成/实际可知时间和来源SHA。评分只含symbol、方向/置信度、上述批次/证据身份、evaluated/available/valid_until、来源、冻结标识、发布/交易资格、佐证状态与有限证据。没有评分批次用None，禁止伪造完成批次或填补评分。

OverlayFrame携带完整有序基础AllocationEvent、显式基础算法/来源和可知时间、外部批次/评分、唯一递增共同交易日、目标失效时刻、knowledge_cutoff、必要证据、budget_weight和科创综指执行选择。目标在下一共同交易日生效；Shanghai日期采用固定core a6/tzdata2026.3，输入时间归一为UTC，失效日期按上海交易日校验。cutoff早于目标失效时刻，基础日已收盘且base_available_at<=cutoff；所有提供的批次/评分实际available_at<=cutoff，评分evaluated_at<=available_at、valid_until>evaluated_at。未来或无来源事实直接拒绝，没有可用部分结果。过期、缺失、不完整、身份失配、非策略资格、未佐证方向变化沿原规则保留上一完整最终权重；无上一完整值时保留当前基础权重，同时readiness=unavailable。窗口失效属于事实资格，保留权重属于纯业务连续性，二者分别呈现。

完整评分要求完成批次、一证券一张、ID全集一致、run/bundle及内容SHA一致、有效期覆盖目标、strategy_eligible/trading_eligible，并保留原未佐证社交只能hold。未知/重复评分ID、非法数值/类型和无来源输入拒绝；重复symbol的完整性失败沿原分支不可用。符号为规范六位沪深代码，最多64个，基础向量唯一且有序。589680.SH可显式映射589000.SH；完整执行向量若碰撞则拒绝，不能覆盖或加总掩盖角色冲突。

## NAI-R3 连续性、身份和预算

唯一计算入口evaluate_ai_overlay接收有界tuple帧、可选CompleteTarget和显式预算。按唯一递增来源日回放；上一个完整结果只在真正应用评分后更新，失败帧不会代替完整状态。CompleteTarget只有完整目标/来源日/生效日/失效/已知时刻/证据与producer_input/state SHA，重算验证内容且不持有账户事实。未来状态拒绝；重启可用相同冻结输入和显式状态重算，无后台线程或自动持久化。

保留原失败延续的原始目标，包括此前完整目标高于本帧新预算的差额；公开exceeds_requested_budget且评分不可用，禁止暗中缩放或提升执行资格。base/final/overlay及原目标日期可解释。返回规范JSON、全部输入/来源/算法/时间policy及结果SHA；公开to_dict返回独立值，complete_state递归不可变。输入修订、cutoff、基础算法、映射、业务资金预算budget_weight和状态均参与身份。OverlayBudget是调用资源额度，收紧且计算成功时保持相同策略值身份。

默认/硬上限：4096帧、每帧标的/评分/批次最终ID集合各64项、合计32768评分、每帧4096日历日、外部单事实/帧证据tuple各32项/单项256字符、输入/输出各8MiB、输入文本8Mi字符、单次5秒。CompleteTarget的聚合证据输入最多8192项；完整生成状态聚合基础/帧/全部评分引用，失败输出帧完整合并当前与上一完整证据，统一受全部文本、字节与截止约束，保留来源链。输入准入和结果序列化按相同集合维度计量，较大评分或回执集合在不可用结果中也保持其真实宽度。可收紧；一单调高精度perf_counter截止覆盖快照/准入、数学/回放、编码与哈希，随输入增长的循环检查同一截止。Windows/Python3.12的monotonic低精度计时不用于本库细粒度预算。标量类型/长度先核再查表/解析/哈希；Python单次stdlib操作有界但非硬实时，外层Job继续独立控制完整进程。

## NAI-R4 主链与验收

先跑基础目标+完整评分→分配、失败/缺失→延续、随后完整评分→新目标的整体链，再集中核手算3pp/10pp/预算、零和上限、失效/可知/来源/身份、未佐证hold、重复/缺失、原目标/状态日期、执行替换/碰撞、初始空、冻结要求、数值/联合容量/单一期限、不可变和修订身份。冻结样本含输入、逐帧完整输出和状态，静态原件对照不执行旧工程。正式非editable新安装、公开JSON消费与不同hashseed结果一致，所有资源关闭和精确SHA经独立规格/规范审查。真实评分生产者、原生桥/数量/资金/报告及完整C/M1分别继续验收。
