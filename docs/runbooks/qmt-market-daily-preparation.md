# 全市场日线准备操作

WT负责启动已配对的HPR/v8 Host及正式QMT共享内存策略。外部连接配置只包含原loopback
base_url、key_id、secret_env、timeout和并行客户端数，秘密由受管环境提供。
HPR必须显式声明v3及原read_retention；原单SDK/业务截止、队列和容量由配对声明。
CLI使用完整WT角色及其精确锁中的原native-analysis-core运输；基础Host角色只提供库接口。
Host、Agent与Core以已验组合的精确wheel锁选择。CLI内部使用有界HTTP连接复用，操作员
继续提供原连接配置；每个业务请求仍有原截止，单次命令没有额外的常驻连接进程。

1. 固定证券池版本及业务日期窗口，保存同一正式组合正文摘要到source_association。
2. 使用正式普通安装运行`python -I -m guanheng_qmt_shm.market_daily_preparation_cli`，提供
   `--configuration`、`--request`、`--directory`及有限`--seconds`。分段准备可指定
   `--max-preparations`，相同目录再次运行沿原请求续接。
3. state=completed后，将capture目录及其原始batch slots交给C，通过原read_capture校验。
   HPR函数返回与数据覆盖分别显示；缓存尾日早于目标日保留实际日期。
4. state=pending保留原目录和Journal，等待原来源恢复再续核。state=source_unavailable保留
   明确原失败材料，由操作方决定下一次观察；禁止删除slot重派未知请求。
5. 单次命令完成或暂停后，WT、Host和QMT来源策略按其原实例生命周期继续运行。需要
   停运整个实例时，由WT统一管理消费者及Host的关闭；QMT策略按终端运行管理流程处理。
   工作流本身不启动、停止或自动重开终端及其他策略。

完整SDK替身、真实少量更新、全市场实际覆盖分别验收。SDK合成结果保留source_kind标记，
用于验证调用与恢复，不能用于真实市场指标。

部署时为外部Host和完整WT角色指定固定版本的CPython工具锚点，并记录解释器摘要、
版本/位数、base_prefix及pip可用性。IDE或辅助工具的可变运行缓存保持其原用途；
已发布实例使用独立的固定解释器路径。解释器变化时在新目录普通离线重装角色并核对
模块/RECORD，不替换正在运行的实例。QMT内置Python及正式共享内存正文沿其独立版本记录。

## cache-first新观察维护

先核实际v8/HPR完整signed binding、原Source身份及维护owner；与并行分析窗口协调独占准备窗口。v2必须使用新业务根和显式mode=cache-first，capture/preparation日期窗口分别固定读取范围和允许准备范围。CLI入口及--seconds/--max-preparations沿原命令；max-preparations在v2计实际缺口区间数，不计已就绪证券。

按cache→PLAN→原HPR slots→capture回读→QUALITY→RESULT核事实。尾日补齐从实际缓存尾日次日起；暖机仅补此前缺口，不重下已足窗口。HPR call_returned与QUALITY数据资格分别展示。Pending继续同根原ID，修订外部作业预算应记录原计划不足，不能改旧SDK截止。部分质量不得写成全市场100%；最终ready仍由原消费发布器依据原包验证。

v1目录继续用v1请求收尾；旧已完成或未知HPR回执按原Client恢复，不换ID。新模块的source CAS只覆盖自有Python与上述规格/模块/手册；安装/运行使用隔离候选，正在运行的Host/生产者包及共享配置保持。小量真实验证前binding变化或来源身份未确认时停止副作用，交清阻断；全市场实际执行沿已授权范围由来源owner管理，观察消费端保持只读。

v2独立后继可在明确保留旧Unknown后建立新观察身份。整次CLI的初读→本阶段准备→最终回读共用一个外部阶段D；观察预算应覆盖整条链。阶段预算与max_preparations由来源owner的执行计划指定，总绝对截止沿原责任继承；新准入不足30秒的固定read_new_request_budget_exhausted仅作阶段paused续接，既有槽原ID/SDK截止保持。其他Pending仍交回原责任。
