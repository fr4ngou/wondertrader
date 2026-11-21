# WT56 日线当前视图来源合并修复

状态：candidate。目标为独立 WT 历史查询服务；操作者 Codex，日期 2026-11-22。正式配置切换待用户确认。

## 根因与实现

510300 日线 `view=current` 经过嵌套 `DailyOverlayMarket` 时，下层组合结果的逐段 `provenance` 被上层丢弃，整批 `SourceSelection` 汇总身份被当作每根日线的原捕获会话。协议校验触发 `MarketProtocolError: market object fields are invalid`，对外显示 `IoError: 原生日线或闭合快照读取失败`。后继日更批次绕开该分支，使现场查询恢复；原固定发布配置仍可复现故障。

修复在合并器入口校验下层响应，按分段 offset/count 恢复每根日线的原来源，再沿统一选择逻辑生成结果。覆盖限量截取、再次叠加、Writer 尾部追加和两种响应形态，归档视图沿原入口。

源提交 `ca95e68ec2d9e39e8f7d6e55b658386fc0922f05`。数据程序从 `0.2.0a1+unified.55` 升至 `.56`，协议、持久格式和数据原值保持原契约。实现与回归入口见[模块正文](../modules/collected-daily-history.md)。

## 制品与验证

- 制品：`D:/wt-build/wt-unified56-daily-provenance-20261122-001/artifact`，清单 SHA256 `2cb55e58563ec9a8f865264b947c862669ce16da23d90b31c1c716a0ed7798ca`。普通离线安装至 `E:/workspace/wondertrader-data/wt-programs/unified56-daily-provenance-20261122-001`，188 个源码成员核验通过，206 项构建输入与集成主干一致。
- 固定故障配置 `E:/workspace/wondertrader-data/observation-history-20261122-005/configuration.json`：WT55 返回 IoError/0 根；WT56 同请求成功/2 根，异常追踪为空。证据在 `D:/wt-data/510300-daily-current-20261122-001/INSTALLED55-RED.json` 与 `INSTALLED56-GREEN.json`。
- 相关回归 41 项通过；完整本地 CI 516 项通过。收据：`E:/workspace/wondertrader-qa/510300-daily-current-20261122-001/local-ci-003/RESULT.json`。测试环境缺依赖的首次失败保留于同根 `local-ci`、`local-ci-002`，补齐独立测试环境后通过。
- 正式入口切换前：510300 当前/归档及观衡图表读回 2026-11-19 至 20 日各 2 根；588000 分钟抽样 2021-12-01、2026-08-24、2026-11-20 分别 240、239、240 根。原值摘要与独立交易实例指针摘要保存在 `D:/wt-data/510300-daily-current-20261122-001/SERVICE-before.json`。

## 正式接续与回退

候选配置 `E:/workspace/wondertrader-data/510300-daily-provenance-20261122-001/wt-service.json`，SHA256 `89f8ad8a135bd9df697f6750ba835c3df6c1583a02ae9a762eea372c9eb18df0`。仅替换历史查询程序路径及对应校验值，沿用原实例、数据、发布入口、588000 早期分钟补充与 18136 端口；独立交易实例由原 owner 继续持有。

确认后通过原 ServiceController 停止旧历史查询代、核进程退出，再 adopt-bootstrap 接续新代，并更新既有启动组的历史角色引用。切换后逐项对照原查询摘要和交易实例指针，从 18143 的图表接口核实际返回。需要回退时，先停止新查询代，再用原 `588000-minute-history-20261122-001/wt-service.json` 接续 WT55，并还原启动组备份。

当前结论：代码修复、主干集成、制品安装和固定故障回放已完成；正式采用待确认。该验证覆盖已指定请求和组合路径，逐证券完整历史覆盖沿数据来源资格另行核实。
