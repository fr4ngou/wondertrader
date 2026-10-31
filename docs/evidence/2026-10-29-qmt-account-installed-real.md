# 真实QMT账户经独立安装App的只读主链

类型：开发隔离验收。状态：真实只读主链通过，整体系统继续开发。范围为四类账户查询、原生扫描、App托管Host及实际中文页面；真实下单、撤单、生产切换均为0。

## 来源与装配

复用已有`QMT_MEMORY_GATEWAY`条目。原正文属于旧协议，先核旧文件SHA与逐字私有备份一致，再替换为封存e安装包原配对器生成的v3完整正文。只准入`account.trade_detail`的position/order/deal/account，固定注入`get_trade_detail_data`；无交易、行情订阅、下载、终端文件或网络能力。两份既有真实账户绑定已逐字段相同；账号、配对凭据及实际账户正文保留在151私有材料。

QMT实际打开已有编辑器，编译保存后从原“运行”入口执行，日志标识simulation mode。该标识描述指标运行方式；本轮账户查询绑定既有live账户，取得真实账户数据。没有把该入口称为模型交易部署或真实交易验收。结束后使用同一编辑器“停止”，关闭编辑器。原`GH_WT_MEMORY_VERIFY`090行情策略、137/140采集及其他模型策略保持。

生成正文原SHA为`02037acf0cdaf3b7265322b31150ae1a0a2af5cbb04e34970567c8d998d8a11a`；编辑器保存后SHA为`7bcbc81e917deb7b6204fe1e2e6e9a45018f8baf05bd380c13e720e306619dde`，ASCII规范换行及尾部空行比较完全一致。正文保留在原条目且已停止；旧正文备份保留。

Host使用封存e普通安装，INSTALLATION SHA为`5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3`。原生组件使用`account-broker-current-002`的GuanhengAccountScan.exe及TraderQMTReadOnly.dll；基础资料取137真实采集的sessions/commodities/contracts，三份原字节SHA固定，不使用合成两证券资料。

## 实际结果

第一条主链为原Native扫描→TraderQMTReadOnly→签名外部Host→命名SHM→QMT原策略线程→券商账户API→原DTO。position/order/deal/account各一次，结果4/0/0/1，四组complete；原生close完整、exit0、无在途任务/线程。159外层耗时6.594秒，正常整树0、双EOF、读线程join及资源关闭。157 Host独立生命周期正常closed，forced=false、pending=false；外层159.453秒正常关闭。

第二条主链使用C已封存的Appa13普通安装及18文件生产SPA。App真实lifespan自动创建并管理e Host，来源运行后由实际内置浏览器访问`/account`。账户页面显示真实资金、4行持仓及可卖数量；委托/成交页签均明确显示“查询完整，返回0条记录”。未知来源均价、券商登录会话与交易日保持未知；运输绑定已核验。刷新按钮可用，浏览器error/warning为0。本轮只读取和切换页签，没有点击刷新或产生交易动作。

160/BROWSER-OBSERVATION.json记录脱敏页面观察，真实金额和账户明细未复制到公开证据。浏览器页关闭后，停止本次QMT账户运行体，再让App正常退出。160/RESULT.json确认shutdown_complete、Host closed、forced=false、pending=false、HTTP线程join和两读池线程0；161外层140.235秒、exit0、树0、双EOF/join/资源关闭。实际PID已终结，ready收据不作为持续存活证明。

原通信Journal以SQLite只读模式核验：8项原请求按position/order/deal/account两组排列，全部terminal/ok，无其他业务操作。第一次核验工具误把原状态名写成done，162断言失败；按原合同terminal及ok修正，163通过，没有重发任何账户查询。失败日志保留。Journal用于通信身份与结果恢复，账户金融事实仍取券商查询。

## 原件与身份

- `build/qmt-account-source-main-151/REAL-SCAN-RESULT.json`及157/159外层结果：真实原生四查询和独立Host回收。
- `build/qmt-account-app-real-160/{main.py,RESULT.json,BROWSER-OBSERVATION.json,AUDIT.json}`及161外层结果：普通安装App托管与实际页面。
- `build/qmt-account-app-real-160/IDENTITY.json`：App安装成员与原a13 wheel逐字节核验、e安装清单及本次原件SHA；核验命令及结果保存在164外层目录。
- 私有绑定、原始DTO、Journal及正文备份位于151/private-003；公开材料只输出状态、条数和摘要。

本轮产品源码与WT核心修改0。沿已有安装、原扫描/映射及App契约执行真实集成，原合成异常/恢复和独立审查资格分别沿[账户安装记录](2026-10-29-account-installed-app.md)及[HPR App记录](2026-10-29-history-preparation-app.md)保持。本轮不重复声称完整QAR矩阵、全部App版本或生产环境已通过。

## 剩余与风险

只读链已具备真实可用证据；原交易身份扩展、策略理论仓位与券商账户的完整组合、异常恢复、统一候选安装升级和最小真实下撤单仍需分别完成。原生组合仓位条目生命期故障另按[四核心提案](../migration/native-position-ownership-proposal.md)等待批准，不能据账户成功授正式策略稳定性。盘中分钟/收盘归档与按需补齐继续由模块A推进。本轮无须用户操作QMT。
