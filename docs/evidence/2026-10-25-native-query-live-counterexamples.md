# 2026-10-25 原版查询与实时回报交错反例

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：原生诊断验证记录。状态：动态反例已复现；独立成品静态审查完成。对应测试规范（外部历史/待归仓路径：`../../tests/integration/qmt_standard_trader/query_live_counterexample.md`）和[来源能力边界](2026-10-24-qmt-query-live-source.md)。这份证据证明接入时必须处理的归约边界，生产首次/重连交接继续未完成。

## 目的与实际输入

固定WonderTrader原上游08b230dd05facf6d650d949bfe51054115a2ecb1，仅链接原AdapterHost与原依赖；原TraderAdapter.cpp SHA effa4d8c26767b7c99c1887eb53f3d0edb19babf01575af1ca85f77becba54cf。未编译工作树Adapter、Standard、Common或真实QMT SDK。有限ITraderApi夹具通过原公开回调驱动持仓→委托→成交→资金查询及实时order/trade；同一源只有一笔买入20股成交。它在各查询间发生，回报延迟到ready后投递，原查询各自真实包含该事实的范围由夹具明确定义。

11个主观察、10个独立统计读数实例，共21个原Adapter。正确源事实为持仓120、可用100、未成交80。统计读数使用独立重建实例的原公开buy：only-open、limit_l50、买100，实际mock orderInsert数量30对应已用20，数量10对应已用40；这些数量只认证原生限额归约，不授股票实盘手数资格。

## 实际观察

| 时序 | WT持仓 | WT未成交量 | 独立buy读数 | 含义 |
|---|---:|---:|---:|---|
| 成交在持仓查询前，历史及实时均交付 | 140 | 60 | 10 | 查询已吸收的成交又进入增量回调，持仓/未成交/开仓统计重复 |
| 成交在持仓后、委托查询前 | 120 | 60 | 10 | 持仓正确，未成交与开仓统计重复 |
| 成交在委托后、成交历史查询前 | 120 | 80 | 10 | 持仓与未成交正确，开仓统计仍重复 |
| 成交在成交历史查询后，正常对照 | 120 | 80 | 30 | 查询未吸收该增量，原实时归约正确 |
| 持仓查询后成交，按历史DEAL过滤实时成交 | 100 | 80或100 | 30 | 简单按历史成交键过滤会漏持仓增量；未作为产品算法 |

账户资金始终按显式源字段经原sink逐值转发，不由成交推算资金。源TradeID/OrderID、原WTS行JSON与SHA、查询顺序、真实回调和全部公开金融观察分别保存；191份source-json/SHA由根再次独立核同。此实验未证明真实QMT缓存或回调具有这些任一保证，只复现定义时序下原WT归约。

## 重连与原生缓存边界

同一个Adapter收到完全相同的第二次四查询、期间没有新金融事实：持仓120、未成交80、活动订单1保持，但原buy统计读数由30变10，证明历史成交统计再次累计。私有订单计数翻倍仅保留源码推论，未动态直接采样。

断线期间原100股已卖出、旧买单已撤，重连返回持仓空、两条终态历史委托与close100成交；旧Adapter实际仍持仓100/可用100/活动订单1，未成交0。新Adapter generation对完全相同源输入为持仓0/可用0/活动0/未成交0。此处测试的是持仓为空及活动委托集合为空，ORDER历史本身包含终态行。新generation清旧状态的对照仍未证明查询与live的共同来源覆盖。

固定原Adapter lost后isReady仍true被单列观察；宿主LocalExecuter另有channel_ready写门，实际失联交易准入须结合宿主，不从该值单独推导。后续需同时处理重新ready时宿主旧缓存与原未决命令责任。

## 制品、资源与资格

源码SHA3696a4daa17d4b2edaabf9b61c851db36f5a81a7f02546801f5a6c60b6a39587；测试规范bbe79eeef612270ad422c31cde71b99b1d6f39d0eb7c16d5f4cc123e18dc5773；实际EXE da4c0fe3c28061b98578f9f7fc65893a5c02bd2cb0239dfdd31a1aaaffa5a464。固定构建323原上游/145自有原件均逐字节核同。运行qmt-query-live-counterexample-runtime-001严格检查全部21观察匹配、11主case唯一、191来源hash、测试自持引用0、真实进程exit0及全部容量断言，报告counterexample_reproduced=true、production_qualified=false、sdk_calls=0。

initExt强制save_data=true，实际CSV/rtdata在隔离work/generated；运行最终68文件，在256文件/总8MiB/单文件及报告1MiB上限内。原上游内部orders map对象级回收未证明，报告明确false；固定21实例、测试自持引用释放、最终外层Job实际tree0/EOF/reader join/资源关闭分别保存，不宣称原对象内部全部回收。没有Logger线程。初始化仅initExt→run→排队onLoginResult，WTE_Connect/真实Factory登录没有测。

独立设计、成品full及接线delta均已完成，新增已确认P1/P2为0；静态与动态分别登记。根原件：build/guanheng-workspace/qmt-query-live-counterexample-verification-001，含REPORT、来源hash根核、编译输入、实际link rule及控制器。原始构建与运行目录为qmt-query-live-counterexample-fixed-001/runtime-001。

## 下一动作

薄接入层需要可验证的来源cut/fence，明确P/O/D分别吸收哪些成交，再把真正增量交给原WT；同实例短运输恢复保留原book/index，完整新基线评估受控generation与宿主缓存重建。继续核目标QMT真实字段/订阅回放与查询缓存保证，不使用本地时间、静默、序号或人工完成标记代替来源包含关系，不增加第二账本。WT框架与生产Factory本轮均未改，真实SDK0，整体迁移目标active。

## 同日独立成品审查封存

报告build/qmt-query-live-counterexample-review-001/REVIEW.md SHA a1202519293c4842b3e95ad8a49c097e0ec771d7cac280dbb8a2e08b7b7dc3b9，来源清单SHA af66a4bae58213b6b57075f80a78a3ae91301df4f67539682e2d5620dba3ab56；根复核26份审查原件字节均同。持续OOM/原WT容器异常未注入，内部map对象级回收仍未证明；实际外层进程已reap的证据只授进程资源边界。原框架能力文档与执行模块已按这些原生查询/实时职责补充，仍不授首次/重连R8完成。
