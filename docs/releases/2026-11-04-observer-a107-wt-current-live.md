# 独立观衡a107当前WT实例跟随

日期：2026-11-04。类型：发布与现场验收记录。状态：App/SPA已独立部署18143；当前实例只读接线及页面通过，真实WT正常换代跟随待Root恢复现场后补验。

## 行为与职责

此前观衡启动时固定WT四项身份，WT正常换代需要重新配置Web。a107显式设置`GUANHENG_WT_CURRENT_FILE`，每轮在原有界读池及原截止内读取公开CURRENT，再复用原SDK状态、业务引用和进程身份校验。同一轮账户与策略共用解析后的四身份。固定四环境变量模式继续保留；指针失败沿读取失败路径处理。

账户、策略和实例状态页每15秒刷新，保留手动刷新入口。策略详情新增可选`runtime_scope_id`，已知运行代改变时清除旧代账户回退；整轮失败保留上次成功视图及原时间。实例读取失败仍显示失败/当前未知，同时保留该行上次成功组件和原发布时间。页面布局与金融计算沿[a106交付](2026-11-04-observer-a106-strategy-pages-live.md)保持，观衡仅读取公开定位与结果，WT生命周期由Root拥有。

需求与接口分别沿[服务控制规格](../specs/wt-service-control.md)、[策略详情规格](../specs/observer-acceptance-repair.md)、[模块正文](../modules/observer-strategy-details.md)及[独立运行手册](../runbooks/observer-runtime.md)。采用原SDK文件读取接缝，WT核心源码与金融账本均未因本次观衡接线改变。

## 源码与制品

候选分支`codex/observer-current-20261104`，基线`ad40df03e614ea6cce3e441f7c5878350c4d18a5`，最终业务/测试候选`f0492fe0d153e04a46b58a1f7f58ec619596a9fe`，20项变化。主线集成由Root接收本候选；本记录只授已安装运行制品及下列实际验收范围。

QA根：`E:/workspace/wondertrader-qa/observer-current-20261104-001`。`SOURCE-CAS.json` SHA256为`466804bc9fa6de809ee8c2e73aa63c9790a6cbb51430bd71f78f1481b63f2249`，绑定候选、20项变化、486项构建输入和Root公开契约摘要。构建输入逐项与候选一致，未跟踪文件未进入正式构建。

- 版本：`0.1.0a107+wtcurrent.1`。
- ZIP：QA根下`build-003/observer-0.1.0a107+wtcurrent.1-windows-x64.zip`，SHA256 `1e4ef418500bc55cc34ee9ad59ea84e369ac7c8b17ca95927fc6f520ba25b7f5`。
- 包manifest SHA256：`3e9c21c4a890e1358490f16812c35a304bd89c5d598944284b2fe1fd38d18bc4`。
- role manifest SHA256：`ff06d8faaa536d1e785e6ab9a93eca064a608f7c07906c2597d4ee8cf0bc9e65`。
- 安装根：`E:/workspace/wondertrader-data/observer-programs/0.1.0a107+wtcurrent.1`；安装收据SHA256 `b6fbc9284718c3d35e700cc5e57704721ee56a804fe29d714a58e83a488a2d3c`。

沿永久六项目离线构建、ZIP校验/解压、普通安装和pip check；80项payload、26项SPA、134项App文件与manifest/wheel一致。固定解释器依赖仍为`E:/workspace/wondertrader/build/toolchain-anchors/cpython-3.12.13-win-amd64-001/python`，该目录继续保留。早期build-001在评审修正前正常中止，build-002因测试mock类型不匹配失败；最终build-003在修正、类型检查与回归后完成。

## 运行接线与独立启停

正式地址：`http://127.0.0.1:18143/strategies`。稳定入口：`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`。

本代不可变profile：`E:/workspace/wondertrader-data/observer-web-a107-wtcurrent-20261104-001/formal-001/web-profile.json`，SHA256 `57173946512785dbc3493eab87b50c67041fc677b15e96fcdc27caacdba9b9b7`。相比a106读取配置仅新增`GUANHENG_WT_CURRENT_FILE=E:/workspace/wondertrader-data/wt-current/CURRENT.json`；凭据、行情连接、报告、个人目录、观察根及补充实例目录全部保持，旧原件未改写。

