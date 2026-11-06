# 共振原版独立参考策略

这是用户指定的 [OrangesHuang/Resonance](https://github.com/OrangesHuang/Resonance/tree/351f9d58152e10efd2447c997b8ee4db66b5ac6a) 固定原版离线入口。策略标识 `resonance-original-351f9d5-stable`，依赖Python 3.12+和标准库。源码、数据和输出各有独立身份，现有1.1.2的规则、默认入口及运行配置保持。

该包在独立子进程运行上游34份经过SHA-256核对的纯计算源码，输出原版信号、五灯、组合曲线和数据检查。用户提供的上游检出保存在本机；本包保存自有适配代码及来源清单。当前上游未声明许可证，源码复制与再发行资格另行核实。

## 使用

仓库根目录执行，输出父目录须已存在，每次指定新文件：

```powershell
python -B apps/guanheng/strategy_original/run.py export --database "<原版etf_monitor.db>" --output "research/resonance-20261105/original-input.json"
python -B apps/guanheng/strategy_original/run.py run --source "research/resonance-20261105/upstream-resonance" --input "research/resonance-20261105/original-input.json" --output "research/resonance-20261105/original-report.json"
```

`export`仅通过只读事务读取原库已提交业务行，保存默认九证券及必要参考证券。可用 `--codes 510300,588000` 显式选择原监控标的；日历、成交额和融资序列保持完整预热。无需运行上游Web应用或安装其联网依赖。`run`默认最多120秒，可用 `--timeout-seconds`设定0至600秒内的正值。失败退出1；源码差异、错序、重复、非法数值和缺必要参考证券均返回失败。

上游参考检出可通过 `git clone https://github.com/OrangesHuang/Resonance.git <本地目录>` 获取，随后 `git -C <本地目录> checkout 351f9d58152e10efd2447c997b8ee4db66b5ac6a`。运行时对照随包 `source_manifest.json` 核验实际内容，分支名不能代替内容校验。

## 输入和报告

`export`生成 `guanheng.resonance-original-input.v1`；也可以提供相同格式的冻结JSON，顶层为：

| 字段 | 含义 |
|---|---|
| schema / upstream_commit | 协议及固定原版提交 |
| data_kind / source | synthetic或historical-final；来源、采集时刻、复权说明及未知可知时间 |
| units | 价格CNY/share、份额1e8-share、市场金额1e8-CNY、成交量保持原来源单位 |
| codes / daily | 交易证券与按六位代码分组的升序原etf_daily行 |
| turnover / margin | 日期及total_amount_yi / fin_balance_yi，原事实日期保持 |
| calendar / evaluation_start | 原交易日历、组合信号裁剪起点（默认2021-01-01） |

日线字段由 `reference.py::DAILY_FIELDS`固定。辅助事实缺失保留null，不能以零冒充无申赎，也不能把589000映射为589680。原库若没有复权/首次发布时间，快照仍保留未知。

报告 `guanheng.resonance-original-report.v1`包含：

- `strategy_results`：全部预热历史的原路由结果。其轮次收益可能按信号收盘计算。
- `trades_by_code`：按起点筛选的原BUY/SELL信号。
- `resonance`：五灯及历史，独立于专属交易算法。
- `portfolio`：原组合原始结构，history、trade_log、收益、回撤及未平仓结果。归一化初值1.0。
- `data_audit`：输入覆盖、缺失、日历缺口和可复算派生字段比较；不匹配保留实际计数。
- `model`：原成交时点、分配、零费用、浮点份额、历史最终行和逐时点限制。

原组合在**下一交易日收盘**成交；首个买点可用全仓，新BUY按全部权益等权分配，SELL释放现金且其余仓位保持。费用、滑点、100份整手、涨跌停、流动性和券商约束需要后续独立模型验证。当前报告用于原组合对照，`execution_qualified`和`point_in_time_qualified`始终为false。观衡通过独立ORR只读报告族展示，正式WT回测采用独立original-native身份与人民币模型，分别比较。

## 只读报告导入

App维护入口接受显式manifest和现有归档根目录：

```powershell
python -B -m guanheng_app.original_report_import --manifest "<绝对路径import.json>" --archive-root "<已配置归档根绝对路径>"
```

manifest字段、原件摘要、分页和单位合同沿[ORR-06](../../../docs/specs/original-resonance-reference.md#orr-06-观衡只读目录与报告导入)。导入保留报告、输入、算法清单原件，完成证明最后发布；同run身份拒绝覆盖。该命令不重新运行算法，不改变已有报告或运行策略。

## 验证边界

数据检查只比较可由快照重建的字段：量比/量概率、完整60行窗口位置、无近期折算的份额概率、存量组件综合分数、recalc口径方向分数。原始seed与recalc使用不同方向口径，检查结果保持分项，回放始终使用输入已存行。真实首次发布时间、原始复权因子、缺失前部历史、折算附近处理和原作者收益复现需要相应原件。

规格和验收标准沿[ORR](../../../docs/specs/original-resonance-reference.md)，研究正文和具体证据沿[研究指引](../../../docs/research/resonance-research-guide.md)。构建使用普通Flit包，无须修改现有发行闭包；安装和生产切换分别验收。
