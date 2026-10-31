# 2026-10-21 公开 Reader 所有权与原生组合验证

类型：限定运行证据及源码研究。状态：历史隔离正常路径通过；实时并发、失败清理、完整策略链与生产资格待验。承接[Servo行为实验](2026-10-21-native-servo-behavior.md)。

## 输入与步骤

固定上游 `08b230dd05facf6d650d949bfe51054115a2ecb1`，使用前序已逐Git blob匹配的原样快照。Storage DLL SHA256 `359782d8ba23293995727f3baa4e74aa0c7b88a7adb9a5cf9ec3114934b7d4e5`，Helper SHA256 `da75291338ab8f9618ee3befde4c81f98dbdb6047e11d3e2cbc94ca3119bb055`。原DataFactory来自同次原样WTSTools静态构建。

只在 `build/native/capability-audit` 编写、编译隔离C++探针，未修改正式源码、发行配置或运行服务。公开create/delete工厂动态加载原Storage；sink和基础资料存活至Reader销毁之后。借用切片在清理前复制并release，动态库保持加载直到进程退出，热卸载未验。

探针使用简化基础资料、固定日历、合成历史副本，无Parser、无实时DMB或外部来源。Reader内部检查线程按原实现运行。本次独立研究者只读复核两个CPP及结果，未通过重写底层Reader取得资格。

## Reader 创建与销毁

探针：`reader_owner_probe.cpp`、`build_reader_owner_probe.py`、`run_reader_owner_probe.py`；结果由 `reader-owner-probe/latest-run.txt` 指向独占运行目录。

| 场景 | declared /实际块记录 | 观察 |
|---|---:|---|
| 12根历史，请求100 | 12/12 | 正常尾部读取 |
| 合法证券空历史 | 100/0 | 底层空count异常独立于Servo宿主，不能通过换宿主消除 |
| count截至首条之前 | 0/0 | 该固定输入返回空 |
| range全部早于首条 | 0/0 | 该固定输入返回空 |
| range全部晚于末条 | 0/0 | 该固定输入返回空 |
| range 09:33–09:35 | 3/3 | 两端均包含 |

6个子进程正常退出0；create/init后进程线程4→5，deleteReader后5→4，删除耗时4935–4952毫秒。该结果证明此历史-only配置的公开销毁链实际等待了检查线程，宿主可以通过原工厂管理Reader，不必为此修改Servo C ABI。

非空数组边界有迭代器递减的静态风险；上述返回空与未崩溃结果不消除未定义行为，也不扩展为所有日期/计数安全保证。原始探针字段检查只覆盖date/time及数量，不是完整OHLC验证。空集合的字段谓词为真不构成有效数据证据。

## 同实例刷新与原生 DataFactory

探针：`reader_factory_probe.cpp`、`build_reader_factory_probe.py`、`run_reader_factory_probe.py`；结果由 `reader-factory-probe/latest-run.txt` 定位。

同一公开IRdmDtReader读取12根m1，调用原 `WTSDataFactory::extractKlineData` 得到4根m3。释放借用切片后，原Helper向临时DSB写入新值并替换隔离文件；未清缓存时仍读旧值，clearCache后再读取、重新调用原Factory。

| 阶段 | m1首收盘 | m3首收盘 | 根数 |
|---|---:|---:|---|
| 初次 | 110.25 | 112.25 | m1=12，m3=4 |
| 发布后未刷新 | 110.25 | 按旧输入重新生成 | 输入仍旧 |
| clearCache后 | 210.25 | 212.25 | m1=12，m3=4 |

退出0，deleteReader耗时4940毫秒，线程4→5→4。每次从当前输入调用原Factory，避免继续使用Servo自身独立派生缓存。断言覆盖条数及首收盘，尚未覆盖所有OHLC/量额聚合、午休、因子修订或全市场容量。前序428条真实m1逐字段对照资格单独保留。

## 原生闭合分钟研究

独立报告 `build/native/capability-audit/closed-minute-path.md` 沿固定源码核对Ticker→IDataReader::onMinuteEnd→DtMgr统一通知→Engine/上下文→on_schedule与线程池wait。已确认多证券、主K线、无tick分钟、断流回补与Writer/DMB拓扑的具体边界；本轮未对这条实时链新增运行资格。

默认Reader从DMB读未消费bar；策略只接收Parser tick并不足以生成这些文件。原Writer应先写入，再按原广播拓扑触发策略侧。稀疏HTTP快照不能直接获得供应商真实分钟OHLC资格，IDataWriter也没有通用writeBar入口；现成分钟源需要核公开Reader适配。补发多条bar不等于逐条策略计算，缺源时原时钟不制造行情。

长期结论已同步[数据能力](../modules/wondertrader-data-capabilities.md)及[框架并发文档](../architecture/wondertrader-framework.md)。方案选择见[原生行情接入收敛](../migration/native-market-integration-plan.md)；无新增框架修改审批或生产操作。
