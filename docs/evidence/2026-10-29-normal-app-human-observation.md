# 普通安装的中文指标说明与导出

类型：模块C验证记录。状态：in-progress。对应[COP-A1/A2/A7/A8](../specs/guanheng-operator-platform.md)、[OBI3](../specs/independent-market-observation.md#obi3-http与页面)。完整C和M1继续。

2026-10-30当前后继：用户页面503的直接原因是旧预览仅配置回测归档，观察目录和更新接口返回not_configured。现预览72048/pid54664使用普通a27安装及SPA004，在http://127.0.0.1:18120/observation提供48项已发布指标；preview-qa-003实际默认图表16行、目录/更新/定义/历史/series/CSV全部200、桌面及手机无横向溢出、pageerror空。数据沿原归档覆盖，自动更新心跳过期如实展示；自动调度和整个系统正式发布资格仍待完成。

SPA004的typecheck006、build004、chunks004和frontend-threads005共81项通过；完整调用链复用main008的真实分钟/日线、自选、400条绩效、三格式逐值下载和503/缓存恢复，最后两项P3只涉及两处中文频率和毫秒变量命名，实际预览再次验图表/说明/CSV。独立full002及delta003分别登记规格与规范结论，输入冻结见REVIEW-INPUTS-002/003。WT/观衡解耦按ADR-0016/WRI另行推进，完整C/M1/M3继续。下文各代预览和失败保留当时事实。

## 根因与实现

原市场观察直接渲染机器资产清单、内容哈希、字段代码、谱系JSON和HTTP示例，违反用户确认的日常业务页面范围。DataAssets改为中文指标说明，按名称/来源搜索、频率筛选，展示来源、覆盖、字段含义、公式、读法和限制。定义刷新失败保留同指标成功内容及原读取时间。

原/observation/api兼容地址改为导出页面，复用exports接口，固定指标、当前快照和日期，支持CSV/JSON/JSONL。日期越界或倒置时停止生成下载链接。原件、谱系、内容校验与机器API保持原owner，本轮未改后台算法、存储、读取预算、交易或WT源码。

## 安装与验证入口

复用A已接受build/guanheng-app-a27-install-001/runtime001普通安装：Appa27/V1a7/corea8/nativea1/SDK0.15，App29/Host15发行；交付SHA f3fc93b82dea2bc9aee7a425171cf66c713474f7b351733013bfac008b4a541f。历史沿原R7 entry及原Host pythonw，由App实际SourceMarketProcess管理，固定336 store，排除跨夜采集根；无源码覆盖。

观察复用build/observation-provider-completion-001/main-003/data已发布48指标，零采集更新；回测复用retained-real-analysis-003/ui-002原400条归档，零新运行；自选/配置只写本轮独占根。工具与SPA在当前visualizations下normal-app-user-chain-001，原件在build/normal-app-user-chain-001。所有辅助执行沿原native.run隐藏Job、有限总截止、有界输出和实际树/管道回收。用户18120预览保持原运行。

Browser插件未列出，使用仓库现有Playwright/Edge：1440×1000、390×844、洛杉矶浏览器时区。typecheck-002、build-001、chunks-001通过；focused-threads-001四项新增回归及frontend-threads-001共75项通过，含中文筛选、空目录、技术字段退出、失败保留/恢复、导出快照及日期固定。保留现有Vite配置提示，未修改依赖或延长产品截止。

## 原触发、失败和诊断

main-003使用旧SPA005：真实2000分钟、日线、自选和400条报告通过，随后用户展示断言失败，资产ID/64位哈希/pre实际可见。main-005/006使用新SPA001：中文说明、宽窄屏及技术字段断言通过，浏览器导出超时，运行保持失败。main-007停在自选保存结果未知；未重复提交，保留原请求和文件。

main-002/004/005报告失败，main-003/006成功。main-004两个实际HTTP报告请求均约5秒后503。原Archive单读400条成功；直接并发库调用429属于原库容量语义，App已有单worker串行调度，不据此改锁。profile001原5秒预算失败：系统读取调用累计约4.65秒，JSON校验约0.34秒；同期E盘队列27，支持磁盘等待是本次耗时的重要因素，完整负载归因仍待。

main-006导出实际503/observation_timeout。codec001初始化约2.33秒；observation-probe001经原BoundedReader/原_dispatch、同一首指标及末日导出成功，1行/322字节、约0.875秒、线程0。此对照不足以证明全部冷启动/负载条件正常，组合浏览器仍待。005的REPORT-HTTP曾因QA并行写同一文件损坏，006起汇总后单次写；损坏原件不计为可解析成功证据。

main-001在App启动前遍历约1GB全部对象导致QA截止耗尽；后继只绑定三份目录数据库，选中内容由原owner核摘要。main-005的App正常关闭未在预算内确认，外层原Job实际回收/树归零/EOF/join/资源关闭九项全true，错误空，无保留owner；其子PID复核已退出。006正常关闭、监听关闭、读池0及源closed通过。各代关闭分别核实，外层强制物理回收不替代App正常关闭资格。

frontend-001总150秒超时，focused-001为fork worker启动超时，均未执行到测试，失败/清理收据保留。相同源改用线程worker后四项通过，后继75项约22秒通过；该工具差异单列，不改变产品行为。

## 剩余

独立审查001期间发现新导出直链绕过原浏览器2并发/32等待/15秒D，作者确认并停止该实现的完成判定。现request统一拥有JSON/Blob的传输和解码，完整正文结束后归还名额，finally取消剩余传输；下载核当前快照响应头并限制16MiB。ObservationDownload按查询身份隔离进度/错误和取消，释放对象URL。导出页面、看板和原图对照均消费它，原API/算法保持。新增共享名额持续到正文结束、正文停滞取消/恢复、超容量和错快照拒绝、失败重试、查询变化/卸载取消回归均通过。

typecheck-005、build-003、chunks-003及frontend-threads-004通过，共81项。frontend-threads-002有77通过/3个旧导航用例超时：QA遗漏package.json既定testTimeout=15000，实际沿默认5秒；按原仓库15秒参数的003通过80项，新增错快照后004通过81项。原失败保留，未改产品读取预算。文档检查docs003在普通App解释器下150秒超时，九项清理true/errors空；相同150秒预算的默认Python3.14入口docs004于116.972秒通过，不据两个不同运行归因解释器性能。

main-008沿普通安装原create_app/SourceMarketProcess、原336商店及真实48指标根，生产SPA003完成2000根分钟、日线末五根与A原响应相等、自选一次保存、正式策略资料及原400条绩效；三格式浏览器实际GET固定同指标/快照/末日，JSON/JSONL与原series相等，Python csv逐字段比对同一行，503后用户重试CSV字节相同。说明刷新503保留计算方法和原time，恢复后错误退出。两个console错误均来自显式注入503，其余pageerror/框架覆盖/资产谱系请求0，1440/390无横向溢出。App线程join、双监听关闭、shutdown_complete、两读池0、源closed/nonforced且errors空；只读目录数据库三SHA保持。

旧用户预览32511/pid44584在后继续接时句柄missing且进程已不存在，原控制路径匹配的辅助进程0；终止原因和原App正常关闭资格unknown。已从普通安装重新启动开发预览18270/pid65468，原地址18120，仍用已看过的SPA001与48指标/真实历史；最终修正SPA003在隔离main008验收，待复审后更新。没有停止QMT或跨夜采集。当前私有历史辅助进程属于旧候选预览，最终WT数据服务归独立WT运行包。

用户实看预览后确认原18120的catalog/updates实际503、code=not_configured，回测活动任务0。旧预览沿原exec会话47158中断，exit1，正常App关闭未单独获证；随后新预览32511/pid44584在相同地址启动，使用A普通安装、SPA001、已发布48指标和原历史owner。唯一长期用户预览保留；本轮QA均终态。预览启动器沿原CLI，先执行已有Parquet启动自检，未覆盖源码或改API预算；未启采集、账户、执行或真实写。

preview-qa-001已读目录/定义/更新200，但未在45秒观察到series响应，保留失败；首次QA没有保存页面错误/正文，原因unknown。补充网络/正文记录后preview-qa-002真实浏览器通过：默认债券看板16行和实际canvas图表，目录48项，目录/更新/定义/历史/series全部200；1440/390无横向溢出，说明技术字段退出，CSV实际下载通过，pageerror空。该次约2.985秒、外层Job/树/EOF/join正常；不抹去前述冷启动/负载失败。截图和BROWSER-RESULT在visualizations本根preview-001，当前用户地址http://127.0.0.1:18120/observation。

最终浏览器下载/失败恢复已由main008覆盖，独立full002分别核131份冻结输入：规格一项P3为频率代码遗漏、规范一项P3为毫秒量命名，P0–P2均未发现；最后源码与19份SPA004在delta003共30份输入复验，要求及代码范围分别确认。完整冷启动/负载验收保持缺口。最终资料沿build/normal-app-user-chain-001/DELIVERY-001.json绑定，当前预览仅为开发实看。

文档检查005发现共享工作树新增的ETF规格/证据及独立WT手册/证据四项尚未加入索引，按现有正文补齐导航后以006重新核验；005失败原件保留，未更改对应功能状态。

旧预览18270/pid65468切换前仍有进程但18120未监听；沿原会话中断exit1，正常App关闭资格unknown。新预览003采用相同普通安装及原CLI启动，日志确认startup complete；实际用户地址浏览器验收通过，唯一长期用户预览保留。未触动QMT或跨夜采集。B真实资料首目标/BT比较已有后继，完整RT观察交接、股票退出和实际周期仍待B；独立WT/统一安装、升级回退和完整模块资格继续。真实写、QMT界面、生产、共享Git和新增WT源码均未操作。
