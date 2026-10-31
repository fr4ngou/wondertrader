# QMT终端只读HTTP源端

类型：功能最终规格。状态：accepted。前缀：QTS。依据：观衡全部迁入本仓库、QMT HTTP优先、终端Python3.6.8标准库边界，以及[GBW-R1/R5](guanheng-business-workspace.md)。这是源端适配，WT原生账户/存储/策略职责继续复用；完整迁入范围保持。

2026-10-22用户更新适用边界：本HTTP规格仅保留今晚前的临时流程验证及已冻结证据，不再作为正式交付的源端部署要求，后续停止优化及新安装/重启路线。共享内存由另一对话完成；待其开发完成且今晚真实验证通过、确认可用后，另以已验证契约实施WT接入。本规格的HTTP字段和请求/恢复语义不能直接假定为SHM协议，实际来源/全账户和生产资格在获准的新通道分别验证。最新约束见[DEC-001](../migration/decisions.md)。

## 原生复用与实际缺口

WT-T01/T08及现有只读插件负责四查询映射、原TraderAdapter和v2逐批值接口；WT-D01/D03/D04/D05/D11负责快照接入、DSB、历史读取及周期。QMT内嵌读取必须由终端策略线程调用，HMAC HTTP、原请求ID和逐查询来源属于供应商边界，原生WT不提供这套终端协议。

固定参考为旧源`34777db5eab144d6fe8a2f259b9f2c0de167435a`。源码调查位于`build/guanheng-workspace/terminal-source-audit-001`和`account-native-seam-001`。旧Gateway原HTTP依赖Tornado；新源端遵循终端标准库要求，传输采用有界标准库HTTP，复用原签名、请求身份、受限读取、编码与来源契约。旧策略入口、BridgeClient、执行/风控、CommandJournal和SHM不迁入此只读包。

## QTS-R1 源码与安装归属

实现位于`connectors/qmt/guanheng_qmt`，包名`guanheng-qmt-connector`。所有源码、非私密资源、测试、安装制品和手册由本仓库拥有；旧工程只读参考，不进入运行、构建、测试或发布依赖。保留逐文件/符号来源和实际摘要，机械迁入与职责适配分别登记。包导入不读取旧配置、不联网、不启动线程。

终端实现仅使用Python3.6.8标准库；现代构建工具在开发主机运行，不成为终端依赖。提供标准wheel/独立源ZIP及显式安装方法；不得自动安装到当前终端。静态3.6语法准入与真实3.6/QMT运行证据分别登记。

## QTS-R2 三类只读操作

仅开放`account.trade_detail`、`market.full_tick`、`market.market_data_ex`。账户只接受`scope=account`、`account_type=stock`及position/order/deal/account四datatype，使用显式绑定账户调用原三参get_trade_detail_data，不带策略名过滤。分钟仅1m、未复权、fill_data=False、subscribe=False；读用户已下载缓存，不触发订阅、补下载或交易范围激活。未知参数、主动订阅/下载、命令、下单、撤单及旧策略执行入口均拒绝，且不调用对应原生函数。

沿原账号查询契约保留59个显式字段和缺失/非有限值规则，保持32个新增来源字段；不得以默认零推导成本、今昨、冻结原因或真实价格类型。账户结果4096行、65536节点、262144累计标量字符、UTF8结果1MiB上限保持。分钟/快照使用明确股票数、字段、条数和结果字节上限，合法空与失败分别表达。

## QTS-R3 来源与终端owner

ReadOnlyTerminal由策略线程创建、bind_context、pump及最终关闭；HTTP线程只验签、准入、读状态/结果值。供应商函数调用只在pump中执行；锁不覆盖原生调用。绑定显式agent_id、account_id、stock、account_environment及新的qmt_session_id，维护generation；执行前后来源变化使本批失败，不能跨代际授观察资格。

保留qmt.account-query.v1的source/query/execution/completeness/trading_date，UTC带时区开始/结束时刻、原始条数和截断原因真实产生；未知券商交易日保持unknown。四批分别记录，不拼共同事务快照。健康就绪基于绑定、策略tick及在途操作，不引用旧对账结果；交易始终关闭。

