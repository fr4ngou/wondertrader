# WT六组件账户及数据联合运行

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证证据。日期：2026-10-30。状态：完整隔离主链与账户重认证恢复通过，独立full审查通过；实际QMT、独立页面与唯一策略执行分别继续。

## 目标与事实所有者

沿[WRI](../specs/independent-wt-runtime.md)和[NAP](../migration/native-account-publication-proposal.md)，正式普通a3 WT入口同时持有HPR、交易Host、账户Host、原生账户发布、历史服务、行情采集六组件。观衡继续独立只读；此次QA调用原C validator/projector核金融投影，未安装Web/App到WT。

来源为同一个正式四连接正文，在QMT配套3.6.8解释器下执行SDK替身。真实QMT进程内能力、真实账户稳定性与SDK替身结论分开登记。

## 实际调用链

- 两轮原Scan四组查询和原帧发布，SDK可用资金82000→82100，原C投影同步更新；每轮50项原事实、6项浮点逐位一致。
- 原交易Host完成SDK替身下单→查单→撤单各1次；真实委托/撤单为0。
- 原HPR补齐请求及读取、原DataKit/Writer形成两根原DSB分钟；原生回读时间、OHLC、量额一致。
- 原Reader使用final7083统一候选，查询新ETF、指数及旧证券五项各5根，与冻结原响应一致。既有活动历史/采集配置保持。
- 同实例仅断账户运输后，原owner回收旧代并重新认证，后继NAP四批共同使用新binding；其他连接binding及六owner PID保持。

## 原件与身份

完整入口及范围（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/README.md`）、交付（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/DELIVERY-001.json`）、根接收核验（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/ROOT-INTAKE-001.json`）。根已重核42项制品摘要一致；公共产品源、WT核心及现场改动0。

main001（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/main001/RESULT.json`）与main002（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/main002/RESULT.json`）分别43.382秒、39.229秒exit0；1947/1958输入前后保持。终端正文运行的file/network guard计数0；所有内外Job正常树0、管道EOF、线程join及句柄关闭。实际现场WT33636/Host46288/history60964/collection75000在模块交付时OS核实保持，本模块18个进程已消失。

## 剩余资格

公共组合及恢复边界新增，触发独立full审查，报告（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/review001/REVIEW.md`）双轴complete、P0–P3均0，根重核源码/原件并限定接收（外部历史/待归仓路径：`../../build/wt-account-data-composition-001/ROOT-ACCEPTANCE-001.json`）。该主链未配置execution，不授唯一策略完整运行、实际C HTTP/中文页面、真实QMT四连接、生产发布或全目标资格。真实通信中断沿[实机诊断](2026-10-30-wt-real-read-diagnostic-003.md)及[逐代诊断](2026-10-30-read-transport-interruption.md)继续。完整目标active，无新增用户必需处理。
