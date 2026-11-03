# WT日常启停入口普通安装验收

日期：2026-11-04。范围：隔离WT Runtime服务控制；现场WT、QMT、账户和交易保持原状。

## 根因与实现

日常操作原先直接调用底层Runtime，操作员需要管理控制UUID、配置摘要和代际恢复材料。新增`guanheng-wt-service start|status|stop`统一拥有代际配置、严格五字段`CURRENT.json`和正常停止请求。正常重启保持逻辑`instance_id`，生成新`control_id`；执行组件沿既有`prepare_transition`准备后继配置。故障代保持当前，不自动重启。

普通安装首次主链发现Windows上的`os.kill(pid, 0)`会把已ready的Runtime误判为丢失。当前实现使用Windows `OpenProcess`及`GetExitCodeProcess`核进程存活，重复启动回到幂等路径。

## 制品身份

- 源码CAS：`E:\workspace\wondertrader-qa\daily-mainline-20261103-001\wt-service-control\source-cas\99ff50876622996ac6cbf0325c45b275a4174da40e65792570307e2652e8f580`
- 源码清单SHA256：`696b8508c06b2340440b4924912d09bcc4a3aef5173370dfa514ba9838c17459`
- 服务wheel：`guanheng_wt_runtime-0.1.0a12+integrated.2.market.35.3.service.1-py3-none-any.whl`
- 服务wheel SHA256：`56dcf27a92eca684ab7089a6a5c605a021995fbe2ad2be25546ea43fc04b9bce`
- 精确SDK依赖：`guanheng-market-client==0.15.0`，wheel SHA256 `2b2e3d17b25c624ac6369385ffebf5e414583f5ea4a6080c5aca9da19af98b51`
- 完整交付收据：`E:\workspace\wondertrader-qa\daily-mainline-20261103-001\wt-service-control\candidate-service-005\DELIVERY.json`

服务wheel以已交付35.2 wheel SHA256 `1ed341a235a9713f8ef014cb25535f8009107a40391e3befa29466fbcda47032`为唯一运行基线，只增加固定服务源码；没有从共享树带入其它运行源码或0.16 SDK。

## 验证

- 服务单元/协议回归7项通过：幂等启动、正常停止、同实例后继、显式故障后继、严格CURRENT、越界控制根拒绝、实际执行配置恢复代际及Windows PID创建身份探测。
- 全新Python 3.12普通环境离线安装上述两个wheel，通过`start → start → status → stop → stop → start → status → stop`。
- 两代`control_id`分别为`36ef372e-3e73-4eba-be22-0cea6e267206`和`8f46aa49-73dd-4c41-9f03-c1d00e33ee28`；`instance_id`保持`7c0359e5-5239-4bb3-a532-1d6c979a6d50`。
- F1沿`business_observation`、原`ready.json`及实际`execution.json`三重身份取得前代原字节，后继移除已完成的`initial_inventory`准备描述；F3将用户显式故障后继交给既有`prepare_transition`和Native判断；F4以Runtime ready PID及进程创建时间识别本代owner，陈旧ready和PID复用报告`process_lost`。
- F2的`market_origin_configuration`在完成同业务核验后保留已绑定原模型预算身份，同时实际执行配置保留本代`run_ms`。70000到0、0到70000、业务字段变化拒绝三项回归通过；真实正式配置回归见`continuous-runtime/INVENTORY-ORIGIN-REGRESSION.json`。
- 每代Runtime和采集协议替身均形成正常关闭收据；公开CURRENT严格保持五字段。
- 隔离验收产生QMT调用0、账户调用0、下单0、撤单0；现场实例未改变。

## 剩余生产验收

本证据确认服务控制、普通安装和同逻辑实例代际主链。Root继续使用当前模拟账户执行真实Native SDK同账户、资金、持仓、策略记忆和未知委托连续性验收，并统一完成现场切换。观衡消费者跟随CURRENT由对应模块单独验收。
