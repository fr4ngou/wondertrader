# 原生历史窗口与周期查询

类型：功能规格。状态：accepted。前缀NQW。承接[NHQ原生查询](native-history-query.md)，依据用户要求统一原生行情、图表与研究读取并复用WonderTrader已有能力。该增量提供图表需要的最多N根和原生周期；来源补齐、策略确认、复权及用户入口继续按各自要求验收。

## 复用与职责

现有HTTP `history.query` → MarketBridge → Store → 已拥有的IRdm；原count/range选择基础m1，原WTSDataFactory提取周期。继续单一DSB/sidecar、RootLease、缓存代际、来源与预算，不增加数据库、服务或核心修改。原生不足的输入准入、字段映射、输出窗口及数量限制由适配层承担；OHLC/量额聚合使用原工厂。

来源能力WT-D01/D02/D04见[原数据能力](../modules/wondertrader-data-capabilities.md)。固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`；原Factory的alignSec第二小节公式和session静态小节列表需限定。本入口仅m1和已核沪深标准09:30–11:30、13:00–15:00时段的5/15/30/60分钟，固定`includeOpen=false, alignSec=false`。其他周期/时段返回NotSupported，后续按原生能力逐项扩展。该限制不改变WT其他原入口。

## 公共数据与兼容

`history.query.request`在既有exchange/code/from/to之上增加可选`period_minutes`（1/5/15/30/60）和`limit`（1..10000）。from/to仍是上海右端分钟的闭区间，均显式给定；limit缺省为0，表示范围全部，超出响应容量仍背压。limit为最多条数，不能作为完整历史或恰好根数证明。选取目标bar右端在区间内的最后limit根。from若落在周期内部，聚合仍包含完整桶的已有基础输入，禁止先截断桶再计算。to仍是输出截止，尾部未完成周期不返回。

新增选择器只允许`history.query`，`history.read/prepare/task`保持原m1补齐协议。显式选择器禁止非空expected_minutes或calendar_version，以免把派生条数或尾部截断解释为m1覆盖证据。扩展响应保留bars/metadata/coverage/missing_minutes，并增加`selection={period_minutes,limit}`精确回显；coverage为Unknown、missing为空。普通旧查询请求/响应形状保持。未配置native_reader的扩展查询返回NotSupported，禁止退回旧手工索引或Python聚合。

C++ `HistoryQuery`包含原MinuteRequest window、period_minutes=1和limit=0；Store原MinuteRequest重载委托到同一实现。Reader原range保留兼容包装，增加query selector。客户端沿原SDK和HTTP传输，响应验证选择器、数量、时间、来源和字段；没有独立客户端服务或新协议。SDK沿原history_query(request)组装窗口字段，不新增客户端服务，也不复制日历/聚合/来源合并。

## 原生选择与生命周期

每代首次校验沿NHQ，基线首末已知后才能调用count，截止在首条前直接空返回，避免原索引回退begin。m1 limit调用原count并裁剪lower bound；m1范围沿原range。

派生范围将基础读取起点扩到from的当日开始，再由原range选择；限定周期整除沪深两个120分钟小节，不跨日。派生tail用原count取得截止内的已加载有界基础历史，再原Factory提取并取尾部，避免假定N倍基础条数足够。源条数、完整首次加载、缓存字节继续受NHQ约束；响应仍至多10000。派生数组为本次临时结果，无独立长期缓存，修订自然沿Reader代际生效。内存预算是载荷约束，不能声称进程RSS硬上限。

Factory调用前核真实session映射及基础bar在有效右端分钟中；非法09:30/13:00、非交易时间不交给其无符号分钟算法。同模块内所有本入口的Factory提取以统一互斥串行，避免其首次静态小节列表填充在适配实例之间并发。该锁不扩授任意其他上游调用路径的线程安全。

所有借用切片、工厂结果通过RAII释放；输出数组自有，生成过程在Store互斥和RootLease内。原结果字段口径为首open/reserve、最高high、最低low、末close/settle/hold，vol/money/add累加；业务不能另写聚合算法。原工厂只删除最后一个未闭合输出桶，不证明内部桶拥有全部源分钟，覆盖继续Unknown。

时间预算沿NHQ：本地同步磁盘/DLL不能中断，history.query仅大小限制，客户端HTTP截止不代表服务端取消；不能将本入口放到策略ticker回调。页面5秒总预算仍在业务接线阶段验证。

## 验收

| ID | 预期结果 | 验证 |
|---|---|---|
| NQW-R1 | m1最多N，短历史/截止前/空档/下界/端点正确，旧查询兼容 | 原DLL+独立数组oracle、SDK/HTTP链 |
| NQW-R2 | 5/15/30/60完整字段、午休/跨日/内部起点/截止闭合符合原Factory与独立预期 | 可核算完整时段数据；缺口保持Unknown |
| NQW-R3 | 同实例修订/追加后基础与派生同步更新，旧副本稳定、快速换代背压可恢复 | 原Store发布/查询、原delete生命周期回归 |
| NQW-R4 | 不支持的周期/时段、非法源分钟、选择器/覆盖冲突、容量明确失败；native失败无旧聚合回退 | 真实DLL负向及严格wire测试 |
| NQW-R5 | 独立SDK安装后可读原服务窗口；真实428输入与来源身份保持；核心摘要不变 | wheel-only/HTTP/真实样本/独立full审查 |

## 交付与后续

先完成本入口原生与协议验收，再替换图表recent_bars及墙钟Python5m聚合，保留MarketChartBundle和Console路由。特征纯算法、复权研究和策略状态独立适配，不能以窗口测试冒充业务页面验收。源码、规格、构建、测试、制品和剩余范围写入证据；生产发布仍按明确授权。
