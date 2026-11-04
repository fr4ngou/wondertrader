# QMT证券名册与资料

类型：模块说明。状态：实现、隔离主链及真实SDK目录核实完成，完整现场接入与全市场覆盖继续验收。

## 职责与数据流

WT受管只读Host通过原共享内存连接，由QMT策略原线程调用公开SDK。Source负责冻结证券名册与分页、取得逐只资料；统一日线owner负责保存原结果、建立价格池及更新WT原生数据。观衡只读取结果。该模块不下载行情、不订阅证券、不查询账户、不下单。

资料Host由数据侧WT只读运行实例独立托管，生命周期与金融执行实例分开，交易关闭不传播为资料服务停止。沿既有Runtime只读组件及ServiceController管理；QMT正文可以组合多条共享内存通道，终端外各通道仍分别持有owner、Journal和关闭收据。

完整链为：统一数据owner → `SecurityReferenceSource` → 原`RetainedReadClient` → 签名HTTP → Host原Journal → Windows命名共享内存 → 原策略唯一timer → SDK → 原结果保存和消费。QMT内部新代码仅使用Python3.6.8标准库及内置SDK，文件和网络读取保持禁止。

## 接口与字段

唯一业务契约为[证券名册与资料规格](../specs/qmt-security-reference.md)，包含请求、逐字段定义、空值、时刻、来源、分页和消费边界。`market.security_universe`返回同次`catalog_id`、分组、证券及游标；`market.security_details`返回名称、上市/到期日、交易状态和有界原字段。缺资料的证券继续留在价格池。真实0保持；缺失、非有限值、SDK失败及歧义分别表达。

Source名册缓存最多2份、20000证券、原件总8MiB、900秒；单次页最多256证券，详情最多64只、data最多300KiB。缓存期与每次原请求30秒截止分别管理。SDK同步调用本身不提供抢占或瞬时内存硬限制；返回后和编码时仍核原D。消费方可按单批实测延迟缩小批次。

证券分类取实际SDK目录及显式映射，代码前缀不参与分类。目录存在、成员取得、上市资格和日线覆盖各自验收；ETF业务码及资料缺项不能静默计入完整上市ETF分母。已核目录包含沪市/深市/京市股票和指数、沪市/深市ETF，北交所ETF缺映射保持unsupported。

## 源码与运行

- Agent：[security_reference.py](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/security_reference.py)，单代目录/缓存、SDK原线程、返回准入及中文字段注释。
- Host：[security_reference_source.py](../../connectors/qmt_shm/host/guanheng_qmt_shm/security_reference_source.py)、[组合声明](../../connectors/qmt_shm/host/guanheng_qmt_shm/security_reference_composition.py)，复用原绑定、UUID、保存/消费和未知责任。
- 产品：[trade_pair.py](../../connectors/qmt_shm/host/guanheng_qmt_shm/trade_pair.py)、[trade_source.py](../../connectors/qmt_shm/host/guanheng_qmt_shm/trade_source.py)，显式v5组合原交易/账户/v7/v8及新增v9连接，仍是同一完整策略正文与原timer。
- WT父端：[trade_host_process.py](../../apps/wt_runtime/guanheng_wt_runtime/trade_host_process.py)，核显式v5、strategy_tick、v9两操作及原存在的v7/v8身份；Host负责完整私有设置和闭包核验。

运行与回退见[接入手册](../runbooks/qmt-security-reference.md)。相关回归入口为`tests/integration/qmt_security_reference`及`tests/integration/wt_runtime/test_trade_pair_analysis.py`。
