# 策略配置版本工作区

类型：配置服务规格。状态：accepted。前缀：SCW。范围：[COP-R2](guanheng-operator-platform.md)的App配置版本服务，页面入口已替换，实际运行生效沿B产品宿主事实另验。

2026-10-28用户纠正：策略页只展示名称、简介与版本，参考旧QMT。主App已按[策略目录](strategy-catalog.md)移出参数编辑表单；下文原配置tab和SCW-A5记录历史实现，当前页面验收沿策略目录规格。后端参数所有权、唯一核校验、保存与恢复语义继续保持。

## SCW-R1 职责与主流程

浏览器StrategyWorkspace的配置tab→策略配置HTTP→应用BoundedReader→StrategyConfigurationOwner→单写者安全文档存储。回测tab继续组合原BacktestWorkspace与[NBW](native-backtest-workspace.md)。WT-S01/S05/S06拥有原生调度、理论状态及目标，WT-B01/B02拥有回放和撮合；本切片只补C业务参数及版本保存，新增行情/持仓/交易账本0。

当前页面目录保持元数据展示，上述配置tab为已封存的首版入口。当前主流程为受控调用者→原配置HTTP/owner，实际生效继续消费B宿主。

当前新配置只允许resonance-regime-v1@1.1.2。业务对象schema为guanheng.retained-configuration.v1，含strategy_id、strategy_version及RetainedConfig的修订、策略预算比例和六项固定参数。校验调用纯包公开validate_retained_configuration，与实际决策复用同一规则：预算为(0,0.95]，其余固定参数沿正式版本；修订沿领域模型为1..256个ASCII字符。缺省固定参数经领域模型补全，额外字段拒绝。合成示例只说明结构，空目录保持零个保存版本；保存不会启动策略、交易、下载或回测。

正式1.1.2配置的有效性由运行时数据及周期准入核实，配置对象没有旧示例的日期有效窗口。校验响应validity=not_applicable，validation_time表示本次纯配置检查时间；data/runtime/execution仍未准入。历史1.2.0配置仅在存储原件校验时沿原ConfiguredStrategyConfig规则读取，保留原字节、摘要及请求回执；新validate/PUT均拒绝旧版本。包含旧版本的存储可以追加正式1.1.2，原store_id和连续revision保持。

纯包V1 a7公开`validate_retained_configuration(config: RetainedConfig) -> None`；失败为RetainedValidationError，与evaluate_current_view/evaluate_historical_model共用原参数规则，数学和计算顺序保持。旧core验证器继续服务已保存历史原件，其他策略包不进入当前安装依赖。

## SCW-R2 DTO与身份

固定前缀`/v1/ui/strategy-configurations`。所有JSON严格字段、重复键拒绝、有限数值、UTF-8及容量校验；键和值只接受Unicode标量，转义孤立代理和直接值均拒绝。相同规则覆盖HTTP解码、owner直接配置、规范编码及持久原件读取；各版本修订规则归其唯一领域模型，旧原件的合法非BMP修订仍可查询。调用者只提交纯业务配置。

| 方法/路径 | 输入 | 输出及语义 |
|---|---|---|
| GET 前缀 | 无query/body | `guanheng.strategy-configuration-workspace.v1`，catalog、owner_id、available/editable/reason及store或null |
| POST `/validate` | schema=`guanheng.strategy-configuration-validation-request.v1`、configuration | `guanheng.strategy-configuration-validation.v1`，规范configuration/configuration_sha256、validation_time/validity；只校验配置 |
| PUT 前缀 | schema=`guanheng.strategy-configuration-save.v1`、store_id、expected_revision、request_id、configuration | `guanheng.strategy-configuration-saved.v1`，store_id及持久receipt；同请求重复返回原receipt |
| GET `/requests/{request_id}` | store_id query，32位小写hex身份 | `guanheng.strategy-configuration-request.v1`，store_id/request_id、saved/absent、receipt或null；只查原请求 |

