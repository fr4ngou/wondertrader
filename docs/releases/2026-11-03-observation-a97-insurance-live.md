# 保险原表独立更新与四处页面核实

类型：本机来源接续部署与用户入口验真。日期：2026-11-03 12:24。接续[独立账户24](2026-11-03-observer-account24-received.md)与[保险来源隔离验收](../evidence/2026-11-03-insurance-allocation-continuation.md)。

## 用户入口

观衡仍为`0.1.0a93+status.1`、http://127.0.0.1:18143/ 。真实总览只显示账户资产、可用/冻结资金、三类记录数和快捷入口，具体策略未写入总览。桌面1440×1000及手机390×844实页已验，刷新有效、页面异常0、手机无横向溢出。系统状态实页显示账户WT及四组件就绪；账户批次在12:24仍推进，5持仓/2委托/1成交。策略执行当前明确`not_started`，资金保持空值；原理论账、只读目标边界及实际策略计算由开发者2继续，尚未接收正式完整后继。

高管六组资料截止11月3日，覆盖2025-10-30起370个自然观察日；页面保留“已披露资料，非盘中实时”说明。独立计划为北京时间09:00、17:30、21:00，事件按实际披露后可见的变动资料统计，公告与发生时间分别保留。此频率与季度/年度资料的报告期分别表达。

## 来源根因与实际交付

原保险来源只检查官网披露页，没有将资金运用XLS数字送入序列。新`nfra_insurance`沿原来源ID、列表、同身份详情及XLS原表接回数字，比例及亿元口径保持。已合入`6632802`，干净主干完成普通构建和离线安装；固定xlrd 2.0.2纳入原registry/锁与完整依赖闭包。构建器数量校验按实际锁登记计算，精确包名/版本/逐wheel SHA检查继续保留，本次25项第三方加6项自有发行共31项。

独立更新角色已切至`0.1.0a97+insurance.1`。旧a96经原controller正常关闭exit0后启动新角色，控制`1efc0f1f-e84a-4ada-842b-dc86ccc98ef1`，启动PID5292、监督PID52092及原创建时间匹配；12:24心跳推进、waiting。Web、WT、QMT及金融命令均未操作。28路配置只改变原`nfra.disclosures`的数值适配，其他来源、模型、日历、预算和计划保持。

新安装沿原refresh实际访问官网成功，当前快照由`680ebf7a86302e8abe501c3a5efbff053ac921d72cb1a64564abffb5f9d78a0e`变为`f874c6f961d622d27668586426b04cfc85c447a7fdb2419afebc6ee0f6a93bff`；寿险/财险各6条原历史及定义版本保持，其余70组完整记录、源表和股票分区保持。官网最新资金表仍是2026Q2，公布于8月14日；寿险债券占比51.208351400693296%，财险40.50727114445173%。保留真实6月30日期次，不把本次查询时间写成新报告期。当前Web/API已消费新快照，寿险图表“全部”范围展示原6条、两个画布且错误0。

## 制品、维护与回退

ZIP SHA256`73c067115862f92d52ed44dbcc4c105faf524fb4b78d12c42e8ad049d74ac901`；包清单`ee830231308ccfad6120ad701247e0dee63487ffe338cfbee49e9d7843e92c80`；角色清单`0b2e01ec681e75239899f3f0d612749f5bad4ecbe9abed54fac822a45d07f709`；安装收据`b0e8d4aa642a22c861d61c0010abc167513e3839111e4e2d31a1c196fc09e65c`。

稳定定位`E:/workspace/wondertrader-data/observer-current/UPDATE-DEPLOYMENT.json`已原子切换；配置SHA256`32c77cb6bb8be542328efb8aa17bc6242778a8df10aecb82ae7f93f4d7c10519`，部署SHA256`f8f8a34666c592ba746b87c6b322976c159265b98c3575bbb14048eaa457c067`。运行目录为LocalCache/Local/Guanheng/observation-update/a97-insurance-20261103-001。status/stop/start沿原独立更新控制入口；回退时正常停止a97，再用原a96配置启动其原角色并更新维护定位。旧a96不读取新保险kind，两组已发布数据保留，其他来源持续；禁止将旧配置改指新kind。

原件在`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`的A97-UPDATE-PREPARED、A97-ACTUAL-INSURANCE-REFRESH、原启停/status收据、UPDATE-DEPLOYMENT-BEFORE-A97及user-four-findings-20261103截图。源码/配置CAS与原官方材料在`wondertrader-data/insurance-allocation-20261103-001`。构建Temp/root-observer-a97-insurance-build-001；原独立安装目录observer/0.1.0a97+insurance.1。原已验68项根因回归复用，本次验证新增固定依赖闭包、实际安装、运行和公开用户入口，未扩大无关测试。

## 仍需完成

策略资金和自然行情计算尚未恢复到当前页面；账户读取已恢复。SGX日/月数字生产者由开发者1交付，部分其它外部数值来源仍有缺口。全A006在原owner和绝对截止下继续，最终回读与质量通过后才接T2108；原生日线/50指数现场切换另行统一维护。自然下一季度披露与下一调度窗口尚未发生，本次仅授原表实际读取/持续生产实现资格。当前无新增用户审批项。
