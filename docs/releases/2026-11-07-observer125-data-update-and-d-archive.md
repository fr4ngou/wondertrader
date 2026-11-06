# 观衡125、日更恢复与D盘正式归档

类型：后继发布记录。状态：App125 deployed / verified，Data25原任务 published / verified，D盘归档 active / verified。核对日期：2026-11-07。范围：先修复界面及数据自动更新；原版线上适配与100万元部署属于后续阶段。前次[App123发布](2026-11-07-native-target-cash-gapplan-live.md)保留当时原批读未运行的观察，本记录登记后继恢复与采用。

## 采用身份与界面结果

观衡 `0.1.0a125+fastjson.1` 已普通安装并在 `http://127.0.0.1:18143` 运行。产品源码 `e94b1999a745ce54587fcaac8e32b08a22409aa7`，标签 `deploy/observer125-nvme-daily-20261107`，源码包SHA为 `d1e404cc5d0db7650905532402c8f6aa721eed6b9e320aae391e4a676814dc2a`。后继 `598c873817292a1cc49d8887a2005b3b4d917be0` 补齐测试夹具，产品字节保持。已安装模块实际来自独立venv的site-packages，源码注入为false；原App已正常关闭。

列表先核轻量目录，选择报告后才加载完整分析；图表悬停使用本地每日摘要，点击固定日期读取明细。App125继续保留App124已验的按需加载、chunk失败提示和显式重试。严格JSON重复CPU遍历已定位，本次解析优化实测收益约8.35%；后台Native批量I/O期间，App124普通安装首次列表曾耗8825ms，无并发的归档owner读取为1875ms。E盘为SATA HDD，正式回测与全市场日更共用该盘；Native重I/O与长列表同时出现已观察。同盘并发存在存储竞争风险，本次按用户要求迁移至D盘分离归档。受控并发负载A/B尚未执行，D采用的独立量化性能收益尚未验证。

正式App125+D盘的实际浏览器结果：列表3704ms，完整报告打开2911ms（包含人为350ms chunk延迟），打开前图表/自动绩效请求均为0；悬停HTTP为0，点击固定日期30ms，键盘与详情标签通过，窄屏无横向溢出，写请求与浏览器错误均为0。首次冷读取仍需数秒。计时对应各自负载及缓存状态；D盘采用后的实测单列，跨轮计时保持各轮条件。

## 正式归档位置与原件

