# 独立更新a94、自然09点窗口与报告页面验收

类型：实际开发环境发布及接收记录。北京时间2026-11-03 09:14核实。Web继续运行`0.1.0a93+status.1`、入口 http://127.0.0.1:18143/ ；独立市场更新角色已采用`0.1.0a94+shared.1`。两者独立启停，WT、QMT和原采集本轮保持运行现状。

## 实现与制品

全A更新先复用同批成功PB来源已存的股票基础表、日线原件，校验内容SHA、表头、实收日期和目标交易日，再取得其余公开资料。原先重复网络取数导致已取得输入仍超时；修正位于自有公开来源及采集编排层，原件、计算、完整性和发布事务保持。源码`f8d0dc2`，构建基线为干净主干`3b4593b`，没有WT框架差异。

- ZIP SHA256 `37ee39d20e03a0c886cfcd0283c4293404868b58c2609fa08740b7f82ba9e78b`。
- 制品清单SHA256 `8dd3e54f18a7795c9509f43b050d3475f4a260fbe993744dde41b34cf5e5008b`；安装收据SHA256 `3e7af6628a3cf4897dd6ba467e06bae3c5d9032979ecf0dc46a10049af32dd82`。
- 更新部署SHA256 `efc9fe81ba8a01ad59194c34ae505f06222bcbb1a7fe8baf046e79ae80bb71d9`；原27来源配置SHA256 `dc79564526c226179e08ccdb10215a1b50c72d8843afc3fa80b6652751239fcc`。
- 维护稳定定位为`E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json`，绑定实际解释器、控制入口、PREPARED、部署及本代身份。Web的`DEPLOYMENT.json`独立保留。

旧a92更新角色沿原控制入口正常关闭，退出码0、父子实际退出、原截止与关闭证明均取得。新控制`1ded693e-2ef1-4763-bad5-ce1c5a64e556`，监督PID1152、子PID65284；09:13按进程创建时间再次核实两者存活，调度waiting且心跳推进。PID是本次观察，维护继续核控制ID与创建时间。

## 实际更新结果

安装后的完整27来源手动刷新耗时253秒，成功发布`5b00a15761ae88adf8e1f14492e6491e37b63ac161b09840f42624505424d683`，其中全A输入处理成功约1.07秒。随后原常驻调度自然执行11月3日09:00窗口，09:03:10完成并发布`d0115604a5ee80535f9a7eee402dc5c2f21ca5e14a31ad24c81b496491a8d5a8`。该窗口实际339次HTTP/SDK请求，27来源中20项success、4项checked_disclosure、3项failed；整体partial。保留原完成窗口、尝试和历史数据，未复制隔离成功状态。

72组目录中45组尾日为最新已收盘交易日11月2日，另6组高管披露尾日为11月3日。全A六组广度、Breadth Thrust、MSI、RANA、TRIN及换手占比到11月2日；年度、季度和月度资料仍显示实际报告期。高管数据按已披露变动日回溯，披露可能晚于交易发生日，历史也可能随新披露修订，属于每日抓取的已披露资料。更新计划保持北京时间09:00、17:30、21:00。

本次仍失败的三路为银行间回购权限拒绝、指数背景`market_existing_coverage_missing`和T2108输入未就绪。各路旧合格结果及原日期保留。原月频全A PB与当前独立日频PB属于不同口径，历史资料分开；数据日期、来源成功与系统进程存活分别判断。

T2108当前停在10月30日。原全池工作流已留下349份准备记录，末项仍按原ID核查；进程退出和监督脚本误分类均保留证据。三只未准备股票的原v8缓存实读有82期正前复权收盘，均缺11月2日；不能把缓存读取成功算成最新指标。后继在原编排层实现先读缓存、只准备实际缺口、再次实读封存，原349个请求和既有资格保持。

## 账户与报告的当前边界

09:11页面仍读到原49279控制最后发布的ready，发布停在04:46，开发者2已核其原进程及子进程退出。该磁盘状态不证明当前执行存活。策略现金余额633,075.20元及100万元基准保持，当前可用资金为空：资金约束仍停在01:01、01:06到期。账户查询曾持续推进到04:46，根因为成功查询后的结果发布超时中断后继刷新；自有发布流程修正与缺关闭凭据时的恢复由执行所有者继续，尚未接收新的上线身份。本记录更正[00:32短时恢复](2026-11-03-observer-market-account-current.md)之后的当前状态。

当前a93真实浏览器入口`/strategies?tab=backtests`已验收列表、400条日末绩效、四页导航和初始化/买入/达到持仓目标三种单日详情。报告为既有1.1.2真实市场输入的原生历史模拟，结束日2026-10-28，模型本金120,000元、收益率2.9904%、最大日末回撤22.3823%；模型本金与当前策略100万元独立。桌面1440×1000的页面有实际内容、净值图、持仓表及交互，控制台/框架错误0。本轮没有重跑或新建回测，未把历史模拟提升为实盘资格。

证据根为`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：`A94-ACTUAL-FULL-REFRESH.json`、`A94-UPDATE-STATUS-20261103-0913.json`、`A94-UPDATES-20261103-0914.json`、`A94-ACTUAL-MARKET-20261103-0914.json`及`report-browser-20261103-001/RESULT.json`、report.png。完整报告来源审计在`E:/workspace/wondertrader-qa/retained-quote-preparation-20261102-001/reports-audit001/HANDOFF.md`。Browser插件未提供，沿用户已授权的Playwright验收，只读观衡。

## 维护与回退

在PowerShell读取上述稳定更新定位，核控制入口与PREPARED摘要，再沿原入口维护：

```powershell
$update = Get-Content -LiteralPath E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $update.controller -Algorithm SHA256).Hash.ToLowerInvariant() -ne $update.controller_sha256) { throw 'Update controller changed' }
if ((Get-FileHash -LiteralPath $update.prepared -Algorithm SHA256).Hash.ToLowerInvariant() -ne $update.prepared_sha256) { throw 'Update preparation changed' }
& $update.python -I -B $update.controller status
# 需要维护时单独执行stop；取得同代closed后才能start。
& $update.python -I -B $update.controller stop
& $update.python -I -B $update.controller start
```

这些命令仅管理独立市场更新角色。Web正常启停仍沿其DEPLOYMENT和[运行手册](../runbooks/observer-runtime.md)，WT/QMT继续由其所有者维护。停止、未知和失败的界线沿[市场观察手册](../runbooks/market-observation.md)，保留当前实例及原请求；确认关闭后升级或回退，数据根、窗口和原件保持。a92为保留的回退安装，若回退会恢复重复网络读取的旧行为，先核新数据合同兼容并正常停止a94。回退维护定位应重新记录实际新控制身份，禁止照抄本代PID。

持续日线与50指数配置已合入`68f4f42`并在干净主干通过文档检查；现场配对/启停和自然开市收盘资格仍待统一接收，见[候选范围](../evidence/2026-11-03-continuous-native-day.md)。本次Root没有QMT界面操作、金融命令或WT框架修改。
