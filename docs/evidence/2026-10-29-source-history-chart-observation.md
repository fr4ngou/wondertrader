# 来源范围与分段来源的独立App链

类型：开发验证记录。结果：pass（固定HCO开发候选），独立双轴complete；完整模块C及M1继续in-progress。关联[HCO-R1..R4](../specs/source-history-chart-observation.md)。

## 根因与实现

SDK0.15已返回实际观测窗口、Archive/Observed/Partial、准备原请求身份和跨根provenance。App的native_chart只投影K线及集合摘要，页面因而丢失这些来源事实。本轮在唯一投影层复用SDK闭合校验，新增图表1.7及有限typed观测、完整原分段metadata和各段实际首尾时间；原reason丢弃。canonical1.4、旧source1.5、日线1.6的JSON继续省略新增空字段。

MinuteWorkspace与保留MarketPage复用SourceHistoryStatus，显示当前根数/请求根数、实际来源窗口与读回根数、有限中文准备状态；分段身份/内容/单位折叠展示。读取中、失败时图表及来源一起隐藏，恢复后显示本次结果。Partial完全沿源状态，即使实际返回6/请求6也保持Partial。策略目录继续只读名称、简介与版本。

## 固定输入

本轮公开QA根为`build/source-selection-display-001`。14来源/13QA/65原件分别固定在SOURCE-002.json、QA-002.json、RAW-002.json及对应frozen-*-002镜像；REVIEW-INPUTS-002.json绑定清单SHA。冻结过程的001因B并发源变化失败，九项原native清理标记均true、cleanup_errors为空、owner未保留；其原件继续保存。

| 输入 | 本轮固定身份 |
|---|---|
| 独立Appa18 wheel | `04a7abb8d8e684b2d99660d81c68c91ae46acd895bb019d7bf9de0e3ff5842fa` |
| SDK0.15 wheel | `33bf4675a063c0cd46d6a510d582d7c2f4f9755b9e3b46d4e3a69cc121cdc335` |
| 普通离线安装 | runtime-venv-001，35发行、4787 RECORD；11私有wheel逐成员字节核对，pip check通过；INSTALLATION-001 SHA `e00cc1d921a38bb4361de2e63cdf67ee2173cabb88b15efbc20c41c114b10a55` |
| A来源005安装清单 | `fdbaf6b644919d2988add73ab216ab10958a3636e2e1cb0687e92b3dd1043727` |
| HPR e安装清单 | `5c3e3ffb082f09c2965c70336664f81b1816b951c8c676d58d397c35d4623ad3` |
| App根锁 | `4b7357d9a0e90e233f854ef33349bb1da95d9c6a04332882b31abbcaad594477` |
| 来源清单002 | `d07b129db8d8021b6f101a1e3eb708283782869d38fc6dce100e0a815cdeb62c` |
| QA清单002 | `66b47567011d2423c53d3c922074c15cb808c6a8923a96ad7ae3be453ae92823` |
| 原件清单002 | `f7240ef40b586bef996879f5839beb9020aeb42fe2cd9e5ac5798d21e661422b` |

App001包含已交V1历史三版本、signals a4、V2 a3、risk a2、AI、ETF规则及原core/variants/native；此处只证明共同安装，不增加这些算法的原生执行资格。App构建后B更新execution_configured.py和execution_process.py；APP-SOURCE-DRIFT-002.json明确列旧安装/当前源码SHA，HCO七产品文件与安装输入保持一致。该固定App沿构建时完整快照，不冒称已包含B后继改动；本轮执行配置关闭。

私有HPR/源进程部署及认证仅留ACL目录`main-002/private`，CONTROLLED-INPUTS.json保存配置摘要，不复制正文到公开镜像。输入六根来自已有离线原值根，原根所有文件SHA前后相同；测试prefix与晚到来源单独标识synthetic/unknown单位。

## 主链与回归

全部运行命令经原`scripts/native.py::run`，private_console=True、创建期Job、有限总截止/输出，结果在原命令终态后确认。main-001、main-002各自独立目录，App/来源/HPR均经正式Settings/lifespan/SDK启动；QMT3.6.8仅运行SDK替身，保留原SHM/Journal/原Helper及Reader，没有操作实际QMT。

| 阶段 | 实际观察 |
|---|---|
| package.py | 离线新环境、35发行/4787记录、11wheel成员及App源前后身份核验通过，外层Job正常关闭 |
| validate.py backend | 127通过；Archive/Observed/全部准备状态、原RID/窗口/单位/分段/未知原因去敏、坏计数/不连续段/错集合身份/未来窗口、旧模式/日线与HTTP失败后恢复；TestClient依赖有一条既有deprecated警告 |
| validate.py frontend | 7文件43通过；共有来源文案/折叠/HTML纯文本、旧组件重读隐藏/失败恢复、现独立行情/日线/自选、策略目录/旧深链接 |
| typecheck002/build-final002/chunks002 | 全通过；18成员生产SPA，主入口268.2KiB，五个必要页面分块可达，ZIP逐成员SHA一致 |
| main.py 001及002 | App先Archive5、Journal0；来源晚到后6根OHLCV逐字段等于六根输入；两原分段4+2，原捕获身份/单位完整保留。源窗口09:35..09:36读回2根，准备调用返回及原RID保留；6/6仍为Partial，6/300亦为Partial |
| 同请求/界面重读 | SDK及App重复结果一致；Journal保持3次（准备前读/原准备/准备后读），SDK替身download调用仅1次；浏览器GET不新增准备或下载 |
| 生产SPA实际页面 | `http://127.0.0.1:53003/market`（验收后关闭）；1440×1000、390×844，LA浏览器仍显示上海时间；实际Partial6/2000、窗口2根、分段详情、主动刷新、注入503后重试恢复实际来源通过 |
| 明确DTO边界替身 | 浏览器回放实际Archive DTO及构造Observed、Unknown、旧1.5、空结果，分别核文案/无旧段/0根/空时间；这些状态仅授边界展示资格，不冒充来源实跑 |
| 实际停止 | 同页等待实际App停止、HTTP线程join/owner关闭完成后再点读取，完成态失败明确、旧K线/日期/来源隐藏；未用loading态验收 |
| 完整关闭 | 两轮App shutdown_complete、reader_threads0；SourceMarket/HPR的Job/句柄/EOF/reader/monitor全部闭合，forced=false、pending=false；源3.6资源闭合且forbidden_attempts0；外层原native成功返回。main002外层11.172秒 |

