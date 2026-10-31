# 2026-10-22 观衡独立业务工作区

类型：验证记录。结果：partial。关联规格：[GBW-R1–R8](../specs/guanheng-business-workspace.md)。完整观衡迁入仍为in-progress。

## 输入与归属

用户确认旧QMT业务工程整体废弃，观衡全部迁入WonderTrader。停止旧工程开发、测试、门禁、制品追加与合入；未合入候选、组合状态、数据及现有运行保留。原源码仅作只读迁移参考。

新业务包为`apps/guanheng/guanheng_app`，版本`0.1.0a1`；独立SDK在`integrations`，版本`0.12.0`。固定分钟图来源为原候选`4e5595c156731ce66f3e0a199096a863354eeda8`。完整范围由[功能清单](../migration/business-feature-inventory.md)逐项登记；页面与路由数量不代表迁入完成。

本仓库`.venv`使用CPython3.12.14，锁文件`apps/guanheng/uv.lock` SHA256为`4fdbd41f5331595be02f888ffd0149788c68758663e0934c9af82c3f2f760c81`。初始环境身份保存在`build/guanheng-workspace/bootstrap-001/environment.json`。开发环境中的应用为editable，下面安装验证另建环境并使用非editable wheel。

首轮两个wheel摘要：`guanheng_app-0.1.0a1-py3-none-any.whl`为`46fc620e2de81785e74d3c2b4bda1cf36fba006070ad9fcdf493184d6d551c67`；`guanheng_market_client-0.12.0-py3-none-any.whl`为`94a384bdd2eb25e56105694cb5507e6b6aae2e7244cb115a4a33f94487754109`。同版本历史候选具有不同内容，当前安装资格只对应这两个实际摘要。

## 已实际执行

| 入口 | 实际结果与证明范围 |
|---|---|
| 本仓库后端公开接口回归 | 32项通过，覆盖正常、空、非法来源、错误、超时、恢复、共享预算、容量、线程退出及静态入口；使用合成factory，不授真实来源资格 |
| `uv build apps/guanheng --wheel`及`uv build integrations --wheel` | 两个独立wheel构建成功，保存在`build/guanheng-workspace/package-001/wheels` |
| `uv export --locked --no-dev --no-emit-project --no-emit-package guanheng-market-client` | 导出生产依赖及实际锁定摘要；14项第三方运行依赖按hash安装，未装开发依赖 |
| 新建`package-001/installed`并安装两个wheel | 非editable安装成功；应用和SDK均来自新环境site-packages |
| `tests/integration/app_console/installed_smoke.py --python .../installed/Scripts/python.exe --work .../smoke` | 退出0；`-I`隔离解释器、独立空工作目录，真实HTTP六路由及CLI帮助通过；未知模块/日线/未装静态制品清楚返回501；分钟连接未配置清楚返回不可用 |
| 同一安装进程受管停止 | 退出0；应用读取线程0，监听端口已关闭；没有加载`qmt_platform`。测试stdin只作进程管理接缝，生产HTTP未增加写或停止接口 |
| `ruff check tests/integration/app_console/installed_smoke.py` | 通过 |

安装进程原始证据为`build/guanheng-workspace/package-001/smoke/receipt.json`、`child-receipt.json`及`stderr.log`，包含真实模块来源、sys.path、测试摘要、HTTP响应和退出结果。此步证明独立安装与未配置时的正确行为；真实DLL/DSB、前端和独立审查分别补充。

## 真实原生分钟整链

新增本仓库测试`tests/integration/app_console/test_native_chain.py`，最终摘要`3df40bb87414eaad54237dbefaf65b95e2e2db2f6ef0f920761f9cf6a6f0e0d6`。显式输入为已验`history-public-abi/repair-001/build-002/cmake/bin`内的原生Bridge/Storage，以及`live-source-probe/imports/262717530f31448c87fa4278201854b3/storage`冻结QMT DSB/sidecar和对应原CSV；不访问终端，不重新导入或下载。

