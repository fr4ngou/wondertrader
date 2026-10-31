# 已完成导入目录自动生成读取配置

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：产品CLI、32证券及1088证券已完成批次快照准备、真实SDK/观衡消费通过；5342项整库目录尚待导入完成后验收。合同见[RS10](../specs/qmt-source-history.md#rs10-已完成目录生成统一读取配置)。

## 根因与正确实现

统一source-stores原本需人工填写批次，完整导入与读取服务缺少自动准备入口。新增source_market.prepare_source_config与模块CLI，从已完成目录取得原store/SHA/条数，复用原NativeSourceMarket注册及受管Reader依赖验证，精确比较整个注册集合。通过后关闭Reader，再在同目录完成写入/fsync/关闭并无覆盖硬链接发布新候选。原DSB/sidecar/收据及运行实例保持，无新增数据库、交易或WT核心修改。

输入32MiB、证券10000及原多根/缓存预算保持；running/completed_with_failures、重复证券、根SHA冲突、成员/条数错配、关闭或写入失败均不发布候选。CLI固定ASCII JSON，不输出敏感异常正文；配置无token，目录SHA可选独立绑定并始终回报实际值。

## 真实输入与调用链

首个验证切片包含原002/batch-0000和003/resume-003-batch-0000全部32证券、8672152行。CLI实际exit0生成两根配置，source_rows与成功收据一致，无临时残留。随后以生成文件直接启动同一只读HTTP服务，SDK三次交替查询及观衡000001.SZ/002027.SZ分钟入口通过，原时间/六值与受收据绑定CSV尾部一致，原session保留。

再将当前已完成批次明确冻结为开发快照：68根、1088证券、295763611行。只纳入每根原收据已全部登记的批次，过滤正在发布的部分批次，范围说明见快照说明（外部历史/待归仓路径：`../../build/qmt-source-config-001/SNAPSHOT-SCOPE.json`）。这份快照的completed仅适用于已包含的批次集合，完整5342项作业仍运行。

自动准备1088项通过；实际服务注册1088证券，查询最初批次000001.SZ及较新批次002574.SZ，SDK三次与观衡两个接口通过。各返回两根、schema1.5、source_label及未知单位，原来源保持；App.shutdown_complete、reader线程0、服务/Reader在owner关闭。该应用验证使用前序SDK加载的缓存及5秒预算，不授全市场默认2秒冷读保证；本轮无新浏览器或安装包结论。

物料：32项冻结切片（外部历史/待归仓路径：`../../build/qmt-source-config-001/COMPLETED-BATCH-SLICE.json`）、32项消费（外部历史/待归仓路径：`../../build/qmt-source-config-001/REAL-HTTP-APP.json`）、1088项冻结快照（外部历史/待归仓路径：`../../build/qmt-source-config-001/COMPLETED-BATCHES-SNAPSHOT.json`）、1088项配置（外部历史/待归仓路径：`../../build/qmt-source-config-001/CURRENT-COMPLETED-CONFIG.json`）、大集合实际消费（外部历史/待归仓路径：`../../build/qmt-source-config-001/CURRENT-COMPLETED-HTTP-APP.json`）。真实CLI输出保存在对应受控根stdout，候选配置摘要与回报相同。

## 验证、审查与边界

本轮source_market共17项通过，含原8项路由/身份/LRU/默认兼容和9项准备/完整集合/隐藏成员/数量/目录SHA/已有目标/写入失败/竞争/关闭/CLI编码。独立full静态complete，无实质gap，见审查（外部历史/待归仓路径：`../../build/qmt-source-config-001/REVIEW.md`）。原HTTP服务文件与原Reader未改；上轮15服务兼容通过及1既有环境skip按身份复用，本轮实际源文件/HTTP/App另按上述输入验证。

各短进程实际exit0，tree zero/EOF/join/资源关闭及输入源码SHA见收尾（外部历史/待归仓路径：`../../build/qmt-source-config-001/POSTFLIGHT.json`）。全库存长进程仍由原owner保持，沿原8小时wall/monotonic截止，当前进度见[导入记录](2026-10-27-qmt-full-history-running.md)。未启停QMT策略、真实下撤单0、旧QMT工程只读、未切生产。

剩余：真实5342项最终目录准备/全注册、各证券范围与尾部补齐、标准策略所需分钟边界/单位、完整恢复及独立发行。当前无用户必需操作或待批准事项。
