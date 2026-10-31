# 共享内存日线、因子与持续策略窗口

类型：验证记录。状态：普通安装的共享内存完整 SDK 主链与 WT 托管入口通过；独立审查中；实际 QMT 与生产资格待验。

## 目标与实现

策略需要持续更新分析窗口。原 R24 能读最新 QNA 文件，原 QNA 已能沿 WT Reader 计算复权，但生产侧原来只有单次生成入口。实现增加 [QAS](../specs/qmt-analysis-source.md) 的显式只读 v7 与 [AWP](../specs/qmt-analysis-window-producer.md) 常驻发布者：原策略线程读取日线/七列因子，外部原 Import→day DSB→原 Reader→QNA 计算，原子发布给 R24。数据/复权/策略计算原实现保持，观衡只读，WT 框架新增修改为零。

## 普通安装与来源主链

Host `0.1.0a11`、Agent `0.1.0a9` 来自原离线安装流程的新 Host 角色。安装收据 `1fba3f6b8dc1db4a219493e326f0f6c2ef9cf8565985cba2507425b0399f71de`；120 源、1661 运行输入，原五项测试及正式 pair/verify、实际 Python 3.6.8 内存正文均通过。单 100 毫秒 timer、SDK 同线程、禁止文件/网络尝试零、运输 worker 零。交付为 `build/root-analysis-source-001/package/DELIVERY-001.json`，SHA256 `307ba07815e6dba5cb635b96234d2ef269a6b3f2db7eb7397fe30420f0abf99a`。

AWP `0.1.0a2`、core `0.1.0a1`、WT `0.1.0a8`、Host a11、Agent a9 普通安装到独立 installation003。core 中八个原模块按原字节封存，来源清单另列。根组合入口 `build/root-analysis-bound-main-001/main.py` 的 main003 沿签名外部 HTTP→实际 Windows 命名共享内存→实际 3.6.8 生成正文→SDK 方法替身→原终态→原 Import/Reader/QNA→原 R24，70.406 秒退出 0。

三轮分别为首次窗口、增加共同闭合日、同日价格/量额修订；共 96 次实际 SDK 方法调用（每轮 8 日线、8 因子、16 参考）、3 次原生导入及 Reader、3 次发布与 R24 读取。共同基准从 2026-10-28 到 2026-10-29；同日修订产生新来源与发布身份。原始数据尾行、原候选分析 bars、实际接收时钟与绑定均核对，输入前后相同；来源、Host、发布者及其原 Native 子树正常关闭。

## 配置预算与原失败

main001 在业务启动前因 QA 重复创建目录失败。main002 已完成两轮发布，第三轮 SDK 执行 94/96 时，Host 原结果持久事务超过该测试预先设置的 2 秒 I/O 截止；原读取结果保持未确认，最后成功窗口保留，关闭沿同一个事务报超时，整轮失败原件保留。main003 使用新的独立配置，在运行前把 I/O 总预算明确设为 10 秒，完整三轮通过。产品和 WT 框架没有据此改动，不能以此证明 2 秒预算足够承载该历史数据与当前磁盘负载。

QMT 生成正文中的禁止文件/网络计数为零。外围测试驱动在生成正文之外读取固定 SDK 夹具与控制文件；这项外围读取不属于实际 QMT 运行能力。SDK 替身调用与真实终端查询分开：本次实际 QMT、下载、真实下单和撤单均为零。

## WT 装配与剩余范围

[WRI](../specs/independent-wt-runtime.md#持续策略分析数据装配) 增加可选 analysis_host 和 analysis_window，复用原只读 Host 与原发布 owner。源码启动/关闭回归通过，正式安装 WT a9/producer a3 及公开 WT 入口完整组合继续验收。实际 QMT 同正文组合、真实来源的新数据、完整交易恢复与生产切换尚未授予；最终独立审查沿实际冻结输入登记。

## 正式 WT 入口后继

WT a9、producer a3、Host a11、Agent a9、core a1 共23发行来自原安装及固定wheel组合；WT仅纳入三个装配源码与版本元数据，producer a3的四个行为模块与a2逐字相同，只联动版本依赖。普通安装收据 `a10837d90edced47913d55da5ae233df3e0f52270fcd645ce8f52af06a960f45`，接口为 `build/root-analysis-wri-package-001/INTERFACE-001.json`，SHA256 `c46b40a762344af772e8344ec055f874a6bd95040c300a59730cb7b161fdda5d`。

根 wri002 使用该安装的 `pythonw -I -B -m guanheng_wt_runtime` 实际公开入口。WT先建立 analysis_host，再启动 analysis_window；来源尚未运行时ready成立、data_ready为false。之后启动实际3.6.8内存正文，原签名HTTP/WinSHM及96次SDK方法替身调用完成三轮Import/Reader/QNA/R24，普通模块和输入前后保持。生产者通过自身常驻周期刷新，未添加测试专用触发接口，没有观衡进程。整轮69.281秒exit0，WT closed.json的components_closed=true；Host原closed证明runtime_closed和monitor_joined均为true，发布者、Source及原Native作业正常关闭。

wri001在来源启动前被原pair的精确解释器身份拒绝：配对准备使用python.exe，实际Host使用pythonw.exe。已停止pair在前者构造通过、后者沿原pair.py身份检查失败，原件保持。wri002将准备与运行统一使用发行pythonw.exe，不修改配对身份合同或产品行为。完整源码启动/关闭回归17项通过；实际来源同正文及独立full审查继续，整目标保持active。

## 观察接线与同正文后继

跨消费者检查发现a9发布者状态缺少观衡既有state/pending/forced字段，观衡的组件名集合也未覆盖新增项。根在自有薄适配补齐公共状态，WT a10普通基础/执行角色及17项回归通过；App/SPA兼容由独立观衡模块接入，当前不能授实际页面资格。

QAC显式增加分析连接后使用交易pair v3，原WT父端只认v1/v2会在来源前拒绝。WT a11继续仅扩展自有trade_host_process的公开身份识别，保留旧分支，18项原/新增回归及普通基础/执行角色通过。固定接口为 `build/root-analysis-wri-pair-001/WT-INTERFACE-001.json`，wheel SHA256 `f4e57f9391a7030d3258e2d95c92919ab4f2a82c015526e911a7fdd51370c6fc`；同正文完整运行仍待Host a12/发布者新候选普通组合。

另在全新隔离根实际复现原a3发布者正常退出后的同配置第二次WT启动失败：保留的OWNER.json被永久用作准入哨兵。AWP维护者在其职责层复用WT原OS租约，推进a4及同配置重启主链，既有a3及wri002原件保持。该后继尚未完成，不能用一次正常运行替代持续使用及重启资格。上述改动均在自有Python接入/装配层，WT原框架新增修改为零，实际QMT/交易/生产未执行。

## 运行中的唯一策略仍需接线

本次R24结果证明窗口被原MarketWindowFile解码为RetainedInput，未运行后继原策略/交易。实际execution_configured仍调用native_history_matches，比较原CTA context.bars(d1)与窗口raw历史。既有自有RealtimeReader的日线委托使用原Reader冻结缓存，已明示跨日/修订需独立接缝；AWP每轮发布独立Native目录，不能推导该CTA已自动切换数据。开发者1负责在自有适配层复用原Reader/Helper，连接稳定发布身份、同CTA新日线和原1.1.2决策/SDK执行；不据此修改或审计WT框架线程实现。该完整策略主链、九组件同包、实际QMT与最终交易资格继续待验。
