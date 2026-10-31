# ADR-0014 显式历史缓存补齐权限

状态：accepted。范围：QMT来源缓存准备、认证命令与原策略线程。

## 决策

缓存补齐具有券商来源副作用，由独立显式v6能力授予。普通只读v1-v5及交易profile保持原准入；新专用入口同时冻结证券allowlist、周期、窗口、任务数、排队额度及原绝对截止。调用目标由策略全局固定注入`download_history_data`，QMT内部只消费内存材料。

通信复用原认证SHM/base-control、Host bound Journal、RestrictedReadAgent队列和reconnecting owner。终端跨代保留有限原请求身份，Host持久保存派发与终态。副作用进入后异常、断开和晚回均保留结果未知，不重新派发。原生调用返回前保留原owner；缓存覆盖由后续历史回读证明。

## 后果与验证

WT原数据loader/Helper/Reader、金融事实与订单语义保持。成功只授`call_returned`，覆盖继续unknown；端到端替身、重复、重启、断开、原生不可中断和旧协议分别核验。最终要求见[HPR](../../specs/qmt-history-preparation.md)，接口及使用方式见[模块说明](../../modules/qmt-history-preparation.md)。真实终端资格由操作owner独立登记。


## 2026-10-29来源市场范围后继

用户确认正式按需补齐覆盖来源支持的证券。新limits.v2移除逐只symbols清单，继续原v6能力、固定下载入口、周期/窗口/资源管理和未知结果核查。新配对中descriptor参与完整原签名身份；既有limits.v1配对及其请求/结果保持原清单语义。外部来源服务正式配置省略preparation.symbols，策略证券清单继续描述策略业务用途。该后继修订当前设计，以上原决定保留当时记录；实现与实机状态沿HPR/RS15证据。
