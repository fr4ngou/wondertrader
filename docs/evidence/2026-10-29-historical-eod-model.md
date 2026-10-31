# 真实历史日线输入与原生回测报告

类型：验证记录。日期：2026-10-29。状态：HEM-R1至R3限定切片完成，两轴最终delta均complete；完整模块C/M1继续。要求见[HEM规格](../specs/historical-eod-model.md)。

最终输入004：115源码/70QA/663原件/14图、8项受控摘要，入口SHA `120afbd839fa4a77ed7f05ced3953ad50bd9d8a39937398b5f82797ed3bff3d9`。SOURCE SHA `3427d1eb91a3938aab8d3ed57185196ae33a023999c598a069ebcf3870b5220d`。最终REVIEW-SPEC-003 SHA `69ad11b2e04fcfc341a9346e37f01af12c76431fcef1e619513a4078ba679246`、REVIEW-STANDARDS-003 SHA `9b76e8e828e262c26dfa0cf67b9c43f389af3561807555ae1fe7956c38085fdd`，均关闭两原P2且无新增产品阻断。003清单代号替换遗漏部分002原件及4项受控哈希的事实保留；004恢复35份原002原件和全部8项受控摘要，并保持与原002身份相同。该清单修复保持产品源码/安装/SPA不变。

最终Appa19 wheel SHA `be7440829a714177d2f1acc5c73544be9a05de81014fd9ae79a35f30b15fd31c`，corea7 wheel SHA `facc8d60dee3d951aacaecea5b176cea49302ccedea48fce682f77194c06229d`；普通安装006仍35发行/4789 RECORD/11私wheel。生产SPA009 ZIP SHA `ac71c7208ebaba01194f966ffe4caac722e14c8291998d09ecf5155716569f20`，18成员与最终前端输入一致。402安装回归、120前端回归、006实际原生400条/3模型fill/末核一致及010两代归档恢复闭合。独审分别核全部400绩效点/399合格/1缺失、本金/收益/回撤/费用，不补缺值。

最新策略范围仅为根核实的旧QMT实际启用且有策略持仓清单。本记录收尾既有共享回测候选，保留其实际证据，策略移植名单资格由准确清单另行确定；全部策略/历史版本的后继扩展停止。

后继003：002独审实际复现实例可覆盖validated_copy方法的同根因P2；两消费边界现显式调用HistoricalEodModel.validated_copy(model)，新增纯核/NSB三项方法注入回归，注入行为调用次数为零。普通安装006 SHA `01d7e00e0c7fccf9eea5f3316969469f7751c7be7a4fe7b680c01094d8a46e70`、35发行4789 RECORD/11wheel及402安装回归通过；installed-main006重新执行真实原生400条/末核一致/关闭，ui010在新runtime006及原SHA SPA009上完成两代同007归档读取/503手动恢复/关闭。115源码/65QA/611原件/14图固定于REVIEW-INPUTS-003 SHA `ccf0e599bf59cb58a030b5e26fdf702187ca7a6e7f51ce4d4f07f88408cb6b0b`，两轴delta复核中；原001/002输入与gap报告保持。

## 根因与实现

来源127批次实际在2026-10-29取得过去日线，历史首次可知和修订未知。原严格核要求每行在其当日闭合时已可知，正确拒绝该输入。HEM显式保存批次实收、金额按CNY解释及日末模型假设，原`market_available_at=None`保持，复用唯一算法与WT原生回放；历史报告独立schema且qualified=false。严格核原数学与规范输出保持，旧a6与新核严格结果/历史逐字节对照通过。

两轴首审发现typed对象可绕过构造及V1/core自身身份缺口，两项P2已在责任层修复：公开消费时重建验证模型并隔离原引用；包导入时共同核声明、安装METADATA、自己的版本和实际精确依赖，显式处理Windows tzdata条件。纯计算调用保持无安装I/O。

