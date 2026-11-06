# 当前辅助消费公开读取

类型：开发、独立构建与隔离入口验收；正式部署由原运行owner执行。

根因：V1a13真实main003结果记录16项可用派生和7项当前消费，App117共享策略读取仍只投影历史`diagnostics`，浏览器与页面原状态行未消费当前字段。历史覆盖/信号次数描述历史逐行重放，无法代替当前决策知晓与消费。

实现沿[SDO-R4-current](../specs/strategy-data-and-observability.md#sdo-r4-current-当前辅助消费公开读取)：App118增加独立可选消费投影及可用性/稳定原因码，复用冻结V1a13原值、摘要和知晓时间验证器；角色依赖及浏览器日期数量约束由原V1声明生成。读取层不调用派生、生效日投影、信号或目标重算。坏附加字段只降级当前诊断，历史覆盖、资金、持仓、阶段和时间保持。原计算/运行状态行显示“必需7/7已消费（齐备）”，16项可用派生及行情基准仅放原title；卡片、段落、CSS和个人观察数据保持。

正式离线构建入口为`scripts/observer_source.py build`，本次完整制品为App `0.1.0a118+current.auxiliary.1`，依赖V1 `0.1.0a13`、Core `0.1.0a8+read2`（满足原a8公共精确pin）、Native `0.1.0a1+read2`、Runtime `0.1.0a11+read10.diagnostics.1`及SDK `0.18.0`。读取侧V1十个永久快照成员逐字节匹配冻结生产源码；生产V1、Runtime20与运行目录没有改动。原Runtime execution extra未装入。

证据根：`E:/workspace/wondertrader-qa/current-auxiliary-public-read-20261106-001`。

- `build002/SOURCE-BUILD.json`：最终完整构建exit0；508成员复核变化0。ZIP SHA256 `0308b15aaef8f7fddb238dd380bb897338d883966799ab818d571e3ca45984c9`。
- `install002.log`：原普通离线安装exit0，pip check无损坏依赖；实际安装身份见`INSTALLED-IDENTITIES.json`。安装没有启动Source、Host或交易owner。
- `CHAIN-RESULT.json`：真实main003纯核结果装入明确隔离的原观察/ready/WRI包装，已安装App两个正式策略路由均保留7项消费和原历史诊断。main003包装持仓来自原QA夹具，不作为新增现场资金/成交证据。实际自然等待结果原样返回`waiting_market_input`与current absent；后继真实自然sequence191完整原报告经同一双路由保持current available、7项实际消费，历史这7项评估覆盖原值全部为0。`CHAIN-LEGACY-CORE-COMPARISON.json`核三组报告的核心投影与已安装117逐值相同，新增仅当前消费三字段。
- `ARCHIVE-COMPATIBILITY.json`：原五份已保存旧/新归档26个正式读取路由全部200，与App117逐值一致；未重新执行回测或改归档。
- `frontend-final-regression.log`：68项通过，含直接到达浏览器的单日坏派生依赖独立降级、核心/历史保持；安装包三项Python根因回归通过。
- `BROWSER-RESULT.json`及四份截图：最终普通安装App118正式路由与真实SPA，经系统Edge核桌面/窄屏、当前7/7及title16、坏当前字段局部降级、恢复、实际自然等待及真实自然sequence191的7/7展示。QA服务器只拥有独立冻结观察副本并已关闭。

独立full审查发现浏览器依赖日期数量准入偏宽，随后从冻结V1唯一条件树生成上下界并补原触发回归；delta复核complete，无剩余P0/P1，冻结V1原SHA保持。证据`REVIEW-FINAL.json`按实际源码身份登记。无真实交易/来源SDK调用，无新账本或上线卡点。

App117市场观察updates的旧QA仅保存503状态，缺少当时响应code及异常回执；本次实际读取为200。源码边界定位为原观察读池→调度状态/更新记录，不涉及当前消费投影；旧503的精确首错保持unknown，详见`UPDATES-READ-DIAGNOSIS.json`，本模块没有扩张修改观察页面或来源读取。

真实自然sequence191当前消费已通过冻结原报告→已安装App正式路由→实际SPA的隔离只读验收；原100万元含持仓基准和资金持仓投影保持。尚未授予App118正式部署及其发布后生产入口资格。Root采用新App后核实际生产入口与原运行身份，原报告/个人目录/金融状态沿用原配置。
