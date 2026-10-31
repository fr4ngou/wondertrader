# QMT HTTP 原生只读接线验证

类型：隔离开发证据。状态：原候选227项检查通过，首次独立full要求修正，后继修正中。规格：[NQH](../specs/native-qmt-http-bootstrap.md)。真实 QMT 安装、主构建接入、搬迁和生产尚待验收。

## 实现与所有者

自有 TraderQMTReadOnly 增加显式 qmt_http 来源，复用 QRT Account 与固定原 TraderAdapter；HTTP worker 交值结果，宿主 owner 交付 API/SPI。实际账户范围、来源代际、原终态仍由 QMT 原 Core/Queue/Journal 拥有。本切片使用固定 QMT 提交34777db的合成原生对象及真实签名 HTTP，不访问运行终端；SQLite 是原 Journal 的隔离测试实例。

新增字段映射、v2 值拷贝观察及有界关闭，保留 fixture 和 Diagnostics v1。原 Adapter 的合计持仓、订单成交及资金链各自复用；真实今昨、冻结原因、价格类型、四批原子性和执行资格分别限定。详细接口见[模块说明](../modules/qmt-readonly-trader.md)。

## 构建与根任务复核

最终普通构建为`build/native/qmt-http-bootstrap/implementation-001/build-020`，实际回调门控构建为build-021。两者各322个固定上游Git blob逐字节核对、2322项实际编译头、9个编译对象、31项实际库搜索输入和4项编译工具；库搜索记录与实际动态依赖分别解释。主任务独立读取Git blob并核全部文件SHA、当前27自有输入、DLL/probe及日志摘要，959个跟踪核心与此前冻结候选无新漂移。该结论表示沿既有候选无新增核心修改，未声明当前工作树等同干净上游。

冻结清单SHA `57ff339137b1ac37dd7094896840093ec8846680627b9105d5011df48f09e005`；根任务验证在`build/native/qmt-http-bootstrap/source-boundary-001/nqh-final.json`。原静态工具库来自已核原original-build，本切片尚未在新机器从锁定依赖重新构建这些库。

## 检查范围

| 检查组 | 通过项数 | 范围 |
|---|---:|---|
| 实际签名 HTTP 链 | 71 | 合成原 Core/tick/Journal，经 QRT 到固定原 Adapter；来源、映射、空错、预算及回调 |
| 原 fixture 矩阵 | 68 | 原初始化、数据及异常路径 |
| 根因回归 | 60 | 原解析、归属、去重和生命周期回归 |
| fixture 补充 | 8 | 含5项复用结果重核 |
| 实际延迟回调关闭 | 3 | prepare、POST、原 ID GET 的真实回调门控 |
| 直接 ABI | 14 | 单进程内长度、指针、版本、owner、状态等断言 |
| 未 connect/失败 init 关闭 | 3 | 补充探针的资源终态 |

总计227项检查、零失败；检查数与独立进程数分别记录。HTTP 每case没有内嵌运行时 DLL 摘要；工具调用、冻结源码、manifest、加载路径断言及产物SHA构成联合输入绑定，见implementation-001/execution-bindings.json，SHA `2e47c4fcf87895860a37c2b5dbbc44e9de43e749cf99b911b6e496d63dd47083`。

实际延迟回调测试先制造关闭超时，验证指针与依赖保留，再允许 OS 回调结束、再次 owner release、真实 join 和删除。已成功初始化的最终探针场景退出 Adapter/sink/BaseData 栈并平衡已知加载引用后，实际 GetModuleHandle 为空；该一轮探针证据不授生产热卸载资格。

自查修正 owner 观察视图在 worker 完成时自行变化的缺陷；原三例失败保留，修正后 worker 完成至 owner 再次 release 之间视图字节稳定。SPI 异常时保留可能的部分应用事实，未成功返回的行视图保持 Unavailable。对应职责和原因已在自有源码写中文注释。

## 独立审查及剩余资格

首次完整审查包为`build/native/qmt-http-bootstrap/review-full-001/final-package.json`，SHA `b6763467a6b35c418bb86d0a50e25746ce4407fe9df57b86cb9dbe320c416ee2`。独立审查按 NQH-R1–R8、规范和并发关键链核查；发现与最终资格以后继结果追加，当前检查通过不替代独立结论。

主 CMake/profile、CI、锁定依赖 fresh 构建和可搬迁包尚未接入；运行中的 QMT 源身份及真实账户四查询、合约和页面另行验收。持续 push、重连、执行器、跨进程 ticket、OOM/断电与生产均未取得本切片资格。已有账户、订单、分钟数据及运行终端保持。