最终实际运行1项整链测试通过，16.99秒，包含10个检查：两证券`300308.SZ`239根及`688076.SH`189根1m、两者各48根原生5m，逐CSV核对OHLCV、UTC左端时间、来源及Unknown覆盖；空窗口仍保留真实来源、before含端点和limit、基准图、上游停止后的公开失败、同一后端在上游恢复后的重新读取、完整线程/端口回收。共9次图表HTTP及1次health，9次实际原生`history.query`；记录数和检查数分别列示。

本次直接使用本仓库安装SDK，经真实loopback HTTP访问原生服务。Bridge与Storage实际加载路径均为上述批准构建；原生创建/服务/销毁由同一owner线程承担。后端读取线程退出后为0，双方监听已关闭，防意外来源访问的隔离哨兵收到0请求。原DSB、DLL、SDK与后端输入前后摘要完全一致。

原始结果：`build/guanheng-workspace/native-chain-001/run-8e100228cef142ad954eaa05bf284ccf/result.json`，SHA256 `3e21cfb6b7e970adb18eb1ceea3ccf7fe8cf8bd3063a47e787a8d0ceef849e87`；`inputs-before.json`和`inputs-after.json`均为`6900b9f4683773152bd1dc57bb31b95cd2595c0d801e4a2745d0e5c0df9dbff3`。具体环境参数与非私密测试基础资料在同目录登记。

该结果授本独立后端的真实冻结样本开发链资格；CSV/DSB/图表一致性没有证明券商原始股数精度、全天/全市场覆盖或新下载数据质量。前端用户入口和独立审查继续分别验收。

## 后端独立审查

`build/guanheng-workspace/reviews/backend-full-001.md`完成首次full审查。审查者只读取最终规格、适用长期规范、源码与当前原始输入/收据；没有读取任务过程或历史评语。32项公开回归独立重跑通过，另验排队HTTP取消、顺序lifespan重入、worker异常恢复与重复关闭。两个wheel逐字节匹配源码，真实链39项输入及后端身份索引14项摘要与当前内容一致。

该范围内未发现可复现P0–P3实现缺陷；R1/R3/R6及Python构建对应边界通过。R2全业务、R5新券商接入、R4浏览器及R8整体完成仍保留未实现或待验，不能把后端审查扩大为完整观衡迁入。当前源码身份为`build/guanheng-workspace/backend-inputs-001.json`。

## 浏览器迁入与真实入口

`apps/guanheng/console`已迁入固定来源154份源码/非敏密展示配置，其中141份原样、13份适配，逐项身份见`source-manifest.json`。新能力入口使用本仓库`/v1/ui/capabilities`，直接连接独立后端；旧全量页面源码保留，当前只开放1m/5m查询，其余导航清楚显示尚未接通。npm前置已移除旧存储脚本及路径，Vite base=`/`、BFF默认本机18120，生成物和缓存归新目录，构建静态根为`console/dist`。

实际验证：初始41文件/292项原页面与组件测试通过；新增before参数后的API及MarketPage相关41项通过；最终类型检查、构建及分块预算通过。最终3个浏览器场景通过，其中2个使用明确模拟响应检验能力/页面契约，1个直接使用真实批准DLL/冻结DSB→SDK→新后端→构建静态入口，全链无浏览器route mock。

真实浏览器观察到239/189根1m及两者各48根5m；空时间窗口、来源停止返回不可用、来源恢复后保持页面与查询参数直接点击重读均通过。移动表单首次人工检查发现横向溢出，现已局部修复并在390宽度断言`scrollWidth<=innerWidth`及按钮位于视口；最终1440桌面与390移动截图均已人工检查。该场景页面异常、控制台警告/错误均为0，全部业务HTTP为GET，来源哨兵0访问，结束原生线程、后端与Vite监听均已回收，输入摘要保持。

最终输入及命令结果：`apps/guanheng/console/build/evidence/workspace-001.json`；真实宿主结果：`console/build/native-browser/run-177e5e3a65594c8689ef949d7b379347/result.json`；浏览器QA与截图：`console/build/browser-results-a6c48181-4375-42f2-918e-1eb974451e39/native-真实原生DLL与DSB经独立静态应用呈现正常、空、源停止及恢复/`。后两路径以`apps/guanheng`为相对根。旧失败输出保持原样，最终资格只绑定当前输入。

