# 独立观衡安装与更新

观衡独立交付和更新，已完成的观衡版本可先行交给使用者，WT交易开发与恢复验收单独继续。联合候选用于兼容联调；观衡安装、启动和升级不启动WT/Host，也不要求WT同时升级。当前独立交付沿[发布索引](../releases/README.md)，按观衡App和市场更新角色分别核对已验安装、真实数据绑定及当前维护入口。

类型：操作手册。适用范围：[独立观衡development制品](../specs/observer-runtime-package.md)，Windows x64。安装与维护流程的SDK替身资格、真实来源接入及生产发布分别登记；当前实际版本、来源绑定和用户入口以[发布记录](../releases/README.md)的最新后继为准。

正式发布沿用已登记地址和端口；本机固定18143，用户明确同意后才能调整，见[操作员入口](guanheng-operator.md#启动与独立运行)。下方通用命令中的18120仅为示例，不能据此替换本机正式profile的18143。

接收交付记录中的ZIP、ZIP SHA256和OBSERVER-RUNTIME.json SHA256。先用Get-FileHash核ZIP，再用系统Expand-Archive解压至新目录。安装需要显式CPython 3.12 x64（含pip）和uv；离线wheel已随包提供。

```powershell
& $python -I -B "$package/observer-install.py" verify --root $package --manifest-sha256 $manifestSha
& $python -I -B "$package/observer-install.py" install --root $package --manifest-sha256 $manifestSha --target $newRoot --python $python --uv $uv --seconds 300
```

变量指向操作者选定的绝对路径；$newRoot须为全新目录。成功输出包含解释器、模块、SPA目录及安装收据摘要。失败现场保留，后续安装另选新目录。安装步骤只准备文件。

完整成功同时要求入口exit0及返回的收据摘要。最终换名跨截止时可能已留下安装收据，入口仍报失败；保留现场并另选新目录重试。

启动前从受控WT部署记录取GUANHENG_WT_STATUS_FILE、GUANHENG_WT_CONTROL_ID、GUANHENG_WT_INSTANCE_ID及GUANHENG_WT_CONFIGURATION_SHA256四项。账户读取配置按WT实际发布类型选择：执行组件的business_observation提供当前持仓与资金时，设GUANHENG_ACCOUNT_SOURCE=wt_strategy；独立账户快照NAP提供资金、持仓、委托及成交四组发布时，设GUANHENG_ACCOUNT_SOURCE=wt_account_publication。缺少所选类型的发布时，页面保留对应来源不可用状态。两种来源各自保留其查询范围与原时间，实际提供的组别沿部署证据核对。

行情连接由GUANHENG_MARKET_URL、GUANHENG_MARKET_TOKEN提供，历史口径GUANHENG_HISTORY_SEMANTICS=source。策略持仓表的最近报价读取使用 GUANHENG_POSITION_QUOTE_URL、GUANHENG_POSITION_QUOTE_TOKEN，指向 WT 原只读报价入口。密钥保留在外部受控环境。

创建个人专用目录并设GUANHENG_WATCHLIST_ROOT；后续版本沿用这个目录。每次只运行一个使用该目录的观衡实例。市场观察读取已更新的外部GUANHENG_OBSERVATION_ROOT，回测归档读取GUANHENG_BACKTEST_ARCHIVE_ROOT；这些资料的更新和生成由各自组件负责。缺少对应输入时页面会显示能力状态。

策略观察历史使用外部 `GUANHENG_LIVE_STRATEGY_HISTORY_ROOT`。预建与个人自选目录互不包含的专用目录，使用本地绝对路径；空值仅提供本轮策略观察。目录重叠时策略历史拒绝写入，自选继续使用自己的目录和校验。

回测报告读取使用随App安装的WT纯报告接口，固定基准与逐日基准分别核对其模型和来源。GUANHENG_BACKTEST_ARCHIVE_ROOT指向WT正式发布的原归档根；独立REPORT.json或实验结果尚缺完成证明时，保持未归档状态。该依赖不启动WT或加载回测DLL。当前逐日消费及其正式归档资格分别见[验证记录](../evidence/2026-10-30-per-date-report-observer.md)。

```powershell
& "$newRoot/runtime/app/venv/Scripts/python.exe" -I -B -m guanheng_app --port 18120 --static-directory "$newRoot/payload/spa"
```

上方示例地址为http://127.0.0.1:18120/dashboard；具体安装沿其已登记profile，正式入口变化按[发布规范](release.md#用户入口保持)处理。前台运行适用于交互诊断；隐藏常驻运行使用下方本机维护入口。WT按独立操作手册启停。WT停止后观衡保留最近一次原结果及其时间，并展示停止状态。

更新时保留旧安装、外部读取配置和个人目录，将新包安装至另一全新目录；正常关闭旧观衡，再用新解释器和新SPA启动，核账户/行情/个人观察。回退时正常关闭新观衡，重新使用旧解释器和旧SPA，沿用同一外部配置及个人目录。具体合格回退版本、数据兼容范围和可读取的报告模式以该次交付记录为准；旧版本尚未支持的新报告模式需要使用支持该模式的已验证安装查看。旧托管App需要另行迁移。两个版本并行占用同一个人目录会触发独占保护。

交付和验收证据见[证据入口](../evidence/README.md)。运行与正式发布遵循[发布规范](release.md)。

当前独立版本升级回退已实际验证a63/spa2→a64/SPA002→a63/spa2，沿同一外部观察快照、两份完整400报告及个人目录，数据、证券顺序和原保存时间保持。a63回退后恢复其原状态文案，a64新增的执行资格显示需使用a64查看。该范围及精确包身份见[升级回退证据](../evidence/2026-10-31-observer-upgrade-rollback.md)；运行中WT整套切换由统一候选另验。

当前a68的T2108采用新方法/2；a66对新字段的数据读取和21字段CSV已验证，其中文方法说明仍适用于/1。回退a66时，正常停止本数据根的独立观察监督和Web，使用原观察CLI的restore将current切至升级前已验证兼容的/1快照，再启动旧解释器和旧SPA。restore携带本次当前快照expected-current，冲突时核对原指针；沿同一目录lease、完整校验和CAS执行。升级前的快照身份、来源配置、独立服务部署和已完成窗口须保留；回退读取并不修改窗口尝试或完成事实。新/2快照与内容对象继续保存，CSV可固定原版本导出；/2的人用页面使用a68查看。恢复a68时重新采用保留的新快照，并使用同一最终a68安装和相应服务配置。行情、账户及个人目录沿原外部事实保持，具体原件和验证入口见[当前连续性证据](../evidence/2026-10-31-observer-a68-continuity.md)。

独立调度功能与真实自然窗口分别验收。使用原service.now接缝的QA时钟可证明窗口选择、失败保旧/恢复、Web关闭期间发布和同日重启不重复；该验证不改变Windows时钟，也不授新的真实自然09观察或未来每日来源资格。固定原件索引只授该批消费，后续日期需要来源owner提供实际新输入及其内容身份。受控验证的重试上限和批次截止单独记录，原现场政策与失败窗口保持。


## 隐藏 Web 的启动、查询、正常停止与重启

独立交付包中的 `observer-web.py` 管理一个明确版本的 Web。它使用安装好的 App、Uvicorn 和 App 原有关闭流程；WT、行情通信和市场更新角色继续各自运行。Windows 自带的 PowerShell/CIM 只负责隐藏创建 Web 进程，维护命令随即退出。运行期只有该 Web 的解释器及 Windows venv 启动器。

先创建私有控制目录和外部读取配置。读取配置 JSON 的键为原有 `GUANHENG_…` 环境名，值均为字符串；将部署中实际需要的 WT 只读定位、行情连接、市场观察根、个人观察目录等放在这个文件。未列出的继承环境会被清除。凭据保留在私有配置文件，命令行只传文件路径。配置目录采用当前用户已有的访问保护。

WT日常启停使用[当前实例公开契约](../specs/wt-service-control.md)：读取配置显式设置 `GUANHENG_WT_CURRENT_FILE` 为运行侧发布的固定CURRENT绝对路径。每次读取取得本代四项身份，再沿原SDK核对状态和业务结果；同一轮账户与策略共用该身份。指针尚未出现或无效时报告读取失败，页面保留上次成功事实和原时间；指针恢复后可继续读取。账户、策略和实例状态页每15秒更新，页面保留手动刷新入口。WT关闭时按发布的停止状态展示。旧部署继续支持原四项固定环境变量；设置CURRENT后优先读取CURRENT，文件失败沿失败路径处理。观衡始终只读，不参与WT启停。

另存 `web-profile.json`，其模式如下；替换所有示例路径、版本、摘要和端口为安装收据中的实际值。`pythonw` 是已安装 App 角色解释器，`static_directory` 是同一安装的 SPA。Windows 打包应用可能将 LocalAppData 映射到自己的目录，使用安装收据的实际绝对路径。维护命令与 Web 分别核配置摘要和 App 版本；Web 找不到 SPA 时会报告失败。

```json
{
  "schema": "guanheng.observer-web.v1",
  "pythonw": "E:/example/observer/runtime/app/venv/Scripts/pythonw.exe",
  "pythonw_sha256": "替换为该文件的SHA256",
  "app_version": "替换为安装的guanheng-app版本",
  "static_directory": "E:/example/observer/payload/spa",
  "control_root": "E:/example/private/web-control",
  "host": "127.0.0.1",
  "port": 18120,
  "environment_file": "E:/example/private/web-reading.json",
  "environment_sha256": "替换为读取配置文件的SHA256",
  "startup_seconds": 30,
  "stop_seconds": 45
}
```

`startup_seconds` 和 `stop_seconds` 是本次操作的有限总等待预算。停止预算应覆盖部署中最长的在途只读请求及 App 原有清理预算。使用 CPython 3.12 x64 运行维护命令；可用已安装 App 的 `python.exe`，维护命令自身只用标准库。

```powershell
& $python -I -B "$package/observer-web.py" start --profile $profile
& $python -I -B "$package/observer-web.py" status --profile $profile
& $python -I -B "$package/observer-web.py" stop --profile $profile
& $python -I -B "$package/observer-web.py" restart --profile $profile
```

成功启动返回 `ready` 和该代 PID、控制 ID。重复 start 返回同一运行代。正常停止通过本机控制文件请求 Uvicorn 退出，沿 App lifespan 关闭读取池和个人观察 Owner。只有 `shutdown_complete=true`、两个读取池线程数为零、Web 解释器和 venv 启动器的 OS 退出码均为 0，才返回 `closed`；重复 stop 保留同一证明。该入口没有运维 HTTP 写接口。

`failed` 表示已有明确错误；`unknown` 表示本次截止或身份/退出证据尚不完整。保留控制目录中的 `instance.json`、本代 `ready/closed/failure/exit.json` 和 `web.log`，按原控制 ID 查询；维护入口保持原实例，避免未知启动产生第二个 Web。若启动已经超时且随后取得同代 ready，status 可以接续确认并由 stop 正常关闭。CIM 本身超时而未取得启动器 PID 时需核对该代回执和 OS 进程身份后处理，不自动重发启动。入口提供本地用户级管理，不能阻止同一 Windows 用户主动改写控制资料。

重启同版使用原 profile；外部读取配置与个人目录保持。升级或回退时，先用旧 profile 正常 stop 并保留 closed 证据，再为新版本创建新的 profile 和控制目录，引用新安装的解释器与 SPA，沿用原读取配置及个人目录。修改 profile 会改变运行身份，因此运行期间保留原 profile 供 stop 使用。版本切换只处理 Web，WT 和市场更新角色继续独立运行。

该入口只管理经它启动的 Web。已有直接 `pythonw -m guanheng_app` 启动的实例没有这些控制回执，须由其原 Owner 正常退出后，再迁到本入口；本工具不会附着到任意 PID 或强杀旧实例。

### 从共用目录迁移策略观察历史

以旧 profile 正常停止 Web 并核对关闭回执，再核共用目录只有自选文档、两类锁和策略观察数据库；SQLite 日志或异常临时文件需先由相应 owner 收口。把数据库和原历史锁备份到受控目录，核原文件摘要与 SQLite 完整性后迁往已准备的独立历史目录。保持 `watchlist.json`、原自选锁和 `GUANHENG_WATCHLIST_ROOT` 原样。新 profile 显式绑定历史目录，启动后核实同一列表身份、版本、顺序和两张历史表的原有记录。回退到旧版需要在新 Web 完全关闭后，备份并核对最新历史库，再将历史库和锁一并放回旧版预期位置。

### Web日志留存

有界日志模板沿本代`web.log`及`web.log.1`至`.3`留存，默认每份最多4MiB、合计16MiB；旧代日志和其他业务证据保持原目录。超预算旧日志只保留最新UTF-8尾部。stdout/stderr大段输出按实际字节轮转；本代没有后台日志队列。实现和边界见[运行日志模块](../modules/runtime-logging.md#独立观衡web日志)。

首次日志故障及正常/异常关闭时检查同代`web-log-status.json`：`state=ok`表示本日志owner未观察到文件写失败；`degraded`需查看固定`error_type`、`write_failures`和丢弃字符数。首次故障回执给当次write后的计数，关闭回执给最终累计值。日志故障后本代停止追加，页面读取和原正常stop继续；修复目录或磁盘后沿原profile正常重启，恢复日志写入。磁盘整体不可写可能同时影响状态文件，缺失不授成功。原`ready/closed/failure/exit`继续独立判定Web生命周期，日志状态不控制WT。

日志轮转沿本系列容量自动保留最新记录；历史控制代、来源Journal、账户和交易证据的清理仍沿各自owner及授权，不把16MiB误认为全机所有日志的合计预算。
