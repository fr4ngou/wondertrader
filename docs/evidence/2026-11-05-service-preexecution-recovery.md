# 2026-11-05 执行前置启动失败的原账接续

类型：验证记录。结果：pass（模块及正常安装）；线上采用not-run。要求：[WSC-R1](../specs/wt-service-control.md#wsc-r1-执行组件之前的启动失败)。

## 输入身份

自有`ServiceController`原实现每次恢复都读取紧邻Runtime代的execution业务观察。Runtime在analysis_host等前置依赖start失败时，固定串行顺序尚未调用execution.start；该代没有Native观察，原读取会失败。实际Native、原已准备transition和金融根继续属于最后实际执行代。

源码[service_control.py](../../apps/wt_runtime/guanheng_wt_runtime/service_control.py) SHA `cbf862f70f08a9e109bf7adeb32bd99913d6715ffff7012e5458ee08b94a788d`。回归[test_service_control.py](../../tests/integration/wt_runtime/test_service_control.py) SHA `8b3b7a8c0267643a8611c6fdbdb0c06799532f80866f0f418590c8def12acb20`。原Runtime固定顺序、组件工厂及ManagedLocalProcess的start/close保持原实现。

[固定源码闭包](../../apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance122.fresh.1.cash.2.startrecovery.1/README.md)继承原cash.2的45模块，仅覆盖service_control.py。原cash.2闭包保持原件；策略、QNA、Native及依赖保持原角色。新普通发行版本`0.1.0a12+integrated.2.market.35.3.service.9.resonance122.fresh.1.cash.2.startrecovery.1`。源码清单SHA `4789e94045972a74a2ded8932ba1941515646529aabc05c1a0985d2cc960a83f`，原闭包清单SHA `3e529ab281c3c3e3cdcb57e8b689157f640400209c75456e0a0c5c5a12ab697d`。

## 实现与步骤

Controller核同代failure/status及PID、固定组件全集和早于execution的原component_start错误，要求execution已closed、无PID/业务引用/待回收资源/错误/强杀。由该组合证明执行start未到达。随后校验原descriptor、Native及transition字节摘要，沿原件生成新Runtime身份；原transition继续记录最后实际Native前代，原账及库存保持。其它来源owner的关闭失败保留原结论和恢复责任。

首次bootstrap自带恢复材料时，原generation尚无Controller新建transition；沿原已绑定配置登记同一恢复引用。首次record_clean/库存尚未使用时保留原输入。execution本身启动失败、实际已启动或缺少资源证明继续原Native恢复/核查。

| 步骤 | 结果 |
|---|---|
| 主路径先运行真实Runtime串行start及逆序close、真实ServiceController.start；来源与Native进程采用隔离替身 | 前置analysis_host连续两次启动失败，第三次同一start成功；Native启动次数恰为原实际代及后继成功代两次；prepare_transition仅首次一次 |
| 比较各失败/后继代原descriptor、transition及隔离账本字节 | 全部保持；transition仍指向首次实际Native，未以失败代新建金融交接 |
| execution.start已调用但无ready、缺失execution pending字段 | 后继保持核查；未走原件复用、未启动新Native |
| 首次未用库存与首次bootstrap已准备transition | 正常后继成功，原库存/transition保持 |
| 全新普通CPython3.12.13环境，离线安装新Runtime wheel及原SDK0.15.0；uv pip check | 两包正常安装且依赖检查通过 |
| 安装后`-I -B`读取实际site-packages的Controller，运行原回归文件 | 14项通过；源码SHA与永久覆盖一致，无源码路径注入 |
| 新闭包build.py分别以新work003/wheels003和work004/wheels004构建 | 45成员逐字节核验；两次wheel字节一致，SHA `c610b8215edd4ec295c193148f1a9615359c9cea5e25529b05895fec6f6d763a` |
| `python -B scripts/project.py check` | 文档静态检查通过 |

QA根为`E:/workspace/wondertrader-qa/wt-service-preexecution-20261105-001`；正式候选取`wheels004/`。`INSTALLATION-VERIFICATION.json`保存安装后源码/测试SHA及14项结果，`wheels004/REBUILD-RESULT.json`保存45模块和wheel身份，`DELIVERY.json`记录重复构建及冻结摘要。`environment001`为独立验证环境。

## 证明范围与采用边界

本次实际运行原Controller、Runtime、未启动执行owner的原close和正常安装源码。来源/Native是明确替身，账本为隔离数据；未操作线上、真实金融根或QMT。Runtime未知执行责任保持原核查，没有伪造clean/关闭成功或重建金融账本。

原transition的successor_python_code_identity绑定整个执行Python闭包。日常同闭包恢复可沿用原已准备材料；安装新Runtime至实际Native执行环境时，由原prepare_transition针对最后实际Native代准备绑定新闭包的一次原账交接，然后交原Native接收。若只用新环境运行Controller而service.pythonw保持原固定执行环境，原已准备transition继续绑定其原执行代码。该身份校验保持，Root统一完成采用及现场原账验证。
