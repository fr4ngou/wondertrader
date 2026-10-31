# 历史工作进程部署工厂

类型：功能最终规格。状态：accepted。范围：补齐既有[独立历史进程](history-worker.md)的正式依赖组合入口，服务继续独立发布。实现位于自有SDK，原QMT与WT核心保持。生产配置、真实作业启动和发布另验。

## HDF-R1 组合与所有权

SDK提供 `guanheng_market_client.history_factory:create`，兼容现有worker的零参数factory入口。它在调用线程构造现有OperationsClient、MarketClient、CalendarProjectionProvider、MinioEvidenceSink与HistoryRunner，不查询或创建作业、不读取行情、不创建bucket、不修改服务器配置。首次业务请求仍由已取得作业锁的worker发起。配置加载与构造不启动线程。

原Operations继续持有作业/CAS/checkpoint；原日历owner持有事实；原行情服务持有临时任务；证据存储沿已有内容地址实现。工厂不增加持久状态或业务恢复算法，既有自定义factory入口保持可用。

## HDF-R2 唯一配置

零参数入口读取部署环境变量 `GUANHENG_HISTORY_WORKER_CONFIG`，最大16384 UTF-8字节，严格JSON对象，拒绝重复键、非有限数、未知字段和类型。公开纯构造函数 `build_runner(config, environ)` 便于受控部署及测试；它只读取传入映射，不自动合并进程环境。config输入和环境快照在构造期间固定，完成后更改环境不改变已构造客户端。

v1对象字段全部必填，禁止隐含来源、版本或来源单位：

```json
{
  "schema_version": "guanheng.history.factory.v1",
  "operations": {"url": "http://127.0.0.1:19001", "token_env": "EXAMPLE_OPS_TOKEN", "timeout": 2},
  "market": {"url": "http://127.0.0.1:19002", "token_env": "EXAMPLE_MARKET_TOKEN", "timeout": 2},
  "calendar": {"url": "http://127.0.0.1:19003", "token_env": "EXAMPLE_CALENDAR_TOKEN", "source_version": "example-only", "timeout": 8, "http_timeout": 2},
  "evidence": {"endpoint": "127.0.0.1:19004", "secure": false, "region": "example-region", "bucket": "example-history", "prefix": "example-only", "access_key_env": "EXAMPLE_ACCESS_KEY", "secret_key_env": "EXAMPLE_SECRET_KEY", "timeout": 2},
  "binding": {"agent_id": "example-agent", "profile_version": "example-profile", "source_license": "example-only", "volume_to_shares": 100.0, "amount_to_yuan": 1.0},
  "budget_ms": 30000
}
```

以上均为合成示例，不属于生产配置或单位依据。evidence允许一个可选字段 `session_token_env`；未提供即不注入临时token，提供则环境值必须存在。其余嵌套对象按列出的字段严格校验。环境引用仅接受ASCII `[A-Z][A-Z0-9_]{0,127}`；仅从这些显式名字取凭据；值必须为1..4096字符的str，每个字符为ASCII 33..126，拒绝空格、控制符、非ASCII与空值。凭据原文不进入JSON配置、命令参数、本模块公开返回对象的repr或自身异常/诊断。调用方禁止把第三方SDK私有凭据对象输出；本切片不改造第三方内部对象的repr。缺失/无效配置统一抛出固定消息的配置错误，异常链不携带输入。

## HDF-R3 复用既有约束

HTTP/HTTPS地址、loopback明文限制、鉴权字符、响应上界、时间预算及MinIO版本约束继续由既有客户端校验，禁止新增重试、重定向、跳过TLS验证或自动创建资源。工厂使用既有storage extra，基础SDK导入不要求安装MinIO。

binding.calendar_version通过唯一 `calendar_binding_version(calendar.source_version)` 生成，与provider.version一致；来源保持当前支持的Qmt和规范股/元/右端分钟语义。实际volume_to_shares/amount_to_yuan必须显式给出。构造拒绝任何单依赖完整调用预算大于等于runner预算的配置，并要求calendar预算严格大于HTTP预算与两次evidence预算之和，保留调用准入余量。这里校验可执行的单调用组合，不承诺整步最坏耗时或外部阻塞的抢占截止；worker原步数/运行/排空预算继续生效。

## HDF-R4 验证与发行

最小回归覆盖：错误/缺失/重复字段、未知schema、秘密env缺失、无效地址/预算/单位、不同owner凭据隔离、calendar版本绑定、环境变更、无storage依赖、构造期间零网络/零业务推进、worker配置失败的凭据去敏。已有客户端校验沿实际构造调用，测试不能仅验证模拟构造参数。

通过独立wheel安装的真实worker使用本工厂，连接原日历生产者、原Operations归约器、实际原生行情/DSB服务和真实锁定MinIO SDK的隔离S3 HTTP。至少完成一次作业→存证回读→CAS确认→排空；覆盖证据故障后由同一owner断点恢复和错误配置提前拒绝。数据与存储均为合成隔离输入，禁止现场写入。子进程只加载安装的SDK及已锁定storage依赖，不导入QMT业务包、WT源码或测试factory；服务端夹具可以使用受控原owner实现。

新增模块进入显式wheel源清单，SDK版本递增，原worker及calendar调用链回归。构建、包级搬迁与独立full审查绑定最终输入。操作手册给出配置、已有job UUID运行命令、独立发布边界和失败诊断；无生产凭据或真实账户数据。全系统完成仍以真实服务与用户入口验收为准。

SDK 0.12.0 的 `market` 对象增加可选 `connect_ip`，HTTPS域名须显式给数值IP；数字回环示例保持。地址与截止规则统一引用[CTD规格](client-transport-deadline.md)。仅市场客户端采用该参数，其他依赖仍由各自传输owner负责。
