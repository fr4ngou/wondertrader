# 观衡148撤下IPO供给回购图

状态：deployed。按用户“算了，这个也删掉吧”授权，撤下“IPO减持供给压强与科创50折价”，原式与事件推导工作结束。统一页面目录排除该看板、指标及近期事件；单图、多看板、布局恢复、指标说明与导出沿同一筛选，历史分区和后端采集保留。

## 实现与验证

源码 `88e3a930bcbe48c86e979d43df4f71ed7609e3a1`，注释标签 `guanheng-remove-ipo-board-20261122`。前端3文件30项回归、TypeScript/Vite构建和独立delta审查通过。本地CI003通过516项软件回归并合入master；原001验证环境SDK身份不符、002单项读取超时均保留失败原件，修正专用QA环境及停止重复安装后003通过。完整收据、日志、前端结果与审查材料保留于 `E:/workspace/wondertrader-data/observer-remove-ipo-20261122-001`，CI子目录为 `ci-001`、`ci-002`、`ci-003`。

## 正式采用与页面验收

App `0.1.0a148` 普通构建并安装至 `E:/workspace/wondertrader-data/observer-programs/a148-remove-ipo-board-20261122-001`。包清单SHA256 `b7494e2457ab94999ae9b663513cdbbf4cfd3bc828f3c0171a1989cc60778021`，角色安装SHA256 `388ee3929cc643943b9028535dfb860ed0088ce23a85c03664334acd32b8233e`。交付ZIP保留在 `D:/wt-releases/observer148-remove-ipo-board-20261122-001/observer-0.1.0a148-windows-x64.zip`，SHA256 `7b4cf2214433ab9bade36f42aded13ab42744ba430eade435b6a4eff93a99119`。

147正常关闭、OS退出码0；148正常启动并在启动命令退出后保持ready，PID51240，控制身份 `5b2e9f5e-f473-4a5e-84cd-b207daf99cc3`。正式地址仍为 `http://127.0.0.1:18143`。稳定profile与DEPLOYMENT同步148，profile SHA256 `a3ef6fafdbcfe19d32922f364d5fb0227f282330de1231eaf98cbb6aed4d5b2a`；读取环境SHA256 `626743631ddeee8942492923500a905c4f3bbf3016d022837a2f4e79452f7518` 完整继承。原146独立采集两个进程创建身份保持；UPDATE-DEPLOYMENT与WT CURRENT发布前后字节摘要一致。

正式Chrome逐项验收：导航14项、IPO选项已撤；多看板选择器已撤；旧组合链接只打开ETF净申赎；旧IPO单图链接回退到可用指标；指标说明搜索IPO为0项；导出指标目录已撤。沪深300ETF市值占比6个月124条、末值2.2522%保持可读。浏览器曾从旧地址缓存载入147入口HTML，刷新后加载148并确认撤图；已打开的旧页面需刷新。最终截图 `UI-a148-boards.png` 保留于上述证据根。

本代ready存在，failure、closed、OS_exit均空；延迟创建的web.log尚无落盘文件，该事实仅说明本轮未产生已落盘Web日志。既有来源缺口继续沿146证据，本轮仅验收撤图展示，不扩大数据完整性结论。

## 回退与产物

原147安装及证据根中的BEFORE配置保留；回退时正常关闭148，按原147profile启动并恢复稳定入口，再核18143实际读取。正式安装、交付ZIP和验收证据长期保留。专用开发QA解释器 `E:/workspace/wondertrader-qa/shared-tools/observer-ci-py312` 与已核flit_core构建依赖作为共享工具保留，不依赖任务worktree；临时构建、CI目录及任务worktree按开发收尾清理，结果写入证据根的CLEANUP.json。
