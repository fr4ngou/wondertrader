# 权威分钟计划消费者

类型：运行手册。适用范围：独立 SDK 的 `guanheng_market_client.history_calendar`。状态：实现与隔离验收；生产可达端点、日历覆盖及受管存储权限由部署 owner 验收。需求见 [CAL-R1–R6](../specs/history-calendar-projection.md)。

`CalendarProjectionProvider` 通过原 MarketData 的 `POST /v1/market/calendar/minutes/query` 消费完整 SH/SZ 日历事实与闭合分钟计划。交易日、假期及午休窗口继续由原日历 owner 生成。证券历史停牌和上市/退市排除为 `not_applied`，缺 bar 继续交给历史 runner 判定缺口。

## 部署接线

部署工厂从受管配置注入 HTTPS 端点、`X-Internal-Token`、精确源日历版本和既有 `EvidenceSink`，再将 provider 与同一 sink 注入 `HistoryRunner`。HTTP 仅支持字面回环 IP；HTTPS 使用系统默认 CA/主机名校验。单次调用执行一次 HTTP 交换，随后只调用本地注入 sink 的 `put/get`；代理环境、重定向和 HTTP 自动重试均不参与。

```python
# 示例配置，所有值均须由实际部署 owner 提供。
from guanheng_market_client.history_calendar import (
    CalendarProjectionProvider, calendar_binding_version,
)

calendar = CalendarProjectionProvider(
    base_url=managed_market_data_url,
    token=managed_internal_token,
    evidence=managed_evidence_sink,
    source_calendar_version=managed_calendar_source_version,
    timeout=20,
    http_timeout=5,
)
binding_version = calendar_binding_version(managed_calendar_source_version)
# 使用 binding_version 构造既有 HistoryBinding.calendar_version。
# managed_evidence_sink 同时注入既有 HistoryRunner。
```

基础 SDK 与此模块只依赖标准库。对象存储配置沿用[证据手册](history-evidence.md)的 namespace、凭据和不可变保留规则。provider 在构造时要求 sink 声明有限 `timeout`，范围 1..30 秒，并提供 `put(sha256, canonical_bytes)` 与 `get(sha256)`。

## 完整调用预算

`timeout` 是整个 HTTP、解析、规范校验及证据 `put/get` 的单调时间预算，范围 1..30 秒；默认 15。`http_timeout` 是一次 HTTP 交换的上界，默认 5 秒且须小于等于总预算。成功响应最大 512 KiB，可用 `max_response_bytes` 配置更小上限。请求由严格证券、最多三天日期、源版本与带时区 as_of 组成，长度由字段范围固定限制。

每次有界 HTTP 或 sink 调用开始前，剩余时间须容纳该调用的完整上界；调用完成后及规范校验后再次核查同一截止。实际配置应满足 `timeout > http_timeout + 2 * evidence.timeout`，并为校验与调度预留时间。例如 HTTP 5 秒、sink 每次 5 秒时总预算设 20 秒。默认 15 秒适用于实际交换较快的调用；最坏耗时可能在后续准入时返回超时。runner 的 step 预算同时须容纳其原有 Operations、市场和证据调用，provider 的 `.timeout` 会参加现有准入判断。

上述预算会拒绝超时结果；进程内调用无法强制中断被注入依赖的阻塞或系统 DNS/清理。受管 HTTP/sink 继续配置有限 IO 和单交换契约，部署监督者承担硬停止。

## 响应与证据

客户端严格检查精确证券、日期/as_of 字符串、源版本和派生绑定，校验固定 schema/projection/scope/exclusions、完整有序的两市场事实、开闭市一致性、会话时间与来源时间。分钟必须为升序唯一的严格整数、位于查询日期与已闭合 as_of 内，并落在对应开市事实的开闭边界内。客户端消费 owner 已产生的分钟列表，日历业务窗口保持唯一实现。

响应 `facts_sha256` 覆盖规范事实；响应 `sha256` 覆盖排除自身的规范响应。存储摘要 `storage_sha256` 覆盖包含响应 `sha256` 的完整规范响应字节，两种摘要具有不同含义。校验全部通过后才写入既有 sink，随即按存储摘要读取并核对完整相同字节；返回的 `CalendarSlice.evidence_ref` 使用 sink 提供的受管引用。重复内容沿 sink 的内容地址复用。这里保存原件证据，原日历事实库继续由 MarketData owner 持有。

只有整个日期范围已经结束、每一天均具有完整 SH/SZ 闭市事实、分钟为空且 `authoritative_empty=true`，才能返回权威空段。开市前尚无闭合分钟时，空列表保持 `authoritative_empty=false`，既有 runner 返回 Pending。投影本身继续保留市场来源与生产资格的独立验收边界。

## 错误与恢复

公开错误消息均为固定去敏文本，远端正文、凭据和注入依赖异常保持在内部边界。

| 类型 | 含义与处理 |
|---|---|
| `CalendarUnavailable(OSError)` | 传输、非 200 回复、响应格式/体积、证据服务或清理不可用；后续受控 step 可重新读取同一请求 |
| `CalendarTimeout(CalendarUnavailable, TimeoutError)` | 总截止或后续完整上界准入不足；检查总预算与依赖上界，保留下一回合恢复路径 |
| `CalendarConflict(ValueError)` | 输入、响应身份、事实、摘要或回读证据冲突；核查权威源及配置后继续 |

失败校验发生在任何证据写入之前。证据 put 已完成但回复丢失时，此次返回不可用；后续同一请求重新获得相同规范响应，sink 使用相同完整摘要先回读并恢复。原 Operations 的 CAS/断点和已确认结果规则继续生效，provider 自身不创建作业账本。

## 隔离验证

```powershell
python -B -m unittest discover -s tests/integration/history_calendar -p 'test_*.py' -v
```

独立测试使用合成响应和真实回环 HTTP，覆盖 240 分钟、右端/as_of、闭市权威空、开市空、严格字段和原始事实/hash、重复 JSON 键/非有限值、传输/体积/重定向/代理、慢速交换、同一总截止、证据回读及丢回复恢复。真实原 producer、Operations、wheel-only 进程和制品源码身份由主集成流程另行验真。
