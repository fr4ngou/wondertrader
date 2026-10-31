# 独立观衡安装与更新

类型：操作手册。适用范围：[独立观衡development制品](../specs/observer-runtime-package.md)，Windows x64。当前验收使用SDK替身；真实QMT及生产发布分别登记。

接收交付记录中的ZIP、ZIP SHA256和OBSERVER-RUNTIME.json SHA256。先用Get-FileHash核ZIP，再用系统Expand-Archive解压至新目录。安装需要显式CPython 3.12 x64（含pip）和uv；离线wheel已随包提供。

```powershell
& $python -I -B "$package/observer-install.py" verify --root $package --manifest-sha256 $manifestSha
& $python -I -B "$package/observer-install.py" install --root $package --manifest-sha256 $manifestSha --target $newRoot --python $python --uv $uv --seconds 300
```

变量指向操作者选定的绝对路径；$newRoot须为全新目录。成功输出包含解释器、模块、SPA目录及安装收据摘要。失败现场保留，后续安装另选新目录。安装步骤只准备文件。

完整成功同时要求入口exit0及返回的收据摘要。最终换名跨截止时可能已留下安装收据，入口仍报失败；保留现场并另选新目录重试。

启动前从受控WT部署记录取GUANHENG_WT_STATUS_FILE、GUANHENG_WT_CONTROL_ID、GUANHENG_WT_INSTANCE_ID及GUANHENG_WT_CONFIGURATION_SHA256四项。账户读取配置按WT实际发布类型选择：执行组件的business_observation提供当前持仓与资金时，设GUANHENG_ACCOUNT_SOURCE=wt_strategy；独立账户快照NAP提供资金、持仓、委托及成交四组发布时，设GUANHENG_ACCOUNT_SOURCE=wt_account_publication。缺少所选类型的发布时，页面保留对应来源不可用状态。两种来源各自保留其查询范围与原时间，实际提供的组别沿部署证据核对。

行情连接由GUANHENG_MARKET_URL、GUANHENG_MARKET_TOKEN提供，历史口径GUANHENG_HISTORY_SEMANTICS=source。密钥保留在外部受控环境。

创建个人专用目录并设GUANHENG_WATCHLIST_ROOT；后续版本沿用这个目录。每次只运行一个使用该目录的观衡实例。市场观察读取已更新的外部GUANHENG_OBSERVATION_ROOT，回测归档读取GUANHENG_BACKTEST_ARCHIVE_ROOT；这些资料的更新和生成由各自组件负责。缺少对应输入时页面会显示能力状态。

回测报告读取使用随App安装的WT纯报告接口，固定基准与逐日基准分别核对其模型和来源。GUANHENG_BACKTEST_ARCHIVE_ROOT指向WT正式发布的原归档根；独立REPORT.json或实验结果尚缺完成证明时，保持未归档状态。该依赖不启动WT或加载回测DLL。当前逐日消费及其正式归档资格分别见[验证记录](../evidence/2026-10-30-per-date-report-observer.md)。

```powershell
& "$newRoot/runtime/app/venv/Scripts/python.exe" -I -B -m guanheng_app --port 18120 --static-directory "$newRoot/payload/spa"
```

地址为http://127.0.0.1:18120/dashboard；端口可以显式更换。关闭该观衡终端会停止页面服务；WT按独立操作手册启停。WT停止后观衡保留最近一次原结果及其时间，并展示停止状态。

更新时保留旧安装、外部读取配置和个人目录，将新包安装至另一全新目录；正常关闭旧观衡，再用新解释器和新SPA启动，核账户/行情/个人观察。回退时正常关闭新观衡，重新使用旧解释器和旧SPA，沿用同一外部配置及个人目录。具体合格回退版本、数据兼容范围和可读取的报告模式以该次交付记录为准；旧版本尚未支持的新报告模式需要使用支持该模式的已验证安装查看。旧托管App需要另行迁移。两个版本并行占用同一个人目录会触发独占保护。

交付和验收证据见[证据入口](../evidence/README.md)。运行与正式发布遵循[发布规范](release.md)。

当前独立版本升级回退已实际验证a63/spa2→a64/SPA002→a63/spa2，沿同一外部观察快照、两份完整400报告及个人目录，数据、证券顺序和原保存时间保持。a63回退后恢复其原状态文案，a64新增的执行资格显示需使用a64查看。该范围及精确包身份见[升级回退证据](../evidence/2026-10-31-observer-upgrade-rollback.md)；运行中WT整套切换由统一候选另验。

当前a68的T2108采用新方法/2；a66对新字段的数据读取和21字段CSV已验证，其中文方法说明仍适用于/1。回退a66时，正常停止本数据根的独立观察监督和Web，使用原观察CLI的restore将current切至升级前已验证兼容的/1快照，再启动旧解释器和旧SPA。restore携带本次当前快照expected-current，冲突时核对原指针；沿同一目录lease、完整校验和CAS执行。升级前的快照身份、来源配置、独立服务部署和已完成窗口须保留；回退读取并不修改窗口尝试或完成事实。新/2快照与内容对象继续保存，CSV可固定原版本导出；/2的人用页面使用a68查看。恢复a68时重新采用保留的新快照，并使用同一最终a68安装和相应服务配置。行情、账户及个人目录沿原外部事实保持，具体原件和验证入口见[当前连续性证据](../evidence/2026-10-31-observer-a68-continuity.md)。

独立调度功能与真实自然窗口分别验收。使用原service.now接缝的QA时钟可证明窗口选择、失败保旧/恢复、Web关闭期间发布和同日重启不重复；该验证不改变Windows时钟，也不授新的真实自然09观察或未来每日来源资格。固定原件索引只授该批消费，后续日期需要来源owner提供实际新输入及其内容身份。受控验证的重试上限和批次截止单独记录，原现场政策与失败窗口保持。
