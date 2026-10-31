# QMT完整交易配置准入验证

日期：2026-10-24。类型：实现与验证证据。范围：[QST-R15](../specs/qmt-shm-trading.md#qst-r15-完整交易配置准入)的显式私有配置与联合额度。运行派发、源策略回调和WT交易消费继续开发；本记录不授真实交易资格。

## 实现与边界

Agent新增validate_trade_configuration，返回完整v4/control2的公开配置及私有绑定快照。旧读配置与新配置共用原预算和运输布局实现，旧入口继续拒绝v4。读写账户必须相同；私有绑定及部署写请求不进入公开value，绑定以规范bytes保存并返回副本。writes_enabled只表示部署请求，真实权限、源会话、回报连续性和WT消费由后续运行owner核验。

Host新增validate_trade_launch和trade_agent_settings，复用原配置/凭证快照、policy加载、逐项roundtrip和只读Journal额度。它使用实际v4，不伪造旧profile。旧build_runtime在policy及owner创建前拒绝新字段。新准入只读取终端外policy文件，不创建Journal/运输/SDK。

Host与实际HostTradingJournal共用validate_trade_journal_configuration计算原交易存储身份及逻辑上下界，Host另核至少能预留一条最大命令、最大结果和metadata。存储仍为原通信SQLite；没有新增金融账本或数据库服务。原Journal SHA c40a6ffea83386c64beaadffaa2cda8713da6290c241ad1888b4e6705917629c，提取后b4f5ac644c88894c42d2ce63724aeb5b075c78a1e271df47c2240a85bc75a741。根用原冻结副本反向替换新增纯函数及构造段，确认其余文件字节完全一致；事务、派发、时钟和恢复正文未改。

## 控制窗口的实际约束

完整命令按base64完整三字节组计量，结果和事件页计入完整RPC开销；TTL、Session周期和映射布局仍沿原owner。联合配置保留七份最大reservation，经固定角色算法至少给Host四槽、Agent三槽。

实际双ControlPeer测试：seq1读取和seq2交易未完成，seq3事件页已交付并模拟领域提交，RPC ACK实际发送后，seq3虽然retired仍受连续floor阻挡。三Host槽无法再发业务事件ACK；四槽允许seq4确认，之后seq5继续背压。它证明一次页→业务ACK进展，未证明真实事件持久化，也不承诺悬挂前缀下无限轮询。原ControlPeer算法保持。

## 实际验证

| 范围 | 实际结果 | 控制收据后缀 |
|---|---|---|
| 开发Python3.12配置及Host测试 | 20通过，0.175s | qmt-trade-config-unit-001 |
| 国信Python3.6.8纯Agent配置 | 11通过，0.030s | qmt-trade-config-sdk-unit-001 |
| 既有控制/读取/bootstrap/pair/history及两类Journal | 148通过，6.76s | qmt-trade-config-regression-001 |
| 88模块完整内存闭包准备 | 通过，正文1,501,315 bytes | qmt-trade-config-memory-prepare-001 |
| 目标3.6.8禁文件/外部导入探针 | 通过，实际尝试0、实际SDK0 | qmt-trade-config-memory-target-001 |

控制收据位于build/guanheng-workspace/account-runtime-install-001/build-加表中后缀。全部正常退出0，非强杀，创建前Job归属、无控制台、树归零、双EOF、reader join和资源关闭均确认。

20项含11项共用Agent测试和9项现代Host测试。覆盖完整字段、旧配置原值、私有无别名、账户/摘要关系、base64尾组、结果/事件页、TTL/固定额度、运输布局及前述三槽/四槽对照。Host使用真实临时policy并验证I/O前配置/凭证快照、旧工厂拒绝、policy/roundtrip、存储额度及临时实际Journal身份。148项包含原99项旧链、37项交易Journal和12项只读Journal，适用于当前提取后的源码。

qmt-trading-memory-probe-005保存完整目标探针与runtime-identity。禁文件验证区实际加载新配置模块并完成完整合成v4准入，确认公开值不含私有三项、writes_enabled=false、四Host槽及旧读validator拒绝新配置。沿前轮探针同时复核kernel下单/撤单两个SDK替身及事件/时钟/control2；实际SDK0。准备和结果输出发生在终端外验证工具中，探针没有运行真实QMT策略或共享内存交易通道。memory_runtime.py和pair.py保持原摘要。

## 独立审查与归档

qmt-trade-config-review-001/REVIEW.md为新配置与共享提取影响的独立full静态审查：complete、确认P1/P2为0，35来源根核无漂移。报告SHA 76d9b70d746ac1d27221b157fe0f3a42830876718d83c52644adf906ca7ef968。Host另一路qmt-trade-host-config-review-001静态审查34来源根核无漂移，无确认问题；其作者曾参与原R10主体，报告明确保留作者关联边界，未计为原R10独立full。两路均零执行，实际测试证据由上表提供。

build/guanheng-workspace/qmt-trade-config-evidence-001保存最终来源、两路审查、控制收据、原提取比对及探针摘要。文档导航检查按同次最终输入另附控制结果。前轮[控制协议](2026-10-24-qmt-trade-wire.md)及[命令Journal](2026-10-24-qmt-trading-communication.md)按各自身份保留。

## 继续接线

现有策略的SDK/回调注册、Host写命令派发与事件持久确认、标准C++ TraderQMT/SPI及真实业务整链仍未完成。已查清init须先发布回调owner再set_account，回报需并发/账户单次取值过滤，停止需处理在途回调和结果交接；这些接缝继续实现，不能由配置成功替代。旧QMT工程保持静态只读，WT框架本轮无新增修改，未切换终端/运行策略或生产。整体目标active。
