# 观衡123、原版WT现金及Data25后验真

类型：delta证据。状态：App与WT历史回测 verified；Data25原任务恢复 verified，完整新发布受原批读服务未运行阻塞。

机器结果统一保存在 `E:/workspace/wondertrader-qa/observer-target-cash-release-20261106-001`。源码归档 `APP123-SOURCE.json` / `DATA25-SOURCE.json`，普通制品 `observer-build002/BUILD.json` / `daily-build002/BUILD.json`，离线安装 `APP123-INSTALL.log` / `DATA25-INSTALL.log`。两个产品由干净Git导出构建；SDK20、固定Python及各自锁定依赖完整安装，无生产site-packages覆盖。

## App与实际页面

`actual-performance001/BROWSER-POSTFLIGHT.json`：App122实际列表1067ms、摘要请求547ms、未打开报告的绩效读取0、切策略26ms、返回45ms、悬停0 HTTP。App123后端144个Python文件与App122逐字相同，证据 `APP123-BACKEND-REUSE.json`；复用App122普通安装52项目标/线上/生命周期/归档回归，App123客户端完整重建。首次旧报告实际8278ms，新现金报告9107ms；预览较快结果单列，未冒充正式耗时。

`actual-targets002/UI-RESULT.json`：App123实际目标记录20条首页、三页42条、详情及策略切换清空、390px适配通过。原1160完整行的独立计数为变化33、首次9、重复1118。最终读取器独立审查覆盖原始文件配置身份、物理前缀修改、句柄、截止和坏输入；16项后端、7项客户端及12组独立断言通过。Root实际核看页面截图。

`actual-cash001/RESULT.json` 保留App122客户端只准a1导致真实a2页面失败的证据。后继已知版本身份统一，17项客户端回归及类型检查通过；`actual-cash002/RESULT.json` 在普通App123实际通过：新版1415日/407成交、负现金日0、实际收益/净值/费用匹配、旧a1的216负现金日及旧模型仍可读。Root核看桌面和390px截图，未出现浏览器/console错误或写请求。

## WT实际回测与归档

实际WT报告 `E:/workspace/wondertrader-qa/original-native-cash-20261106-002/runs/3529d7f374774ef3a6c0fe341d65ce31`；运行资格使用普通发行WT `0.1.0a20+snapshotwire.1` / SDK20，金融生产服务未采用本次回测源码metadata中的a21。源价格/日历与旧报告一致，原137个信号保持。`CASH-ADOPTION-MANIFEST.json`、`CASH-VERIFICATION.json`及独立 `INDEPENDENT-CASH-REVIEW.json` 保存在忽略研究根的 `original-native-validation`。逐成交/逐日复算无差异，费用22482.55、最低逐成交现金4.160、期末2842051.25、最大回撤21.676841528%。原生限价方向及费用预算另逐笔验证。

`CASH-STAGE.json` 固定新增28文件及保留224文件SHA；正式采纳沿旧App正常关闭后进行独立目录原子采用，旧归档未改。普通安装只读消费者直接重核新配置/完整绩效；最终页面新增一个a2版本报告，正式目录共9份WT，原ORR入口继续撤回。

## 日更恢复

`DATA23-STOP.log` 记录旧history正常closed及旧Runtime停止，OS确认20604/37780退出。`DATA25-ADOPT.log` 为history-only显式采用：Runtime31248/history57764 ready，控制代76416f9a-eade-46a2-a347-206e672280b7。原daily-v2配置SHA `3bf118d8d82506d22dfd5f446808f51130494b567444e3c31e2b667469ac1b56`、原request SHA `16a9eb2a8e0e343d198f65c8decbea1421d21f18f38e21581ee960e4a8f00836` 保持。

17MB原计划、30843保护槽、43任务的隔离恢复与最终独立审查位于 `E:/workspace/wondertrader-qa/gap-plan-recovery-20261107-002`；最终冻结SHA `e038f80ca2cfbcd6f3793eaac0de5fd8c09d8e37cc747df2b1248e2a9bc75d81`。实际恢复采用原计划SHA `693e751712dd8e35365e2f17789aa1bacf518d3934c73fb19b03fe3a2c8b7898`。00:33原owner越过gap_plan，43项原HPR准备结果均记录call_returned，并冻结了回读前的该状态；SDK逐槽独立复核通过。这些是HPR准备结果，完整价格覆盖仍由后续批读及Native回读确认。

`DATA25-ACTUAL-POSTFLIGHT.json`确认原回读REQUEST已固定，BINDING/slots/manifest均未创建；原批读端口61136无监听，HPR50885仍监听。SourcePending在此表示尚未准入新批次；没有已发批次可宣称已返回。原任务、计划、43个SDK核验原槽身份保持，自动重试继续。正式CURRENT的辅助日期仍11月5日；完整新MSF发布需要原批读服务恢复。Data25 ready与完整补数成功分别登记。

11月6日价格与补充事实来源检查在忽略研究根 `daily-auto-development/today-20261106`。九ETF原价/前复权该日可读；七SSE份额新取得；两SZSE份额失败、融资9201空结果/最新11月5日、官方成交额失败及代理单位未知均保持显式缺口。CURRENT的observation_date与price-first已包含的行情日期分别读取。

`WT-MARKER-READONLY-CHECK.json`与最终 `APP123-FINAL-REVIEW.json`确认金融Runtime31140/execution50960已退出，当前control7bcde9cb代faulted，页面marker false/exited正确；目标历史available保留。本任务未操作该金融运行、原账户及其他开发文件。开发预览/临时浏览器已正常关闭；正式App和日更继续运行。最终状态、剩余来源缺口及项目检查以同根最终机器收据及[发布记录](../releases/2026-11-07-native-target-cash-gapplan-live.md)为准。
