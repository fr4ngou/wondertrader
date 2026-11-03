# 观衡a107与真实WT换代联合验收

日期：2026-11-04，北京时间。类型：现场验证证据。状态：本次独立观衡交付及免Web重启跟随验收完成；首次自然策略计算和账户Host旧故障根因分别沿Root主线继续。

## 条件与职责

用户确认的策略、回测及日期持仓布局保持；观衡版本`0.1.0a107+wtcurrent.1`、制品和部署沿[a107发布记录](../releases/2026-11-04-observer-a107-wt-current-live.md)。原代码候选`f0492fe0d153e04a46b58a1f7f58ec619596a9fe`、SOURCE-CAS及构建输入均保持。本次只读验收并补文档，独立观衡源码和制品已交Root，主树源码集成仍由Root执行，未将其表述为已合入。

此前WT发布faulted并退出，观衡保留故障及最后成功持仓。Root处理运行侧恢复并通过日常`guanheng-wt-service`完成真实stop→start；本模块保持Web运行，核原页面、原读链及本代事实。旧故障原件与早期受阻审计继续留存。

## 真实身份与连续性

- 公开CURRENT仍为`E:/workspace/wondertrader-data/wt-current/CURRENT.json`；现control `b5133e1b-2760-48fb-a81f-8e589fdcfd5d`、instance `a309716d-1288-4328-ac57-abd6ef0bb2e9`、配置SHA256 `21e0e46146dd650946b2ce01f495d67dad89c591c0bb6fe6ec76931d655cdc9c`，WRI PID75068，全部组件ready。
- Web始终PID60848、启动器PID52576、control `7804e837-e17f-4ced-b4b1-22d24f37ace5`，creation_time `134382005291916232`、profile SHA256 `57173946512785dbc3493eab87b50c67041fc677b15e96fcdc27caacdba9b9b7`均与01:28:49的a107启动收据一致。本次只执行Web状态查询，未执行其stop/start/restart或重新部署。
- 实际HTTP策略详情的runtime_scope从`1ca11a70005dc6b3b51aad0d00be1c8f95ba628c18a688bbd61fda292bbf59e2`变为`9e18c7dfc67898a89602f44d86e61f144784c26c16d5f2b8eee8cd57d6e38975`，与新CURRENT完整四身份计算一致。WRI的execution业务引用与Root最终Native引用完全一致。
- 实际策略状态为1.1.2 `waiting_market_input`，页面显示“运行中 · 等待新行情”；首个自然策略计算尚待，未将组件就绪写成已完成计算或已成交。
- 100万元基准、现金及可用633075.2元保持；5个非零持仓数量分别为510050=33500、510300=100、510500=12900、512100=32700、515080=65200。页面金融值直接匹配Root原发布，金融计算与账本未改变。
- Root真实服务重启证明为`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/continuous-runtime/SERVICE-RESTART-PROOF.json`，schema `wt.actual-service-restart-proof.v1`、passed=true；同instance、现金/持仓/本金保持，financial_setters=0、source_restart_performed=false。BASELINE SHA256 `8701e1ae8e632d8e1229079b60a7137f0bc0a0663b47ceca694909da70c6eac3`。Native持续运行和策略记忆连续的运行侧资格沿此原证明，本模块核其真实业务引用和金融消费结果。

## 原网页与系统实页

原观察标签页8、provider `browser-use:da820728-6133-40fa-ad22-2003ef1b7959`始终为`/strategies`。重新连接读取工具时，原页面已显示新代02:10:51的执行开始时间、100万基准、五项资金和5持仓；本模块没有对该页执行goto、reload或手动刷新。系统页另开标签页9，五个WT实例全部已就绪，行情查询可响应，原采集owner16440、历史41220、市场观察42932/44840的creation_time继续保持。

