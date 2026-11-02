# 观衡a92接收当前正式账户与资金

类型：实际开发环境接收。北京时间2026-11-02 23:43后，开发者2交付正式只读实例12i，Root沿原App业务投影核对后正常更换观衡绑定。用户入口保持 http://127.0.0.1:18143/strategies ，观衡版本仍`0.1.0a92+postclose.1`，本次没有重新构建或改变交易运行组件。

## 当前实际结果

策略页显示“运行中 · 等待新行情”，实际策略总资产1,000,000.00元、现金余额及当前可用均633,075.20元、持仓市值366,924.80元。原5项持仓、2笔委托、1笔成交继续读取；原历史交易未另迁移。累计历史收益仍未知，本次运行盈亏为0，未用100万元重构旧项目的历史收益。

系统页账户WT、交易通信、账户通信、账户更新、策略执行均已就绪；原数据owner后继亦已接收为当前“行情与历史WT”。个人观察、统一历史18148、市场观察数据根、独立盘后更新角色保持。总览沿账户级资金和数量显示，具体策略没有嵌入总览。

原账户查询持续更新，资金估值完成时间、持仓来源时间、原QMT报价时间分别保留。当前闭市报价仍为16:27附近；组件ready与新行情策略决策分开验收，策略分析窗口输入继续接线。

## 当前维护身份

- 正式WT控制`05e76323-4bd9-4c83-87ff-f97972398e84`，实例`a309716d-1288-4328-ac57-abd6ef0bb2e9`，配置SHA256`d751d43b73247e9f52e57bd18845f096e0b53fd4614bbc1d42d07957c0922d21`。
- 精确状态文件位于`E:/workspace/wondertrader-data/strategy-capital-real-20261102-001/wt-controls/05e76323-4bd9-4c83-87ff-f97972398e84/status.json`；接收交接为Root QA的A92-READ-RECOVERY-ACCEPTED.json，保留原12i版本，不依赖后续会变化的交接文件。
- 观衡稳定维护定位`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；实际profile为`observer-controlled-web-20261102-a92-read-recovery-001/web-profile.json`，SHA256`f75105ed806c3741d5dcd6ec8fb37ce446662a21b586b6bbc29afbe311a6988e`，Web PID12156。日常沿原控制身份及创建时间核实，PID只作本次记录。

原a92 Web正常关闭，Web与启动器均exit0、shutdown_complete=true。新Web沿原工具启动并通过实际策略、账户及实例API；浏览器核策略资金与系统页，pageerror=0。三个金融写入口保持关闭，本次Root下单/撤单均0。

## 验证证据与剩余范围

证据位于`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：A92-READ-PREFLIGHT、A92-READ-RECOVERY-DEPLOYED、A92-READY-PAGES，以及a92-ready-strategies和a92-ready-system-refreshed截图。当前恢复属于真实主路径接通；短时不可用后的持续接续仍由开发者2复验。

浏览器本轮另遇一次策略投影unavailable/资本空及一次额外数据实例读取失败，同期WT运行状态保持ready；正常刷新均恢复。原因尚未证明，原观察事实保留，不能将其报告为新一次Native执行退出，也不能据最后一次成功宣称所有瞬时读取问题已解决。

T2108与部分全A来源仍缺11月2日输入；完整v7/v8配对已与实际GH核一致，证券池及捕获原件接续单独推进。市场盘后更新已实际完成两窗口、43组最新行到当日，见[独立更新发布](2026-11-02-observer-a92-postclose.md)。报价消费回收与原采集接入见[实际行情恢复](2026-11-02-wt-retained-quotes-live.md)。
