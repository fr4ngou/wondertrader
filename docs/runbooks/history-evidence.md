# 历史证据存储适配

`guanheng_market_client.history_evidence` 随独立 SDK 发行，提供 `MinioEvidenceSink` 和可选工厂。模块基础导入只使用标准库；生产对象存储权限、命名空间、保留及不可变策略由部署 owner 提供。当前交付只使用隔离 S3 HTTP 和合成认证信息验证，真实 MinIO 与日历端点仍需部署资格验收；原日线 family 拒绝保护已在 owner 分支完成[HFA 隔离验收](../evidence/2026-10-21-history-family-admission.md)，正式安装随其独立发布流程继续。

安装 SDK 的 `storage` extra 使用锁定的 `minio==7.2.20` 与 `urllib3==2.7.0`。部署系统显式提供配置和凭据，不把凭据放入命令行、日志或证据。

```python
from guanheng_market_client.history_evidence import create_minio_evidence_sink

# config、credentials 由部署 owner 提供，不读取默认环境或默认 bucket。
evidence = create_minio_evidence_sink(
    endpoint=config.endpoint,
    bucket=config.bucket,
    prefix=config.history_prefix,
    access_key=credentials.access_key,
    secret_key=credentials.secret_key,
    session_token=credentials.session_token,
    secure=True,
    region=config.region,
    timeout=5,
    max_bytes=16 * 1024 * 1024,
)
```

可以传入已受管客户端：`MinioEvidenceSink(client, bucket=..., prefix=..., timeout=..., max_bytes=...)`。客户端类必须显式声明 `history_single_exchange=True`、关闭传输及 SDK 语义重试、使用有限 IO timeout，并支持官方 `put_object` 的 `part_size`、`num_parallel_uploads` 参数。直接 Minio 及继承原 `_execute` 重试实现的子类即使声明标记也会被拒绝；其他 owner wrapper 仍须提供独立 QA 依据，能力声明本身不授生产资格。

工厂精确核对 minio 7.2.20/urllib3 2.7.0，版本不同返回固定不可用诊断。在本机已核实的7.2.20中，`Minio._execute` 遇到 RetryHead 会第二次调用 `_url_open`，包含可能已提交的 PUT；关闭 urllib3 重试仍会触发该 SDK 行为。工厂通过最小子类统一将 `_execute` 限为一次官方 `_get_region`/`_url_open`，保留官方签名、序列化及错误解析，不按 method 或错误码添加放行特例。该私有依赖接缝只适用已核实的精确版本，升级 SDK 须重新审查和行为验真。

工厂启用 TLS 验证；明文仅接受字面 loopback IP，拒绝远端明文、隐含凭据 URL 及路径。显式 region 避免 SDK 自动区域发现。构造不会连接对象服务。

调用 `put(sha256, canonical_bytes)` 前，使用现有 runner 的 `canonical_bytes` 和 SHA-256；只接受完整小写64位摘要与完全匹配的规范 JSON bytes，拒绝重复键、非有限数、非法 UTF-8、过深结构及大小越界。路径固定为 `prefix/<sha256>.json`，引用为 `minio://bucket/prefix/<sha256>.json`。调用者不能用 job 指定对象路径。

`put` 先 GET；仅官方 SDK 的 NoSuchKey/NoSuchObject/NotFound 可以授权写入，其他错误返回固定不可用诊断。已有内容经摘要/规范验证且字节一致时直接复用；已有损坏或不同内容返回冲突。缺失时显式限制单次 PUT（part_size=16MiB、并行数1），上限内不启动多段上传；写后 GET 完整一致才返回引用。写回复未知不自动重发，下次同摘要调用先 GET 核查。两个合规同摘要写者内容相同可幂等；本适配器不承诺通用原子 create-if-absent 或抵御第三方对象篡改。

`get(sha256)` 验证实际读取字节上限、摘要与规范内容。`resolve(object_ref)` 仅接受本 sink 自己派生的完整 URI，拒绝其他 bucket/prefix、query、fragment、路径编码及异常摘要，然后委派 get。最终 result manifest 的 segment_sha256 可以逐个 get 验真；result_ref 与证据内容都不授予额外存储权限。响应成功、读取异常、超限和关闭异常时都会尝试 close 与 release_conn。

`timeout` 为每个 put/get 复合调用的总预算，范围1..30秒；`max_bytes` 范围1KiB..16MiB。适配器在各阶段、读取分块前后及最终摘要/规范校验后核查截止，get/resolve 校验自身耗尽预算也返回超时；公开 timeout 供 HistoryRunner 预算准入。官方 SDK 网络调用与清理本身必须有界；注入方阻塞超过预算时只能在其返回后诊断超时，强制抢占由部署监督者承担。原 runner 每步预算也必须能容纳整个存储调用上界。

公开 `EvidenceUnavailable` 继承 OSError，表示不可用/未知，恢复从同摘要读取开始；`EvidenceConflict` 继承 ValueError，表示命名空间、摘要、内容或契约冲突。二者使用固定消息，handler/CLI 只输出受管诊断，不显示底层 SDK 异常、响应正文或凭据。模块不创建 bucket、不修改 ACL、不列举/删除对象、不持久化作业事实。

验真命令（仓库根目录）：

```powershell
$env:GH_QMT_SOURCE_ROOT='D:/workspace/qmt'
D:/workspace/qmt/.venv/Scripts/python.exe -B tests/integration/history_evidence/test_history_evidence.py
```

测试使用真实锁定 SDK、本机隔离 S3 HTTP、原 Operations 纯 DTO/内存归约器和原 HistoryRunner：覆盖大于5MiB的单 PUT、响应资源、重复/并发、损坏/非缺失错误、超限/截断、写/读回丢回复、同摘要重启读取、严格 URI 与完整结果回查。真实400 XML RetryHead 的 PUT已写入场景只发送一次PUT并返回未知，下次同摘要先GET恢复；GET RetryHead也只交换一次且不授写入。另覆盖版本与标记拒绝、get/resolve 校验耗时超预算且资源释放/零写。组合故障验证对象写入未知后恢复，再丢 Operations checkpoint 回复，最终仅一次确认、一次源 work。未配置 QMT 源路径时仅原纯 oracle 组合用例显式 skip；缺 storage extra 时相关 SDK 用例显式 skip。实际本地验收要求无 skip。
