# 独立观察更新与503根因修复

状态：限定开发预览已部署并实际显示图表/数据，后台更新与Web由两个Windows用户级任务独立运行。完整模块C、OBI9、全部来源、未来自然09:00与生产发布分别待验。

## 根因与实现

用户截图的早期预览缺少观察数据根接线，已在前轮修正并验证48指标。后继持续更新验收又复现两个独立根因：DELETE日志的大目录事务阻塞HTTP读，发布时的心跳写与人工数据事务争用导致调度退出。原失败保留在`build/observation-live-001/main-001`和`main-003`。

唯一观察Repository采用WAL/FULL并准入SQLite>=3.51.3；实际安装为3.53.1。调度有效lease在存续期保留无事务目录连接，避免最后连接反复关闭清理。业务current、快照、回执与完成窗口保持同一SQLite事务。心跳属于独立运行观察，由同根有效调度lease唯一写者原子替换有限`scheduler-status.json`，读者使用共享删除句柄取得完整旧值或新值。当前文件损坏固定503，旧catalog只在当前文件缺少时供历史迁入。

独立`guanheng-observation`入口复用原ObservationCollectionProcess/ManagedLocalProcess、Job及停止合同，Web只读同根。启动等待交给具名ThreadOwner，主线程持续接收文件停止/信号，原首D关闭并join启动与控制监视线程。最终收据逐阶段和返回后复核原D，发布晚到退出非0；已可见收据只保留资源事实，完整有界成功同时需要退出0。驻留Web启动器将损坏停止控制保留为失败。

## 实际主链

- a39普通安装`main-004`运行21路真实来源，14成功、4披露目录核验、3失败；人工截止2026-10-29，发布48指标。没有时钟或来源替换。2路货币网请求超时、A八指数日线Unavailable保持真实失败，披露目录不授已解析数据资格。
- IAB实际页面自动取新目录/图表；图中最后日期2026-10-29。浏览器局部updates503期间保留已成功图，移除拦截后显式重读恢复。实际CSV下载16行，与所选窗口逐值核对，原件`main-004/browser-export.csv`。
- main004两代Web正常关闭时同独立调度心跳继续；两代调度正常退出，2026-10-29窗口attempt保持1。实际崩溃exit7的`lifecycle-001`原Job/tree/EOF/join/资源关闭成立，恢复零新请求及零重复窗口。
- 最终a40普通安装`installed-001`完成启动未ready前停止、两代Web/调度、48项实际HTTP及空范围、同根原snapshot/runs/attempt连续性。全部原生包装入口与线程关闭成功，新增来源及交易请求0。它复用main004真实来源数据，来源资格保持原范围。
- `resident-check-001`实际安装CLI验证有效停止exit0、错误control_id退出2且failure=stop_control，监视线程均join，原Job及管道关闭成立。该轮没有注册后台任务。

## 固定输入与验证

根目录：`build/observation-live-001`。最终a40安装为`install-005/installation.json`，SHA256 `91048e74da53d6ee102c42a9d2bd8b02f43e7cdbad8a3ac6fa3e0424ece65d2b`；29发行普通copy安装、pip check通过。源输入在`PREPARED-005.json`，生产18文件SPA为`SPA-002.json`。该阶段用户预览由旧18120实例提供；最终入口与后台后验见末节。

最终观察/WT只读组合255项通过（`pytest-full005.xml`）；新增文件/信号启动停止与晚收据5项（`pytest-stop-green002.xml`）和固定503保图数据3项（`pytest-concurrency006.xml`）通过。全量前端先前有Overview两项失败及总截止，原失败保留；观察范围9文件58项、类型、构建和分块通过。构建与测试分别授资格。

独立full报告`REVIEW-SPEC-001.md`、`REVIEW-STANDARDS-001.md`基于441份冻结输入，提出4项P2：启动停止、最终收据截止、驻留控制错误、深层JSON归约。上述修复及根条件回归已完成，后继固定delta连同安装/wheel/RECORD原件补审；原报告不改写。最终审查及驻留后验结果另行登记。

## 剩余范围

未来自然09:00必须等待实际窗口；后台维护需核真实OS任务、PID/ready、持续心跳与HTTP，ACTIVE文件存在只表示启动尝试。当前候选配置仅给本机开发预览，生产发布另按授权。A的精确八标的只读失败记录见`SOURCE-BLOCKERS-001.json`，原WT/QMT、行情采集及交易权限均保持。统一安装升级回退、完整C/M1/M3及OBI9仍待完成。