现有回测页接新报告及原生资金/持仓/目标，展示实际批次接收的上海时间和模型限制。金额按分显示，原文保留。归档配置完成后才开放记录/绩效读取；刷新目录保留已核组件，避免卸载重挂导致单worker的三路重复读取。策略介绍页沿既有名称/简介/版本，Grafana、新闻和研究服务/页面继续排除。

## 输入、安装与实际结果

原件根：`build/historical-eod-model-001`。真实交付127 SHA为`63d7295f1b2f7c5e9da2d5543c7f9d4faf7276b7d43818fbf56b54b5b626a7c8`。9证券共同2025-03-05至2026-10-28共401日/3609行；价格CNY/份，成交量lot100显式换算为份，金额源单位unknown。实际实收`2026-10-29T01:23:25.163+08:00`。

- `source-002`：9次真实SDK/来源服务/Reader/DSB请求，每只401行，OHLC/量额与原始119逐字段一致；服务、监听与原native Job关闭。
- `INSTALLATION-005.json` SHA `9644a97e474868b2e41bf5f8d95c8781ed275e46f7c1f53e77faeb0b1864b791`：Appa19、corea7、signalsa5、V1a2、V2a4、riska3、AIa2；35发行/4789 RECORD成员及11私有wheel普通安装校验通过，标准库venv无启动钩子。
- `installed-main-005`：普通安装入口→受管Host→独立runner→固定WtBtPorter/CtaMocker，400条计算/最终converged；末个完整核结果与同输入纯核逐字段一致。子进程exit0、非强杀、pid/pipes回收。原生DLL SHA `4726fdb9c48d32ec46fe0793eabb23d120aec8a536dc8dc140b57b636b533b2e`。
- 六组安装回归399项通过，所有业务模块均实际来自runtime-venv-005：core/HEM283、signals22、V1 26、V2 14、risk23、AI31。输入篡改、typed突变、原对象后续修改、依赖自身版本/条件、严格因果及报告资格拒绝均覆盖。
- `ui-007/first-workspace.json`：普通App实际HTTP页面启动同一真实输入，原生运行约71秒，400条记录且归档available；运行`8cb9f7b776eb4b8ea507a8a4e4e15095`，报告SHA `51fe419ca4174483c336526fbfd1854fccb60beb41224b723ca03695ce0e617b`。原QA绩效读取拥塞失败已保留。
- `ui-009`：修正后的生产SPA009，两个新App代际读取上项同份归档，前后原件哈希相同/新增执行0。400记录分页、详情、实际绩效HTTP、503手动恢复、上海时间显示均通过；1440×1000和390×844无页面横溢，浏览器置America/Los_Angeles仍显示上海时间。两代App shutdown_complete、线程join、监听关闭；原native Job树/EOF/join完成。
- 前端类型检查、生产构建/分块与7文件120项回归通过。入口268.2KiB、五个业务懒分块；Vite配置扩展名警告沿既有工具链登记。Browser plugin不可用，沿现有Playwright/Edge验证。

## 失败与资格边界

原001源码试跑、安装启动钩子/旧解释器锚点、旧依赖硬编码、core测试导入模式、首审两P2及UI006/007/008尝试均保留原脚本/日志/关闭收据。UI006为QA写错产品标题；UI007/008的额外绩效读取触发有限队列超时。后继先修职责/读取顺序再验；全部失败的原native关闭九项为真、cleanup_errors为空且owner未保留。

旧冻结88源码/20QA/265原件、002方法注入gap及003材料范围不足保持原身份。当前B正式实时桥仍消费严格核，真实历史预热沿[CHD](../specs/current-history-decision.md)待实现；HEM继续只用于历史回测。最终006新原生执行与010当前App/SPA读取旧007归档分别证明对应段，最终SPA009重新点击启动006新回测未另验。准确持仓策略名单、实时目标/隔离委托撤单整链和完整M1未由本记录证明。未真实下撤单、操作旧QMT界面、切生产或新增WT核心行为；Git由主会话唯一集成。
