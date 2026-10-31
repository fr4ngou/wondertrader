# 2026-10-25 标准TraderQMT共享内存事件组合

类型：验证记录。结果：限定动态通过；独立full及revision002 delta完成，剩余已确认P1/P2为0。关联[SEV-R12](../specs/native-qmt-standard-events.md#sev-r12-共享内存事件至原生adapter组合验收accepted验证范围)，复用前轮R4a/R11对应源码的[限定结果](2026-10-24-qmt-standard-events.md)。整体迁移目标仍active。

## 输入身份

原生探针以固定上游08b230dd05facf6d650d949bfe51054115a2ecb1编译原TraderAdapter，未使用工作树中冻结的框架差异。fixed018仅为本轮新探针编译；其新DLL仅有编译资格。运行019明确加载前轮最终fixed015/TraderQMT.dll，SHA256为942210e0f93934d150c3a96319f891ac9e884cf03a268f70968735de69da4713；新NqpStandardShmEventProbe.exe为ef012d5af9cb4702a0b08471ba026f31169b9e29e37fb7b9cb2db237d149bcbd。

本轮自有修改仅新共享内存组合探针/测试及其CMake、build.py接线、规格和文档。StandardQmtTrader、Common、mapper、Agent、Host产品保持前轮字节。新Python测试revision002为73c36fc2308f46f754318124fc83ac05b8a194020f0798d122e8d5f1eb815c1c，CPP为f82c66b7a46aa394cdf2474875017c1bff530d59abf37173039cb380fe8d4a54。本轮26项已有框架差异逐字节核对未变；旧QMT项目未执行或修改。

运行在Windows隔离环境，真实RestrictedTradingAgent、Windows命名共享内存、build_trade_runtime、原Journal/R21及HMAC HTTP实际参与。SDK下单/撤单及账户读取均为原fixture线程上的合成替身；真实券商SDK调用为0。原生ITraderApi/ITraderSpi及Adapter.buy/cancel实际执行，不预填Host身份或事件证明。

## 步骤与观察

| 步骤 | 实际结果 | 结论 |
|---|---|---|
| fixed018隐藏编译五目标 | exit0；新SHM探针及旧四目标生成 | 编译通过，运行限定另记 |
| runtime018首次三方法 | exit1；三项均在输出根目录is_dir前置失败，未触达SHM/SDK | 原失败保留；后继运行器创建隔离cases根目录 |
| runtime019最终四方法 | 4/4，0skip，9.778秒，exit0 | 三项真实SHM组合及一项清理异常回归通过 |
| 初次只读Git状态控制器 | bare git不满足绝对程序路径要求，受控拒绝 | 后继绝对git.exe成功；没有Git写操作 |
| 原框架26项保护清单 | 当前SHA与开工快照全部相符 | 本轮无新增框架修改 |

| SHM场景 | 源原始回报数 | 原WT唯一订单/成交SPI | 原WT持仓/可用 | 未成交/活动委托 | 源insert/cancel替身 |
|---|---:|---|---|---|---|
| 正常委托→20股成交→部分撤单 | 3 | 2/1 | 120/100 | 0/0 | 1/1 |
| 跨seq重复订单、成交、撤单及旧订单快照 | 7 | 2/1 | 120/100 | 0/0 | 1/1 |
| 成交SPI内stop | 4 | 1/1 | 120/100 | 80/1 | 1/0 |

合成初始持仓为100/可用100，当日订单/成交为空。新委托由原Adapter.buy自动产生原localid、EntrustID和userTag，完整命令token随原SDK替身同步回调返回。原订单、成交、部分撤单原文由Host事务/R21建立关联，标准消费者读取的每项与原源回调逐字节/摘要核对；未用独立客户端替代标准消费者。成交后的原Adapter自动queryAccount实际出现，正常/重复模式共五查询，stop模式四查询。

三种模式均单独验证源ACK及持久前沿3/7/4、无gap及源retained0。它们与WT的SPI次数及持仓断言分别记录。stop模式回调借用存活、关闭延后到退栈、未隐式取消残留委托；所有模式pending_commands0、DLL实际删除、worker joined/drained，Host/Agent/HTTP/proxy和子进程均实际关闭，Job在resume前绑定、无强制终止、输出EOF齐全。

独立审查发现的测试采证P2在revision002修正：清理异常原对象曾使最终JSON序列化失败；同一落盘边界现转换有限内建类型和固定归属，原业务首异常保持。第四项隔离helper真实触发RuntimeError，核失败原件可读、敏感哨兵不落盘、原首异常实例不变。该修改没有改变产品异常语义。

## 证明范围

真实共享内存和原版Adapter的已知基线后完整字段增量、部分成交/取消、跨seq重复抑制及回调stop在本合成来源成立。前轮同DLL旧16场景、19事件模式、索引499断言和30分配失败按原精确输入复用；本轮没有重新执行或扩大这些历史结论。

独立full及revision002 delta完成，原采证P2已关闭，剩余已确认P1/P2为0；33项最终审查来源逐字节根核一致。报告为build/qmt-standard-shm-event-independent-review-001/FINAL-REVIEW.md，最终源码清单为同目录FINAL-SOURCE-SHA256.json。根封存位于build/guanheng-workspace/qmt-standard-shm-events-final-001。新probe的446项冻结编译输入及149项运行fixture原件均逐项核对，源码存在、静态审查、动态通过、生产运行和发布资格分别登记。

## 限制与后继

生产首次query/live交接及重连覆盖（R8）、缺字段真实补查（R5）、unknown原委托定向核查/取消、完整容量与父死亡矩阵尚未完成。真实SDK字段、订单状态更新、跨日券商ID范围及终端内安装资格须按真实来源独立验收。候选event_consumption_complete保持0，生产Factory未切换；无真实委托/撤单、终端重启、权限或部署变化。

后继unknown取消调查已依据21份当前源码原件核同，根因涉及多层共用停写和unknown/硬故障/close混用；需先冻结完整按操作准入、同目标未决cancel原ID及版本兼容契约，再在各事实owner实现。该调查不授予取消能力，也不增设第二份资金持仓账本。

文档后继独审DOC-DELTA-REVIEW.md核五份正文及八项冻结参照，13项SHA根核一致；testing.md的新版本独立追加，原33项审查原件保持。最终project.py check通过，仅授本地文档导航与技能清单完整性。共八次本轮受控执行均非强制结束、tree0、输出EOF及资源关闭确认；其中首次Git绝对路径前置及runtime018目录前置失败各按原观察保留。

原始结果位于E:/workspace/wondertrader/build/guanheng-workspace/qmt-standard-shm-events-runtime-019，首次失败位于同级runtime-018；五目标构建为qmt-standard-trader-fixed-018。源码清单、控制器、fixture原文、独立审查与最终根核按收尾记录定位。原始合成账户和完整请求/回报仅供隔离测试复验。
