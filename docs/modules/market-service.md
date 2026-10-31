# 独立行情服务

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。职责：在原生数据资源与独立观衡消费者之间提供版本化、只读行情边界。

现行调用链：独立观衡 `MarketClient` → WT管理的本机历史服务 → 已配置来源适配器 → WT原生Reader与DSB。source-store(s)/source-catalog读取已导入历史，source-collected读取采集归档，source-preparing通过WT管理的外部Host及QMT共享内存补齐缓存。WT沿[WRI](../specs/independent-wt-runtime.md)拥有服务生命周期，观衡关闭后历史服务继续运行。Python服务不依赖wtpy或旧QMT项目源码。

早期canonical适配保留 `MarketBridge` JSON ABI → `QmtHttpEndpoint` → `QmtHttpClient` → 原QMT Gateway兼容链，以及 `NativeHistoryStore` / `HistoryPreparationQueue`；其旧HTTP来源资格与现行共享内存部署分别登记。DSB继续由WT原生组件保存和读取。

原生配置和凭证由启动 owner 固定；HTTP 请求不能更改源地址、文件根、许可或账户权限。服务创建、调用和销毁原生 handle 的线程保持相同，所有回调在该线程完成。ABI 结果在下次调用前复制，异常不跨 C 边界。

`guanheng.market.v1` 保留来源身份、单位、闭合时点、资格与覆盖；交易能力始终关闭。缺少真实 profile、服务无监听、源时钟缺失或会话变化分别可诊断，不推断可用。单次补数窗口最多 72 小时，长历史通过有界分窗作业准备。覆盖 complete 仍需要日历及停牌等适用证据。

接口以[HTTP 规格](../specs/qmt-http-market.md)为准；运行见[服务手册](../runbooks/market-service.md)，各业务真实切换条件见[适配地图](../migration/business-adaptation-map.md)。验证入口为 `tests/integration/http`、`tests/integration/service` 及 CTest 的独立行情链路。独立打包与受管发布保留服务、配置和原生制品各自身份。

客户端使用独立[标准 SDK wheel](../runbooks/client-sdk.md)，规范源码与原生包来自同一实现。历史任务的实例身份、定向推进和显式释放见[生命周期规格](../specs/history-lifecycle-and-service-adapters.md)；业务持久作业继续归 Operations，内存队列不承担持久恢复权威。

显式`native_reader`启动配置将历史查询委托给原生Reader适配（外部历史/待归仓路径：`../../src/GuanhengData/NativeHistoryReader.h`），经Store来源校验与单写者门后调用公开IRdm工厂；原Helper继续负责发布和恢复。数据修订采用有界实例换代，旧实例在后台通过原delete释放，查询线程不调用clearCache；返回数组已复制。历史根出现`rt`目录时拒绝该配置路径。生命周期、预算及限定验收见[历史查询规格](../specs/native-history-query.md)。该查询用于业务读取，策略ticker上的网络及补数仍须在其独立接线阶段处理。

[窗口查询](../specs/native-history-window.md)沿原history.query提供最多N根及沪深标准时段1/5/15/30/60分钟。原IRdm选择基础m1，原DataFactory计算派生，输出右端区间与数量限制由适配层裁剪；派生数组请求结束即释放，不保留另一份周期缓存。显式选择器回显于selection，覆盖Unknown；它与策略精确分钟网格读取具有不同的完整性要求。


## 来源原值历史查询

显式 `mode=source-store` 由 source_market.py（外部历史/待归仓路径：`../../integrations/guanheng/source_market.py`） 复用 `NativeHistory.read_source_store` 读取已导入的 WT DSB；数据生成见[本地 DAT 手册](../runbooks/qmt-local-dat.md)。该模式无需在线 QMT、Host 或券商凭证。原 HTTP 服务负责认证和请求边界，所有 Reader 创建、读取与关闭在同一拥有线程完成，条数预算控制来源缓存，证券内使用已加载时间序列进行区间定位。

