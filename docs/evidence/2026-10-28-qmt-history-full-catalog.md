# 历史全目录读取与尾部收尾

类型：开发运行证据。日期：2026-10-28。状态：5337证券目录注册及抽样HTTP/SDK/观衡ASGI主路径 passed；最终尾部/目录与真实全推继续pending-verification。

## 已完成目录

005已结束：5337成功、1388404040根、2空、3隔离；最终目录SHA c9237bc8cd298224fa048a5976562a5ec806434e4da78c3f0d6226aead588998。完整原342批store保持，通过现成source_market.prepare_source_config注册5337证券，精确排除000001.SH/000300.SH/399001.SZ。原失败和空项仍保留；未重导成功数据、未覆盖活动配置。

候选build/qmt-history-finish-main-001/SOURCE-005.json，SHA 05f470ac5da41a574ba43f834e047c7bca3a4b303b08ab70ccb8ba90966616b4；Reader DLL SHA 4f5e2696559011d755edfac1d58296626fdedb6ba46c6d6a0fafc0203eebe62c。实际配置准备exit0，约39.392秒，关闭后才发布候选，临时文件无残留。tail_refresh=pending_current_qmt_download如实保留。

## 真实消费主路径

完整配置→原NativeSourceMarket/DSB→真实回环HTTP→同版SDK→观衡create_app公开分钟图接口。App先首次访问，再用SDK核原值，未提前预热样本。

| 证券 | 开始分钟抽样 | 最后分钟 | 首次App秒数 |
| --- | --- | --- | --- |
| 600000.SH | 202111010931 | 202610271500 | 3.375 |
| 000001.SZ | 202111010931 | 202610211500 | 3.157 |
| 300331.SZ | 202111010931 | 202610211500 | 3.484 |

各两根尾部分钟的OHLC/volume与SDK逐项相等，来源标签转UTC后不移位，schema1.5/source/source_label/Unknown保持。查询2021-11-01起始窗口也实际可读。注册全部5337不代表逐一重读全部13.88亿根；本轮读取三证券，未做浏览器DOM或正式部署验收。数据仍由原WT文件保存，未新增数据库。

最终运行qmt-history-5337-http-app-main-004实际exit0，约12.565秒，源服务与App/线程关闭确认。结果build/qmt-history-finish-main-001/REAL-5337-HTTP-SDK-APP.json。前3次因测试环境缺tzdata、未设置本仓策略包路径和SDK来源不一致而失败，已通过完整开发环境与同版规范SDK路径修正验证接线；未修改运行产品代码以绕过问题。当前是源码开发组合，不授wheel/搬迁/发布资格。

## 当前缓存与未刷新的差集

只读清点当前5343个分钟DAT：首次120秒范围观察完成3035份后到截止，保留完整已关闭JSONL行；第二次仅处理余下2308份，实际66.442秒exit0。以原字节摘要绑定两次输入，证券唯一且并集精确5343，合并记录为qmt.local-dat-composite-inventory.v1；不把首轮超时记作整次inspect成功，不宣称原子快照。当前2空、不可读0。

复核最终准备保留的189根/3015证券：首标签、末标签、条数及原export记录的source_size/mtime_ns/device/file_id均匹配当前观察，差异0。整数比较由Python保留精度。这里没有重新对整个源文件集合计算SHA或逐分钟回读，validation明确为header/first-last/count/stat。已导入DSB继续在实际Reader读取时核内容身份。依据CURRENT-INVENTORY.json、CURRENT-TAIL-COMPARISON.json；复核实际exit0，约3.669秒。

当前5343份是已下载缓存库存，区别于实时来源6982只沪深股票/ETF清单。1758只当前ETF中仅18只在此分钟缓存中；因此本记录不能声称全体ETF历史已齐。新增证券301718.SZ纳入尾部刷新，真实全推采集和历史缺口来源继续接通。

## 原尾部作业终态与新范围

原qmt-tail-batch-refresh-main-001在既定截止前因单批剩余期限到达而停止：1824成功、492741385根、余53，failure_type=TimeoutExpired。控制器实际exit2/子进程exit1，约9645.485秒，forced=false，tree_zero/EOF/join/资源关闭均确认。原截止和失败终态保持，不按运行中状态重启整批。

核原114个成功store的收据摘要、完整成员、条数和DSB摘要登记后复用1824证券。新作业qmt-tail-finish-selected-499-main-001选择原余53及另外28旧store的446成员，共499不重叠，使用新的独立45分钟总预算。该新范围不是延长原作业，也未宣称原任务在原预算内完成；PLAN保留旧状态和截止。

