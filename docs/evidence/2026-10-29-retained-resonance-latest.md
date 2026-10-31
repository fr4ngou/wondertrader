# 唯一保留策略与最新正式在用版本

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：用户范围确认与只读来源核实。日期：2026-10-29。状态：策略归属/版本/原参数材料已确认；实际券商持仓接管与运行另验。

用户明确当前只有“共振市场状态ETF策略”运行、全部当前券商持仓归它；本次只保留该策略最新版本，之前版本不需要。对应唯一策略为resonance-regime-v1，其他策略/候选及旧版本退出运行入口、页面选择、发行依赖和开发验收范围。通用行情/账户执行、多策略扩展接口与恢复保持。历史交易记录不迁入，历史K线保留；封存历史证据与原QMT项目只读。

## 最新正式在用规则来源

旧项目的实际启用记录2026-10-20受控启用验真（D:/workspace/qmt/docs/process/entries/2026-10-20-stoploss-controlled-activation-verification.md）说明1.1.2已激活、原生配置核对和目标采用通过。机器原件位于独立诊断存储E:/workspace/qmt-storage/diagnostics/stoploss-activation-readiness-20261019：final-delivery-clock-stable.json、final-runtime-clock-stable.json、final-runtime-execution-integrity-released-1556.json、target-config-draft.json。

受控捕获同时核：启用passed、active_simulation_112和native_matches_current_config为true；最早/较晚两份实际运行记录与目标配置的config_id/version相同，均为direction-v2026101901；实际workbench策略为1.1.2，六参数和预算与目标配置完全相同。最新该批来源捕获时间为2026-10-20T07:54:28.876610+00:00。早期activation-current-active-config.json是升级前2026093001，已明确排除，不能拿它代替生效后参数。

1.2.0属于另一可配置角色分支，数字较大不能证明包含当前1.1.2账本周期与前复权规则。本次锁定最后已确认正式在用的1.1.2，避免迁移时静默更换规则。没有把原注册表默认1.0.0当作实际版本，也没有把QMT终端AI_ETF名称当作业务算法ID。

## 可消费材料及边界

CONFIRMED.json（外部历史/待归仓路径：`../../build/retained-resonance-latest-001/CONFIRMED.json`）绑定四份源原件摘要、参数/预算相等事实及私有材料摘要。私有strategy-source.json仅含实际版本、六参数、策略预算比例、八个信号证券和来源时间，按原private_files工具建立；这是只读迁移来源材料，明确execution_enabled=false，不是可直接运行的配置。预算归实际策略配置，不把账户全部现金自动当策略预算。

没有复制凭据、原自动执行权限、成交/资金流水、旧持仓数量或周期状态。券商当前持仓另行查询；用户确认其归属后，由B复用WT原生策略状态/组合形成接管候选，C实现唯一1.1.2纯核和参数/页面/回测。开仓时间、成本及止损周期初值需要按可取得的券商/WT事实形成明确映射；历史快照不冒充当前券商持仓，不以数量相等推断连续周期。

捕获312使用已安装HPR解释器、只读JSON、无数据库或QMT请求；0.391秒exit0、树0/EOF/join/句柄回收。新材料位于WonderTrader独占运行目录，后继运行不读取旧QMT项目。实际券商查询/策略接管、唯一版本源码收敛、完整回测/实时执行及生产资格继续开发，未做真实下撤单或生产切换。
