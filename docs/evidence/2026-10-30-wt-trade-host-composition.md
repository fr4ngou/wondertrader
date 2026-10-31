# 交易Host与历史Host的独立WT组合接缝

类型：源码装配及局部回归证据。范围：[WRI](../specs/independent-wt-runtime.md)可选交易通信组合；完整安装及真实账户资格继续pending-verification。

## 问题与实现

原components.host只能配置一项来源Host。如果用交易Host替换现有HPR，原历史补齐接口将失去owner。独立运行装配增加可选components.trade_host（kind=qmt_trade），使用原交易产品的固定create_process(descriptor, SHA)，host继续承载只读/HPR。各Host沿自己已配对的控制通道及原Journal，不添加第二套金融事实。原四组件配置省略新项时继续原路径。

启动依赖顺序为host→trade_host→history→collection→execution，关闭顺序相反，沿原整套共享启动/停止截止。全部owner先构造验证后再启动，状态只读原安全DTO。新增交易选择不改变原HPR市场权限、委托/撤单协议或未知结果恢复。当前源码WT运行包版本升为0.1.0a2；已运行0.1.0a1冻结安装保留原件及原资格。

## 验证及剩余

原运行装配回归与两项新增并存/工厂验证共8项通过：HPR与交易Host同时保留、执行/采集等消费者先关闭、全组件状态及固定descriptor/SHA委派；原三/四组件失败/关闭及无Web依赖保持。control417实际0.156秒exit0，未强制终止，树0、两路EOF、reader join及句柄回收通过。

原件位于build/wt-trade-host-composition-001/verify.py、RESULT.json及build/guanheng-workspace/wt-data-live-read-control-417/build-wt-data-live-read-control-417/result.json。该证据只授源码装配资格；交易Host实际pair/verify/run、真实Windows SHM和3.6.8正文的SDK替身主链由THP单独验收，不能用工厂替身代替完整安装后的联合运行。

独立观衡消费者的trade_host“交易通信”状态映射由界面模块所有者继续适配；源端三owner完整正文、正式新候选安装、HPR与交易共存及唯一策略/账户整体主链仍待组合。本轮现场QMT、既有WT配置、真实委托/撤单及WT框架修改均为0。