最终Web PID60848、venv启动器PID52576，control `7804e837-e17f-4ced-b4b1-22d24f37ace5`。a106正常closed，a107首次启动后再正常停止/启动；停止收据均为shutdown_complete、两读池线程0、子进程及启动器exit0。采集owner16440、行情查询41220、观察监督42932/44840在两次Web停止期间保持PID和creation_time。WT在观衡切换前已发布faulted且原PID57756已退出，该事实在观衡启停前后保持，不能将其写成当前WT正在运行的连续性证明；运行中WT不受App启停影响的原范围沿a106对应记录复用。

发布时CURRENT仍指原control `43a02121-cf9c-4104-ac24-fc5baabeebc3`；实际发布为faulted/ready=false。策略页面正确显示运行失败及最后5项持仓，账户页显示已停止和原批次时间；原100万策略基准、现金与持仓值沿原发布保持，可用资金的未知状态原样显示。现场故障事实已交Root，原因及恢复资格归运行侧实际证据。

## 验证证据

| 要求 | 实际证据与范围 |
|---|---|
| 同App读取两代公开身份 | `MAIN-CHAIN.json`经原SDK原子发布及实际HTTP验证NAP/策略/状态五入口；缺失、无效、恢复均有结果；无WT进程操作 |
| 新增回归可复现 | `pure-regression.txt`从git archive纯候选展开App/SDK及自含fixture，15项通过 |
| 关联后端回归 | `regression-final.txt`126通过，1项既有“基础就绪/已就绪”文案断言失败；原a106基线亦复现。早期缺build目录的准备错误已更正并单独通过 |
| 页面刷新与缓存边界 | `frontend-regression-final.txt`27通过，真实15秒自动读取；最终Operations mock修正后6项通过，`typecheck.txt`退出0 |
| 双轴独立评审 | `REVIEW-SPEC-FINAL.md`及`REVIEW-STANDARDS-FINAL.md`开放P1/P2均0；两项缓存问题已修正并覆盖原触发条件 |
| 正式读取绑定 | `WEB-PREPARED.json`、`LIVE-before/after/after-restart.json`及`INSTALLED-IDENTITY.json`；runtime_scope与当前公开四身份一致 |
| 页面主路径 | `live-strategy-audit.json`、`live-account-audit.json`、`live-operations-audit.json`：5持仓、5个WT实例、同一新SPA entry `index-DjDNBQhX.js`，状态与原发布吻合 |
| 策略与日期盈亏 | 实际策略→3份正式报告→403日期→2026-06-09三持仓及浮盈/累计已实现盈亏、当日无成交；`live-report-date-audit.json`和`live-date-detail-desktop.png` |
| 手机 | `live-strategy-mobile-audit.json`与PNG：390px显示策略选择和5持仓，文档宽度390；原日期明细窄屏布局沿a106保持 |
| 独立启停 | `A106-WEB-STOP.json`、`A107-WEB-START/STOP/START-002.json`、`LIFECYCLE-RESULT.json` |

行情/搜索、观察指标、数据资产、全部成交分页与CSV在本次未修改，复用a106同一输入范围的实际验收；该次浏览器保存按钮未触发，实际导出API的44行CSV已保存E盘，覆盖边界继续保留。本次未新增交易、账户写入或金融状态迁移。项目文档检查在稀疏工作树仍报告既有/未检出链接和技能清单缺失，`project-check.txt`未被表述为全仓通过；本次新增正文链接单独核对。

## 维护、回退与剩余

使用本代安装的`runtime/app/venv/Scripts/python.exe -I -B payload/observer-web.py status|stop|start|restart --profile 本代不可变profile`；运行手册维护完整参数。每次停止使用原profile原件；稳定别名只在ready及实际页面验真后更新。发布动作只控制观衡Web。

保留a106安装及原profile。本代准备了`formal-001/rollback-a106-profile.json`，使用新控制根及发布时CURRENT四身份的固定读取配置。回退先正常停止a107，再用a106安装维护工具启动该回退profile，核账户/报告/个人目录后更新稳定指针。本次未实际回退；后续WT换代后，a106回退配置的四身份须先按当时CURRENT重新准备，a106不具备自动跟随能力。原金融、观察与个人数据格式均保持。

剩余：Root沿原账恢复并完成真实WT正常重启；保持当前a107 Web不重启，核账户和策略页面自动接收新代、原持仓/资金/记忆连续。代码、隔离验证、独立制品和Web部署已分别完成，该联合现场条件继续登记为pending-verification。
