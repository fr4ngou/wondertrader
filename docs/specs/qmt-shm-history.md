# 共享内存历史一分钟行情接入

源值接入采用[源值分钟历史合同](qmt-source-history.md)：新 v2 保留来源 double 量额和时间标签；本页已有 v1 标准化合同保持。存储复用同一 WT Helper/DSB，不增加数据库。

类型：功能最终规格。状态：accepted。前缀：QH。所有者：券商接入与原生行情维护者。继承[QSW](qmt-shm-wt-binding.md)的通信、原ID、三绑定和关闭约束；扩展显式历史只读能力，复用WT原生存储与读取。真实数据、组合运行和生产资格分别验证。

## QH-R1 能力与版本

Agent标准库模块read_capabilities拥有唯一封闭operation描述与profile/request/policy联合准入；Host、配对工具、Journal入口和Agent派发共同使用。本历史契约登记market.full_tick和market.history_1m，部署显式选择非空有序子集；未知、重复、通配符、policy错配及额外字段拒绝。请求不能提供模块、类、函数或回调。账户操作由独立 QAR 契约准入；历史 CLI 始终只发历史操作。

仅full_tick保留已验v1三字段profile及canonical原字节。单独历史能力及行情加历史组合使用qmt.read-profile.v2；含账户加历史的组合沿 QAR 已定义的 v3。v2 精确结构为：精确字段read_profile_version、read_operations、execution_timeout_ms、control_profile、operation_profiles。operation_profiles与read_operations键集相同；每项精确含policy_id、policy_version、execution_timeout_ms、limits；全局执行上限等于各项最大值。full_tick limits为空对象，history limits精确含schema_version=qmt.history-1m.v1、max_calendar_days、max_rows、max_data_bytes；days最多5、rows最多2000、bytes为显式受管额度，均可收紧。逐项执行/排队/总期限与Host policy核对，v1全局标量不授其他操作额外预算。完整profile原bytes/SHA进入原认证绑定，两端必须相符。

旧C++ full_tick客户端保持严格v1行为并拒新profile。新历史阶段资格只授同版历史客户端；同时行情/历史/未来账户并用须另验同版client/profile组合，不假定同一现场可同时运行多个Host/Agent。新安装版本及材料与既有已验包并存，运行实例由明确维护动作切换。

## QH-R2 请求及原线程

operation=market.history_1m，policy=qmt.history-read.v1、version=1.0。arguments精确为symbol/start_time/end_time/max_rows：单个六位.SH/.SZ；14位整分钟且包含起止；日期域2021-11-01..2099、最多5个日历日；max_rows为精确int 1..2000、拒bool。结束日早于受信owner的当前上海日期。Host准入与Agent执行再核，公开请求不能指定now。

固定SDK调用ContextInfo.get_market_data_ex：fields为time/open/high/low/close/volume/amount，stock_code=[symbol]、period=1m、显式start_time/end_time、count=max_rows、dividend_type=none、fill_data=False、subscribe=False。仅构造bindings的原策略线程执行；没有主动下载、订阅、账户或交易调用。

History1mAdapter.execute只返回有界普通DTO。原tick唯一拥有排队、开始时间、SDK/转换、完成时间、错误、既有finalize_result及一次future发布。adapter接收原monotonic绝对截止，不嵌套演示handle、不新增另一套封装算法或结果发布者；完成时点在SDK/转换结束后采样。封装后若发现原截止已到，同一owner可用同一finalizer将尚未发布的成功结果改为有界超期错误，成功字节始终不发布；SDK不重调、Journal仍仅落原ID的一份终态。公开错误使用固定原因，不携带SDK异常正文。

## QH-R3 数据形状

先核受信SDK Frame的shape、七列精确集合和行数，再用itertuples(index=False,name=None)有界遍历。拒绝缺行/多行、超长标量、非有限数、错误OHLC、负量额、重复/乱序/越界/非整分钟time。普通JSON只接精确内建类型；Frame方法和item转换限于受信SDK边界。time取显式epoch毫秒列；volume/amount保留源值，不按金额反算、不改用其他量字段。

data使用qmt.history-1m.v1，精确含symbol/period/start_time/end_time/max_rows/rows/coverage/source_options；rows为原七字段，coverage恒unknown，source_options固定none/fillfalse/subscribefalse。rows>=max_rows返回history_window_limit并整批拒绝，空Frame保留为空观察且不生成成功DSB。行数小于count也不授完整覆盖、停牌或精确股数资格。

## QH-R4 单总预算

同时核rows/标量、max_data_bytes、原result/frame、CALL/REPLY/cycle、HTTP、Journal reservation及累计输出额度；max_data_bytes<=max_result_bytes-4096。实际UTF-8 bytes必须计入，禁止先无限制展开再测大小。沿原canonical与result finalizer保留原字节和摘要。

Agent执行的一个绝对截止覆盖准入、SDK、遍历、转换和封装；Host原队列/运输期限及a2关闭发布语义保持。SDK原生调用不可安全抢占，晚回不证明撤回，须保存原ID的超期/未知终态；不重POST或强杀QMT。达到Journal计数/逻辑预算即停止新准入，terminal继续计入保留；长期轮询和大规模导入需要另定保留方案，本规格不授权自动删除、透明轮换或现场重启。

