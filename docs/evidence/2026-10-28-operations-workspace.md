# 中文只读运行状态工作区验证

类型：验证记录。日期：2026-10-28。状态：首切片与后继详细采集状态隔离安装开发验收通过；真实QMT、完整F20/模块C及生产资格继续待验。

范围与验收见 [OPS 规格](../specs/operations-workspace.md)。开发者2拥有专用投影、路由、页面及测试；公共接线仅修改规格列出的片段。既有来源与采集证据继续归原 owner；本次不把历史 passed、6982/6928/54 等现场记录转化为当前状态。

## 根因与最终实现

IndependentApp 的 `/operations` 原先进入通用占位，旧 OperationsPage 依赖未迁入的 workbench/bootstrap/运行服务模型。当前实现新增专用 `guanheng_app/operations.py` 与 `workspace/OperationsWorkspace.tsx`，只消费当前 owner 的公开 status 与原独立 SDK 的 capabilities。复用已有读池和原 SDK 截止，无新增监督者、持久状态、账户读取或交易动作。

公共接线限于 `app.py` 的 router import/include、operations capability 及从未迁入字典移出 operations；`IndependentApp.tsx` 的懒加载和显式路由。索引与业务集成说明分别追加专用链接。未修改 NOW/CURRENT、settings、quote_collection_process、采集服务/连接器、QMT 源端、原生核心或其他交易任务文件。

## 固定输入与制品

Windows，Python 3.12.14，Node/Vite/React 取本仓锁定环境；安装目标与运行输出在 `build/operations-workspace-002`，原件保留。`source-manifest.json` 固定全部 App Python 与本切片前端输入；构建前、安装后、实际主链后及交付核对均无漂移。`review-manifest.json` 补充最终测试入口身份。以下为主要源码 SHA256：

| 文件 | SHA256 |
|---|---|
| guanheng_app/operations.py | f36b80d6bb4be468b0285499320c620e6019df4edf3fcba7b3734549221f7ded |
| guanheng_app/app.py | c99c23d4296ff0a328f626f09cefb5afc32bbfbe082978fa874eb7257348f66e |
| workspace/OperationsWorkspace.tsx | f151dba7bf81acc6ac1f2d0e7f89fcdfbec9a11e27dba67e93cd79ca5aa9e25e |
| workspace/operationsApi.ts | 7d655e04c3a1dcca4675d8c23f5f20e7cc4ea8db995f398706a38cd5f7da07b0 |
| workspace/IndependentApp.tsx | ca4e76bab069181c7127ef2ee3ce2d0c4e1b8af386a60939fec932ab358ef3e0 |

独立 App wheel：`guanheng_app-0.1.0a3-py3-none-any.whl`，SHA256 `3cdba8d92adaca47be26b29cc0052d4df731ec310062e2e499fff7205bc2332e`。通过 pip 安装到本切片 site，五个原有策略依赖分别构建 wheel 后安装；SDK 来自已安装的 site-packages。运行以 `-I -B` 启动并断言 App 来自安装目标，运行目录保持独立。未更改共享虚拟环境安装内容。

## 实际主调用链

入口：`tests/integration/operations_workspace/user_chain.py`，内部调用同目录 `user_chain.mjs`。显式传入 site、生产 dist、独占 output、外部截图目录、Node 与 Edge。原 native.run 沿有限120秒总预算管理隐藏 Job；内部浏览器60秒预算。实际退出0；`main-chain/main-chain.json`、`browser.json` 和原日志保存原件。

原 App HTTP 在隔离端口 52999/53004 启动：第一实例无来源配置，读取原 QuoteCollectionProcess/QmtHostProcess 的 disabled；第二实例连接仅本测试拥有的 HTTP 能力替身，经实际已安装 MarketClient 发出4次 GET `/api/market/v1/capabilities`，投影“本次可响应、历史支持、快照未声明支持、QMT 来源”。该响应属于隔离合成来源，未访问实际 QMT 端口或共享内存，不证明现场行情正常。

生产 dist 经同一 FastAPI 实例服务，Playwright/Edge headless 实际打开 `/operations` 并点击“重新读取状态”。Browser plugin not available，采用显式 Playwright。两实例页面均读真实 HTTP；全部浏览器请求为 GET；未请求旧 workbench/bootstrap 服务。两个 App 的 lifespan、读池线程和监听已确认关闭，测试能力源线程也已 join。

