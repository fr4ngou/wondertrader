# 2026-10-23 原生独立执行薄宿主

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：源码设计核实与测试级可行性证据。状态：公开C++接缝已验证；产品接线及完整生命周期待验。

## 复用结论

固定上游`08b230dd05facf6d650d949bfe51054115a2ecb1`的`WtExecRunner`提供公开虚接口`handle_push_quote/get_real_time`。自有派生宿主可以维护owner时间，再调用原行情入口；原`setStub(this)`继续虚派发。原`config/run/setPosition/commitPositions → LocalExecuter → MinImpact → TraderAdapter`全部复用，框架源码零修改。原C ABI使用静态Runner，没有配置注入派生类的入口；本结论仅覆盖公开C++装配。

单个执行单元内队列不能覆盖此前的原Trader状态更新；poolsize=0/1分别控制局部直调/线程池，不能外推为全局串行。现有ExecMon窄宿主给出了汇聚目标、行情、SPI的候选，当前没有据此证明必须分进程。配置与调用者仍须保证实际输入线程、值所有权及关闭语义。

## 精确时钟实验

`WtSimpDataMgr::handle_push_quote`局部变量遮蔽raw时间成员。真实消费链为`LocalExecuter::get_real_time → MinImpact → WtOrdMon`订单超时；下单间隔与交易时段走其他时间路径，影响范围分别核实。

本机实际编译运行两组隔离合成用例：同日两条tick相差2000ms，expire=1，原MinImpact持有可撤未完成订单。baseline原Runner时钟不推进，撤单0次；公开派生owner时钟推进2000ms，原算法撤单1次。两组各产生一次内存合成委托，API线程违例为0。所有委托/撤单均作用于假ITraderApi，没有终端、账户或网络。

原件见POC报告（外部历史/待归仓路径：`../../build/native-execmon-owner-001/REPORT.md`）。两Job自然exit0、未强杀、创建时成员身份及进程/管道回收通过；实际可见控制台为false。外线程读clock拒绝、倒退tick拒绝、关闭准入后拒新并排空的测试通过。根任务完整性核实（外部历史/待归仓路径：`../../build/native-execmon-owner-001/root-integrity.json`）357份上游SHA/Git对象、4份自有测试和3个二进制全部匹配；补充七个ExecMon文件的Git对象由固定仓库重新取得。报告SHA `56c0f491af9a5fb24a40726d94b40e266472af984b9edc2bf6744791de68e613`。

## 资格边界

该实验使用合成期货合约和原MinImpact，证明公开薄宿主接缝与指定时钟消费差异。股票T+1、现金与数量规则、QMT命令身份、断线恢复、完整压力并发及业务策略尚未接入。

自有队列close/drain通过不替代原Runner完整停止：原`release`仅停止日志，合成API仍登记，完整停止/卸载明确unverified。实验没有调用含Windows dump/CrashReporter入口的原`init`；基础目录由公开接口设置。因此完整init、真实SDK停止与DLL热卸载不在此资格内。后续先沿公开宿主和插件接口确认最小接线与生命周期，再确定产品文件范围；现有冻结CORE差异没有获得新增批准。

## 后继：原组件释放能力与股票时钟收窄

静态生命周期报告（外部历史/待归仓路径：`../../build/guanheng-workspace/native-execmon-lifecycle-audit-001/REPORT.md`）逐项核清：原TraderAdapter明确撤销SPI并调用API.release，原Local线程池具有wait/join。先前POC中API仍登记，是因为只调用了Runner.release，不能外推成Adapter缺少撤销能力。Runner私有managers及默认成员析构没有代调用这些release；有活动任务时的数据依赖顺序属于静态风险，尚未取得动态失败反例。

公开组件组合可以由自有薄宿主持有原Adapter、Local、工厂与数据依赖，并表达停准入、停源/回调退出、释放API、销毁Unit、再释放依赖与日志的顺序。该方案优先复用原生组件，下一轮先做pool0合成完整停止验收，当前未授完整stop/join或热卸载资格。`initExt`会调用api.init(NULL)且不等同normal init的风险/配置路径，后续保持原普通配置入口。

股票MinImpact使用本机TimeUtils时钟；StockVWap混合使用本机与context时钟。先前期货MinImpact的Runner虚时钟实验继续只覆盖其实际单元，不能推广到全部股票算法。真实QMT调用、股票规则、并发排空与重复启动逐项另验。

根任务重新核357份固定来源及25份实际读取来源，差异0；报告SHA `ddd5bc5fe4544891400e73acfa2b288fcf45cc48cb5cc2cf0af202837bdc2f43`，收据见`build/guanheng-workspace/native-execmon-lifecycle-root-001/integrity.json`。本轮调查零新进程，框架零修改。
