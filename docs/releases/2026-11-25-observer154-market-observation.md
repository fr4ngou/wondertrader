# 观衡154估值简化与破净观察发布

状态：deployed。用户明确授权“先合入，然后发布”，已完成本地master集成、普通制品构建、安装及正式18143切换。全A日频PB补齐保持待完成；本记录的上线范围为已验收展示、沪深日频PB和破净统计。

## 实现与验证

- 破净观察默认主板，点击创业板或科创板直接替换选择；打开多选后按所选板块合并家数和有效样本。上图为破净率曲线及家数柱，下图为5交易日变化，图、表和导出固定同一快照。
- PB主入口改为“沪深等权PB（日线）”和“全A等权PB（月末）”两按钮；申万加权补充口径从主入口撤下。全A原月末及最新观察保留实际频率。
- 市值/GDP只展示沪深北全A总市值与其除以上年全年GDP的比例，两条曲线共图，并显示实际除式。原图复用指数坐标范围造成市值曲线被裁切，已在坐标所属层恢复按数据自动定界，并通过原触发条件回归。
- 换手活跃度从统一展示目录撤下，历史分区与既有来源采集保留。

源码 `41b09e70a2b04033ae496ae1f0f1dbf7ca88764a`，注释标签 `observer154-market-observation-20261125-001`。最终38项针对性前端回归、TypeScript/Vite正式构建、572项本地软件回归及文档检查通过；CI002成功回执用于实际集成。上述前端结果有明确范围，未授整个前端测试集通过。破净归档独立复审及发布切换独立审查均通过，详见证据根的 `RELEASE-REVIEW.md`。

证据根：`E:/workspace/wondertrader-data/observer154-market-observation-20261125-001`，保存源码身份、CI002、安装、启停、正式接口、页面截图、数据保护比较及清理结果。CI001中断现场与后继成功回执分别保留。

## 正式采用

App `0.1.0a154` 安装于 `E:/workspace/wondertrader-data/observer-programs/a154-market-observation-20261125-001`。交付ZIP位于 `D:/wt-releases/observer154-market-observation-20261125-001/observer-0.1.0a154-windows-x64.zip`，SHA256 `e5327692811f6c5b3c1de873e9db82a59db84d0be822a94fcd333e7daffffe41`。包清单SHA256 `9af5d9e406957ae43bf8c89d0cf83890d6c646835da34e64188285222263fbd4`，安装收据SHA256 `8c06461c26fe00843d063961ec5b8ec164fa5719d51b77d764f2644ab462ce0d`；95个包文件核验及实际安装依赖检查通过。

正式地址仍为 `http://127.0.0.1:18143`。153正常关闭，154 ready且alive，Web PID53704，控制身份 `9d175ed5-6e91-404b-85a3-308c7d90bbb5`。稳定 `web-profile.json` 和 `DEPLOYMENT.json` 已采用154，profile SHA256 `a00354d76d288bc66ad5b6c8195db68997666756295e6d26a9ae63feb7cdf4bc`。原受保护读取配置路径及SHA256 `626743631ddeee8942492923500a905c4f3bbf3016d022837a2f4e79452f7518` 保持，原个人观察目录接续。正式HTTP静态资源逐文件等于新安装，避免浏览器旧缓存掩盖升级。

原146观察更新监督者和子进程均正常关闭，新154控制根为 `E:/workspace/wondertrader-data/observation-update/observer154-breaknet-20261125-001`，控制身份 `5c2ced89-6dab-481d-b841-ea155f822789`。新监督者及子进程ready且alive，稳定 `UPDATE-DEPLOYMENT.json` 已原子采用154并独立核对解释器、入口、controller、prepared及deployment摘要。38路来源保持，唯一业务配置变化为 `baostock.pb.derived_metrics` 增加 `valuation.breaknet`；原09:00、17:30、21:00北京时间计划保持。

## 数据与页面验收

原数据根 `E:/workspace/wondertrader-data/observer-market-unified-20261104-001` 沿原lease/CAS发布破净历史，新增997交易日。派生快照 `c2f4f2c0167d4bcc2a8bca939d4812db91fc8181ada694027ed5a6078f99be67` 与前代逐项比较：84个旧指标的完整登记、31张源表、10份逐股分区及5,087,167条逐股事实保持。更新器随后正常推进到后继快照 `3515d964db0f0a01a6924a101aeb401f664cc9e93a53fbe5c0455f6b3e7a018d`，正式接口再次验证通过；后继采集的来源修订由原更新回执追溯。

正式近三年窗口2023-11-24至2026-11-24，七种板块组合均为726交易日，破净率及5日变化均有值；沪深等权PB同窗726日。最新主板585家/3151个有效样本=18.5655%，科创板21家/616=3.4091%，三板合计644家/5164；多选CSV共726行且快照身份相同。

正式浏览器验证主板直接点选科创板、主板恢复、PB两按钮及日线读数、市值合图与除式、换手导航撤下。截图 `UI-production-breaknet-full.png`、`UI-production-gdp-all.png` 留存。最新全A市值112.57万亿元，除以2025年GDP140.19万亿元，显示0.803倍/80.3%。浏览器警告和错误列表为空；并发采集期间曾有一次更新状态503，后续轮询自行恢复。Web生命周期failure/closed/OS_exit为空；本代延迟日志未产生web.log或web-log-status文件，更新器无failure/closed文件。该结果只证明本轮已观察范围。

## 待验与回退

- 全A日频PB仍缺北交所历史PB/净资产输入，外部连接中断后未取得完整可核历史；保留全A原月频/最新观察，近三年54个实际观察点。沪深日频覆盖与全A频率分别显示。
- 本次全A市值/GDP序列从2026-10-16开始，当前18条实际记录；未拼接其它市场口径或补造更早日线。
- 已验升级后的自动补齐及后继发布；下一09:00自然窗口和全部来源最新性继续待验。当前资料有效截至11月24日。
- 本轮未启停或更新交易WT/QMT。交易恢复资格沿原交易发布记录继续核实。

回退沿证据根BEFORE配置：正常关闭154 Web，使用原153 profile启动并核18143，再恢复稳定Web入口。更新器回退需先正常关闭154监督者及子进程，沿原146配置启动并恢复UPDATE-DEPLOYMENT；原数据根及已保存历史快照保留，实际当前快照另行核实。

## 收尾

已正常移除 `E:/workspace/wondertrader-worktrees/observation-controls-20261124` 与 `E:/workspace/wondertrader-worktrees/observer154-release-20261125`，实体目录和Git登记均已核对。旧开发树14份工作文件逐字节匹配采用结果，原分支、工作差异、独有测试及可验证bundle保留于证据根 `development-recovery`。发布记录工作树在文档CI集成后按同一规则移除，结果归 `CLEANUP.json`。

已检查E盘任务worktree与证据根、D盘本次构建根。`D:/wt-build/observer154-market-observation-20261125-001`、本次复制的第三方轮子、隔离QA历史/自选、私有配置副本及CI缓存已删除；正式安装、D盘交付ZIP/包、日志和恢复材料保留。两个CI pytest-temp目录普通删除失败，随后强制删除被自动安全检查拒绝（blocked by policy）；未绕过拒绝，残留路径与下一步沿证据根 `CI-TEMP-CLEANUP.json`、`CLEANUP.json` 登记。本任务负责后续在允许的维护方式下完成这两处清理，软件发布不受影响。
