# 共振 1.2.2

八角色策略，科创角色的信号、执行、实际周期及前复权历史统一使用博时科创100 ETF（588030.SH）自身数据。其余七只证券、资金策略、实际开仓止损和首次库存基准保持。

正常同账换代通过 `role_replacement` 显式引用原执行配置；原始库存、现金锚点和100万资金基准不重置。旧589680实际持仓为零且原自有挂单已撤清后，退役原冻结NSQ计划，使用当前实际持仓重新规划。WT原生证券过滤器保留旧理论账并过滤退役证券，不生成假卖平。新基金若已有本轮实际验证成交，以完整券商成交和原flat基准核实真实开仓时间。

## SDO业务诊断候选

类型：模块接口及专属交付说明。状态：candidate，现场采用由Root统一处理。合同沿[SDO](../../../docs/specs/strategy-data-and-observability.md)。包后继为0.1.0a12，策略算法身份继续为1.2.2；Shared Core、信号阈值、目标、持仓和资金规则保持。

完整实时和历史纯核都向 `validate_observations` 显式传入本版角色 `SYMBOLS`。588030的准入由角色所有者提供，Core默认/测试集合保持原用途。当前版本仍拒绝其他物理证券作为该角色，旧报告的证券从其原捕获与配置读取。

`RetainedResult.to_dict()['diagnostics']` 为 `guanheng.strategy-business-diagnostics.v1`。`describe_evaluation` 也接受已冻结原事实和已有机器结果，供报告读取复用；计算和来源取得均由原owner执行。

| 字段 | 含义 |
|---|---|
| calculation_state/error_code | 未调度、行情未就绪、预热、输入拒绝、计算失败、完成及原稳定原因 |
| input_range/evaluation_range | 完整输入及实际交给信号机的日期范围、应有日期数 |
| roles/symbol/role | 本次实际证券与业务角色；历史角色显式提供映射 |
| field_coverage | 每个实际依赖字段在两范围内的应有/非空数、首尾有值日期及缺失计数 |
| auxiliary_fields/branches | 原规则读取哪些辅助项、哪些分支输入不可用；不改变原条件 |
| input_state/latest_missing_fields | 当前评估日的字段缺口，行情与辅助缺失分别记录 |
| signal_counts/latest_action/signal_state | 原模型BUY/SELL次数及当日转换，区别于原生目标提交和成交 |
| last_successful_calculation_date | 原信号机成功完成调用的最近日期，合法None字段仍可存在 |
| last_fully_informed_date | 全部角色依赖同时有值的最近日期；辅助缺失时保持None |
| target_state/execution_state | 产生目标、比较后不变与独立执行状态；无执行证据保持not_observed |
| auxiliary_availability_model | 默认actually-received、显式研究模型或旧输入声明未知 |

`None`是缺失，明确零和负份额变化仍计为已有值。缺失原因只从已存观察得到 `observation_missing` 或 `not_supplied_in_observation`，不会把空字段猜成特定来源超时。CSI300只有部分辅助灯缺失时仍标为部分观察；SH50/KC50及部分其他角色按具体份额分支列缺口，价格退出等原独立路径保持原规则。

`RetainedValidationError.diagnostics` 只携带原失败阶段和原因；没有取得完整输入覆盖时保持未知，不追加昂贵计算。有效但不足百日的完整窗口为warming_up，异常输入先按原准入拒绝。

## 显式历史辅助研究

默认 `evaluate_current_view` 拒绝任何 `auxiliary-research:` 行。默认历史模型也拒绝研究行；操作员须显式执行：

```python
model = market_model.with_auxiliary_research(request.history, declaration)
result = evaluate_historical_model(request, model)
```

声明由唯一辅助合并模块产生，固定模型 `research-next-common-session-0925-v1`。声明保存原数据/派生/发布清单SHA、策略/模型身份、真实辅助取得首尾时刻与历史首次未知，历史因果/实时资格均False。模型另绑定实际合并后FrozenHistory的SHA，全部行必须保留同一研究标记；回测每个截止前缀独立绑定输入，批次和声明保持。原市场15:00/最终复权模型与辅助09:25研究假设分别表达。

正常实时 `auxiliary_available_at <= 当行15:00收盘` 约束保持；研究输入不写回实时文件。研究原件来自开发者1最终普通安装的导出，模块不重写辅助公式或已核种子。

## 原生报告与历史兼容

WT回放在报告末日保存一次完整诊断，逐日保存 `guanheng.strategy-business-diagnostics-summary.v1`，避免重复整段字段覆盖。原完整结果摘要继续绑定实际纯核结果。读者沿WT `backtest_reports.project_business_diagnostics` / `project_input_business_diagnostics` 及现有单日投影读取；观衡只转发，不增加UI布局或第二算法。

旧1.1.2/1.2.1报告由只读 `ReportIdentity` 使用其原版本和实际八证券，不切换全局身份。当前1.2.2仍核当前角色。实时经济目标投影仍严格核当前版本；归档只读投影与它共享同一原投影/NSQ逻辑。旧报告缺诊断字段保持可读，从已核原输入补字段覆盖解释；未保存信号次数保持None，不能补成零或据空stderr推断成功。原报告、请求、费用、持仓和原生成交保留。

## 验证与采用

专属回归：在匹配普通安装候选的Python中执行 `-I -B -m unittest discover -s tests/integration/strategy_diagnostics -v`。覆盖完整纯核双入口、角色缺口、零值、预热与输入拒绝、目标/执行状态、研究默认关闭与标记/摘要约束。真实归档及原DLL回测另在独立QA根验证，路径与固定SHA由最终HANDOFF登记。

Root组合开发者1的 `auxiliary.py` 与本模块源码后重建V1、WT报告业务接缝及观衡只读闭包，核固定安装SHA，再沿同账采用。单独复制运行环境源码不属于采用步骤。回退恢复原包/只读闭包及原服务描述符，保留所有新旧回测根、原件和金融状态；研究会话按其固定安装读取。当前现场启停、自动交易和页面验收由Root处理。
