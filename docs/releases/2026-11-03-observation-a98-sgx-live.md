# SGX A50日频及月报独立接续交付

类型：本机来源接收及独立更新角色部署。日期：2026-11-03 12:39。接续[保险原表独立交付](2026-11-03-observation-a97-insurance-live.md)；来源设计与隔离链见[SGX证据](../evidence/2026-11-03-sgx-a50-continuation.md)。

原持续配置只有日频入口，月频仍依靠旧归档。自有`sgx_reports.monthly`读取官网动态目录、实际报告月份和原PDF两张表的当月A50列，沿原Fetcher、归档、刷新、CAS和调度；日频原算法及接口保持。月末未平仓与整月成交分别保存；不从单日成交推月成交。原首次可知时间和基差未知继续为空。

SOURCE-CAS的15项冻结交付已逐字校验，限定SGX分流、新数字模块及对应测试/文档；应用版本由Root分配为`0.1.0a98+sgx.1`。合入干净主干`c765e52`，原PDF提取文本的尾空格保留原字节/摘要，格式检查例外仅作用于这三个源样本。固定31项依赖保持，无registry或WT框架变更。普通源码构建、离线安装和文档检查完成；65项已有来源/恢复回归沿精确代码身份复用。

## 实际数据与页面

新安装12:37:34至12:37:50沿原refresh只取`sgx.a50`及新增`sgx.a50.monthly`，success，当前从`f874c6f961d622d27668586426b04cfc85c447a7fdb2419afebc6ee0f6a93bff`变为`a1cf29ff48965b5a93abdec6a2e71f5d6cbc8015bdd2357795e78b0d426bf9d3`。日频1836条（2019-10-10至2026-10-30）、月频10条（2025-12-31至2026-09-30），全部旧行和定义版本保持；其它70组完整记录、源表及股票分区保持。保险新数字kind保留，旧隔离数据候选没有覆盖当前快照。

官网日频1d/1y当前均返回10月30日，未平仓1,043,060手、当日成交496,725手；官网月报目录最新9月，月末未平仓836,157手、整月成交8,917,354手。目录/文件元数据10月9日与公告广播10月12日分别登记，原available_at保持未知。尚无官网11月2日日频和10月月报的实际返回，不能将本次抓取日写成统计日。

当前Web仍是a93、http://127.0.0.1:18143/ 。真实Edge/Playwright1440×1000验收两条曲线的“全部”交互、1836/10记录数和实际末期，每页2画布、页面异常0；截图和RESULT在`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001/sgx-actual-browser`。本次未修改前端，手机布局复用同输入已有证据。

## 独立角色、制品与回退

原a97以原controller正常关闭exit0、父子退出和关闭截止已确认；新a98控制`d63821be-b901-4ec3-8394-c82226539bfb`，PID58484、监督PID43192及创建时间匹配，12:38心跳推进、waiting。Web、WT及QMT生命周期保持，金融命令0。稳定维护定位为`E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json`；本机目录LocalCache/Local/Guanheng/observation-update/a98-sgx-20261103-001，沿原status/stop/start维护入口。

原28来源逐项保持，追加独立`sgx.a50.monthly`与官网两个主机，共29路；原模型、日历、预算及北京时间09:00/17:30/21:00计划保持。配置SHA256`a8bb6da68aa18ecd37385b66e8a3488c8671f1615a3a4bfc5468050c996faae5`，部署SHA256`7cb4783d48574124dfadfdfb296a0d363f4d603e0aaeb3f6dfd86bb52bfb7492`。原09点部分成功窗口保持，本次手动两路成功未冒充29路自然整轮成功。

ZIP SHA256`32a4d06c1fa5a8f0d2f7b9f2f804205e2119c6dec71e99c296edfa5ade56289a`；包清单`c6848ef7b95e08543da5e7400a21f7915c74deed54af8f2cde121de9c2f31301`；角色清单`6746e5066a1dd26760b5cbcf011b34c8b7ec15e357ef62effd723dc5970ffa20`；安装收据`a8140045665677bcaf8547520e6594e0554138f07fcda6b45c0020018f36b4d9`。构建Temp/root-observer-a98-sgx-build-001，稳定安装observer/0.1.0a98+sgx.1。

回退：原入口正常停止a98，按原a97配置启动a97，再核其正常运行后更新稳定维护定位；旧版使用其原28路配置，月报持续生产暂停。已经接纳的1836/10历史及新原件保持，新月频生产暂停；数据回退须沿原CAS单独处理，保护其它来源后继。a97保险数字来源继续受原配置管理。

完整接收原件为SGX-SOURCE-RECEIVED、A98-UPDATE-PREPARED、A98-ACTUAL-SGX-REFRESH、三份启停/status、UPDATE-DEPLOYMENT-BEFORE-A98及两页浏览器证据。来源原Source/Data/配置CAS和HANDOFF-002保留在`E:/workspace/wondertrader-data/sgx-a50-continuation-20261103-001`。

剩余主路径：开发者2继续策略只读边界/原资金恢复和自然行情计算，账户24保持持续发布；全A006补缺后的最终回读/质量、T2108和原生日线现场维护继续。市值/GDP最新原口径生产者已分工给开发者1；其余旧报告期数值来源仍分别保留缺口。当前无新增用户审批项，自然下一交易日及新月报披露尚未发生。