owner_id每次进程新32位hex；store_id为持久32位hex，空库revision=0。每次保存新增连续revision1..32；receipt保存request_id、request_sha256、configuration_sha256、规范configuration及saved_at UTC。request_sha256绑定store_id/expected_revision/规范configuration，request_id绑定一份完整请求。重复id先核原内容再返回；同id异内容409，旧CAS409，满32版本503。旧版本保留，首切片不删除或自动淘汰。配置摘要用纯核规范JSON；保存时间表示App落盘时间。

新1.1.2对象以自身schema和strategy_version标识，混合存储的reader至少为Appa27。Appa26仅识别旧配置对象；回退必须先确认候选兼容完整存储，原件和所有请求回执保持，避免通过删行或改摘要获得准入。

catalog只含正式1.1.2和显式合成example；store包含store_id/revision/versions。可读但维护时editable=false，原因固定中文。未配置时store=null、available=false；validate仍可用于纯参数检查，保存503。输入上限16KiB，完整状态/响应上限512KiB，版本32。JSON错误详情保持固定中文，纯核错误只映射白名单原因码/中文。

## SCW-R3 持久化、CAS及恢复

显式`GUANHENG_STRATEGY_CONFIGURATION_ROOT`默认空；root预先建立于Windows本地盘，构造零IO，lifespan在已有有界worker初始化。复用个人偏好的安全单文档机制：目录/文件身份、排除重解析点/硬链接、CreateFileW单writer、有限读取、fsync临时文件、原子替换、原件重读及关闭保留owner。状态仅保存配置版本与请求回执。

单锁覆盖读取→查原request→CAS→唯一领域校验→追加版本→原子提交→重读确认。未知保存结果返回503固定说明，GET沿同store/request核查；GET未见回执只证明本次观察尚未确认，客户端保留原请求与暂停，不自动换id/重发。跨tab沿同QueryClient保留至多一个未确认请求；路由卸载不取消已发保存。进程/浏览器重启后持久receipt可查询。文件损坏、残留tmp或锁冲突保留原件，暂停编辑；恢复先停止全部writer再由操作员核查。

所有操作共享2秒monotonic绝对截止，文件IO只能在BoundedReader中执行，复用其队列/线程关闭。写请求沿ui_origin同源规则；HTTP断连/超时只停止本连接等待，正在保存仍归原worker/owner。App先停配置准入，读池排空后续核owner关闭，原OS锁在在途结束前保持。

## SCW-R4 页面、兼容及生效边界

StrategyWorkspace当前仅展示名称、简介、正式版本及原回测入口，参数表单已移出。配置服务供受控调用者使用，预算为策略账户比例；独立配置维护不改变页面目录或默认运行输入。

校验失败、CAS冲突、未配置、满额、保存未知及恢复均中文展示；失败/读取期间隐藏旧可编辑准入。保存按钮要求当前校验与当前草稿一致，未知请求先核查；客户端无自动POST/PUT重试。页面明确“已保存App配置；实际运行生效尚待宿主确认”。回测当前仍消费部署冻结session，保存配置不会自动替换该输入。运行启停、激活/回退及实时结果沿COP后继接B正式契约，不猜接口。

## SCW-R5 验收

| ID | 验收入口与预期 |
|---|---|
| SCW-A1 | 专项真实文件/HTTP：空根→加载唯一版本→校验→保存→CAS重读→关闭重启，配置、摘要及receipt逐值相符 |
| SCW-A2 | 唯一核规则拒绝非法预算/固定参数/修订和退役版本；同一RetainedConfig送实际核时沿同一校验，缺历史不授运行资格 |
| SCW-A3 | 同CAS并发仅一追加、重复request幂等、异内容/错store/旧CAS拒绝、响应丢失后同ID GET确认 |
| SCW-A4 | tmp/坏文件/单writer/超时/关闭在途/输入和版本容量/来源去敏，未知保留原owner及原件 |
| SCW-A5 | 正式App/独立安装服务支持1.1.2；生产SPA保持元数据目录和回测入口，参数表单退出。旧配置原件/回执可读，追加1.1.2及重启保持 |

独立review以本规格及固定最终来源为准。[专项证据](../evidence/2026-10-28-strategy-configuration-workspace.md)登记当前开发、文件/HTTP、组件与隔离安装结果，B运行生效、真实A日线、交易及发布分别登记。
