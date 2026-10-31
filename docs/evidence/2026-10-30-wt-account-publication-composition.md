# WT正式入口账户发布组合

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证证据。日期：2026-10-30。状态：限定SDK主链通过；真实QMT、独立观衡HTTP/页面和全系统发布继续。

## 行为与职责

普通离线安装的 WT 0.1.0a3 从正式模块入口管理原账户 Host 与原 NAP 发布组件。依赖顺序为 account_host → account_observation，停止按逆序进行。观衡独立消费原始扫描帧，金融字段由原 validator/projector 解释。

基础WT依赖仍为运行包和SDK两个发行；显式 execution extra 形成6发行闭包。此次安装只有host/wt角色，WT环境未安装观衡、FastAPI或Uvicorn。默认配置未选账户发布时继续原组件相对顺序。

## 输入与入口

- [WRI规格](../specs/independent-wt-runtime.md)、[NAP合同](../migration/native-account-publication-proposal.md)。
- 自有Runtime注册、版本、依赖声明及三项装配回归；B冻结的四份账户生产者源码未改，WT上游核心新增修改0。
- 普通安装结果（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/INSTALL-RESULT-001.json`）：192份冻结源码；host/wt普通离线安装和安装后13项装配验证通过。
- 整链入口（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/qa/main.py`）：QA使用原SDK账户替身和原C投影，实际WT子进程从安装site-packages正式CLI启动；Host及扫描均归WT。
- 源码与限定接收身份（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/ROOT-MAIN-001.json`）。

## 实际结果

主链结果（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/main001/RESULT.json`）与外层控制（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/control-main002/build-account-publication-main002/result.json`）：7.803504秒，exit0，无强制终止。

两轮共8次查询，每轮原生取得2持仓、1订单、1成交、1资金。SDK可用资金从82000变为82100，原C投影观察到同一更新；每轮50项原事实、6项浮点逐位一致。公开locator实际PID对应WT，Host PID与locator跨轮保持。1363份执行输入前后摘要一致。

WT、Host、Scan及SDK源正常关闭；内外Job树为0，管道EOF、读线程join和句柄释放均完成。原数据WT33636、Host46288、history60964、collection75000在本轮由OS核实存活，未启停或切换。

## 验证范围与剩余

本次SDK来源证明正式产品装配及原值更新。C独立HTTP/中文页面、真实四连接来源、唯一策略完整运行恢复和全系统安装/发布分别继续；真实下单、撤单为0。完整目标保持active。

公共契约/依赖变化触发独立full审查，范围为Runtime注册、默认兼容、依赖闭包和组合生命周期；原B内部实现沿自身独审。当前双轴full报告（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/review001/REVIEW.md`）已通过，P0–P3均0；根重核7源及17份证据身份一致，限定接收（外部历史/待归仓路径：`../../build/wt-account-publication-composition-001/ROOT-ACCEPTANCE-001.json`）不转授实际C页面、真实来源、执行或全系统资格。

## QA失败保留

旧control-install首次命中既有目录，发生于启动前；control-main001使用持久工具内残留QA路径，子解释器返回2，产品未启动，子树/EOF/join/资源正常回收。原件均保留。后继显式绝对路径及AST检查通过后才启动main001，未改产品或延长预算。旧失败与当前通过分别登记。