## QTS-R4 原协议与请求认领

沿现有HMAC规范、五个X-QMT头、规范路径/排序query、body SHA256、时间窗口和有界nonce缓存；恒定时间比较。仅提供已鉴权health/capabilities、POST operations/{id}及GET operation-results/{UUID}。状态/事件/同步和交易路由不在此切片，不宣称其已迁入。

POST受理立即返回原进度202，结果仍由原ID拥有，GET同一ID取得202进度或原终态200；同ID同操作/参数不重复调用SDK，冲突409。绝对排队/执行/HTTP等待预算分别定义；客户端超时或断连不意味着原生调用被中断。所有响应保持原schema1.0及当前QRT能够消费的health、capability和账户来源契约，验收直接使用原生产只读DLL，不只验证Python自环。

## QTS-R5 有界内存与恢复边界

待办数量、在途、请求行/头/体、响应字节、nonce数量、终态身份/结果保留数量与总字节均有独立上限。终态保留窗口覆盖已准入调用者的最大查询/认领预算；保留期内不驱逐未确认身份以接纳新请求，满额返回背压且不调用SDK。仅回收已终态且过期记录；未知/在途结果不得当成功回收。每类集合的字节和条数限制是协议预算，不宣称等于Python进程RSS。

原Core event_store=None会使_records长期累积，新模块须在结果owner处统一解决，不能由HTTP层清理私有字典。只读源不创建订单/持仓数据库，不搬交易Journal。源重启产生新会话；已丢失的旧ID明确未知/不可恢复，禁止假称跨重启持久幂等，禁止自动改ID重试。交易持久状态未来单独接线，现有生产原件保留。

## QTS-R6 HTTP与退出

StandardHTTPServer仅监听显式回环地址，默认127.0.0.1，测试支持临时端口。单个拥有线程处理有界请求，socket及整体收包截止、请求头总量、连接关闭、重复安全头/Content-Length、Transfer-Encoding和非法JSON均明确校验。不得派生无界处理线程或让HTTP线程调用QMT。

start与关闭有真实状态和完成事件；启动超时/取消后禁止迟到监听或留下第二线程。停止先停准入、完成或拒绝排队读取，由策略owner解绑并失效代际，HTTP实际关闭/join后才报告closed。期限到达保留closing及依赖，后续有界重试；不以daemon、queue.depth=0或事件注销冒充资源回收。

## QTS-R7 公共接缝与配置

ReadOnlyTerminal(config, *, clock=None)提供bind_context(context, global_functions=None)、pump(max_operations=1)、stop_accepting()、close()及供HTTP线程调用的health/capabilities/submit_operation(operation_id,payload)/operation_record/operation_progress。内部队列和源码实现不暴露给消费者。StandardHTTPServer(runtime, verifier, host='127.0.0.1', port=18010)提供start(timeout)、close(timeout)、实际port及closed状态。HMACVerifier复用原实现语义并集中于本包auth模块，凭据显式注入、不落源码/示例/日志。

配置显式校验，运行值只有一个所有者；默认shadow/read-only，未知项拒绝。示例无真实账户/地址/凭证；策略示例只创建只读源并注册有限pump，禁止set_account、set_universe、旧AgentRuntime或执行lambda。安装/策略装载不自动替换当前运行。

## QTS-R8 验证与交付

在本仓库验证标准库及3.6语法、无旧导入、独立安装、已下载缓存读取且subscribe=False、账户59字段/完整空/未知/错误、签名/重放/重复头、请求ID重复/冲突/202认领、错owner/重入/代际切换、容量/保留/背压、超时/断连/恢复、启动取消/重复关闭/线程端口释放。源模拟SDK清楚标注；实际生产普通DLL→QRT→新源端→原TraderAdapter→v2值须独立整链验收，fixture不得冒充真实账户。

源包和新的安装制品绑定当前输入，适用独立full及delta闭合后授开发资格。真实QMT装载、现有运行切换、生产、连续push/重启恢复与交易分别验收；本切片完成不代表完整观衡迁入完成。
