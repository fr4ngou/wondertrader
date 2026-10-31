# 账户读取责任回收的配置与维护

类型：操作手册。唯一规则见[AAR规格](../specs/qmt-account-read-retirement.md)，实现入口见[模块说明](../modules/qmt-account-read-retirement.md)。

## 选择同批制品

采用同一交付中Host、Agent和全部自有Native消费者。Native receipt包含进程内票据字段，账户工具、标准交易插件、CTA运行组件及历史工具按同一源码闭包编译。发行锁记录每个wheel、组件和依赖的版本及SHA；已安装目录保持原样，新版本使用全新安装根。

仅显式v3账户或v4混合交易配置声明 `read_retention={"schema":"qmt.read-retention.v1","max_lifetime_ms":N}` 才选择回收路径。N沿规格的100..300000毫秒范围，由部署配置确定。配对正文必须由相同版本工具从完整profile生成，使用原pair验证。省略该字段沿旧配置路径。实际配置、身份和容量来自原权威配置，手册中的字段形式属于说明。

## 正常运行

Native在原查询返回前验证完整结果并取得有界内存所有权，随后确认消费。Host在票据结束或epoch结束后释放已确定、已确认的只读责任。状态中的 `awaiting_ticket_end` 表示已交付结果等待原票据结束；正常持续扫描可以短暂等待，原业务截止继续生效。

查看 `held_unknown`、`queued_or_running`、`awaiting_consumer`、`legacy_records` 和v4的 `held_financial_proof`，同时核对原记录上限及字节占用。仍被金融订单关联引用的ORDER结果继续保存；后继原观察自然更新关联后，旧证明才能回收。已有无票据读行继续占容量。

## 待确认与重启

确认响应丢失时，同一进程沿原receipt、票据、请求ID及截止恢复，先lookup原结果再确认。网络未知及404/410保留原责任，操作员沿原故障处理流程核对。账户扫描进程结束后遵循ADR0007：确认旧进程树关闭，再由业务刷新开启新scan。金融命令与事件沿原Journal恢复规则维护。

容量被未知、历史无票据记录或金融证明占满时，保存原材料并定位责任状态；配置变更采用独立方案及身份核验。维护过程保持原命令ID、结果和金融证明。回退选择原冻结安装及其匹配配置，新增元数据的金融Journal兼容性按本次固定证据核对。

## 验收范围

固定容量SDK、默认路径、金融原件保留及ACK恢复证据见[验证记录](../evidence/2026-10-30-account-read-retirement.md)。真实QMT、生产、跨日和整个系统的正常重启由对应整链另行验收。
