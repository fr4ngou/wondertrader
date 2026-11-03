# 观衡a105图形化回测独立交付

类型：本机独立观衡发布与接收。核实时点：2026-11-03 21:45（北京时间）。状态：已安装并切换18143，真实回测与原读取主链通过；WT自动交易仍关闭。

## 用户验收入口

打开 <http://127.0.0.1:18143/backtests>，侧栏新增“回测”。原策略回测地址继续可达。当前安装为 `0.1.0a105+btvisual.1`，Web PID34184、启动器57160，控制ID `c324b40f-bbce-49dd-a002-96ab9e793c28`。默认选择截至11月2日的100万元报告，显示403期、收益2.74898%、日末最大回撤22.92086642%、末净值1,027,489.80元及费用29,299元。

- 主报告和对比报告分别选择，收益/净值曲线、日末回撤共用日期轴。
- 悬停显示日期及日收益；实页2026-03-30为0.0567%，点击同步日期明细。买卖标记开关已实测，图形路径由111降至66。
- 日期明细提供持仓与盈亏、当日交易；完整交易可分页，共101笔。对比12万元报告时保留其自己的本金、区间和2.99041667%收益，不混用主报告资金。
- “刷新”更新归档目录和当前绩效，发现后续已保存报告；原精确日期净值表在折叠口径中保留。

已确认设计、数据定义和模块验收沿[BPC](../specs/backtest-performance-comparison.md#bpc-r5-可视化与日期明细)、[模块证据](../evidence/2026-11-03-backtest-visual-redesign.md)及[视觉对照](../../apps/guanheng/console/design-qa.md)。持仓浮盈亏与累计已实现盈亏均取原WT CSV、未扣费用；本期不推造逐证券当日盈亏、成本、价格或市值。费用继续原模拟数量费率，实际券商费率尚未校准。

## 限定源码与制品

开发者1在独立工作树完成23份模块源码、规格、通用设计规范及验证。Root先固定已验快照，再与最终`SOURCE-CAS.json`和`HANDOFF.json`逐项对照：23份after摘要全部相同，交接证据摘要无差异。只整合本模块内容，证据索引保留共享工作区其他未合入改动；没有整包覆盖开发者1的隔离App。

主干提交为 `f91cc884221ac0c1bdbe4150307ce2d294a6b700`，带注释本地标签 `observer/0.1.0a105+btvisual.1`。从干净主干、固定CPython3.12.13/Node24.18.0、原离线锁及npm缓存重新构建六读取项目和SPA；WT执行与Host发行保持。

| 制品 | SHA256 |
|---|---|
| 独立ZIP | `d113c95d2553fd70fba6b72b3c4a55b0b0c7cf56186884cf9a8be5e93df4db22` |
| OBSERVER-RUNTIME.json | `f3b9c65acb25b29195727fdc5b68312cbec5d64fae94a2c85157d152a372885a` |
| 角色清单 | `6b643923520d8447cf0e634d442b82171df1361099f489620e01b897ad02fe51` |
| 安装收据 | `af8f1ba0295b127f9b381ffbb981055fb9aff774f294ea62bf25b9030fbc8b1a` |

构建原件为 `C:/Users/frangou/AppData/Local/Temp/root-observer-a105-btvisual-build-002/SOURCE-BUILD.json`，同目录保留ZIP、package及roles。首次构建误选旧第三方缓存，因缺已锁xlrd在建目录前失败；失败日志保留。后继使用已有完整`observer-source-002/third-party`，原锁、版本和摘要保持，最终构建exit0。普通离线安装到 `C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observer/0.1.0a105+btvisual.1/`，pip check及安装入口exit0。

## 独立接线与真实验证

当前稳定指针为 `E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`，源Profile为 `observer-web-a105-btvisual-20261103-001/web-profile.json`，SHA256 `d5fae21b1f43e08c5d1ec50043af1396259569f46935e3101213153039c06b48`。本轮新旧读取环境文件逐字一致，行情18149、Full37四项绑定、三项自选、观察根及正式报告目录保持。正式报告根仍为 `E:/workspace/wondertrader-data/oar-dev1-20261101-001/formal-backtests`。

旧a104经原维护入口正常关闭：shutdown_complete=true、两个读取池线程数0、Web和启动器退出码均0；新a105正常启动。WT Full37启动器66544、历史18149进程41220、原采集owner29056/采集69884、独立更新监督者42932/子44840的进程及创建时间保持。

| 实际主链 | 结果 |
|---|---|
| 已安装报告投影 | 403图点、101笔成交，四组账户结果complete |
| 图表及比较 | 真实曲线、日收益提示、点日、标记开关、双报告和交易列表通过 |
| 策略与状态 | 现金及可用633,075.20元、五持仓、Full37五组件就绪，正式策略等待首次自然计算 |
| 行情 | 默认60个交易日日线；原2000根分钟、11月3日尾部及68817即时下拉通过 |
| 观察及账户页面 | 上证/RANA/MSI/T2108/推力/TRIN及原日期保持；总览`/dashboard`、账户和委托实值可读 |
| 桌面及手机 | 1440×1024和390×844实际页面；390px无横向溢出，pageerror和console error均0 |

模块原143项前端回归、5项后端及两轴独立审查沿相同after摘要复用，开放P1/P2为0；Root补已安装完整App及真实18143主链，不重复扩张异常矩阵。空归档及错误参数沿最终模块证据复用。总览没有硬编码正式策略；根地址`/`按原路由进入行情，不能将其截图标为总览。

## 启停和回退

沿[独立Web手册](../runbooks/observer-runtime.md#隐藏-web-的启动查询正常停止与重启)使用当前DEPLOYMENT的python、tool、source_profile执行status/stop/start。正常停止仅关闭Web，WT、通信、采集和公开更新继续运行。完整操作和图表读法已同步[操作员手册](../runbooks/guanheng-operator.md)。

回退时先正常停止a105并核关闭回执，再使用 `DEPLOYMENT-BEFORE-A105.json` 保留的a104解释器、工具和源Profile启动；核对仍连接Full37及18149、原个人目录和报告根，正常后更新稳定指针。a104安装与旧Profile均保留；新只读路由没有更改归档、资金账本或个人数据格式。当前轮未实际回退；旧版继续其原回测展示，新增图形化界面需a105。回退操作不切换WT或公开更新版本。

## 剩余事项与依据

本期OAR独立读取交付与较早分钟补齐已可验收。现行正式策略自动写仍关闭，最终模拟自动执行及自然策略输入组合沿交易主线继续；当前读取就绪不授实盘结论。ETF缓存的2021—2025分钟缺口、当前全A日终/T2108原件及部分高管来源失败仍按[Full37记录](2026-11-03-observer-full37-recovered.md)和原更新证据分别登记，未以旧数据冒充今日数据。

Root原件集中于 `E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001/`：`backtest-source-intake/SNAPSHOT.json`、`FINAL-HANDOFF-MATCH.json`、`INTEGRATED.json`、`A105-SOURCE-BUILD-002.log`、`A105-INSTALL.log`、`A105-INSTALLED-READSIDE-PREFLIGHT.json`、`A105-WEB-STOP/START/DEPLOYED.json`及`a105-actual-browser/RESULT.json`与截图。最终模块材料在 `E:/workspace/wondertrader-qa/backtest-redesign-20261103-001/HANDOFF.json`。本轮未操作QMT、发出金融命令或修改WT框架。
