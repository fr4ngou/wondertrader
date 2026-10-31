# 来源价格范围差异与历史导入修复

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发验证记录。日期：2026-10-27。状态：三个实际证券的本地原值保存、原生回读和来源查询完成；来源价格本身保持，完整市场导入与迁移继续。要求见[RS8](../specs/qmt-source-history.md#rs8-来源价格范围质量与原值保存)。

## 根因与同源核对

原DAT导出以标准OHLC关系拒绝整只来源证券。实际命令qmt_local_dat export --symbols 600000.SH约0.8秒稳定返回ohlc，原触发为2024-03-20 09:31 open=7.01/low=7.02。此前[三条首个异常观察](2026-10-27-qmt-local-dat-inventory.md)只定位时间，尚不能判断解码或来源原因。

本次用本机国信自带qmt_api.api.get_market_data/getMarketData只读接口，period=1m、dividend_type=none，查询对应分钟及相邻记录。初始9条与新增13条共22条，DAT时间及OHLC/volume/amount六字段均与官方接口逐值一致，覆盖全部8个异常分钟。独立xtquant接口曾返回空数据，未作为成功证据。没有通过通达信交叉推断，没有新下载或修改来源缓存，没有启动/停止QMT策略。

三份源DAT的字节SHA、长度和mtime前后完全相同。已证明当前异常组合就是官方接口和缓存保存的来源值；供应商内部为何产生该组合仍无官方解释，本记录不将其归因于集合竞价或厂商bug。

## 正确实现与能力边界

自有price_quality提供唯一四价关系分类。source保存有限正价、非负量额与合法时间，并将范围异常作为有界质量摘要，保留全部价格与记录；不按09:31、证券或日期特判。异常证券的QMI成功收据及sidecar绑定price_range_quality，含全行计数、分类计数、至多8个异常标签。SourceReader重新读取DSB逐行重算摘要，提供每bar.price_range_status及metadata.price_range_inconsistent_rows；摘要错配拒绝读取。无异常证券的原sidecar/收据字段形状保持。

canonical导入、MarketBar和canonical Reader继续严格OHLC。旧无声明source也保持原严格校验。来源HTTP/SDK wire字段保持，完整原值可按显式source查询；标准K线图遇异常来源区间显示具体分钟的中文质量原因，继续保持严格绘图，不改价或静默丢行。此修复解决历史导入卡点，未把异常价格变成标准合格K线。

本项只修改自有Python适配/读取/图表代码与测试，WT框架及原DLL保持。既有SHM分钟协议的严格OHLC准入保持，在线原值质量后继单独接线；不静默改变活动协议，不新增订单或账户功能。

## 三只完整转换与回读

| 证券 | 全部记录 | 范围异常数 | 原生逐行结果 |
|---|---:|---:|---|
| 600000.SH | 287284 | 1 | 时间及六字段全部相等 |
| 600015.SH | 287215 | 1 | 时间及六字段全部相等 |
| 000007.SZ | 245755 | 6 | 时间及六字段全部相等 |
| 合计 | 820254 | 8 | 完整保存，无删行 |

000007另外五个分钟为2023-06-02、2023-11-09、2023-12-06、2024-06-26、2024-12-26的09:31；已全部同源核对。转换约14.56秒、最终原生逐行回读约14.12秒。实际链为DAT→QMI/CSV→原Importer/Helper→标准DSB→原生SourceReader，导出与回读未调用QMT SDK；前述官方接口调用仅供独立来源核对。

真实DSB→NativeSourceMarket→认证HTTP→公开SDK的8个异常分钟查询全部返回Ok及完整原值，owner正常关闭。旧source v2、无质量扩展的两证券301946根用新Reader正常读取，异常计数0；不是重写旧产物。

## 回归与审查

修前新增真实根因模式回归失败于ohlc。修后33项导入/实际Helper回归中32通过、1项既有权限场景跳过；包含非开盘异常保留、至多8标签、canonical拒绝、实际DSB往返、同摘要重写后实际质量矛盾拒绝、原CLI与正常读取。图表公开接口34项通过（1项既有warning），验证中文具体分钟错误、正常/空/异常及原路径。首次实际Reader探针暴露元数据参数遗漏，修正字段归属后完整820254根回读通过；首次图表测试环境缺独立策略包，补齐本仓路径后全部通过。原失败记录保持，不提升为成功。

独立full静态审查complete、无实质发现，实际源码身份与审查记录（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/REVIEW.md`）匹配。审查者只读取最终规格、规则、源码与测试，未读取任务历史或既有报告；未执行运行验证。

## 物料、命令与资源

- 完整转换（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/converted-001/convert.json`）、成功收据（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/converted-001/store/qmt-import.json`）、逐行回读（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/NATIVE-READ-002.json`）。
- 原同源22条对照的第一组（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/VENDOR-DAT-COMPARE.json`）、后继组（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/VENDOR-EXTRA-DAT-COMPARE.json`）、来源HTTP/SDK（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/SOURCE-HTTP-SDK.json`）。
- 旧源兼容（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/OLD-SOURCE-COMPATIBILITY.json`）、源码/原文件/进程收尾（外部历史/待归仓路径：`../../build/qmt-local-dat-price-001/POSTFLIGHT.json`）。

正式命令使用qmt_local_dat convert --cache-root D:/software/guoxin/datadir --symbols 600000.SH,600015.SH,000007.SZ和独占新输出根；Helper与NativeBarFile保持既有受管制品，SHA分别59696d42d8985ca09ddacf0e583525d025dba91ff66ffaa296cec8f6174cc45a、4f5e2696559011d755edfac1d58296626fdedb6ba46c6d6a0fafc0203eebe62c。回归入口tests/integration/importer，原生测试显式设置GH_WT_DT_HELPER/GH_NATIVE_BAR_FILE；图表入口tests/integration/app_console/test_public_chart.py。

成功转换根17760、回读59148、原生回归35852、图表63776、真实来源HTTP67572、旧源兼容65380均exit0、原预算内完成；整树归零、EOF、reader join和资源关闭均核实。SDK核对根23508/34896同样闭合。运行过程使用隐藏受控进程，无新增控制台窗口。真实下撤单0、未切换生产、旧QMT工程只读。

## 后续

三只证券此前被OHLC拒绝的导入阻塞已解决。QMT异常原值及其未知来源口径明确保留；依赖标准OHLC的策略须检查质量，不通过自动调价放行。全市场其余缓存转换、10月21日后尾部补齐、在线质量协议及正式策略宿主/独立发行仍未完成。当前无需用户决策或手工操作。