浏览器读取连接首次失效，通过重置JavaScript检查会话重新绑定原标签页恢复；该动作保留浏览器页面。原CDP事件游标在检查会话重置后归零，因此不声称具有跨整个重启区间的连续事件历史。恢复后的原页另取得10次自动策略读取HTTP200、零页面导航的事件证据。原provider、无主动页面导航/重载的操作记录、原页新代内容、变化的四身份scope与不变Web进程共同构成本次自动跟随证明。

QA根为`E:/workspace/wondertrader-qa/observer-current-20261104-001`：

| 证据 | 实际覆盖 |
|---|---|
| `JOINT-ACCEPTANCE.json`，SHA256 `c8b21fbec3f47d6f333d19af07d538d923de6bf76dd815e61aa709e99d8086ac` | 严格身份、原进程、Root证明、金融值、原页面、实际轮询的统一断言，passed=true |
| `joint-acceptance.py` | 使用已安装a107原SDK、实际HTTP和原页面审计；只读，无服务控制或金融命令 |
| `JOINT-WEB-STATUS.json`、`LIVE-joint.json` | 原Web与当前WRI的真实状态、进程身份及4个独立数据/观察进程连续性 |
| `JOINT-ORIGINAL-PAGE.json`、`JOINT-SYSTEM-PAGE.json` | 原策略页5持仓/五项资金、新执行时间和系统五实例就绪 |
| `JOINT-CURRENT-POLLING.json`、`JOINT-ORIGINAL-PAGE-EVENTS.json` | 恢复检查会话后的自动轮询；旧事件游标重置的限制明确保留 |
| `joint-original-strategy-desktop.png` | 实际原页健康状态与完整5持仓，保持原布局 |

此前已经通过的桌面/手机、策略→三报告→日期持仓/当日交易、101笔全部成交分页、搜索/行情/观察/CSV、独立Web启停、代码评审及固定制品身份继续沿[a106](../releases/2026-11-04-observer-a106-strategy-pages-live.md)和[a107](../releases/2026-11-04-observer-a107-wt-current-live.md)对应证据复用。此次运行输入变化只重验实际受影响的当前实例、账户/策略及系统状态；布局与这些业务实现保持。

## 操作入口与回退

日常打开`http://127.0.0.1:18143/strategies`查看策略、资金和当前持仓；回测入口为`http://127.0.0.1:18143/backtests`，系统状态为`http://127.0.0.1:18143/operations`。WT日常启停使用[原服务入口](../runbooks/wt-independent-runtime.md#日常启动停止和状态查看)，观衡保持运行并沿CURRENT自动接收新代。用户无需修改UUID、配置摘要或重启观衡。

Web维护继续使用安装中的`observer-web.py status|stop|start|restart`及原不可变profile：`E:/workspace/wondertrader-data/observer-web-a107-wtcurrent-20261104-001/formal-001/web-profile.json`。解释器与SPA从`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`取得，保持版本和profile配对；具体命令沿[Web手册](../runbooks/observer-runtime.md)。

旧a106采用固定四身份，本次按最终b513新代重新准备了未运行的回退profile：`E:/workspace/wondertrader-data/observer-web-a107-wtcurrent-20261104-001/formal-001/rollback-after-service-001/web-profile.json`，SHA256 `44d0590d78b17ac76efe4c51af37054e34a146cc8ba171f7fd4f2a0beb168c68`。`JOINT-ROLLBACK-PREPARED.json`和`JOINT-ROLLBACK-PREFLIGHT.json`确认原件未改、旧维护工具可读取该配置并返回stopped；未实际切换或启动回退版本。未来WT再次换代后，a106回退前仍须按当时CURRENT准备新的固定四身份配置，保留每代旧原件。

## 仍有的边界

账户Host旧异常的具体根因仍未知，Root新增首因诊断并完成当前恢复；本记录保留其故障事实。首次自然行情驱动计算及新的交易执行继续属于Root主线；观衡交付完成不扩大这些资格。原a106浏览器保存按钮未触发，实际CSV API文件已验，覆盖限制继续保留；本次未改变导出实现。全仓静态文档检查仍有已有/稀疏未检出目标，新增正文与链接单独核对，不写成全仓通过。
