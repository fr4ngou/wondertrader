# QMT 实时事件的金融映射与委托关联

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-24。结果：accepted 切片限定验证通过；完整 Standard 实时消费者尚未完成。关联要求：[SEV-R2b](../specs/native-qmt-standard-events.md#sev-r2b-独立事件mapper与p8-beginaccepted切片)、SEV-R3、STQ-P8。

## 最终行为与输入

事件通过真实有界事件页进入独立 event provenance，保留原 B、session、sequence、页中下标、原 page/profile、请求边界和本地派生摘要。事件不构造账户查询封套，不填写查询 UUID、查询结果摘要或 SDK 查询 UTC。查询结果的 event_provenance 为空；原查询接口及视图保持。

AccountMapping 新增显式 map_trade_event_rows，完整单条 order/deal 与账户查询共用唯一金融循环。Bootstrap 新增 begin_qmt_trade_event_identity；owner 构造 WT 候选及读取 BaseData，worker 只接纯值 Plan 并沿真实原来源解析身份，owner finish 后交出数组。错 owner/ticket 保留句柄，失败不交出半批；Candidate、Plan、Resolved、Result 共享独立有限 provenance。所有阶段沿原绝对截止及原预算，不给后继阶段重授额度。

最终八个产品/测试输入摘要及原字节见 SOURCES（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-final-001/SOURCES.json`）。实际运行的全量输入由 native-002 快照（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-native-002/identity-build-inputs.json`）绑定。环境为 Windows、MSVC、项目原生 CMake；测试为隔离合成数据与认证回环服务，真实券商 SDK 调用 0。

## 执行与根因修正

| 实际执行 | 结果与范围 |
| --- | --- |
| native-001 五组 CTest | 修正前 42 事件身份场景、31 事件映射及既有查询回归通过；不据此授最终版本准入资格 |
| 合法旧 policy 原样复现 | 正式 builder 生成一致的 policy1.0 profile、B、receipt 和命令关联；旧二进制在 order/deal 两类均误接受为 owned，真实经过认证 HTTP 与 Common |
| native-002 五组 CTest | 全部通过，60.96 秒；事件 9 方法、46 场景；旧金融 128、规范金融 115、事件金融 31 个样本，以及 4 个真实 append 所有权场景 |
| native-002 进程收尾 | exit0、非强杀；创建期 Job 成员关系、整树归零、两管道 EOF、reader join 和资源关闭全部核实；运行输入前后无漂移 |

版本缺口根因是 Common 读取器为已有调用兼容账户 policy1.0/2.0，事件金融入口却要求 2.0。修正位于自有 Bootstrap 事件入口，在 Common 成功校验后精确要求账户 policy2.0；Common 旧兼容规则保持。合法 policy1.0 反例先要求真实 Common 读取成功，再确认事件 begin 拒绝，避免以错摘要或错 B 遮蔽版本条件。

预算验收分别对 order/deal 实际完成等值、总量少 1、lookup 少 1、身份视图少 1 的 begin→resolve→finish 链。固定 128/64 为契约逻辑预留，测试独立计算页、profile、来源、行、金融视图、规范标识、分组、token、lookup 与身份视图；不声称该预算等于进程物理内存。源变化、错来源/边界/代际、非法/缺字段、空页、合法 gap prefix、截止、错误 owner/ticket、输入销毁及 worker 退出后输出寿命均按实际场景断言。

原始运行日志（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-final-001/LastTest.log`）、五组汇总（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-native-002/ctest-identity.log`）与 policy 修前复现（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-policy-repro-001/RESULT.json`）分别保留，历史运行不改写为最终版本。

## 独立审查

首次 full（外部历史/待归仓路径：`../../build/qmt-event-identity-review-001/NOTES.md`）保留 P1=0/P2=1，读取修前源码及 42 场景，未执行。其后 DELTA-001（外部历史/待归仓路径：`../../build/qmt-event-identity-review-001/DELTA-001.md`）核最终修正、合法 policy 反例、精确预算和新增 mapper 样本，P2 静态关闭，新增 P1/P2=0，执行 0、动态 unknown。根对 47 项最终来源与审查原字节（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-final-001/REVIEW-ROOT-CHECK.json`）逐项核同，动态结果由作者实际运行单独证明。

## 未覆盖与后继

本次尚未装配 Standard 的持续事件调度、volatile 交付索引、SPI 回调、缺字段真实补查、首 cursor、query/live 交接及重连恢复；event_consumption_complete 仍为 0。合法 gap 的纯映射通过也不授写准入。完整共享内存三回调金融链、固定原版 WT 上的受影响候选、独立安装和真实终端分别继续验收。

本次没有新增 WT 框架或旧 QMT 工程修改，没有切生产 Factory、重启终端、真实下单/撤单或生产发布。全部保留策略、全量历史覆盖、观衡业务入口与整体独立发行仍为完整目标。

## 后继：固定原版 WT 受影响组合

fixed-009（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-009/result.json`）从固定08b230原Git blob重新构建当前自有候选，未混入工作树框架差异。DLL SHA256为2780319f70e2d412a082d6e808edcc7704da7b8be11d0f268eed29cf4e6eb053，Probe为8c02dfc2f11568706b58e5d9b83451fcfc6f4680938d7c46f7e0bc75e82ca2d0。

runtime-009（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-009/result.json`）同版实际通过15方法16场景：12方法5.990秒，3个实际共享内存方法18.852秒。测试fixture在运行前复制原字节到独占目录，运行使用该快照并核前后不变；不受并行新测试编辑影响。16场景逐项回核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-identity-final-001/STANDARD-CASES.json`）确认passed/closed/deleted/drained/joined均真、真实SDK0、event_consumption_complete=0，进程非强杀并实际回收。两类fixture退出字段分别按原schema核child_exit/exit_code。该组合证明旧标准候选受影响回归，仍未将新事件begin接入Standard/SPI。

## 后继：原线程三回报共享内存整链

SHM实际五组运行（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-shm-native-001/ctest-identity.log`）全部通过，62.44秒。原生客户端测试实际8方法，包含新增显式event_identity场景；其完整结果与根核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-shm-final-001/SUMMARY.json`）保留原线程order→deal→order三回调，真实builtin-shm/Host持久页及C++取页，owner begin→独立worker resolve/drain/join→owner finish，三次金融映射与原WT委托归属全部断言通过。

原回调事实（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-shm-final-001/fixture-facts.json`）确认SDK替身insert/cancel各1次、四类账户查询各1次，真实券商SDK0；委托100、成交20、价10.01、成交额200.2，取消80的源事实与WT取消后余量0分别核对。原事件页/来源、三派生摘要、唯一mapper金融key/hash及六查询元数据空值均核实。三个短worker为测试线程装配，尚未装配Standard唯一worker或SPI，亦不授Standard整页总预留资格。关闭原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-shm-final-001/cleanup-facts.json`）确认原D内源worker/IO、Host IO、server及Job实际回收，运行输入无漂移；独立测试delta另绑定最终输入。

SHM测试独立delta（外部历史/待归仓路径：`../../build/qmt-event-shm-review-001/NOTES.md`）已封存，限定装配静态complete，P1/P2=0、执行0/动态unknown；根逐项核34项输入及原字节（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-event-shm-final-001/REVIEW-ROOT-CHECK.json`）相符。Common/旧CMake采用该实际运行保存的原源码，后继R2c变化单独记录，未将其混入这份资格。
