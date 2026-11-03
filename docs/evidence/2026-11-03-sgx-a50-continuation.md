# SGX A50日频与月报持续来源隔离验收

类型：验证记录。日期：2026-11-03。状态：开发与隔离安装验收通过，正式独立更新角色由Root另行接收。

## 背景、实际期次与发布时间

原`providers.sgx`只读取官方CN产品日历史并返回sgx_a50_daily，来源配置也仅声明日频；sgx_a50_monthly始终来自既有月报归档。日频与月频的最新日期应分别核对应官方来源。

本次原Fetcher实读[官方CN产品历史](https://api.sgx.com/derivatives/v1.0/history/cc/CN)，days=1y返回365个统计日，最新为2026-10-30；另以days=1d独立核到同日。持仓1,043,060手、当日成交496,725手，与原已发布行精确一致。因此当前日频10/30直接对应所核官方接口的最新返回，11月2日的该口径数据尚未返回。此次未获得官方固定发布延迟承诺，不据周末/本地时钟推定缺失原因或补日期。旧官网另一结算列表接口本次返回空正文，未作为替代数据。

[官方市场统计页面](https://www.sgx.com/research-education/historical-data/market-statistics)的实际公开appconfig及market_statistics_reports_list已实读，最新仍为September 2026；当次24条报告由2026年9月向前排列，未列10月报告。目录reportDate折算新加坡/北京时间为2026-10-09 00:00；文件元数据date为2026-10-09 15:46:56。相关[官方公告](https://links.sgx.com/1.0.0/corporate-announcements/0DMQR3CB5MZJ0VQW/cb10dea2fbda21370679f21d4b80448b038f32d25bed1b6fe2391b508b335347)广播时间另为2026-10-12 08:02:04。两入口PDF字节SHA完全相同。目录/文件元数据和公告时间分别存证，原available_at仍为空，不将其中一个时间声称为历史首次公开时刻。

月报第14页Equity Index Futures Volume的A50当月列为8,917,354手；第28页Equity Index Futures Month-End Open Interest当月列为836,157手。该月末日期2026-09-30与原行一致。91,886,267手年累计、30,507,149手季度累计、去年同期和单日数字不参与当月值。10月报本次尚未在官方目录出现，保留9/30符合当次官方披露状态。

## 实现和原职责

日频原函数、全CN合约口径、异常非整手值留空及保留原值规则继续。providers.sgx仅新增月频显式分流，sgx_reports.monthly沿appconfig取得公开CMS版本→核官方目录/分页/期次→读同记录原PDF。月份列按标题识别，持仓和成交来自各自表，页码动态登记；报告文件名沿原sgx_YYYYMM.pdf。原Fetcher/原件归档、单批预算/D、排他刷新、CAS与调度保持。

月频采用独立sgx.a50.monthly来源和report_latest游标，避免原日频最新10/30使月频9/30落在日频起点10/23之前。kind复用sgx；配置增加1路及必要官方主机，原日频及其他28来源、模型、计划和预算保持，来源总数28→29。pypdf复用已固定依赖，无构建、版本或registry修改。

## 实际主路径及回归

所有新运行材料在E:/workspace/wondertrader-qa/sgx-a50-continuation-20261103-001，Source/Data/配置CAS及中文接收在E:/workspace/wondertrader-data/sgx-a50-continuation-20261103-001。REAL-PARSER-RESULT.json为真实日/月数字核对；原件、请求、SHA及PDF逐页文本保留。

以原已完整准入的隔离后继96d360e8…为基线，其父为680ebf7a…。run_main.py沿原refresh实际请求两路并发布b1e8dcd2…，约18.406秒。日频1836条、月频10条原历史、原定义版本保持；其余70组完整记录、源表及股票分区精确保持。check_recovery.py以错误PDF触发sgx_monthly_pdf_budget_or_format，原current及72组分区保持；随后普通安装沿真实官网恢复，两路均零历史修订，最终候选6cdda82bb99a9fc7a8e8663d268153463d90da7542c2e046f047b058225e567a。

普通非editable wheel安装在E盘，与原版本号保持；verify_installed.py实际读取FastAPI catalog、series和JSON exports。日频按900/900/36条分3次覆盖全部1836条，月频10条1次，逐字段等于原历史，导出等于相同查询结果，应用完整关闭；最终模块与wheel/安装源码逐字核对。

固定E盘解释器-I -B run_regression.py，65项通过，覆盖真实完整PDF、表跨页重复表头、当月列/累计列区别、日/月独立游标、旧日频及非整手规则、未来披露、变更产品/文件/目录、分页不足、原截止和合成未来月份/动态页码。首轮1项测试夹具在要求分页不足前误读取了不匹配月份PDF，改为明确全体未到期的截止后通过；产品源码保持。源码按规格与规范人工full审查，当前开放发现0，未另派独立审查者。

project.py check仍有共享工作区原30份历史未索引文档，本项没有新增链接/索引错误。原providers.py保持CRLF，格式检查按core.whitespace=cr-at-eol运行，避免共享整文件换行重写。

## 资格与接收

SOURCE/DATA/CONFIGURATION三份CAS及HANDOFF-001.json冻结源码、实际wheel、原配置/候选配置、基线/候选manifest与增量对象。Root接收时current若变化，保留原current并仅重跑两路SGX来源。正式29源角色、自然调度及未来新统计日/月报继续由Root在实际发生时验真；当前证明未来自动识别与隔离完整链。

现场current写入、角色启停、WT/QMT动作、真实下撤单以及构建/版本/registry改动均为0。正式发布不使用此同版本隔离wheel覆盖现有制品，由Root统一维护后继发行和当前状态。
