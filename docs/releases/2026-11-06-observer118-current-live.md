# 独立观衡118当前辅助消费上线

类型：独立App/SPA发布及正式用户入口验收。状态：已发布并核实。实际启动时间2026-11-06北京时间14:06，入口http://127.0.0.1:18143/strategies。

## 修改与固定身份

App117仅投影历史诊断，实时已消费字段未进入公开策略接口。App118沿冻结V1a13的原校验器读取当前辅助事实，两个正式入口及原状态行表达“必需7/7已消费（齐备）”，title说明16项可用派生和行情基准。原布局、历史覆盖、资金、持仓和个人观察保持。详细实现及旧归档兼容见[模块验收](../evidence/2026-11-06-current-auxiliary-public-read.md)。

版本0.1.0a118+current.auxiliary.1，源提交dbf2034e0af0cab2ee0d0a75f6e430180ac174af，标签deploy/observer-a118-current-20261106。ZIP SHA256为0308b15aaef8f7fddb238dd380bb897338d883966799ab818d571e3ca45984c9，manifest为e1ecb0b2bf2e2537fb593da732aec8c3ffa4d5cd5bc3c83d4e008cbd44d48dfc。

原普通安装器verify/install通过，31包pip check通过；全新安装observer-programs/a118-current-auxiliary-20261106-001。读取侧V1a13/Corea8+read2/Nativea1+read2/原read10及SDK0.18，与执行安装分开。508构建成员复核无差异，独立审查无剩余P0/P1。

## 独立切换与验真

旧117正常关闭，两个读取池线程均0、Web及启动器退出码0。沿原外部读取配置、CURRENT、账户、个人目录、观察快照和五份报告启动118；新Web20940/启动器13464，控制代72ce8c75-e9e5-4b4f-b186-400935f12f97。WT六角色的PID及创建身份均保持，QMT与市场更新进程未操作。稳定observer-current/web-profile.json及DEPLOYMENT已更新。

14:07系统Edge实际SPA经已获授权的Playwright验收；当前Browser插件未列入可用工具，使用既有依赖和系统浏览器，未安装新浏览器依赖。

| 用户入口 | 实际结果 |
|---|---|
| 策略 | 原状态行显示必需7/7，title16，当前资金与8行持仓可见，桌面1440及窄屏390截图 |
| 账户、系统状态 | 实际账户内容及六个WT角色就绪可见；历史查询可响应 |
| 回测列表 | 当前策略2份，实际2.954秒可见 |
| 回测分析及操作 | 原收益/回撤SVG、日期与绩效可见；买卖标记关/开及全部交易记录有效；完成14.313秒 |
| 市场观察 | 实际上证参考及广度多图，日期10月7日至11月5日，发布时间可见；3.210秒 |

正式调用无失败响应、浏览器控制台错误0、框架覆盖层0；页面身份/非空、截图及实际交互均通过。此前117一次updates503缺少首错正文，精确原因仍unknown；118此次同入口200，不将旧故障改写为已定位。

证据根E:/workspace/wondertrader-qa/observer118-live-20261106-001：verify/install.log、STOP/START/POSTFLIGHT.json、PUBLIC-STRATEGY.json及browser/RESULT.json和截图。现场维护脚本先后误读outcome字段、遗漏控制目录，原失败log保留；按原API补齐后正式启动。切换没有改产品代码、金融事实或WT角色。

Web日志延迟打开，本代尚无stdout/stderr输出，因此只有ready回执，日志实际追加资格保持未发生。已匹配源码的轮转/故障回归沿117采用，当前实际页面无异常；WT Native日志及完整业务沿[运行发布](2026-11-06-current-auxiliary-automatic-live.md)分别核实。

回退先用当前profile正常停止118，再沿保留117安装及原读取配置启动；旧117缺少当前辅助公开字段。WT、账户与行情持续运行，回退观衡不回滚任何委托或成交。后续只读页面更新与自动交易独立发布。
