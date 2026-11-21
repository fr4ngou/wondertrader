# 观衡146与只读WT55市场观察历史发布

状态：deployed，新增图表正式页面验收通过；融资末日外部缺项单列。用户已授权实施、发布及通过其他来源补齐回购历史。2026-11-22本机正式18143正常接续。

## 发布身份

源码 `bded553c7c8f6e1f34b93b4a6127ac2fd9ca568f`，标签 `guanheng-observation-history-20261122`。App `0.1.0a146` 与只读日线 `0.2.0a1+unified.55`。观衡包清单 SHA256 `ab8494c44328bd9d4f98d5e0818e0b2f7ecae94e921913f59c5ab53213d8c683`，WT清单 `eddd91901cbfa91036794a38207218c2b39371ccd6a4c39901834385c0debb66`。普通安装于 `E:/workspace/wondertrader-data/observer-programs/a146-observation-history-20261122-001` 和 `wt-programs/unified55-observation-history-20261122-001`。

原正式观衡145、只读日线54正常关闭；原金融运行、账户、持仓、下单开关读取环境保持。新分母采用用户选择的供应商公告金额，免费公开查询不依赖Key/积分。取消后续旧回购执行增量抓取目标，历史原事实保留。旧29路观衡采集职责保持。

## 验证与入口

本地CI文档及516项软件回归通过；251项根因调用链回归通过；独立审查未发现功能阻塞。实际历史、公式独立复算、同屏选择和每张图截图见[完整验收证据](../evidence/2026-11-22-observation-history.md)。

稳定 `observer-current/web-profile.json`、`DEPLOYMENT.json`、`UPDATE-DEPLOYMENT.json` 均同步146；沿正常服务控制器启动且命令结束后存活。09:00、17:30、21:00调度已恢复，启动补数浮层实读。只读WT沿 `observation-update/unified55-observer146-history-20261122-003/wt-service.json` 纳管；三个原启停/自启操作组已同步。新目录保留112个已登记原REQUEST和全部已发布数据，原任务目录保留。

## 剩余风险与回退

融资2026-11-20的全国报表原源仍空，券商图截至11月19日有效；后续沿原owner采集。科创、小盘采用明确公开的观衡研究公式；原作者未公开的事件条件保持未知。回购以供应商当前公告金额、减持以可计价估算额展示。

回退配置和入口字节保留于146控制目录的 `BEFORE-*` 及 `GROUP-*-BEFORE.json`，原145/54安装及历史数据保留。需要回退时正常关闭新网页/独立日线角色后采用原bootstrap和profile，再核原地址及数据读取。回退不撤销已归档的数据事实。
