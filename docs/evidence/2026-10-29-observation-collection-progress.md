# 独立观察采集发布主链

类型：开发进度与验证记录。状态：in-progress。依据：[OBI5–7](../specs/independent-market-observation.md)。本轮完成来源回放到完整快照及实际页面的初始主链，完整采集/每日09:00/发行与独审继续。

## 实现与事实边界

迁入原专用解析、完整历史重算、日终官方PCR数量口径和股票原始字符串归档。来源配置保留21路；大陆行情改为A统一SDK，腾讯适配只允许港股，原CSI直接行情抓取退出。大陆行情完整重取原表覆盖后才能替换，单位未知或已有日期缺失明确失败，保留旧表。宏观/估值/PCR继续专用来源，usage.executable=false。

原ContentStore/SnapshotRepository继续拥有对象、current、回执和采集lease。新增完成窗口索引与尝试记录，完成标记/快照/current/成功回执在同一事务；失败回执保持旧current。原物理窗口调度尚未接线。新独立CLI refresh入口消费来源配置及原字节SHA，默认读取不会联网。App版本推进a14，采集依赖在可选observation-collection extra，普通读取保持原依赖边界。版本与安装资格以实际候选验收为准。

本轮来源/计算正文来自旧QMT只读源码；原始来源SHA在build/observation-collection-001/retained-source-sha256.json，运行代码全部归本仓。新配置在独占QA目录冻结，SHA见sources-identity.json，原21路拆分为港股及统一大陆行情，09:00保持当前规格。原SDK/wheel身份沿此前已验输入。

## 初始实际主链

独占根build/observation-collection-001，完整复制此前已验真实历史快照到data-main-001，旧数据根catalog字节保持。使用独立采集依赖环境及当前源码运行；本轮尚未构建最终a14 App wheel。

MAIN-003.json/main-003-run.json：固定HTTP响应回放更新eastmoney.shibor，三次GET，经原解析/完整历史重算、全部引用及股票分区验证后发布48指标新快照。snapshot=2febbcf9b2921b9960f4ff6327f8d66991b71a577db944ab52012ad3455c6943，10-28单行数值为明确合成1.125等，旧snapshot保持。其余来源没有授新增实取资格。逐行诊断首轮导致200秒校验截止失败，旧current保持；去掉逐行跟踪，阶段计时的正常主链通过，完整校验约80.157秒。诊断运行与前次缺依赖/配置失败日志保留在QA根。

APP-BROWSER.json/browser.json：当前源码App实际TCP提供既有生产SPA，读取新snapshot；1440×1000及390×844显示新日期/1.125、固定同版本原始行与图表。全部GET，未预期控制台/pageerror为0；HTTP线程/监听、App读池与owner关闭确认。截图在本任务visualizations/observation-collection-001。Browser plugin未提供，使用现有Playwright/Edge。此处为源码App与已冻结生产SPA组合，不能扩称最终新wheel安装或真实供应商发布。

## 边界验证

原观察和App生命周期回归加本轮5项，36通过。覆盖窗口落库中断时current/回执/完成/尝试整体回滚，完成窗口不依赖最近100条回执且拒绝重复提交，403原字节保留/旧快照/HTTP关闭，长限流立即停止，以及股票历史/新增字符串精度、可选列和父原件完整保留。

股票更新采用字典列合并，仅展开日期/证券两个排序键，再写逻辑string Parquet；避免历史字符串整表重复展开，兼容原读取/验证。新增预算检查限制更新行数、列数和Arrow字节。原始无顶层usage的合法manifest通过既有asset_contract默认规则补足新资产约束。相关初次失败日志保留，最终pytest.xml为36通过。

初始主链后补了资产默认/字典合并与排序修正；最终候选仍需在调度接线完成后重新绑定源码身份及安装主链。未将初始MAIN-003扩称最终a14全量资格。

## 继续工作

受管调度后继已完成原入口普通安装的三代停止/同窗口恢复/完整发布/完成去重及生产SPA，当前精确输入与剩余范围见[安装进展](2026-10-29-observation-scheduler-progress.md)。下段初始待办保留当时上下文，09:00接线/安装已按该后继推进；真实来源、自然窗口及完整观察资格继续核实。

完成同一采集入口的09:00两日补跑、有限重试/停止/恢复和公开状态；补齐21路解析/实际来源与A大陆指数合同验证，处理全部失败/部分失败/CAS/超时/资源边界；完整新安装App/生产SPA和独立两轴审查。新股票原始响应的字段/类型容量边界、配置递归/URL准入及CLI异常也继续集中核查。真实自然09:00窗口、统一升级回退、真实策略M1及完整模块C保持未完成。

旧QMT源码/配置/数据保持只读，未操作QMT界面、137/140实例、真实下载/下撤单或生产。模块goal active，本轮无用户必需操作。
