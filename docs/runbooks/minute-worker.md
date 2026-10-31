# 分钟worker部署与恢复

类型：运行手册。范围：独立安装、显式依赖组合和有限进程运行。模块边界见[分钟消费](../modules/minute-consumer.md)，生产授权与真实调用链资格单独核实。

## 安装与启动

安装经SDK构建收据核对的0.9.0或兼容后继wheel；正式工厂需要storage extra中的锁定MinIO/urllib3依赖。基础HTTP/worker模块只依赖标准库，安装不需要WT DLL、wtpy或原QMT源码。

```powershell
python -B -m guanheng_market_client.minute_worker --stream-id configured-stream --lock-dir E:/runtime/minute-locks --max-steps 100 --max-seconds 300 --wait-seconds 1
```

示例目录须预先建立；factory默认 `guanheng_market_client.minute_factory:create`。锁先于工厂加载，同stream同机器互斥。部署监督负责进程重启和最终硬截止；正常退出保留owner持久事实。命令有限结束不表示持续订阅任务完成。

## 配置

`GUANHENG_MINUTE_WORKER_CONFIG` 为最多65536 UTF-8字节严格JSON；重复字段、未知字段和非有限数值拒绝。所有字段必需，仅 `evidence.session_token_env` 可选。下例均为测试占位值；实际policy SHA、数据集及日历版本必须取受管环境的权威配置。配置只引用凭据环境名字，不包含凭据值：

```json
{
  "schema_version": "guanheng.minute.factory.v1",
  "owner": {"url": "http://127.0.0.1:19901", "token_env": "OWNER_TOKEN", "timeout": 2},
  "stream": {"stream_id": "configured-stream", "policy_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "max_batch_minutes": 240},
  "sources": [{"name": "qmt", "url": "http://127.0.0.1:19902", "token_env": "MARKET_TOKEN", "timeout": 2, "dataset_version": "configured-source-v1", "provider": "Qmt", "allow_prepare": true}],
  "calendar": {"url": "http://127.0.0.1:19903", "token_env": "CALENDAR_TOKEN", "source_version": "configured-calendar-v1", "timeout": 8, "http_timeout": 2},
  "evidence": {"endpoint": "127.0.0.1:19904", "secure": false, "region": "configured-region", "bucket": "configured-evidence", "prefix": "minutes", "access_key_env": "ACCESS_KEY", "secret_key_env": "SECRET_KEY", "timeout": 2},
  "market": {"timeout": 20, "max_bars": 512, "max_windows": 1, "minimum_qualification": "NativeVerified"},
  "budget_seconds": 30
}
```

源码入口为 `integrations/guanheng_market_client/minute_factory.py`。工厂只构造依赖，不进行请求、启动线程或推进游标。`build_worker(config,environ)` 仅使用传入环境快照，不合并进程环境。

准入规则：扫描跨度取min(本地max_batch_minutes,owner checkpoint.max_batch_minutes)，两个上限均为1..1440；max_bars最多512。market.timeout须严格大于每个source.timeout与calendar.timeout；calendar.timeout须严格大于http_timeout+2×evidence.timeout；budget_seconds须严格大于market.timeout+4×owner.timeout。最后一个预算包括恢复回查、提交、再次回查及CAS刷新。

## 运行和故障处理

owner使用X-Internal-Token，行情HTTP使用原Bearer协议；凭据不互换。HTTP只接受字面回环地址或验证证书的HTTPS，拒绝重定向，每个请求和响应最多1MiB。固定结构日志只输出schema、phase、status、steps和recovery_required。

| 退出码 | 含义与处理 |
|---|---|
| 0 | 此次有限进程正常关闭，按监督计划继续启动；检查owner游标了解实际进度 |
| 2 | 配置或启动失败；核查显式配置、依赖版本与锁占用 |
| 4 | 关闭失败或接纳尚待核查；保留owner数据，下次从checkpoint/原收据恢复 |
| 5 | 永久身份/协议/请求等错误；核查owner政策及事实冲突后再恢复 |

信号只请求停止，当前有限步骤完成后回查未知结果。关闭期间不开始新poll、不重投POST。未知结果用原batch和request摘要核查，禁止手工推进游标或以本地最高bar替代。

## 验证

`integration.minute_worker` 和 `integration.minute_factory` 注册在CTest。独立命令可用 `python -B -m unittest discover -s tests/integration/minute_worker -v` 及对应minute_factory目录。

安装验证使用 `tests/integration/minute_sdk_flow`；`GH_MARKET_CLIENT_WHEEL` 指定当前SDK构建的wheel，`GH_MINUTE_FACTORY_STORAGE_SITE` 可显式选择storage依赖目录，缺省沿 `GH_HISTORY_FACTORY_STORAGE_SITE` 或当前验证解释器的purelib。子进程用 `-I -S -B`，显式添加安装site和选定依赖目录，不执行.pth，拒绝私有QMT/WT源码导入。测试证明基础模块独立导入、正式工厂零副作用构造、有限CLI入口和关闭；真实业务接纳、消息、策略和页面仍按整体验收单独验证。

SDK 0.12.0 的 `sources[]` 可配置 `connect_ip`；HTTPS域名必须给显式数值地址，数字回环HTTP兼容。仅行情来源使用[CTD网络截止](../specs/client-transport-deadline.md)，owner/calendar/evidence传输保持各自资格，配置转发不代表完整分钟链已验。
