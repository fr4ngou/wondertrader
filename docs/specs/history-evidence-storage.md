# 历史证据对象存储接线

类型：功能最终规格。状态：accepted。承接 HSA-R5 的 EvidenceSink 缺项，复用观衡现有 MinIO 归档模式和已锁定 SDK；本轮不修改原 QMT 主工作树、不连接生产对象存储，也不增加作业数据库。

## HES-R1 所有者与接口

在独立 SDK 中新增 history_evidence 模块，MinioEvidenceSink 实现既有 put(sha256,canonical_bytes)→object_ref、get(sha256)→bytes。对象路径仅由部署 owner 固定 bucket、prefix 与验证过的完整 SHA-256 派生为 prefix/<sha256>.json，返回 minio://bucket/path；job 和远端数据不能指定任意路径。默认无 bucket/prefix/凭证，不创建 bucket、不修改 ACL、不删除对象、不列举或下载无关对象。

resolve(object_ref) 只接受该 sink 自己派生的完整 URI，核对固定 bucket/prefix、无额外 query/fragment/编码及完整小写摘要，再委派 get；用于受管结果读取，既有 EvidenceSink 协议保持不变。越界引用在请求前拒绝，不根据job提供地址创建新客户端。

复用原 market_data/archive.py 的读上限、close/release_conn、已有对象比对、缺失后写入及回读模式。内容地址只能接收规范 JSON bytes（与 history_runner.canonical_bytes 相同），摘要须完全匹配。重复相同内容复用已有对象；已有不同/损坏内容明确 Conflict 且不覆盖。两个合规调用者同摘要同bytes并发允许幂等写入；存储 ACL/保留/WORM 由原 owner 提供，本适配器不宣称通用原子 create-if-absent 或防止第三方篡改。

## HES-R2 错误与恢复

只有 SDK 的明确 NoSuchKey/NoSuchObject/NotFound 视为对象缺失，其他错误不触发写入。读写/响应异常转换成无私有正文的 OSError 子类，契约/摘要冲突为 ValueError 子类，适用 HistoryRunner 当前处理；保留 cause 时上层公开输出仍使用固定诊断。put 回复未知不自动重发，后续 step 用相同摘要先GET再确认；写后回读完全一致才返回引用。get 限制实际bytes且每次验证摘要/规范内容，ETag不充当SHA。

注入客户端必须以 history_single_exchange=True 明确声明单次交换契约；原生 Minio._execute 或未覆盖该重试实现的子类即使声明标记也拒绝。自定义 wrapper 的声明仍由其 owner 提供独立行为证据，不等同于生产资格。受管 factory 使用已核实版本的最小 Minio 子类，将 _execute 统一收敛为一次官方 _get_region/_url_open；避免 SDK RetryHead 内部分支再次执行 PUT，签名、序列化和错误解析继续由 SDK 提供。

## HES-R3 预算与依赖

每对象最大 16 MiB，与 runner manifest 回读上限一致；可配置 1 KiB..16 MiB。显式有限 timeout 1..30秒，适配器拥有复合调用截止并在前后检查；SDK/注入客户端须具备有限IO与关闭重试，阻塞依赖的强制抢占由部署监督者承担。超时或结果未知保持可恢复，不提升持久成功资格。

本范围以单 PUT 写对象；显式将 SDK part_size 设为 16 MiB、num_parallel_uploads=1，使上限内数据不会触发默认约5MiB多段上传门槛。真实SDK验证包含大于5MiB对象及零multipart请求，不依赖小样本推断大对象路径。

get/resolve 的规范 JSON/摘要校验结束后再次核截止，校验自身超预算也返回超时诊断。factory 在使用私有 SDK 交换接缝前精确核实 minio 7.2.20、urllib3 2.7.0；版本不符明确不可用，升级时重新验证此依赖边界。关闭 urllib3 重试与 SDK 语义重试分别验证。

优先使用原受管 minio==7.2.20 与 urllib3==2.7.0，复用官方 SDK，不实现 S3签名协议。SDK基础 import 和客户端仍为标准库；storage 可选 extra 单独声明/锁定第三方需求，构建 metadata 必须只允许所声明的 extra 依赖，不允许无条件新依赖。配置与认证由调用者注入，凭证不进异常输出、manifest、示例或制品收据。

## HES-R4 验证

以实际已锁定 MinIO SDK连接隔离 loopback S3测试服务，覆盖真实PUT/GET、响应资源释放、同内容重复零新写、并发同内容、已有损坏拒绝、不存在以外错误零写、超大/截断/未知写回复、重启读取恢复及 namespace拒绝。组合原 HistoryRunner和Operations纯DTO/归约器，证明证据写入后PUT回复丢失/证据响应丢失时不重复确认；确认记录引用可从同一对象存储重新解析并验hash。外部SDK缺少时明确skip该可选资格，实际本地验收要求无skip。

新状态/存储适配首次full独立审查，修复delta；源身份与wheel/搬迁包需重新绑定。复用无变化原生/接口行为证据，实际发布、MinIO部署权限、日历分钟权威导出、旧family路由和市场分析窗口升级仍单列pending-verification。

## HES-R5 分工

执行Agent：唯一 history_evidence.py、独立 tests/integration/history_evidence 测试、对应runbook；不改runner状态机、SDK __init__、构建脚本或原QMT。主Agent：规格/依赖extra声明与构建校验、CMake/打包/隔离安装、跨模块调用链及证据。业务Agent只读日历/导出事实调查，待契约具备后继续日历实现。只有主Agent执行原生构建。
