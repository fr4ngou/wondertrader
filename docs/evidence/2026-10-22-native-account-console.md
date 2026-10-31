# 2026-10-22 原生账户只读展示

类型：验证记录。结果：partial（合成本地开发链通过，真实券商与生产未验）。关联[NAC-R1–R8](../specs/native-account-console.md)、[GBW](../specs/guanheng-business-workspace.md)。完整迁入仍按[业务清单](../migration/business-feature-inventory.md)推进。

## 实现与根因

原TraderAdapter正常初始化已经拥有持仓、委托、成交、资金四查询，v2事实视图提供来源、字段资格和逐批执行时间。原getOrders管理活动单范围与全账户查询不同；重复初始化查询还会保留未再出现的持仓并累加统计。自有GuanhengAccountScan每轮使用一个新进程、一套原Adapter/普通只读插件，经正常链取v2值并退出。父端只拥有有界IPC和显示投影；账户、订单与行情均未新增数据库。

独立业务HTTP最多一轮在途、16等待者。完整空、零、未知、非法、部分交付与强制回收分别表达。账户页显示资金、持仓/可卖、全账户委托及成交；刷新隐藏旧观察，四批分别标来源与时间。策略归属、审批、成交push和委托/撤单由各迁入项负责。

两项独审发现已修正：真实HTTP断连不会自动取消GET handler，原等待席位保留到采集结束；现由ASGI断连事件取消本连接等待并回收任务，共享采集保持原scan_id。公共浏览器读取边界曾丢失429繁忙原因，现保留HTTP状态码，由账户边界映射固定中文处理，未经审核的服务端正文保持隔离。

## 输入与制品

全部开发、测试及产物位于本仓库；旧QMT只读参考，不导入旧业务包，不执行旧门禁。原生使用固定WT `08b230dd05facf6d650d949bfe51054115a2ecb1`对象与原接口，无新增框架修改。源端使用[本仓库连接包](2026-10-22-qmt-owned-terminal-source.md)，供应商SDK为明确合成对象，未装载真实运行终端。

| 输入 | 身份或受控路径 |
|---|---|
| 汇总资格 | `build/guanheng-workspace/nac-qualified-001/receipt.json`；SHA256 `d6598ac6f7765631fea070be3129602719b9371242f7fe395f911873e58cc904`，重新核70原生与164应用输入、制品、浏览器及17份证据原件 |
| 固定来源 | `build/guanheng-workspace/nac-build-001/FINAL.json`；323上游、70自有、2518实际编译头依赖、172编译输出 |
| fresh构建 | 同工作目录`attempt-004/receipt.json`；166步，全部阶段passed |
| 开发ZIP | `dev-account-scan-20261022T052047Z-8f7b5456.zip`；SHA256 `efe886b30097a26010426d1239bc1fadc26cb82a1b54dd923d77068531fdb0eb` |
| 产品EXE | SHA256 `e5759b2e5eae148a5898c12d0596a58f73b2ffea8200a03ebadbf89d059500ac` |
| 普通只读DLL | SHA256 `da13655806782000c1a2477fb1af557e0c6cb8b328cd63c20c6c86c74ff2f7e1`；无测试Probe门控导出 |
| 业务wheel | `build/guanheng-workspace/nac-app-package-001/wheels/guanheng_app-0.1.0a1-py3-none-any.whl`；SHA256 `702db2abe3c4b8ff3632bf803d43a887d8a84e5b2ea85362ccf6fa1100fa2e7d` |
| 应用与页面 | 同工作目录`build-receipt.json`绑定164项源码、锁与dist；固定flit构建，模块字节匹配 |
| 独立安装 | 同目录`installed`，Python3.12.14；14锁定外部依赖及app/SDK/QTS共17包，pip check通过，非editable |
| 安装浏览器 | 同目录`browser-receipt.json`、`browser-artifacts/`；原始harness为`build/guanheng-workspace/nac-browser/bee514e978c045eea0d5e7cb632e8bed/result.json` |

独立报告为`build/guanheng-workspace/reviews/nac-runtime-{full,delta}-001.md`、`nac-boundary-{full,delta}-001.md`。原失败与修正后结果保留；两路适用full/delta均已闭合，开放缺陷0。边界审查逐项核当前164输入、三wheel内34模块及17包1112项RECORD，安装与源码字节一致。汇总收据重新核当前输入后关联原件，资格限本次合成本地切片。

## 实际验证

| 命令或入口 | 观察与证明范围 |
|---|---|
| `scripts/native.py all --profile account-scan --work build/guanheng-workspace/nac-build-001/attempt-004 --offline --jobs 4` | 23原生场景、12流水线测试、ZIP及23搬迁场景通过；前轮编译依赖、制品来源和测试输出进入编译闭包问题已修正后fresh重跑 |
| 独立空CWD `C:/Python314/python.exe -S -B scripts/native.py verify --profile account-scan` | 不依赖MSVC配置或源码依赖目录，23场景通过；`verify-004/receipt.json` |
| 原冻结ABI检查最终普通DLL | 19项通过，`nac-build-001/abi-004.json` |
| 独立原生审查实跑 | 最终004的23宿主场景及11业务整链；空资金partial、零资金present、下一轮移除、代际冲突、非法字段、失败停止后续查询、恢复、取消与在途关闭；禁止调用0 |
| 实际一秒父截止与恢复 | 1000ms回收、forced且joined=false，已受理POST仅1次；释放来源后显式新轮4POST/complete；账户线程0，来源端口回收 |
| 实际Uvicorn/socket断连 | 16连接断开后300ms席位归0，新GET认领相同scan_id，子进程累计1；handler任务、线程、子进程和服务器回收 |
| 后端及HTTP增量 | 33项后台/畸形IPC/取消/容量回归及3项HTTP参数/启动失败清理增量通过；原32项分钟接口回归通过 |
| 前端、类型与构建 | 5文件50项通过，含429与恢复、取消/预算、缺失、分页、键盘；tsc、Vite、分块预算通过。独审另跑4文件40项通过 |
| `account.spec.ts`全新安装实际链 | 未mock浏览器路由：静态SPA→安装app→产品EXE→原Adapter/普通DLL→安装QTS签名HTTP→合成SDK。正常/空/partial/不可用/非法/恢复/繁忙共8响应（7个200、1个429），27次SDK读取，禁止副作用0 |
| 真实容量到页面 | 16后台HTTP等待者同一scan_id，第17个浏览器请求429，显示繁忙、等待后刷新及隐藏旧值，释放后同入口恢复 |
| 人工页面检查 | 7截图；根任务查看最终正常、busy及390移动，独审查看全部。资金两列、表格独立滚动，整页无横向溢出；页面异常0；唯一控制台网络错误对应已验证429，其余警告/错误0 |

## 资格、风险与后继

本证据证明合成本地开发与隔离搬迁。真实QMT四查询、账户字段/耗时、终端装载与生产入口仍待验。实际Python3.6.8资格归QTS前序证据，本次业务应用使用3.12，分别记录。

开发包记录54个CRT/UCRT运行库实际来源与SHA；精确分发授权材料仍为gap，当前不授外发和生产发行资格。旧profile与旧包保持历史身份，新profile不要求旧QMT fixture；其他框架差异继续冻结。

账户读取是合计只读观察；策略分配、实时push、持仓恢复、签名命令/幂等、五策略、研究、新闻和运营等继续迁入。本次没有下单、撤单、模式修改、数据删除、终端重启或生产部署。
