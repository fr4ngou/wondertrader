# 股票已达持仓绝对目标替换隔离验收

类型：验证证据。日期：2026-11-06。范围：[已批准方案](../migration/native-stock-target-replacement-proposal.md)及[CORE-012](../maintenance/upstream-overrides.md#core-012已达持仓时接纳新的绝对执行目标)。当前已实施、隔离工厂主链及独立源码审查通过；完整发行和真实恢复分别登记。

## 根因与实现

原股票单元的新目标等于可卖持仓时提前返回，留下原_target_pos；原DLL冻结重放159780连续BUY1000×2、512100 BUY200、515080 SELL100，与实际净变动吻合。配置`replace_equal_position_target`缺省false保留原行为；true使新绝对目标先接纳，再由原do_calc核实际总量、T+1、活动单和量价。Borrowed引用逻辑、原策略数学及金融状态保持。

仅两个批准框架文件变更；原工厂源未修改。既有stock-reference.patch合成CORE-011/012，两个构建来源清单绑定覆盖及结果SHA。自有Host在交易API初始化前拒绝坏型或其它算法声明该键；Python/Native同账比较只在副本归一化已核bool，其它业务字段严格。

## 实际入口与证据

anchor CPython 3.12.13调用`tests/integration/stock_target_replacement/run.py`；固定上游08b230dd05facf6d650d949bfe51054115a2ecb1、MSVC14.51.36231和原锁定依赖源码。最终独立目录为`build/stock-target-004`，全部本项目对象/库在该目录重新编译，无旧项目二进制输入。开发中配置探针调整后在同一独立目录完成重新链接；SOURCE/COMMANDS及各日志保留实际步骤。

新WtExeFact.dll：`build/stock-target-004/cmake/bin/executers/WtExeFact.dll`，SHA256 `9ad2766fcb930cbbd0285048ab71d0b488b7ab737228b7acd98c9a32fa42c496`。
`build/stock-target-004/RESULT.json`记录两个工厂×三模式×七场景的42组实际公开工厂调用及Host准入通过；SOURCE.json绑定已批准覆盖、源快照和工具链，FINAL-SOURCE-SHAS.json固定最终模块文件身份。

| 输入 | 缺省/false | true |
|---|---|---|
| 159780旧220700、新22000、实际22000 | BUY1000 | 无额外买入 |
| 512100旧76400、新76200、实际76200 | BUY200 | 无额外买入 |
| 515080实际136800、新136700 | SELL100 | SELL100 |
| 159780连续两轮、后继实际23000/可卖22000 | BUY1000×2 | 两轮无额外买入 |
| 全新已达目标单元 | 无交易 | 无交易 |
| 原活动买单余量1000 | 无重复insert，余量保持 | 无重复insert，余量保持 |
| 总量23000/可卖22000、明确新目标22000 | 仍朝旧目标BUY1000 | 原算法SELL1000 |

最后一项仅为公开API接缝回归，不将真实额外持仓自动卖回。实际恢复沿R33以当前真实P重算新计划，旧state和真实成交由原owner保留。

Host实际配置函数核缺省、false、true通过，字符串/整数/数组/对象和其它算法声明拒绝。Python同业务比较3项定向测试及原发行恢复2项回归通过；后者保留账户/原件变动拒绝和非策略依赖严格性。项目导航/技能清单check通过；该静态检查不授发布资格。

独立Reviewer按最终规格和源码执行full审查，发现测试替身原在途保留断言不能检测错误撤单；已改为独立活动订单ID4242/余量记录，两个cancel重载记录并删除对应订单，实际回归断言零撤单、原ID和剩量保留。工厂名同时参数化覆盖原名及Borrowed。随后delta复核standards/spec均complete，剩余可行动发现0。Reviewer未独立重跑C++，上述实际42组结果由本次开发者的编译/加载证据证明；Root独占Native恢复和部署不在此审查范围。

## 限制和后续

原金融角色保持关闭，本模块真实SDK/账户操作0、金融文件写入0。工厂加载和Context订单记录证明目标替换与原算法行为，不替代完整发行、真实首回调、真实订单/异常/空态及页面验真。Root同批采用Native比较、日志和新Runtime发行后执行正式完整构建，保持原input、100万元基准、cash_anchor和账根，复用prepare_transition/resume_reconciled。已发生额外库存及未知身份保持，修正不导入历史成交或自动改账。