实际转换继续使用原冻结qmt_local_dat→Importer→Helper，Helper SHA 59696d42d8985ca09ddacf0e583525d025dba91ff66ffaa296cec8f6174cc45a。新输出E:/workspace/wondertrader-data/qmt-tail-batch-refresh-002，方案/冻结输入/runner见build/qmt-tail-batch-refresh-002。新作业只保留原batch store，不再复制一份未被读取服务采用的扁平native数据。原DAT、旧store和旧作业材料全部保留；SDK/真实券商调用0。

本记录时新作业4批64证券/18134931根、余435，实际root句柄仍live；这是快照。后续以原句柄/FINAL确认，观察超时不代表进程终结。

## 最终目录装配

build/qmt-history-finish-main-001/assemble-final.py已经准备，尚未执行。入口先核新作业实际exit0/整树与资源关闭、499的FINAL，再按完整store闭包替换原153根；189根3015证券与新2323证券合并，预计5338成功、2空、3隔离，共5343项。核证券唯一、每store收据完整集合、当前首尾/条数，再交原prepare_source_config。未完成刷新时不能靠配置顺序覆盖重复证券。最终目录和候选配置不自动切换活动服务。

## 实时采集观察

只读截图确认上次GH_WT_MEMORY_VERIFY仍显示停止中；本轮没有点击、改正文或重启QMT。外部45秒监听旧只读配对无认证/行情/心跳，接收端正常关闭；qmt-quote-stop-observe-main-001实际exit0约46.539秒。此观察未证明源端线程已退出，也不能单独判定QMT框架根因。真实全市场完整快照、分钟落盘和停止仍待查清；原3000条观察保持限定结论。

当前没有新增WT框架修改或待批准提案。真实下单/撤单0、未生产切换。整体目标active；后续完成499及最终目录验读，再继续实时源和受管常驻/交易恢复/独立发布主链。

## 收尾快照

新499作业9批/144证券/40912229根，剩355；控制器60128实际句柄live、actual_exit=null。project.py check实际exit0（约11.183秒）；准备脚本两份AST语法及限定文档diff检查另存VERIFICATION.json。当前无运行产品源码或WT框架修改。后续保持同一活作业，不因观察或会话结束重启。


## 后继：尾部与最终读取完成

新499范围已完成32批、140875095根，余0/失败0；qmt-tail-finish-selected-499-main-001实际exit0，2158.5秒，在原45分钟预算内。整树归零、stdout/stderr EOF、reader join及资源关闭已确认。原1824范围的超时终态保留，未改原预算。

最终装配qmt-history-final-assembly-main-001实际exit0（约9.239秒），按完整store收据闭包替换153旧根：3015保留证券加2323刷新证券，得到5338 imported、1390294477根、2 empty、3 quarantined，共5343项/335个成功store。每个store完整成员、收据SHA、条数/DSB SHA登记及所有成功证券首尾/条数与当前清点逐一匹配；保留根source-stat匹配依据沿前述记录，未对全部DAT重新逐字节计算SHA。覆盖仍Unknown，源值/来源标签合同保持。

最终候选build/qmt-history-finish-main-001/final-001/SOURCE-FINAL.json，SHA f1adb3c3930c5edb61785c2da87738c7e39856b430f154b130509541a3be3d3d；catalog SHA bfe6f9e6c1ce2004d46442a9b1e11404a576dc245ab0a71ee877e4ade44d3752。候选未切换活动服务，未改原DAT/旧DSB。

实际DSB→独立回环HTTP→当前SDK→观衡ASGI分钟图最终组合通过：600000.SH、000001.SZ、300331.SZ末分钟均202610271500，301718.SZ起点202610230931、末分钟202610271500；前三只起点202111010931。各两根尾部OHLC/volume与SDK一致，来源时间转UTC后标签保持。冷App首次耗时分别3.422/3.344/3.594/0.203秒。qmt-history-5338-final-http-app-main-003实际exit0，源服务/App关闭确认；结果REAL-5338-HTTP-SDK-APP.json。前两次验收脚本把ISO时间标签误当SDK整数分钟参数而失败，修正测试入参后通过，产品协议保持。此结论覆盖四证券抽样与完整注册，不授浏览器DOM、wheel搬迁或生产发布资格。

缓存库存的导入/尾部合并主路径已完成；三指数负量额的可信源修复、1740只ETF缓存缺失、真实持续采集、常驻第二代/账户恢复与观衡独立发行仍待完成，整体目标active。
