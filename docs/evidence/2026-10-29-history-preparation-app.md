# App托管历史补齐产品

类型：开发隔离验收。状态：done（固定Appa13/e Host工程切片，双独立源码及原件delta complete）。依据：[HPRA1–4](../specs/qmt-history-preparation-app.md)、[模块C](../migration/module-c-delivery.md)。真实QMT/缓存业务覆盖/交易/发布和完整模块资格分别核实。

## 根因与实现

HPR独立安装已提供唯一进程owner，App公共settings/lifespan/状态和中文页面尚缺接线。C新增成对配置及摘要，直接调用原HistoryPreparationProcessConfig/HistoryPreparationProcess，默认disabled且不扫描/导入Host。Host继续独立安装，父App沿既有有界池启动并保留原实例身份。

GET `/v1/ui/qmt-history-preparation`只投影当前owner有限状态，拒绝额外query/body及写方法；不读pair凭据、不查询来源、不触发补齐。系统状态与总览复用同一查询及ProcessCard，重读/失败隐藏旧观察，来源连接保持待核实。策略页继续名称、简介、版本，回测另页签。

两份独立full均发现同一P2：合法HPR60秒+账户Host60秒、前段快速关闭时，累计未用窗口会把约122.5秒传给Host.close；原接口上限120秒，参数校验先抛错而没有发布停止。C在公共关闭调度按每个owner声明窗口与总D扣后续预留的剩余取小值。原owner实现保持，顺序为消费者→执行→查询→采集→HPR→账户Host；某项失败继续关闭其余组件，全部结果归约shutdown_complete。

## 冻结候选与实际主链

独占材料根 `build/history-preparation-app-001`。Appa13 wheel SHA256 `a69744a2557c736aea9218a4cebb2237c8ad5a85f24c9096822f832e0696e180`；生产SPA18文件ZIP SHA256 `e41e057caa4dbfa62780eb056b1b71318e5e365fbe35c5a0823fe0f7b684d48c`。安装身份见installation-final-identity.json，65份冻结输入/63个App成员、22发行1968条有摘要RECORD全部核验；170份前端输入重新构建后18个文件与实际已验SPA逐字节相同。

最终HPR使用A的e候选，独立ZIP重新解包至hpr-install-e，INSTALLATION SHA256 `5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3`，592文件/15wheel及6个App薄适配文件身份均通过。A原DELIVERY仍保留当时pending快照；后继独立delta已在build/hpr-final-review-143的SPEC-DELTA/STANDARDS-DELTA关闭原P2，真实来源资格沿[A证据](2026-10-29-hpr-product-installed.md)单独保持。

`final_validate.py native-e`从普通App安装的-I解释器运行：实际C App lifespan创建原HPR owner，托管e的独立隐藏Job Host，实际TCP提供生产SPA。完整3.6.8组合正文使用合成SDK，来源实际晚到65秒后执行1d/1m显式补齐替身、原分钟七字段回读、快照/增量、来源断开/第二代重新认证、原ID原结果保留、旧binding拒绝；64条任务成功，第65条明确容量拒绝。最终main-e002/RESULT.json与APP-MAIN-E-FINAL.json通过，来源/接收器/Host Job/进程句柄/双pipe EOF/监督与读线程/句柄、App读池及HTTP线程/监听全部收束，forced=false、pending=false。

QA将A原完整协议夹具的生命周期映射到实际App。配对create/verify仍由真实已安装Host解释器调用原产品API，合成授权只存在私有QA目录。初轮夹具用C解释器创建pair，Host身份正确拒绝，main-001失败原件保留；改为独立Host创建/核验后，d、e/a12、e/a13均跑完整主链。原产品准入没有绕过。QA入口不作为生产安装依赖。

## 页面、回归与命令

普通生产SPA实际Edge在1440×1000及390×844验证：系统状态监听/PID/未知来源、503隐藏旧值、手动恢复，总览在账户能力关闭时独立读取补齐状态、刷新、策略页零参数数字输入。全部产品请求GET，唯一503控制台错误来自显式故障注入，pageerror和额外控制台错误0。截图在本任务visualizations的history-preparation-app-001目录；Browser plugin未提供，沿既有Playwright/Edge回退验证。

- `final_validate.py backend`：143通过，覆盖原HPR/Host各60秒原触发、五进程单窗/同总D、默认零Job、配置错误隔离、工厂/启动/关闭失败、只读/去敏及原130项关联回归。一次原Source测试仍断言累计窗口相等，按新单窗及同D上界合同更新后通过，前次日志保留。
- `validate.py frontend`：42通过，涵盖总览、Operations、HPR错误/恢复/待核实、策略目录/旧链接及独立壳。
- TypeScript、Vite、分块检查通过，初始入口268.2KiB，5个工作区动态分块，图表保持分钟懒加载。
- `identity_final_runner.py`：完整普通安装身份、全新进程default/invalid的零Host导入/零Job及读池关闭通过。
- `frontend_identity.py`：当前170输入构建与已验18文件SPA相同。
- `validate.py docs`：本地文档导航检查通过；后继文档继续在交付前核验。

上列入口均经原scripts/native.py.run的隐藏Job/有限截止/树及EOF/join管理。单纯元数据冻结/摘要没有启动服务。核心结果、实际耗时、源码及命令摘要绑定最终DELIVERY；全局旧QMT、137/140运行实例及真实账户/下载/下撤单保持未操作。

## 审查与限制

full原33输入清单SHA `dead1eff7503bf6183329b443f438cd49f427aaad567accb3f2a90cc9fd47517`，原源码镜像保留在review-before。修复后44源码清单SHA `460af61181a303d14258b7c026a0d1c3fec7fa2259680c199c1396c55decb287`，17原件清单SHA `8ee58be5741d4996be72b8d0b87adbbf2422b7d0071ca47f955b2a7684521917`。SPEC/STANDARDS的DELTA及EVIDENCE均complete，原P2闭合，最终输入无漂移；两轴独立复算安装/SPA成员及RECORD，并核原主链/页面/回归原件。报告与准确候选身份登记在build/history-preparation-app-001/DELIVERY.json。

A的e审查33输入中32份当前保持，docs/README.md由C新增本手册导航链接；原产品源码保持该审查身份，导航差异单独登记在a-parent-review-identity.json。60+60秒原触发回归使用原未启动Job的owner，实际60秒慢退出资格另验。实际安装create_app/lifespan/TCP已验，额外configured Console CLI本轮未单独执行。

本轮实际SDK及补齐调用为隔离合成；A的真实只读资格不迁移为本轮真实下载或全业务资格。HPR单文件symlink动态验证受Win1314限制，A保留unknown。跨机、统一安装升级回退、真实M1、所有保留算法、独立观察provider/09:00继续；configured Runtime访问冲突仍按[原故障](2026-10-29-configured-app-entry.md)待B/集成者定位，C保持原生运行体只读。整个模块C goal继续active，未合入、发布或真实写。
