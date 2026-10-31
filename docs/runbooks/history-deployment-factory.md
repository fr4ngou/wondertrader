# 历史工作进程部署与调用

类型：运行手册。范围：使用独立SDK的正式factory组合既有服务；作业、数据、日历与证据的所有者保持。配置契约见[HDF规格](../specs/history-deployment-factory.md)，执行/退出语义见[HW规格](../specs/history-worker.md)。本手册不授予生产作业或发布权限。

## 安装与配置

在受管Python环境安装经摘要核对的 `guanheng-market-client` wheel和storage extra。0.8.0提供 `guanheng_market_client.history_factory:create`；MinIO 7.2.20及urllib3 2.7.0保持已有锁定版本，完整依赖环境由发布方锁定。基础SDK导入不加载这些可选依赖，选择此MinIO工厂时必须具备它们。

部署者向进程注入 `GUANHENG_HISTORY_WORKER_CONFIG`，内容为[规格中的v1 JSON对象](../specs/history-deployment-factory.md)。该JSON只保存端点、来源绑定、预算、bucket/prefix及凭据环境变量名；凭据值分别从进程环境注入。配置不来自作业正文或远端响应。工厂固定组合现有客户端，不执行配置中的任意代码。

Operations、行情、日历使用各自的url和token_env。明文HTTP只支持字面loopback地址；跨主机使用验证TLS的HTTPS。证据存储必须已有受管bucket、namespace/ACL和保留规则，工厂不会创建它们。MinIO endpoint不含协议，secure控制TLS，region必须显式提供。临时存储凭据需要时指定session_token_env。

绑定中的agent、profile、来源许可及量额换算必须来自实际来源契约。calendar.source_version来自权威日历owner；factory通过既有函数生成唯一calendar_version，供日历投影与HistoryBinding共同使用。配置错误、缺失凭据和不支持的依赖版本在业务推进前拒绝。正常构造不产生HTTP或存储请求。

每个依赖完整调用预算须小于runner的budget_ms；calendar.timeout还须大于http_timeout+两次证据存储timeout之和。worker的drain_seconds须严格大于runner预算秒数。示例的30秒runner使用35秒默认排空窗口；配置预算不能替代服务端或进程监督的真实截止。

## 执行已登记作业

Operations控制面先登记/授权历史作业。部署者核对其dataset_version、agent_id、来源及分钟规格与当前HistoryBinding一致；本工厂不创建、resume或修改作业规格。确认作用域后，使用已有job UUID及预建的受管锁目录运行：

```text
python -B -m guanheng_market_client.history_worker --factory guanheng_market_client.history_factory:create --job-id <已有作业UUID> --lock-dir <受管绝对锁目录> --max-steps 100 --max-seconds 300 --drain-seconds 35
```

命令参数不含凭据。worker先获取该job的OS锁，再调用factory；同机同锁目录的冲突执行在构造前拒绝。跨主机单副本/分配由部署owner保证，原Operations CAS继续约束修订。原自定义factory仍可使用，已有调用方式保持。

worker仅输出固定JSON阶段/状态/计数。工厂配置错误显示固定配置失败消息，不回显JSON、环境值或依赖异常。退出0表示观察到作业终态且排空，具体成功/失败以Operations为准；3表示本地预算/信号暂停且排空，4表示排空或队列owner恢复未确认，5表示不可继续的步骤错误且排空。配置错误为2。未知prepare或release结果沿现有恢复诊断，保留原身份，不自动重启共享行情服务。

## 验证与发布

本机自动验证以显式 `GH_CALENDAR_OWNER_SOURCE`、`GH_QMT_SOURCE_ROOT` 选择受控原实现，以 `GH_HISTORY_FACTORY_STORAGE_SITE` 选择已安装锁定storage依赖的site目录。该变量只用于隔离测试子进程，不是生产factory配置。完整native流程在源构建和搬迁包分别运行 `tests/integration/history_factory_flow`；测试服务使用合成数据，子进程以安装wheel调用正式factory，无QMT业务源码或测试factory。

实际发布分别登记SDK/原生行情服务、观衡Operations/日历服务及存储配置身份。开发全链通过后仍需核对生产分钟日历、真实下载覆盖、存储ACL和服务监督，按完整用户入口验收。factory就绪不授予账户或交易能力。

SDK 0.12.0 的 `market` 对象增加可选 `connect_ip`，HTTPS域名须显式给数值IP；数字回环示例保持。地址与截止规则统一引用[CTD规格](../specs/client-transport-deadline.md)。仅市场客户端采用该参数，其他依赖仍由各自传输owner负责。