## QH-R5 原ID恢复与分页

认证bound-read路由只增加已登记operation。保留原请求UTF-8 bytes/SHA、receipt、接纳/派发/结果三绑定及终态原bytes/base64/SHA。首次POST前持久保存原ID/body/预期profile/binding；丢失回执或结果未知仅GET原ID。旧终态绑定原代际；无绑定旧结果保持unqualified。

history_window_limit后，显式计划可将窗口切为[start,mid]及[mid+1minute,end]，新页各有新ID，原页保留。单分钟饱和明确失败。计划受最大页数、累计rows/bytes及整体绝对截止约束，停止时保存已完成页和缺口，不称完整历史。新计划不能把旧未知ID换名重发。

## QH-R6 C++消费及原生复用

内部QmtBoundReadCore复用同一BoundedSignedHttp、绑定/result codec及GET恢复；沿编译期封闭描述选择；原 FullTickV1/History1mV2 保留，历史门面显式 v3 选择复用 QAR 已有 History1mV3，不新增另一套协议。原QmtHostReadClient作兼容门面，新QmtHostHistoryClient作历史门面，不复制网络/签名实现。原公共receipt/result及旧请求字节、错误和严格未知拒绝行为保持。

正式GuanhengQmtHistory CLI使用固定受管配置和显式请求文件；输入不能选择命令/插件，原ID/receipt须在首次POST前原子写入新独占根。resume只GET原请求。页数、rows、bytes、单总截止和输出硬限均明确；stdout有限、原数据文件原子发布。可选Python编排只调用受管正式CLI，不使用开发probe或新Python HTTP栈。

### QH-R6.1 CLI 显式只读版本配置

受管配置 schema 保持 `qmt.history-cli-config.v1`。原六个顶层键 `schema/http/request_root/runs_root/limits/source_profile` 必须保留；仅增加可选键 `read_profile_version`，其他未知键仍拒绝。省略该键或显式字符串 `qmt.read-profile.v2` 选择现有 `QmtReadProfileVersion::Legacy` / `History1mV2`；显式字符串 `qmt.read-profile.v3` 选择现有 `AccountV3` / `History1mV3`。null、布尔、数字、空字符串、v1/v4 及其他值在任何网络调用前拒绝。配置只选择封闭的现有客户端版本，operation 始终为 `market.history_1m`，不增加账户查询或交易调用。

选择 v3 时仍由原 QAR v3 客户端完整验证账户与历史组合 profile、全部 limits、policy、原认证绑定及原结果；选择 v2 时保持原 v2 握手与准入。两种选择均不探测降级、不自动改配、不因收到新版本而自动接受。配对清单 `qmt.shm-pair.v3` 描述材料版本，不能代替 read profile 选择或真实历史来源资格。

原完整配置 raw SHA 同时绑定新增字段。resume 先校原配置 SHA 再建立客户端，版本或其字节变化拒绝沿旧计划继续；通过校验后仍只 GET 原 ID。历史分页、未知结果、单位未知、Journal 容量、原单总截止、QMI/DSB/Reader 及既有默认行为保持。

定向回归须驱动实际正式 CLI：原缺省及显式 v2 对 v2 成功、显式 v3 对合法账户加历史 v3 成功；交叉版本在历史 POST 前拒绝；非法配置在 binding GET 前拒绝；v3 成功保原 receipt、原 native bytes、QMI 数据与 resume 原 ID，配置变更恢复拒绝。合成签名 HTTP 验证消费者选择与闭环，真实 QMT 读取、已下载完整历史、单位和 DSB/Reader 交付分别验收。

每页经完整认证与原终态准入后核数据回显/形状。非空rows交现QMI七字段CSV→固定WtDtHelper DSB→原Reader/分钟消费者；分页重复timestamp或矛盾值拒绝。minute_boundary、量额倍率、资产类别与许可来自明确受管source profile，缺单位证据保持unknown，不暗设100。不填无成交分钟、不复权、不以文件数证明覆盖，不改WT框架、QMI、原DSB/Reader或策略算法。

## QH-R7 验收与发布

覆盖现代及实际Python3.6、H1完成时点成功/异常/晚回、未知op/policy/profile、参数/巨大输入、时间/数据/字节全部联合边界；同一准入owner在所有入口结论一致。不同作者独立审查，新noneditable安装通过实际SHM与合成原线程SDK、唯一finalizer、GET三绑定/原字节→正式CLI→QMI/DSB/原消费者链。完整/空/饱和/分页、丢回执、切代、旧结果、满Journal、超期、停止/排空均需验证。

原full_tick协议、v1原字节与拒未知、HTTP回调排空、a2关闭并发回归保持。合成结果与真实终端字段/单位/ETF覆盖分别登记；准备可审阅新配对材料后才处理现场加载及真实小窗口验收。具体实现分工与当轮原件记入任务记录，规格描述稳定行为。
