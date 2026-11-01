# 观衡策略、账户与报告详情

类型：模块接口正文。状态：开发与模块主路径验收完成，组合安装待集成。需求沿[OAR-06/07/08](../specs/observer-acceptance-repair.md)，职责沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。实际结果见[验收记录](../evidence/2026-11-01-observer-strategy-report-acceptance.md)。

## 数据与界面

`GET /v1/ui/strategy-details`提供`guanheng.strategy-details.v1`只读展示投影。当前唯一1.1.2，现有账户持仓按用户确认归属它；账户观察仍使用原NAP或原business_observation，原持仓数量、可卖、市值、资金字段及各组时间保持。归属属于本次产品展示约定，旧成交和开仓历史不迁移。

账户总资产、可用资金、冻结现金分别复制券商字段；来源没有总现金时保留未知。策略预算只从已经准入的WT策略结果中读取原policy.initial_capital_cny；账户现金不作为策略预算。累计收益缺少起始本金、现金流和连续净值基准时保持未知；当前持仓浮盈作为独立金额展示。未启动执行器时状态为not_started；ready不作为策略已经计算的证明。开始时间和运行时长仅使用原发布者提供的事实，缺少时说明原因，文件修改时间不作为开始时间。

新接口共享原App读池和2秒总截止，分项读取错误只影响所属字段；每项保留状态/中文原因，顶层不返回凭证、原部署路径或私有运行身份。原`strategy-runtime.v1`保持兼容。

`GET /v1/ui/wt-instances`提供`guanheng.wt-instances.v1`。主账户实例沿原ConsoleSettings；可选`GUANHENG_WT_INSTANCE_CATALOG`指向显式JSON文件，最多7个补充实例，每项为`label`和`wt_status_file/wt_control_id/wt_instance_id/wt_configuration_sha256`。复用原WRI身份校验，按实例独立投影状态；失败实例保留中文原因，其他实例继续展示。浏览器仅见标签与不可逆scope摘要。文件最大64KiB，不扫描目录，不创建或控制WT。

回测沿原`BacktestArchive`完整原件校验及5秒截止；补充`GET /v1/ui/backtest/source`仅报告归档配置/目录状态。未配置、配置路径不存在或类型错误、已配置空目录、已归档、完整性错误分别解释。归档为持久原件，WT停止后仍可读取，在线运行状态不作为报告读取前提。SDK演示及实验资料保留原模型资格，不作为正式策略回测。

## 验收

真实NAP四项持仓→策略详情→数量/可卖/市值/账户资金；原无execution实例→未启动及未知起始时间；累计收益保持真实缺失原因。补充原行情实例→分实例组件状态。原正式WT归档根→列表→绩效→逐日详情。随后覆盖未配置、空、错误路径/格式、停止、局部失败和刷新保留结果。主会话负责最终配置、源码清单、组合安装及18120切换。