受控 `E:/workspace/wondertrader-data/backtest-current/STORAGE.json` 已标记active：`archive_root`及`work_root`均为 `D:/wondertrader-data/formal-backtests-20261107-001`。App125的显式归档环境指向D；后续WT CLI同样显式传入D盘 `--work-root`，具体操作沿[运行手册](../runbooks/native-backtest.md#正式归档的唯一位置)。CLI独立解析参数，读取职责与Observer环境分别配置。

迁移从E盘原正式目录重新逐文件复制9个完整run、252个文件、92008583字节；源前后及D目标清单SHA均为 `f5e744aa67fdf83ab40dcdb082e1b8966b6830b8f04b4d929dd1d5f07ad5e92e`。报告、完成证明及原输出保持原字节，原安装绑定和run身份保持；复制过程未建立junction或hardlink。普通App124归档owner对全部9份摘要、配置、完整绩效、记录、曲线、每日摘要和分页成交投影逐值比较相同；该证据用于D盘搬迁正确性，App125正式浏览器另行验真。

E盘原件保留为旧备份。D与E目录的owner、继承状态及8条ACE一致，ACL未改，未新增主体或写权限；权限强化作为后续建议。曾准备约92MB的C盘候选，线上从未采用。用户明确数据位置后，C候选使用已经停止；清理动作被自动审批策略拒绝，随后停止尝试，残留清理状态单独保留。当前正式指针只采用D。

## 日更主链恢复与来源范围

原日更依赖的61136批读Host由金融Runtime拥有，execution故障触发整组关闭，将数据来源一起停掉。独立WT只读服务复用原pair、Host/Agent/pythonw、Journal、端口及 `market.market_data` 能力；沿正式ServiceController启动，并登记在四角色数据服务组中。组状态原件确认历史补齐、证券资料、日更批读、日线与资料均ready。日常启停沿[批读手册](../runbooks/qmt-analysis-batch-source.md#独立日更的来源托管)，批读排在日更之前；金融组后继配置避免重复拥有同pair Host。

Data25沿原自动任务完成恢复、Source回读、Native、价格与快照发布。原REQUEST SHA `16a9eb2a8e0e343d198f65c8decbea1421d21f18f38e21581ee960e4a8f00836`、PLAN SHA `693e751712dd8e35365e2f17789aa1bacf518d3934c73fb19b03fe3a2c8b7898`、capture及43个HPR请求身份保持。旧槽本地资格校验与实际Source调用分别留证；恢复过程没有重置未知请求。主批读5578证券508批、额外价格190批和原owner后继133项准备完成，经原回读和完整旧价格档核验后发布。

完整CURRENT日期为2026-11-06，full snapshot ID `c2af732fa076c5f61acd02802ec6d1f8dfad4754f7b21aab6dde52485cd2a1d9`；北京时间11月7日01:56完成发布。实际已安装SDK经History HTTP读回同一ID，九ETF原价/前复权18项末日均为11月6日。补充目录SHA `9df85f62b5d5fa4cb46c850cae87239f61e68d5ac9dcc237a1d44a754581f5d8` 与完整快照及分页查询绑定。

该目录全历史5758条事实、412项缺口；11月6日总份额7条事实/2项深市来源缺口，融资0条/1项缺口，官方成交额0条/1项缺口，QMT双指数代理1条且单位unknown。融资精确当日源返回空结果，旧冻结目录保留其原reason，后继解析分类修正另有证据。`coverage_qualified=false`、`supplement_complete=false`保留实际资格；代理值保持独立来源，缺口不前填。CURRENT成功发布与来源完整性分别成立。

INDEX的两个continuation标志均false。原任务自动重试与恢复发布已经实证；自然日09:00一次partial修订尚未在本轮触发，Host进程退出后的定时拉起或开机守护仍需环境采用证据。四角色ready证明当时可用。长历史价格口径、原版预热和线上100万元部署继续按后续阶段独立核定。

## 验证材料与复用边界

受控材料根为 `E:/workspace/wondertrader-qa/original-live-readiness-20261107-001`。

| 证据 | 实际范围 |
|---|---|
| `APP125-RELEASE-SOURCE.json`、`APP125-SWITCH.log` | 产品来源、普通构建/安装与正式18143切换 |
| `APP125-R3-ORDINARY-ORIGINS.json`、`APP125-R3-ORDINARY-TESTS.log/XML` | 已安装App125来源核验；干净Git测试导出127 passed / 18.41s。首轮117通过及10项缺测试helper失败原件保留 |
| `ui-cold/FRONTEND-REGRESSION.log`及chunk失败回归 | App124前端29项及后继chunk边界1项；App125前端字节相同，沿此复用 |
| `ci-software-r3/RESULT.json` | 固定1bf7699源码、沿独立CI解释器执行标准software两阶段190项通过（含文档任务新增10项）；属于源码验证，普通安装及自动integrate资格分别核实 |
| `actual-app125-D/PREVIEW-BROWSER-RESULT.json` | 本次正式App125+D的真实页面、计时、交互与零写请求 |
| `archive-disk-correction/d-candidate/*` | E直接复制至D、逐文件SHA与普通已安装owner九报告投影一致；App124资格沿原件保留 |
| `DATA-GROUP-PREPARATION.json`、`DATA-GROUP-STATUS-POST125.json` | 独立四角色数据服务组配置及App125采用后的实际ready |
| `data-audit/FINAL-DATA-POSTFLIGHT.json`、`FINAL-ASSERTIONS.json` | 原任务正式发布、18项价格、四组补充事实及实际缺口；主证据SHA `99180dd57ce4660ee1e09d9a7c8d91d29d2bc7eb3073e93b70db05c9ef2b4159` |

最终汇总 `PHASE1-FINAL-RECEIPT.json` SHA `fee73fc5e6d8de128a9ef1528817bd17fe310d0aea275d5f33b46d22bd781ac7` 绑定实际App125、D归档与四数据角色验真。

本阶段完成界面与原日更任务恢复，原版线上适配、真实新成交及100万元运行采用尚未在本阶段执行。金融运行启停和数据来源缺口分别按其owner处理。旧正式发布及失败证据保持冻结。
