# 批量日线来源操作

类型：运维手册。配置和结果契约沿[QAB](../specs/qmt-analysis-batch-source.md)，职责沿[模块说明](../modules/qmt-analysis-batch-source.md)。

1. 固定已安装 Host/Agent 制品、原证券池及请求日期/行数；v8 的 operation_profiles 使用 qmt.daily-batch-read.v1，read_retention 继续使用同版原合同。
2. 在终端外通过原 create_pair/verify_pair 生成完整正文和认证材料，使用生成时同一正式解释器运行 Host；内置终端只运行已生成正文。私有配对和正文不进入公开结果包。
3. WT 原 qmt_read 组件持有连接。外部 provider 接原 BoundHistorySource 和资源预算，保存新的 capture；unknown 时继续该原目录/ID，不复制成新请求。来源 binding 改变时先处理旧责任，再开始显式新观察。
4. C 只读消费 manifest 与其引用的原 slots，按批次身份核摘要、来源和日期，再展示证券覆盖、共同基准及实际时间。none/front 原参考不直接标成复权已验证。
5. 正常关闭先停外部消费者和 WT owner，再停止来源；保存关闭收据。新的来源能力须用新配置显式选择，原 v7 回退使用其原安装与配对，未知原责任保持可核。

全股票池读取先核资源分片和原容量回收。SDK 替身记录实际调用数、原线程、原值及收尾；真实小切片只验证实际缓存。日线缓存空/旧时交原历史准备模块，读取 owner 不暗中下载。BJ 来源更新需要独立合同和实际证据。