`history.source-query` 与 SDK `MarketClient.source_history_query` 保留原值、来源时间标签和未知单位，按区间返回最新最多 2000 根基础分钟线；合同见 [RS7](../specs/qmt-source-history.md)。该模式不推断完整覆盖、不补造分钟、不转换成交量或分钟左右端。它复用 WT 历史文件，未新增数据库。

观衡显式 `GUANHENG_HISTORY_SEMANTICS=source` 选择该查询并生成图表协议 1.5，页面显示来源时间与单位说明；默认 canonical 路径保持原行为。source 模式暂提供 1m，5m 聚合需先确认分钟边界。真实 HTTP/SDK/App/浏览器主路径见[验证记录](../evidence/2026-10-27-qmt-source-chart-main.md)。


显式`mode=source-stores`按多个原成功收据注册全局唯一证券，共用同一个Reader、LRU和原始查询action；每证券保留原来源，能力页使用明确的收据集合会话。单根source-store及默认canonical保持。多批输入、集合身份及容量见[RS9](../specs/qmt-source-history.md#rs9-多批来源历史的统一证券查询)，受管配置和冻结新实例步骤见[服务手册](../runbooks/market-service.md#同一服务读取多个成功批次)。


`prepare_source_config`及source_market模块CLI将已完成导入目录映射为同一source-stores配置，复用原注册/Reader验证，精确核全部目录成员后独占发布候选文件；原数据和运行实例保持。命令与输出见[配置准备手册](../runbooks/market-service.md#从导入完成目录自动准备配置)，合同见[RS10](../specs/qmt-source-history.md#rs10-已完成目录生成统一读取配置)。

已终止目录含失败项时，prepare_source_config允许显式精确排除全部failed，保持默认准入和原收据完整集合核对；摘要保留失败集与pending尾部。观衡部署读取预算可在原SDK的30秒上限内显式配置，默认2秒保持，首次来源文件解码与关闭沿原总截止。行为见[RS7/RS10](../specs/qmt-source-history.md)，操作见[健康子集手册](../runbooks/market-service.md#已结束目录含失败项时先读取健康证券)。

## 显式源缓存补齐

`source-preparing`由source_history_preparation.py（外部历史/待归仓路径：`../../integrations/guanheng/source_history_preparation.py`）装配原`NativeSourceMarket`；[source_history_transport.py](../../integrations/guanheng/source_history_transport.py)复用原bound身份、HPR及历史读取协议。HTTP与SDK保持`history.source-query`，原三种来源模式继续离线读取。新模式先按原from/to/limit选择已有原值，昨日及以前1m可推进有限尾窗，正式配置省略逐只symbols并按来源支持的沪深市场补齐，窗口/时间/字节预算管理缓存资源；旧含symbols配置沿原范围恢复，日线与canonical交给原base。

单窗口收据保留原请求UUID、绑定和终态；Host Journal继续拥有受理与执行事实，响应未知后只GET原ID。源缓存回读经原Importer/Helper/DSB完整验证后注册独占新根，旧根与来源谱系保留。服务创建线程拥有base及最多一个窗口Reader，切换Reader先关闭旧owner。跨根最近N根保留逐段原metadata，集合身份及Partial观测按[RS13](../specs/qmt-source-history.md#rs13-最近n根选择有限尾窗与分段来源)校验，单位/边界/覆盖保持原事实；配置与运行限制见[服务手册](../runbooks/market-service.md#显式源值按需补齐)。验证入口为`tests/integration/source_history_selection`及原恢复回归`tests/integration/source_history_demand`；真实QMT与生产部署分别验收。


### 空缓存异步再观测

source_history_followup.py（外部历史/待归仓路径：`../../integrations/guanheng/source_history_followup.py`）只拥有显式有限观测排程，原source_history_preparation仍持收据/原bound身份与发布责任。follow_up缺省关闭；启用后空after可按固定次数/间隔/总期限再读，原HPR永不重派，已发布根不变且零新增源操作。公开字段保持SDK015，旧RS13及离线/日线继续适用。合同见[RS14](../specs/qmt-source-history.md#rs14-异步下载后的有限缓存再观测)，验收入口为tests/integration/source_history_followup。
