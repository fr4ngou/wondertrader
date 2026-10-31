# 2026-10-22 Grafana、新闻与研究整体退出

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。结果：pass，限本轮范围退出及受影响保留链；未发布。要求：[ADR-0004](../architecture/adr/0004-core-trading-product-scope.md)、[业务工作区GBW-R2/R3/R4](../specs/guanheng-business-workspace.md)。

## 变化及职责

用户明确撤回三类功能，旧迁入清单及已复制的Console实现仍包含对应业务。当前在产品范围及实现所在层统一移除：专属页面、服务API客户端、DTO、采集/发现/回放和研究编排入口、新闻图层、Grafana iframe与凭据提示、专属测试和发布条件。混合文件保留行情、策略、账户、回测、组合补单及健康/日志诊断职责。

独立市场观察保持其行情及宏观指标边界，用户文案改为市场观察和离线分析。策略必要辅助事实沿各自数据契约处理，缺少外部研究事实的策略继续明确不可用。旧QMT仅作静态参考；未修改旧源码、停止旧生产服务或删除历史数据。WonderTrader框架源码未因本次范围调整发生修改。

后端能力清单移除新闻和研究，旧专属API统一返回410及固定中文说明。schema1.4分钟图移除news事件类型与待接入来源；保留signal/execution及策略、成交、基准缺项表达。旧研究深链回到行情，Grafana深链回到系统状态；导航不再展示退役功能。

## 输入及验证

本工作树含先前未提交开发；输入以文件摘要和独立审查快照绑定。清理前170份Console输入及AST/真实bundler依赖图保存在只读清点（外部历史/待归仓路径：`../../build/guanheng-workspace/scope-retirement-001/INVENTORY.json`）。历史来源清单保留已删除文件原身份并登记retired。

实现冻结包final-inputs（外部历史/待归仓路径：`../../build/guanheng-workspace/console-retirement-001/final-inputs.json`）SHA `44c450c4b1b7132a8ae5f57ac02764f08f6118e827a46db32565e00afd6b4f92`、source ZIP SHA `49d2caf0837aa484dc9e0ac01f1689ec7cccdd81f9fbab55fef60b577b288ebc`、100项manifest SHA `f587e7a25507b405abfa50b58504306dc3b5554408f82368280c012112d0f655`。根任务逐项回核一致，38项已删除、27项当前摘要匹配；ZIP的142个条目均未夹带38项退役源码。

| 验证 | 实际结果及范围 |
|---|---|
| app_console公开图表、NBW、账户后端回归 | 90项通过；JUnit（外部历史/待归仓路径：`../../build/guanheng-workspace/scope-retirement-001/pytest-002.xml`），含退役GET/POST、能力及保留健康/图表 |
| 前端全量组件 | 最终39个测试文件286项通过，含新闻/研究/Grafana深链及市场观察文案收敛后的输入 |
| NBW前端边界及原接口/组件 | 根任务18项通过；独立delta的18项及45项实际Edge异常/类型/页面场景通过，见[NBW后继](2026-10-22-native-backtest-workspace.md)；与退役功能分别归属 |
| 真实渲染Playwright | 7项通过、2项因未配置实际账户/分钟来源跳过；覆盖分钟正常/空/异常恢复及回测报告恢复、手机布局，模拟HTTP不授真实来源资格 |
| 类型、构建与分块 | 最终候选通过；实现冻结输入（外部历史/待归仓路径：`../../build/guanheng-workspace/console-retirement-001/final-inputs.json`），独立审查核对最终制品身份 |
| 文档导航 | project.py check通过；仅证明本地链接/索引完整性 |

第一次Python回归在收集阶段因根开发环境未安装新增本地策略包失败，保留原记录（外部历史/待归仓路径：`../../build/guanheng-workspace/scope-retirement-001/pytest-001.xml`）。第二次显式使用本仓库app/core/native源码路径，90项通过；正式非editable安装仍由独立复核覆盖。没有借用旧QMT运行环境。

## 资格及后继

独立full复核实际源码、专属依赖清理、最终发行物及静态浏览器→HTTP→原DLL保留功能链。NBW两项局部修正另以delta结论登记。开发者正常回放和既有后端安装的组合实验分别保留实际输入身份，不能替代当前新安装结论。

独立full-001（外部历史/待归仓路径：`../../build/guanheng-workspace/reviews/core-trading-scope-retirement-full-001.md`）已complete，本轮gap 0，报告SHA `4d1ea1d9cf1c6768498ec49a7860525c3761170eeb714b56054c1b5d8f0728cf`。1596文件及6项外部只读输入清单（外部历史/待归仓路径：`../../build/guanheng-workspace/scope-retirement-review-001/artifact-manifest.json`）SHA `fc34f83557e3e5eec6b7817be21695ce90b80d44b0809f4bdf4bb70921687487`，根任务全部回核一致。217份源码与1155份安装输入前后身份一致。新Flit非editable安装的90项pytest、独立271项前端回归、双入口构建及类型/分块门禁通过；FE专项测试单独归属上述delta，数量不相加作为全量测试数。

79条实际HTTP核退役410中文、独立市场观察未接通边界与保留能力；实际Edge→新静态dist→新安装HTTP→原DLL两轮五日回放、CSV与Fraction精确资金核通过，页面无异常及退役域请求。运行中的原生进程随ASGI关闭取得wait0，审查服务全部关闭。新安装manifest SHA `6dfef571ccd2cad3fa8ae64bd18f1a580eb479f1beb4d5cf3f703ca19546db12`，app wheel SHA `5c62ed4437ede2797431c259039509549102ef6160a1a06ccc7fb1a9d73d1187`，实际环境和运行原件见独立报告。

本次为开发工作区清理；尚未生产发布。真实QMT来源、SHM接入、策略完整移植及账户交易资格保持原验收边界。范围决定同步产品、架构、模块、迁入方案、规格与TARGET/NOW/CURRENT，新闻/研究/Grafana不再列为待迁入或发布完成条件。
