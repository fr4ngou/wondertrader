# Data28历史计划接续与只读数据组自启

状态：Data28和数据组自启已采用。2026-11-07北京时间验真，范围限日更及四个既有只读服务；金融运行另行核实。上次发布见[观衡126及Data27现场](2026-11-07-observer126-parallel-readiness.md)。

## 发布身份

普通Data28 `0.2.0a1+unified.28`、SDK21，源码`616101b7275d9334ee5f4b2b130ba9ef87be187e`，制品SHA `357e08c806ab9fb79dbba6155dcba5e740709e0fc8ca3d46c9fdc460c8484cd8`。安装于 `E:/workspace/wondertrader-data/unified-daily-20261104-001/program-history28-20261107-001`，Source19与原Runtime实例及稳定入口共用既有目录，TEMP和任务保留在D盘。Source19 service.json SHA `65e62c01e5521b530638ebbc19ce89b8e6ac0fc23b8499b02e04ede2b63d8f93`。

## 根因与采用

原自然价格已成功发布，完整更新在准备阶段读取11月3日原gap-plan时拒绝旧五字段保护行。旧写入合同有效；统一读取边界按确切旧形状识别，并把缺失状态按未知处理。现行写入仍使用完整合同，原2890行、计划SHA、保护槽及原请求保持。独立复核及24项验证覆盖实际准备路径和保守重叠行为；普通安装实读原历史计划通过。旧Source18正常关闭后，Source19由原服务入口接续同一日更，旧配置、数据及请求保留。

Windows任务 `Guanheng-Data-Group-Autostart` 在交互登录时启动，并每5分钟复用既有数据组start。调用限历史补齐、证券资料、日更批读、日线资料，运行策略与交易不在该组。已运行服务保持同PID。正式运行期间，日更时点及恢复仍由原日更owner管理。

## 发布后验真

- 10:42手动调用和10:44自然调度返回0；四个角色ready、进程与上一观测一致。10:49下次自然调度也返回0。登录触发已配置，实际注销或重启未测试。
- 09:00自然轮次处理最近闭合市场日11月6日。140次回读完成，价格先行发布：CURRENT SHA `d22074fde5b21cae879b4c0d50ce419b3c307636b9a5c8527957871cb0aa5765`，原价7950项、前复权7897项。Source19实际已越过旧保护计划校验并开始补充事实回读；该自然轮次完整辅助事实发布尚待核实。
- 实际HTTP原版输入校验发现原价单位回退：510050原选中004档的1902行均为CNY/lot，新发布原价落回旧003的六段来源，部分为unknown，前复权仍保留已核单位。构建原价时先移除选中004层，再以旧Reader为同日首选，导致未移除的003盖过004相同日期。保持原件和真实未知值；下一次修正需保留已核历史来源及新Native有效日期，并用普通HTTP复验。

## 回滚与证据

自动启动可在任务计划程序中先禁用，等待正在运行的启动动作正常退出，再按原入口移除该任务；四个数据服务由原组生命周期分别控制。Data28程序与Source18均保留，后者重接相同旧任务会再次遇到已知历史计划解析问题；不得用重置原任务替代恢复。未执行回滚。

受控证据根 `E:/workspace/wondertrader-qa/original-live-readiness-20261107-001`：`DATA28-BUILD-INSTALL001.json`、`DATA28-ORDINARY-LEGACY.json`、`DATA28-SERVICE-ADOPTED.json`、`DATA28-GROUP-STATUS.json`、`DATA-AUTOSTART-REGISTERED.json`、`DATA28-NATURAL-POSTFLIGHT.json`（SHA `89bd680590b5f2190d81059e70811497cbe13a02b60f55c347d00a2c978c3464`）和`DATA28-ACTUAL-HTTP001.log`。
