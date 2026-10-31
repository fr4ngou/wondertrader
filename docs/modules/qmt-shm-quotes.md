# 共享内存当前报价

类型：模块说明。适用范围：原生报价、历史组合与WT生命周期。状态：实现；实际资格见证据。

WT SourceMarketProcess 拥有 source_market_service、ShmQuotesMarket 和 Native handle。客户端沿 guanheng.market.v1 的 quotes.query 读取；历史请求委托既有历史 backend/Reader，分别保留来源元数据。

ShmQuotesMarket 组合 quotes 与 history。报价由 GuanhengShmQuotes.dll 经 QmtHostReadClient、现有 HPR Host full_tick 和共享内存获取。原 QmtTickMapping 统一映射价格、时间、量额单位，生成时间与来源时间分别保留。服务使用能加载完整 integrations namespace 的固定独立 Host 角色解释器。

同一个HPR Host选择显式历史准备limits.v3时，行情库须使用识别该描述符的匹配构建。Native仍只发送full_tick，完整核验v1/v2/v3的字段、原预算和绑定摘要；沪深北历史准备调用归来源owner，行情门面不提供该调用入口。版本及制品匹配沿[原生v6规格](../specs/qmt-native-parser-v6.md)和相应验收记录核实。

配置 mode=source-shm-quotes，quotes 包含 library、sha256、configuration；history 沿原 source-store/source-stores/source-catalog/source-collected。configuration 中 guanheng.shm-quotes.v1 选择原有限 v6，guanheng.shm-quotes.retained.v1 选择完整 retained v6；凭据保存在受控私有配置。

Native 创建线程独占全部调用与销毁。retained 路径验证完整原 result/receipt/所有映射值，持有快照后确认 consumed。确认回执未知时保留原值、原来源时间和原身份，仅核查或重复同一消费确认。通用 RR3 磁盘 slot 职责保持；Native 快照的进程内边界见 [ADR](../architecture/adr/0019-native-quote-snapshot-consumer.md)。

正常关闭按 quotes、history 反向释放，任一关闭失败继续尝试其余资源并报告失败。报价缺源时 capabilities 保留历史能力；市场结果沿原固定错误类别。跨进程原未知恢复、真实来源时效及发布资格分别验收。

[规格](../specs/qmt-shm-quotes.md) · [装配与停止](../runbooks/qmt-shm-quotes.md)
