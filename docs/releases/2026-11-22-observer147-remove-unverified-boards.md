# 观衡147撤下两张未核实图表

状态：deployed。按用户“先把这两个找不到公式的图给删了”授权，撤下“小盘弹性独强，但成交未接力”与“成交集中度、市场宽度与科创承接”。原作者公式缺失及数值、日期差异见[研究对照](../research/2026-11-22-original-structure-formulas.md)。后续推导范围结束，原历史数据保留。

## 实现与验证

页面统一目录排除两图及其指标和近期事件，单图、多看板、布局恢复、指标说明和导出共用该目录。旧单图链接回退到可用指标，旧多看板链接只打开仍有效的看板。后端历史目录与分区沿原归档保留。

源码 `678830874a85d563d534278028506d016be54f15`，注释标签 `guanheng-remove-unverified-boards-20261122`。前端3文件29项回归、TypeScript类型检查及独立审查通过。本地CI `D:/wt-build/observation-remove-boards-ci-20261122-002/RESULT.json` 文档检查与516项软件回归通过并合入master。此前001因验证期间输入变化失败，原失败收据保留；最终冻结输入通过002。

## 正式采用

App `0.1.0a147` 普通制品构建、普通安装至 `E:/workspace/wondertrader-data/observer-programs/a147-remove-unverified-boards-20261122-001`。包清单SHA256 `9a5b048fc51193c5e0cf17b85ccec4cafe3660f03b0f7c403e3914a86e769606`；ZIP SHA256 `3ee17d1c3dffdb0d81fc371fb8f834141121607c492659f9241716ca4539b526`；安装清单SHA256 `00bac9fa0b8651f5fd4e2acbc0c0b21460db426c5beec0daa7ceeea719ecfa85`。完整构建保留于 `D:/wt-build/observer147-remove-boards-package-20261122-001`。

正式地址仍为 `http://127.0.0.1:18143`。146沿正常控制器关闭、OS退出码0；147正常启动，启动命令结束及页面验收后仍ready，PID58876、控制身份 `d6ac1921-8b50-4777-ba55-fa84357b42b1`。稳定 `observer-current/web-profile.json` 和 `DEPLOYMENT.json` 已同步；读取环境SHA `626743631ddeee8942492923500a905c4f3bbf3016d022837a2f4e79452f7518` 完整继承。原独立采集调度146与WT55保持，`UPDATE-DEPLOYMENT.json` 和WT日线CURRENT前后逐字节摘要一致。

正式Chrome页面已核：导航从17项变15项；多看板选择器无两图；旧组合链接仅打开ETF净申赎，六ETF选项和实际曲线可读；两图旧单图链接均回退；指标说明、导出指标目录无两图；原沪深300ETF占比6个月124条记录仍可读，末值2.2522%。截图与启停、状态、保持原身份收据在 `E:/workspace/wondertrader-data/observer-remove-boards-20261122-001`，截图 `UI-a147-boards.png`。本次运行代ready存在、failure/closed/OS_exit均空，延迟打开的web.log未产生；该事实仅代表本轮无已落盘Web警告，既有数据来源缺口继续沿原146证据。

## 回退与范围

原146安装、`BEFORE-*`配置和历史分区保留在上述受控目录。回退时正常关闭147，再按原146profile启动并还原稳定入口，核原18143与实际数据读取。本次不改变交易、账户、WT数据或原29路自动采集职责。撤图的页面验收完成；原146剩余外部融资缺项按[前次记录](2026-11-22-observer146-history.md)保留。