## 最终部署配置后继

驻留审查新增的线程部分启动P2已通过统一finally及真实start前/后失败回收关闭，原件`resident-threads-002`与双轴003报告。准备控制目录时实查E盘继承AU写权限，改用当前用户LocalAppData继承保护ACL，未修改权限。实际`resident-updater-001`随即暴露观察配置继承SMA的E盘限制；启动在部署准入被拒绝、原Job全部回收，任务尚未注册。

根因在配置类型的职责耦合。最终a41以独立ObservationCollectionProcessConfig拥有同一既有wire字段，复用原公共路径/摘要/预算原语，接受本地绝对控制根；SMA公共配置及其E盘政策保持原实现。原ManagedLocalProcess和数据根保持。`resident-updater-002`实际在C盘子控制根完成ready、持续心跳和正常关闭；`resident-check-003`的正常/坏控制实际CLI继续通过。`installed-002`以a41原安装完成两代Web/调度、启动停止、48指标/空范围及完成窗口去重。

最终普通29发行安装`install-006/installation.json` SHA256 `f4eff860ea7e8a50520132e908bbb6fcf4ee3c9d51cee1bf4b5532eabb662bc3`，259项组合回归通过（`pytest-full006.xml`）。控制ACL原件`RESIDENT-ACL-005.json`，当前部署准备件`RESIDENT-INPUTS-005.json`。a40历史资格及旧失败均保留；a41最终delta及当前部署006的实际后验见下节。

## 实际后台预览后验

最终双轴004对277项固定输入、29wheel/RECORD、4786安装文件及98份App源码独立重核通过，六项P2在限定制品/CLI范围关闭。后继OS部署先遇到Windows PowerShell5.1脚本编码解析失败，改用已知PowerShell7；无权限或凭据变更。旧注册失败的完整文本在会话工具记录，后继同名控制日志被成功执行覆盖，不声称该日志仍为旧失败原件。

OS实际任务随后报告目录错误267和Python退出2。只读任务探针证明Codex AppContainer的逻辑LocalAppData路径在外部任务中不存在；同句柄GetFinalPathName与Path.resolve核出真实LocalCache路径。最终准备入口先resolve本地路径再写所有配置，任务和子控制同用该物理路径，收敛目录原因，未靠权限修改或重试延长预算。当前唯一部署输入`RESIDENT-INPUTS-006.json`；005保留历史准备资格。Web初始WT状态读取同时复用已有SDK `read_status_snapshot`共享删除边界，原始Path.read_bytes在一次QA中出现的共享冲突保留于`resident-check-004`，修后`resident-check-005`实际pythonw正常/坏停止通过。

`Guanheng-Observation-Preview`与`Guanheng-Web-Preview`已实际注册、启动；当前用户Interactive/Limited，AtLogOn及每日08:55触发，重复运行IgnoreNew，服务内部仍按北京时间09:00。两任务当前Running；`postflight-001`在20秒内五次独立读取获得新心跳、同监督/Web PID、同快照、48项目录和HTTP200；记录包括真实ready和OS任务原样配置。长期服务明确交Windows任务持有并保留运行，有限QA命令均已结束。

用户IAB入口已打开`http://127.0.0.1:18126/observation`，实际显示自动更新运行、2026-10-29日期、16行和7.1429%债券配置倾向，以及2018-02-23至2026-10-29的2095条历史图。已恢复浏览器默认viewport、清理旧临时QA页。18120旧进程继续保留；本轮用户入口为18126。来源仍是14成功/4目录核验/3失败，未来自然09及全部来源保持原缺口。本轮没有生产发布、Git提交或WT/QMT生命周期操作。

OS后验双轴005完成50件固定补审，无新增P级问题，六项P2保持关闭；报告分别为`REVIEW-SPEC-005.md`与`REVIEW-STANDARDS-005.md`。其后单次只读补件`OS-IDENTITY-006.json`实际回读Interactive/Limited及006物理目录ACL，自核符合，未扩称为50件独审范围。`project_check-004`通过文档导航及skill完整性检查；此工具不授运行或发布资格。最终交付身份及全部限定资格登记在`build/observation-live-001/DELIVERY-001.json`，长期服务按两任务保留，完整模块与统一升级回退继续。
