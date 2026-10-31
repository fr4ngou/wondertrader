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
