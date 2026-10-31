# 最新真实日线进入固定安装App

类型：模块C组合验证。状态：done（本次固定组合切片）；完整C保持in-progress。

## 原因与装配

此前App日线证据绑定旧7739行数据。A后继133已交9ETF9271行及明确的量价单位，本轮通过既有产品入口消费该固定数据，补齐当前实际页面证据。产品源码修改0，策略页继续名称、简介与版本。

实际使用已审Appa17/010普通安装、SDK0.14/042、039来源组件与生产SPA011。App wheel SHA为`7b6a51eaa266d48a887a1fdb38a0a2037e4d046127b65841c633c24645cc5c5e`，SPA ZIP为`025ebd950cd1f0b471b9804b5ff1c446688e89a24883460d0022f1b8584503ed`；31发行4743带摘要RECORD及App wheel成员逐字节核验，来源147文件经解包搬迁核验。A133 DELIVERY SHA为`e977326a6edbd86991117b718bc006a201c6de2ecca58dc4d991ccd274f449b9`，76项原输入逐SHA/长度匹配。

共享工作树中的三个B执行适配文件已继续演进；本轮加载固定普通安装，身份差异明确记录于`build/latest-history-app-001/IDENTITY.json`。首次QA要求全部活动源码仍等于冻结277项，触发启动前断言；原脚本与失败保留，9项外层回收全true、次错误空且无遗留owner。后继校验原冻结源、实际安装与当前差异；最新B桥和统一候选另验。

## 实际主链与结果

原`native.run`隐藏Job以单一340秒总截止运行实际安装解释器`-I -X utf8 -B`；实际51.438秒exit0，原树/EOF/join收束。App真实lifespan自动管理来源服务，使用336个store，沿SDK→原Reader→HTTP→生产SPA读取。第二代使用新App、新服务、不同control身份和同一数据/自选根。

| 验证 | 结果与原件 |
|---|---|
| 完整日线 | 两代分别9ETF9271根，所有日期/OHLCV及content/source单位与A123原SDK/Reader结果逐值相同；每份完整HTTP响应保存在generation目录 |
| 最新日期与单位 | 九只均到20261028；price CNY、volume lot，amount unknown、coverage Unknown保留；实际历史首次可知与修订继续unknown |
| 分钟兼容 | 第一代5证券各末2根OHLCV/content与A123一致；不扩大为全部分钟覆盖验收 |
| 用户操作 | `/market`→日线→510300.SH显示1210根/2026-10-28→截止2026-09-28→2010真实空结果→最新恢复 |
| 页面故障恢复 | 精确浏览器503注入，旧图与日期隐藏；移除注入后显式重试恢复真实数据。停止真实来源后页面同样隐藏数据；新App恢复读取 |
| 个人观察 | 实际PUT保存510300.SH，第二代读取持久列表；仅一次偏好PUT，其余GET，策略与交易范围保持原合同 |
| 页面与窄屏 | 1440×1000及390×844，实际URL/标题/主体/无框架覆盖，宽390无横溢出；Los Angeles浏览器保持上海来源日期。仅注入503阶段有一条预期console error，其余阶段error/warn为0 |
| 关闭 | 两代App shutdown_complete、HTTP真实join、reader/backtest-reader线程0、来源owner closed且forced/pending均false，App/来源端口关闭，ready/stop/closed的control/pid/configSHA一致 |

QA脚本及实际日志位于`build/latest-history-app-001`。固定277源码/78项A输入/5 QA/56原件/7截图分别由SOURCE、A-INPUTS、QA、EVIDENCE、BROWSER清单绑定；审查镜像位于同根review目录。手机正常图与桌面失败图已人工查看。

独立审查指出同一QA P2：原空/停止分支仅断言无图和无日期，这两个条件在加载中已成立；原stopped截图仍为读取中，页面最终完成态资格当时缺失。原脚本、截图及冻结清单保持。后继`complete_states.py/.mjs`在同一page验证真实图→2010对应HTTP 200/false完成→按钮enabled/无loading/宽窄截图→恢复真实图→文件握手由父原owner正常停止来源→同page旧图仍在→重读等待200/false完成、按钮enabled/无loading及宽窄截图。实际12.5秒exit0，来源/读池/HTTP/browser线程和端口完整关闭；额外SDK042的17个非RECORD成员逐字节匹配安装，九ETF实际HTTP日期交集复算为20250305..20261028共401日。

后继3 QA/14原件/4截图由QA-DELTA、EVIDENCE-DELTA、BROWSER-DELTA清单独立绑定，分别SHA`06a7206e4dc3ad614343e5bbf19131b70d292fa10762a9f5fda4f13debee8665`、`e1e5b27eecb58a3802d881e7c9cb1afb94e81e2048de736d8ecb0982138b4f69`、`102c1c2f16a41a91d6a3386f08e814a13b2710b8ef901b948990a09e73b66881`。手机停止完成图与桌面空完成图已人工查看；两轴最终delta均complete，原QA P2闭合，产品源码修改仍为0。

## 真实账户交接接收

复用A的[真实只读安装主链](2026-10-29-qmt-account-installed-real.md)，本轮以`consume_account.py`核11公开原件SHA、原63 App成员/592 Host文件身份证明、两轮8项terminal/ok、实际浏览器及正常关闭。结果为持仓4、委托0、成交0、资金1，显示资金/可卖及完整空记录。新增账户查询0、QMT界面动作0；私有配置和真实金额未读取或输出。固定资格为Appa13/e Host，最新统一安装和完整异常恢复继续。

## 审查与限制

本轮独立审查按原产品实现reuse及真实组合证据delta执行，最终规格/规范均complete，原QA P2闭合，无新增P级问题。最终SPEC-REVIEW.md SHA为`7cb278ef2318d1c3a980d14fb27961331ed6bffeebf405ba5f1b998cf9328681`，STANDARDS-REVIEW.md SHA为`8bf38bdbd5d9617b6f71cc0edef34c0b33e7e23c624a3b689ed4c1a62a59bdd6`；原gap事实保留，各自只授本轮限定范围。精确交付登记在`build/latest-history-app-001/DELIVERY.json`，包括原与增量清单、实际安装及最终报告。账户的原合成异常/恢复与独立审查保持[原安装记录](2026-10-29-account-installed-app.md)和[HPR接线](2026-10-29-history-preparation-app.md)各自范围。

浏览器503只证明页面错误语义；实际网络故障恢复、实时分钟连续性、全部历史覆盖、金额单位和历史可知模型仍需对应来源资格。9271行进入页面不代表已进入原生策略。M1仍需B稳定候选及显式日末模型；全部策略版本、A八指数/完整观察、统一安装/升级回退和全COP矩阵继续。未真实下撤单、发布、修改WT核心或Git集成。
