# 批量日线来源操作

类型：运维手册。配置和结果契约沿[QAB](../specs/qmt-analysis-batch-source.md)，职责沿[模块说明](../modules/qmt-analysis-batch-source.md)。

1. 固定已安装 Host/Agent 制品、原证券池及请求日期/行数；v8 的 operation_profiles 使用 qmt.daily-batch-read.v1，read_retention 继续使用同版原合同。
2. 在终端外通过原 create_pair/verify_pair 生成完整正文和认证材料，使用生成时同一正式解释器运行 Host；内置终端只运行已生成正文。私有配对和正文不进入公开结果包。
3. WT 原 qmt_read 组件持有连接。外部 provider 接原 BoundHistorySource 和资源预算，保存新的 capture；unknown 时继续该原目录/ID，不复制成新请求。来源 binding 改变时先处理旧责任，再开始显式新观察。
4. C 只读消费 manifest 与其引用的原 slots，按批次身份核摘要、来源和日期，再展示证券覆盖、共同基准及实际时间。none/front 原参考不直接标成复权已验证。
5. 正常关闭先停外部消费者和 WT owner，再停止来源；保存关闭收据。新的来源能力须用新配置显式选择，原 v7 回退使用其原安装与配对，未知原责任保持可核。

全股票池读取先核资源分片和原容量回收。SDK 替身记录实际调用数、原线程、原值及收尾；真实小切片只验证实际缓存。日线缓存空/旧时交原历史准备模块，读取 owner 不暗中下载。BJ 来源更新需要独立合同和实际证据。

## 独立日更的来源托管

持续日更使用的批读Host由单独WT服务拥有：Runtime仅声明analysis_batch_host/qmt_read，使用原安装、原pair、原Journal及端口。沿原ServiceController的start/status/stop管理；同一次start再次调用应保持同代与原PID。新Host前核旧Host已正常关闭、实际退出、端口空闲，再验证原pair与解释器身份。日更观察以旧REQUEST恢复后的实际新槽、Native回读及CURRENT发布为准。

把该服务登记在原服务组的日更之前，停止按逆序先日更后来源。需要HPR或证券资料的日更同时声明其既有服务依赖。数据服务组可以独立于交易组启停；后继金融配置移除同pair批读Host声明，引用独立来源。已有金融代的默认start仍恢复原Runtime，单改bootstrap不能完成迁移；迁移及原金融未知责任沿原恢复流程处理。

resident-read负责QMT连接断开后的重连，日更owner按原请求/slot和原重试节拍续接。ServiceController提供显式启动与恢复入口；进程自身退出后的定时拉起或开机调用属于环境部署动作，未实际采用时保持未验证，不写成已生效的自动守护。
