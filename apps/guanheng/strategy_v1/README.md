# 唯一共振策略1.1.2

`evaluate_current_view(RetainedInput(...))`复用共享特征、八信号机与原分配，按外部已核实际持仓周期补充止损，输出完整八目标及下一退出状态。输入可用`RetainedInput.from_dict`从固定JSON解码。当前唯一算法为`resonance-regime-v1@1.1.2`，旧版本入口及pipeline已移出发行包。

配置沿已核六参数和策略预算比例。B提供原生持仓周期、捕获/有效期及原生策略退出状态；A提供同一基准的前复权分析价、原值映射、来源/因子身份与实际知晓时间。未知周期、实际新成交周期缺开仓行情、未来输入和错复权配对拒绝。当前可见历史重建与历史逐时点可获知资格分别声明；金额保留unknown且不参与算法。

当前券商持仓可作为`PositionCycle(status='initial_inventory', quantity=..., cycle_id=..., source_sha256=..., opened_at=None, baseline_at=...)`进入新运行。带时区`baseline_at`由B持久保存且不晚于周期捕获时间；同一批初始库存基准一致。旧开仓时间、交易流水、年龄、峰值和退出记忆均不导入。严格晚于基准的首个分析收盘形成参考价并从年龄0开始，其后共用原1.1.2规则；参考价形成前年龄0。基准早于提供的行情窗口时返回`initial_inventory_history_missing`，B补齐新运行后的行情并保留原基准。新系统重启延续同一基准和新状态。沪深300保持原模型分档规则。flat/held省略空的新增字段，旧规范输入和结果保持。

`validate_retained_configuration(RetainedConfig(...))`供配置服务检查正式版本参数，成功返回None，失败为RetainedValidationError。它与实际决策共用同一规则；调用为纯同步计算，零IO，未授予数据、周期、资金或执行资格。

包只依赖共享`guanheng-strategy-core`数学与tzdata。计算零文件/网络/线程/账户调用，有总期限与容量限制。结果为独立规范值，数量、费用、T+1、委托撤单、状态持久化及恢复继续归WT原生owner。合成模型明确`synthetic-model`，纯计算不授真实来源或执行资格。完整规格见仓库RR112。

`evaluate_historical_model`显式接收`RetainedHistoricalModel`，复用同一规则回放最终批次的历史前缀。它保留实际接收时间，并声明日末可用和最终基准前复权假设；结果使用独立历史schema。`evaluate_current_view`保持实际接收不晚于决策的原约束。结果中的配置摘要供App固定接缝连接原NSQ完整八目标；回测假设不进入实时准入。
