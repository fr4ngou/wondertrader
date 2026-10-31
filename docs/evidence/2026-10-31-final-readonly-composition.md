# 最终普通安装的真实只读组合

类型：真实只读验收。状态：账户、报价、历史读取及观察服务消费完成。范围：`build/root-final-runtime-004/installed002`，安装收据 SHA256 `28ecebac5d907c84918fabc4979316f455d30b1f08948613aef0e76833667618`。账户资料保留在本机受控 private，公开证据只列计数、摘要和范围。

## 实际完成

独立 WT 入口管理 account/HPR/trade 三个已有 Host、原 Native AccountScan 发布和原生历史服务；观衡使用独立普通安装启动，读取同一 scan_id 的 WT 账户发布。`actual002` 完成两轮 position、order、deal、account，8 个原始查询结果与 Native 帧的 134 个数值及身份字段相同，浮点位、原请求身份、绑定和来源执行时点保持；两份观衡账户 API 的 groups 与对应发布相同。报价保留供应商 `timetag=20261030 16:27:18` 和实际读取时间，该时点不另解释为成交时间或当前交易日新报价。

后继 `history-actual001` 复用上述账户与报价，只发一个新的已有缓存分钟窗口请求：000001.SZ，2026-10-30 14:20—14:25。实际 SHM 回传6根，36个 OHLC/量额字段与官方本机只读 API 逐值相同，原 ID/原结果及 consumed 责任闭合。观衡独立读取 WT 管理的原生历史服务，返回5根历史分钟；该冻结库窗口为 2026-10-27 14:55—15:00，与 QMT 缓存样例分别标识。后继没有启动 Native 账户扫描，账户页面数据沿用 actual002 已停止且有来源时点的原发布。

两次实际来源均由 Root 唯一启停原 SHM_READ_PROBE 并逐字恢复原文，GH/metric 保持。WT、观衡、QST 接收和对应子树正常关闭，Source 实际启停恢复、输入前后摘要和资源关闭均留有收据。Native 范围为账户 Scan/TraderReadOnly 与历史 Reader；本次未运行 CTA 策略、AWP、实际下单或撤单。观衡验收覆盖 API 数据消费，浏览器视觉与生产发布资格沿各自证据。

## 原失败与正确处理

`actual001` 在来源启动前因 QA 装配将 WT site-packages 前置，冻结了另一角色的 Agent 绝对路径；真实 Host 的配对身份核验正常拒绝。修正 QA 角色查找顺序后，Host/Agent 唯一来自 Host 安装，WT 部署配置类作为末尾依赖。HPR 和完整五组件各自实际启动/关闭证明通过，再以新独占 pair 执行 actual002。004 安装及产品源码保持。

`actual002` 整体结果保留 false：原选 14:50—14:55 晚于该票 QMT 缓存 14:25 的实际尾部。正式 SHM 和官方外部 API 同窗都成功返回空；缓存内 14:20—14:25 有6根。缓存读前后 SHA 相同，未下载。后继显式选择新窗口，不改写原空结果、不复跑账户、全池或重装。该票缓存覆盖从2021-11-01起，只确认所读窗口，不授整日或全市场完整性。

## 原件与追溯

工作根为 `build/root-final-readonly-chain-001`，最终入口为该根 `INTERFACE-001.json`；938项固定输入在两次最终运行中分别保持。QA 根分别为 `E:/workspace/wondertrader-qa/root-final-readonly-chain-001` 和 `E:/workspace/wondertrader-qa/root-final-readonly-history-001`，后继不覆盖旧运行输入。

| 证据 | 文件 | 范围 |
|---|---|---|
| 账户与报价实际运行 | `actual002/RESULT.json`、`private/PUBLICATION-*.json`、`private/HTTP-ACCOUNT-*.json`、`private/QUOTE.json` | 原整体失败保留，业务子链与正常关闭分别采用 |
| 账户原值冷核 | `ACCOUNT-AUDIT-001.json` | 2轮8查询、134字段、2份API发布；mode=ro&immutable=1，Journal摘要保持 |
| 缓存内外对照 | `cache-windows001/RESULT.json` | 0根与6根、官方本机API、无下载及原缓存保持 |
| 正常历史后继 | `history-actual001/RESULT.json`、`history-control001/RESULT.json` | 真实6根、独立UI接口5根、正常关闭与实际策略恢复 |
| 历史原值冷核 | `HISTORY-AUDIT-001.json` | 36字段、原请求和原结果、仅1个HPR业务读取、Journal摘要保持 |
| QA角色根因 | `ROLE-IDENTITY-REGRESSION-001.json`、`preparation004/*STARTUP-RESULT.json` | 原身份拒绝与正确身份接收、实际HPR及五组件正常启动/关闭，Source未启动 |

旧账户136次结果及 SDK124 的未变算法证据、actual008 全池5576+508资格按原输入复用，本次补充最终角色组合。交易执行、策略持仓归属、完整当日分钟覆盖、浏览器视觉和生产资格继续分别验收。