首次full正式报告为review-full-001/review.json，SHA `90e061b09243ea63c68ed766ad72bca72de9ad5367dddcdd683a729a089b0d65`，结论request_changes；R1/R2/R3/R4/R6 complete，R5/R7/R8 gap。NQH-F1为映射/序列化/WTS构造后、SPI前缺截止重检，以及同次pump成功控制事件的截止窗口；F2为测试宿主使用inspect/pump/yield忙轮询；F3为HTTP状态49–57、买卖和去重缺原Adapter订单/成交统计oracle。三项分别在自有交付边界、宿主等待和真实消费端断言修正，原框架保持。原227、full包及报告保留其实际输入，后继构建和复审逐项关闭后才授当前开发资格。

## 后继248项与第二次完整审查

repair-001在SPI前统一准入，并加入自有wait事件接口；用实际SPI、原logger和公开risk门槛补统计验证。三个确定性旧晚交付红例均转绿。新普通green-build-002及专用gated-build-001完成248项检查：HTTP86、实际回调/伪唤醒4、ABI19、未connect3、原fixture68/根因60/补充8（含5项复用断言）。普通/门控各322份原Git、30份自有输入、9对象和实际依赖已核，90次HTTP/gate的实际宿主/DLL/工具收据及两套各1526份QMT导出已独立回读Git对象与文件摘要；959跟踪核心无新漂移。根任务验证为source-boundary-001/nqh-repair.json，冻结清单SHA `9d4eca5f16a9af33d7f4c51b86c314d986d4e58b48209614451716fd2013572d`。

新full包review-full-002/final-package.json SHA `bdcd18d05b1b08692d1200f09db46438d3b4b16f35a25321e295a3c7abb93122`。独立审查确认原F1–F3闭合；当前R1/2/3/4/6/7 complete，R5/R8因唯一新P1 NQH-NEW-F1为gap：自有HttpMapping的CNG哈希backing缓冲区先于hash句柄析构，违反[Microsoft生命周期契约](https://learn.microsoft.com/en-us/windows/win32/api/bcrypt/nf-bcrypt-bcryptcreatehash)。该结论为源控制流及官方API要求证明，未宣称已复现进程崩溃。已解除该候选冻结，限定自有RAII顺序、中文注释及真实CNG资源顺序探针修正；原QRT已有正确顺序，保持原实现。

248绿灯保持其原输入和检查范围，当前未取得HTTP最终交付资格；新修正、适用回归及独立delta确认完成后另记。原架构、框架和生产未改。


## repair-002 资源顺序修正与独立 delta

2026-10-22：唯一生产代码差异位于自有 HttpMapping.cpp，先声明 CNG backing buffer，再声明负责销毁 hash/算法句柄的 RAII guard，长度查询后 resize；中文注释说明正常及异常退栈必须维持该顺序。原样三条真实 CNG 回归均观察 backing-delete 早于 DestroyHash；新候选成功、HashData 失败、FinishHash 失败三条均先 DestroyHash/CloseAlgorithm 再释放缓冲区，真实创建/销毁各一次、固定成交 ID 不变。原样测试仅在隔离探针暂缓物理释放以记录失效顺序，该保护不进入生产 DLL。

当前普通 DLL 的 ABI19、未 connect3、原 v1 fixture68 通过。HTTP 首轮83通过/3截止失败，三个同输入同预算定向重验通过，原失败保留，波动原因 unknown。独立审查另核出 bad-date 与 metadata-after-position 的本轮 passed 被更早的超时遮挡：本轮仅证明 fail-closed；日期拒绝和观察总预算的目标证据来自 repair-001 原产物及未变逻辑，不能声称本轮86个目标故障全部触发。后继 NQP 将加强目标断言并取得正式 CTest 证据。

独立 delta-003 decision=approve，NQH-NEW-F1 closed，R1–R8按实际受影响与复用范围 complete；报告 SHA `3d2c3ad21db4ca1b2f92a6961c2864c2011c520d89128c100ad3a9eb1b72fa23`。这是隔离开发资格；生产、真实四查询、push、恢复、下单均未扩授。冻结入口 `build/native/qmt-http-bootstrap/repair-002/handoff-manifest.json` SHA `a813ecbcbe08a62cfa3f9b3d000ab2481a5c710bfc4f8a7c77649c096e8511fc`，freeze SHA `d73632b86168981bff1eadd3b0e6f5bdf47834953c8671c6976990f004942de6`。根任务另按原 Git blob 核322上游、32冻结自有、2629输入、9对象/31库以及959跟踪核心无新变化，回读收据为 `source-boundary-001/nqh-repair-002.json`。

旧 tool-snapshot/manifest.json 意外为空，其路径筛选使用正斜杠而源键为反斜杠；实际五份工具文件已保存，根任务直接与原红/绿 CNG 执行绑定摘要核对相符。原空索引及原收据保持，补充规范化清单另存；后继工具改动不回写旧运行身份。