Browser plugin not available，本轮沿既有Playwright/Edge。页面身份/主体/无框架覆盖、交互、手机scrollWidth390及截图均通过。console仅有明确注入503与实际停止后的ERR_CONNECTION_REFUSED，pageerror0、warning0。截图固定在`C:/Users/frangou/.codex/visualizations/2026/10/28/01a1827c-4d9e-7d23-b0c3-a7ddb931c0d3/source-selection-display-002`，SCREENSHOTS.json绑定SHA；已人工查看分段与Unknown手机图。保留MarketPage由组件回归证明，本次生产入口沿main.tsx挂载MinuteWorkspace。

## 限制与后继

以上证明HCO固定安装/实际页面链及明确边界替身。真实QMT下载、137/140活动实例、真实下撤单与生产发布均未操作；市场完整覆盖、来源实际单位及收盘可知资格继续按A原事实。两个B执行源的后继改动须同候选重建后另验。完整真实策略M1、所有保留算法的原生执行、独立安装升级/回退和模块交付继续，goal active。独立审查和最终作者门原件沿文末登记。

## 分段单位的审查修正003

两名独立审查者分别发现002分段详情只显示成交量单位，HCO-R3要求的每段价格/成交额单位尚未显示。已在共有组件补齐三种原单位，新增两段价格/量/额单位分别不同的回归；SourceHistoryStatus组件13通过，等价于前43项回归加1项新增单位案例，原其他组件/后端输入保持。

最终生产SPA003的18成员ZIP SHA为`cdf772c2b21ece9b0673d5b288ee572cead43fb30db673418c1dc4df0cfe00ae`。TypeScript003、生产构建003、分块检查003及第三轮实际安装/HTTP/浏览器main003均通过，原App001/SDK0.15/来源005/HPR e保持固定；browser逐段对照原metadata三单位。第三轮URL为`http://127.0.0.1:62786/market`，已正常关闭；外层原native11.984秒，Journal仍3/替身download仍1/真实下载0，所有owner清理证明完整。截图在同一visualizations根下`source-selection-display-003`，已人工查看最终分段手机图与实际停止后失败图。

最终SOURCE-003/QA-003/RAW-003及对应镜像共14来源/14QA/101原件，SHA分别为`ac753392c46c34f264268a025dbee547d3574ab3a8c0d60d25ec6c7720b65671`、`652bb5e85af945362cd8d783eb1e82c7eed9fad4809a7e5adf8d5c504c74ffe6`、`5a38c192530cc016a947a1ec49a2798b7d59ca6cb8577361bb53be0cf6e56f5b`。002及其审查前原件保留。003独立delta结论与最终检查继续登记；A新交RS14异步跟踪组件按后续统一候选消费，本轮不将005旧RS13链冒称异步跟踪已验。

截图清单为单独追加身份：RAW-003中的SCREENSHOTS.json快照仍列002八图；当前SCREENSHOTS.json明确列003八图，SHA`2fb4256b701fd9626ec963528098b9d79a64628a42175e97da579ce475f93fdb`。两名审查者分别逐张核003文件，最终DELIVERY另外绑定该清单及八图，保留RAW-003原件。最终门同时复核11个私有wheel、18 SPA成员、19份受控输入摘要、全部003当前源码/QA和适用运行收据；其运行结果沿FINALIZATION登记。

## 最终独立审查与交付

规格轴003报告SHA`ca832aff253623562f3de944ad815fc663f93e943f0e80bcd8a3014c22a39c10`，规范轴003报告SHA`e374f3eb94de49bbbae4cf40e25de9e300ed077f1b0824c7f7f23e72f23db2a9`，结论均为HCO固定开发切片complete，单位P2闭合且新增P级0。两个002 full gap报告保留；003 delta分别确认全部适用要求的影响闭包、独立重算安装/冻结/主链/截图及资源关闭，所有独立检查命令已终态。真实QMT、M1、最新B完整组合和全模块资格继续未授。

最终作者门由`finalize_gate.py`依次通过原native执行project.py check与finalize.py，实际结果以`build/source-selection-display-001/FINALIZATION.json`和对应日志为准。DELIVERY.json绑定App/SDK/生产SPA、14来源14QA101原件、两审查报告、003截图补件、19受控摘要及文档快照；该候选可交A唯一集成者按此身份消费。A新RS14仍以独立后继集成和升级/回退验收，不替换本候选的原证明范围。