| 检查 | 结果与证明范围 |
|---|---|
| 页面身份、非空、框架错误层 | 通过；中文系统状态与三个区块可见 |
| 未配置与本次可响应 | 通过；原进程 owner、实际 SDK 能力查询分别取数 |
| 手动重读 | 通过；点击后实际新增状态 HTTP 请求 |
| 时间与缺项 | 通过；北京时间接口观察，三个数据时间及计数/活跃度未知，显示原因 |
| 503 与恢复 | 通过；浏览器单次拦截503，隐藏旧状态，解除后点击取得真实 HTTP 恢复 |
| 390×844 与1440×1100 | 通过；无横向页面溢出；人工查看实际截图 |
| 控制台 | 仅人为503的预期网络错误，额外 console/pageerror 0 |
| 关闭 | 两实例 shutdown_complete、reader live_threads=0、端口拒绝连接 |

截图保存在 `C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/operations-002/` 的 configured、unconfigured、mobile、error PNG；截图为隔离运行画面。

## 集中边界、审查与静态检查

命令及退出码：

- Python pytest：`tests/integration/operations_workspace/test_operations.py` 与原 `qmt_quote_collection/test_app_collection.py`，退出0，11项通过。覆盖原 owner 默认关闭、当前 owner 已停止→意外退出→就绪、未知资源字段、配置失败隔离/去敏、SDK失败→恢复、原超时与读池满，原 App 采集生命周期4项继续通过。原件位于 `build/operations-workspace-001/pytest.log`、`pytest.xml`。
- Vitest：OperationsWorkspace、operationsApi、IndependentApp 三文件，退出0，31项通过。覆盖中文状态、缺项、只读请求、停止/失败、隐藏旧值、重读恢复、格式拒绝及原导航。原件 `build/operations-workspace-001/vitest.log`。
- TypeScript `tsc -b --pretty false`、Vite production build，退出0；实际新页面独立懒加载。原件 `build/operations-workspace-002/typecheck.log`、`build.log`。
- `python -B scripts/project.py start`、`python -B scripts/project.py check`，退出0。本检查只证明文档静态完整性。

静态自查按最终源码清单核对 OPS-R1–R4、规范、状态来源、固定白名单、截止及现有调用者。发现并修正未知资源布尔值被展示为“无”和查询来源标签缺项，两项均已纳入最终构建及回归。首次组件断言把隐式GET当作显式method，已改为核有效HTTP方法；真实浏览器原本全部GET。首次隔离安装缺少原策略依赖，随后构建其独立wheel补齐并重跑，最终候选002完整通过；不把早期失败作成功证据。

审查范围 none（独立审查触发条件）：本切片复用既有有界读池/owner/SDK，不改变交易副作用、持久化、权限、并发所有权或发布切换。本轮完成开发者静态自查，独立审查未执行；后继接入采集状态契约时应复核新接口与实际来源。本记录不宣称两轴独立full审查通过。

## 首切片剩余项与下一动作（详细接缝由下方后继接通）

OPS-R1、R3及公开可取得范围的R4通过本切片开发验收。OPS-R2的实际来源时间、收到时间、发布/文件时间、采集是否活跃、计数及覆盖仍缺独立 App 可消费的公共契约；按规格列出的字段交采集owner提供接缝，随后本页面消费并验真实正常/停止/失败，继续保持实例身份与时效校验。当前字段保留null及明确原因，禁止将监听就绪提升为实时行情活跃。

未执行真实QMT连接、终端界面操作、生产常驻采集、交易/撤单、合入提交、推送或发布。源时间时钟语义与缺失证券调查继续归主会话；账户/多策略归开发者1。无新增当前用户必需决策。

## 后继：详细状态唯一读取与真实受管采集链

本段承接后继明确授权，替代首切片中“App公共接缝缺失”的当前判断。SDK0.13.0新增`runtime_status.py`，原`guanheng.collection_status`只转发同一模块对象；共享读/写/删除、同句柄前后校验、ReplaceFileW及原有限错误保持，增加同句柄修改时间返回。App0.1.0a4精确依赖新SDK；采集发行闭包的CMake DIRECTORY规则及writer_lifecycle源码清单同步增加SDK。

QuoteCollectionProcess.observe只读当前实例，核control_id、实际pid、configuration_sha256及前后owner身份；锁外读取，发布超过65秒或超前5秒拒绝。源原始毫秒、最近回调墙钟、子服务发布墙钟、同句柄文件修改时间和API观察独立表达。当前进程状态优先，断连/停止不会因累计计数增长显示已连接；停止前记录明确标历史。错误和failure.json按有限白名单投影。

### 最终身份与发行

最终产品实现及首次主链/回归输入：`build/operations-telemetry-002/review-inputs.json`的21文件。SDK wheel `guanheng_market_client-0.13.0-py3-none-any.whl` SHA256 `a9826e42484c308fca719acc18e2f8f5fc5fad9869b38c043ee3be4df6508640`；App wheel `guanheng_app-0.1.0a4-py3-none-any.whl` SHA256 `f8973f59ecb0779cf2936dc4ba758d06eac32b31ed5a9ad544e3db87d0a9ed5e`。前端位于002/dist；安装SDK/App与五个固定策略wheel到002/site，`-I -B`运行并断言App/SDK来自site，无源码PYTHONPATH。