依赖审计保留原件：全量锁的开发依赖链3 high、2 moderate，`--omit=dev`结果0项；本轮未升级锁，生产资格待依赖/发行评估。前端首次独立审查进行中，当前可用入口不代表其余页面已接通。

## 页面审查后继

前端首次独立full报告`build/guanheng-workspace/reviews/frontend-full-001.md`发现两项：P2新入口缺完整`as_of`导致历史年份不可识别；P3能力请求网络异常直接显示底层英文。其他首切片输入与运行证据吻合，原报告及`workspace-001`保持原样。

修正沿现有职责完成：图表按真实`bundle.as_of`显示完整上海时间并标明分钟开始，空、失败和读取中隐藏旧时间；能力与分钟请求共用原`api.ts`调度之上的中文JSON读取边界，以内部超时类型识别网络/截止，保留排队、传输、读体预算及调用者取消。没有修改后端或WT核心。

最终定向42项API/MarketPage/取消回归、类型检查、构建及7个浏览器场景通过，39.3秒；没有重复不受影响292项。实际Edge连接拒绝/6.5秒超时/非法JSON与重试恢复均显示中文；真实数据的1m `2026-10-20T06:59Z`显示上海14:59，5m `06:55Z`显示14:55，空/停源没有旧time节点。最终390截图再次人工核对。

当前冻结身份：`apps/guanheng/console/build/evidence/workspace-002.json`，SHA256 `fffd91f98019ad8a90b5f3da44768d466217b80976deb4dcc69cadfdda41ddf9`，绑定152项源码/dist；改前源码和dist单独归档。最新原生结果为`console/build/native-browser/run-9386e4d52e87408781a80907c0552019/result.json`，浏览器QA为`console/build/browser-results-beb6666d-a943-4102-a1b4-2a91b61ecb3e/native-真实原生DLL与DSB经独立静态应用呈现正常、空、源停止及恢复/`（后两路径相对`apps/guanheng`）。测试宿主/Vite已退出，原始输入保持。独立delta继续核对两项关闭和共享读取影响范围。

### 最终delta与当前资格

独立`frontend-delta-002.md`关闭原F1/F2，另发现D1 P3：调度完成回调先于timer运行时，同步发现过期队列的分支仍使用普通Error，导致超时被误报连接失败。修正将该出口与排队timer、传输截止统一为`ReadDeadlineError`，没有改变原截止或来源调用规则。公开API精确原样回归为1通过/1失败；修正后定向27项通过，逾期第二请求没有访问fetch且timer全部回收；类型与构建通过。

最终源码/dist绑定`apps/guanheng/console/build/evidence/workspace-003.json`，SHA256 `b049bac77f1071ddd608ef917c3142567d63dd6555ac5e4aff7914a980385efa`，152项全部由独立reviewer重新核实。`build/guanheng-workspace/reviews/frontend-delta-003.md`结论passed：D1 closed，新增P0–P3为0；独立短探针重放正确中文超时。原F1/F2及002七个浏览器/真实DLL/移动布局证据未受影响，独立确认复用；没有机械重跑全部测试。各轮原件、改前源码及dist保持原身份。

至此独立业务工作区、原生分钟后端与浏览器首切片完成本地开发验收，后端full、前端full及适用delta闭合。完整观衡迁入仍为in-progress，R2完整功能清单、R5最小券商接入、正式业务制品发布/监督、生产入口及真实交易各自保留未完成；不能据本切片通过提前关闭整体目标。

## 限制

本记录不授完整观衡迁入、真实终端新下载、生产部署、账户迁移或交易资格。策略、账户、审批、新闻、研究和运营等仍须在本仓库按完整清单迁入；最终最小券商接入代码也须本仓库拥有。WT重合行情/运行/订单能力直接复用；旧业务数据库与总线不会随整包复制成为前置。

当前只使用QMT作为真实来源；通达信现场数据及交叉对照暂停，共享内存与WT绑定、通达信交易暂缓。既有WT框架冻结输入及审批边界保持。
