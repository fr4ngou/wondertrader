# 独立QMT SHM Host

内部私有终端外Host，Python3.10+。Host/Agent及HTTP/DTO依赖按实际制品和冻结清单配对。签名bound-read接口保存原请求去重、三绑定与原终态字节；嵌入SQLite只拥有通信事实。Host/Agent共用封闭read_capabilities准入。full_tick-only保留v1完整profile；历史显式选择v2 profile、history policy及各操作预算，账户读取显式使用v3完整profile；旧客户端对新profile继续严格拒绝。

历史小窗口验证、真实源单位/覆盖和生产加载分别登记；多能力现场并用需要同版client/profile组合另验。Journal终态不释放原逻辑预留，满额停止准入；本版本不自动删除、归档或透明轮换通信记录。

上述保留规则适用于默认未配置`read_retention`的连接。显式后继通过票据内容身份及消费者持久确认，回收确定完成且票据失效的只读/HPR责任；未知、执行中、金融交易与bulk保留原责任。新客户端只将明确受理前拒绝保存为独立失败，原生结果与网络未知分别表达。接口及边界见[RR规格](../../../docs/specs/qmt-read-retirement.md)，该能力需要同版消费者显式接线。

显式v3账户与v4混合通道沿[AAR](../../../docs/specs/qmt-account-read-retirement.md)复用同一回收协议：Native在进程内完整验证并持有本轮结果后确认，无账户结果文件要求。v4仍使用原金融Journal；金融命令、事件、未知及当前订单查询proof保留，新的查询按原规则更新引用后，旧的已消费读取才可回收。旧无票据责任计入`legacy_records`，当前金融引用计入`held_financial_proof`；两者都占原容量。

包内`_provenance.py`保存固定来源摘要。原版权头保留，用户授权内部迁入，不推断公开再分发许可。实际安装及完整部署命令见上级连接包README及QSW规格；生成配对与校验不授真实终端/交易资格。

交易开发切片：trading_journal.HostTradingJournal按[QST-R10](../../../docs/specs/qmt-shm-trading.md#qst-r10-共享通信journal的写命令开发接口)扩展同一通信SQLite及独占owner，保存原命令bytes、派发、SDK回执和unknown。它不保存持仓/资金账本，订单执行和消费仍由WT负责；无Docker或新增数据库服务。命令终态占用显式交易额度，重启不重发未明调用；旧只读owner拒绝含交易表的存储。当前runtime/profile尚未装配该类，模块存在不授写能力。

共用Agent包已提供control2语法和read-profile.v4的开发接口，见[交易协议证据](../../../docs/evidence/2026-10-24-qmt-trade-wire.md)。完整交易配置与控制联合额度已有纯验证，公开build_runtime仍沿旧只读配置；Journal派发与事件持久ACK待接通。低层可解析新描述与正式部署已装配分别核实，实际order_ready=false保持。

后继配置接口：`trade_bootstrap.validate_trade_launch(config, credentials=...)`和`trade_agent_settings(config,policies,secret)`沿[QST-R15](../../../docs/specs/qmt-shm-trading.md#qst-r15-完整交易配置准入)实现纯部署准入；完整交易配置及联合额度已有验证，Journal派发/事件ACK与运行工厂继续接通。共用旧凭证快照、policy和预算owner，真实存储与配置校验沿同一交易身份函数。新validator只读取终端外policy文件，不创建Journal/SHM/SDK；旧build_runtime仍拒新字段。验证见[配置证据](../../../docs/evidence/2026-10-24-qmt-trade-configuration.md)。