采集原生二进制复用原005已核制品；在001/release独立复制原005，通过真实CMake配置/安装执行本轮新增的SDK DIRECTORY规则，并替换本次兼容转发文件。其余原005全部文件摘要相同。SDK规范构建器已逐字节校验显式源清单、wheel和许可证。原005文件目录与已运行制品均未覆盖。

本轮完整变更文件与SHA维护于`build/operations-telemetry-003/delivery-manifest.json`；公共片段与模块C归属见[模块C计划](../migration/module-c-delivery.md)。

### 实际功能与清理

主入口为`tests/integration/operations_workspace/collection_user_chain.py`及同名mjs：显式site/release/static/work/screenshots/node/edge/deadline参数。创建期外层ProcessJob持有隐藏driver，内部native.run共用固定预算，不连接实际QMT。安装App启动当前采集子进程→真实WinSHM→原生Writer→实际HTTP→生产SPA。源与基础资料复用原数据采集夹具，2只证券、两包共4条模拟报价。

002/runtime/VERIFIED.json记录等待→已连接→断连→停止：收到/成功提交/原生处理均为4，源心跳覆盖2、缺0、队列0、溢出0；原始源毫秒1793151070123保值。最近回调13:28:29.047797Z、发布13:28:29.088195Z分别表达；文件修改时间来自同句柄stat，允许自然与发布时刻相同。停止后保留同实例最后记录，active=false、status=historical；两个分钟DSB已归档。

003/runtime/VERIFIED.json是同一产品制品的后继截图/重读验真：周期发布允许短暂pending，浏览器按页面提示在原有20秒预算内最多4次重新读取，再断言当前连接和4条原生处理值并截图；不把pending的全未知截图当数据通过。所有请求GET，真实页面核原始13位毫秒、阶段/覆盖/时间，1440及390px无横向溢出、console/pageerror额外0。截图在外部visualizations的`operations-telemetry-004`目录。Browser plugin not available，使用显式Playwright/Edge headless。

最终002和003外层均退出0、树0、pipe EOF与读线程join；App shutdown_complete、reader线程0、监听拒绝连接，采集owner closed/pending=false/forced=false/error=null；源Agent已按原D关闭。原Native自身关闭/归档沿005有效证据和本次实际文件/收据复验，本轮未改其算法或生命周期。

### 边界、review及修复

002/pytest.log及pytest.xml：46项通过（本任务两测试文件及原采集status/managed process/App/lifecycle/service resources），包括错control/PID/配置、过期/未来、身份中途变化、pending/缺文件/截止、无心跳、非法计数、断连/重连/停止、去敏、查询超时保留采集值。002/vitest.log：33项通过，覆盖实际字段/三类时间/原始毫秒、历史故障原因、错误隐藏旧值/恢复、路由/只读与格式拒绝。TypeScript/Vite production构建退出0。

两位独立审查者分别完成full：规范轴初报1项P2，规格轴初报2项P2（共享一项）。已修正查询超时清空已完成采集观察、停止后隐藏具体采集错误；新增原触发条件回归，重建/独立安装并重跑实际主链。两位delta均complete、gap0，确认仅operations后端/页面及对应两回归变化，其他full范围可复用；关键最终源码operations.py `e45e083ac003667a582c26f07ebdc3e585e6c1a9815a41aea01b0da39e96c43d`，OperationsWorkspace.tsx `211d3ea558c02e638e66bc9c882db09c482ab3a087e963b3181f66af0cb8df90`。独立审查只读源码/日志/原件，未另跑进程；真实QMT、完整F20、系统与生产资格继续unknown。

001保留早期工具失败：CMake不在PATH时先失败，后从既有CMakeCache读取明确工具路径；外层harness误把wait返回exit0作False，已改为按退出码/异常处理，并在002/003重跑取得真实关闭证明。并行B修改的execution_process.py不在operations导入/运行链，保留其工作区改动，未把该未调用文件的漂移混入本切片资格。

### 模块C后续

OPS-R1–R4在本切片范围done；完整模块C goal保持active。下一段为V1 configured策略配置/运行主流程、既有回测/报告串联与A/B真实候选组合；正式历史查询进程App父接线按[SMP](../specs/native-source-market-process.md)规划。真实来源时间语义/54证券调查、自动收盘/全规模采集归A，多策略交易/原生运行归B。本轮未操作QMT、真实下撤单、生产切换、提交或发布。
