# 50指数来源日线隔离接入

类型：真实调用链证据。日期：2026-11-02。状态：开发及隔离验收通过；主干集成、独立审查和生产安装由集成者继续。

根因：现有8指数source-daily只有2项稀疏日线，6项缺路由；50指数既有成功仓为分钟。观察适配器另外把unknown量单位作为整张价格表失败条件。

实现：新增QMT完整分钟标签准入，复用原WtDtHelper.resample_bars聚合和原schema3/day导入。每日所有240个必需标签齐备才准入，09:30附加记录参与原生聚合；原件和逐日缺口保持可追溯。来源日线允许unknown量单位，观察量活跃度单独输出null并清空该预热段。

候选根：E:/workspace/wondertrader-qa/index-daily-source-20261102-001。最终真实数据根native-daily-final，11657根、50项。8主指数全部首日2025-10-29/尾日2026-10-29：000001.SH 185日、000300.SH 97日、000016.SH/000905.SH/000852.SH/000688.SH/000985.SH各243日、399006.SZ 190日。50项COVERAGE.json保留名称、目标日期及前后缀/逐日缺口。覆盖unknown，价格/量/额单位unknown，历史可知时刻未核。

CHAIN-FINAL.json绑定隔离WT原运行工厂、原MarketClient、原Helper/Reader及完整SDK逐字段核对；8指数进一步经候选wondertrader_source.history消费生成独立8来源表和24份原SDK响应对象。CHAIN-FULL.json再次验收完整原配置加新指数日仓：新仓注册在base，原5274日仓继续作为supplement fallback，原300308.SZ股票和510300.SH ETF日线的日期、六字段和内容身份逐项保持。business root、fd94与当前owner均未改动。原SDK来源日线运输为HTTP POST；本证据明确沿原接口取数，不将其宣称为GET端点。

同实例000985.SH的原分钟查询返回241根；未来空日期返回Ok空列表，未登记证券返回Unavailable。最终WT exit0、closed.json，history子服务server_closed/native_closed及closed.json成立。全部过程QMT/SHM、账户、订单、撤单、数据库和WT框架修改均0。

REGRESSION.json记录完整/缺失/重复/额外标签、实际原生含09:30聚合、多日边界、输入SHA失配、unknown只读、单位变化和量指标隔离回归。正式源CAS、依赖、测试入口与数据文件摘要见DELIVERY.json。

限制：本批为现有分钟标签的来源聚合，缺2021目标前缀；部分主要指数存在内部缺分钟而排除相应日。000300.SH只有97个准入日，任何要求100/200日预热的使用方须按实际根数处理。未升级为交易日日历完整、官方日线等价或可获知时刻资格。7份更长观察归档保留原供应商语义，000985仅close归档保持原样。该静态候选尚未替换18136或当前更新角色，后续自动尾部更新尚待集成者选择。
