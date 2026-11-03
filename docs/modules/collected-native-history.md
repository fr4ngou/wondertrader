# 原生采集归档历史查询

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。状态：实现、独审、普通组件及App接口主链已验。所有者：行情与历史接入。行为以[CNH规格](../specs/collected-native-history.md)为准。实现入口CollectedSourceMarket（外部历史/待归仓路径：`../../integrations/guanheng/collected_history.py`），构造由来源工厂（外部历史/待归仓路径：`../../integrations/guanheng/source_market.py`）显式选择。

## 职责及数据结构

原Writer负责从接收到的累计快照构造分钟，并由原StateMonitor把实时缓存归档到storage_root/his/min1/SSE或SZSE/code.dsb。模块只读取这一份原生历史，使用原NativeHistory、文件ABI与Helper解码，不另写分钟算法或导入收据。盘中形成中的DMB和分钟订阅沿原NMR；本模块查询已归档DSB。

source-collected配置拥有base、collection、native_reader、max_bars和max_file_bytes，可选supplements为独立导入补齐来源列表。base及每项supplement沿原source-store/source-stores/source-catalog，拥有各自成功收据和Reader预算；base原注册范围保持。collection拥有storage_root、symbols、source、source_license、price_unit/volume_unit/amount_unit。source明确为QMT行情派生的WT采集数据集身份，不等同于原始逐tick通信会话。原始快照会话不从DSB猜测重建。

原生记录为既有88字节WTSBar。API返回原标签minute及open/high/low/close/volume/amount；本模块保持这些已存数值。dataset_version以wt-collected-min1-v1前缀及声明摘要表示方法，content_id绑定本轮DSB字节，source_label表示该采集数据文件的分钟标签。分钟构造与厂商历史分钟逐值一致须另验，原价量额单位按声明保留unknown，不能据WT文件存在自动取得实盘标准化资格。

## 读取、合并及生命周期

一次查询在原Writer目录使用普通只读句柄复制有界文件并复核大小/摘要，将稳定内容写入本次私有临时副本；冻结路径租约只作用于副本。原Reader解码后再次核原DSB身份，变化或形成中返回Unavailable，后继请求重新捕获。临时副本在原ABI返回后释放，不保留第二套长期行情库。

同一进程每次检查当前文件，原归档第一次出现或追加后无需重新登记证券或重启服务。来源缺文件时返回base及显式补齐来源的实际范围；现有文件不稳定或损坏时明确不可用。归档、base及supplements沿原select_sources合并最近N根，同值去重、异值冲突，保留每段原metadata及provenance；coverage保持Unknown。未登记证券的补齐来源跳过，已登记但读取失败保持不可用；日线继续由base原生day历史提供。

supplements省略或空列表沿原路径。该接口只组合原生成功导入的新根，不在原Writer目录重写重叠记录，不新增行情库、聚合器或定时任务。外部已导出的当日缓存可经原Importer成为补齐来源；日期、来源及单位仍由原导出metadata声明，不伪造在线准备收据或后移在线as_of_date。

服务创建线程独占base、归档和显式补齐来源的原Reader与close，HTTP只复用原单服务调用链。调用/文件/解码/响应保持原条数和字节上界，原受管进程/Job负责总截止及停止。独立WT通过SourceMarketProcess拥有子服务，配置/ready/stop/closed模式保持；观衡只配置公开只读连接，停止观衡保持服务运行；未显式选择source-collected的配置继续使用原实现。作为source-preparing的base时，本地读取与原网络补齐各由原owner负责。

## 部署及验证

日线持续更新由现有`DailyOverlayMarket`承接：静态归档提供历史，原Writer的`his/day`及收盘marker提供动态闭合尾部。指数外层用segments保留Mixed，股票/ETF内层原dataset口径保持。`scripts/prepare_market_collection.py`离线生成50指数、原生日线开启和动态读取配置，不启动实例；源端完整GH仍由其所有者配对。日常运行复用原组件和文件，无新增持久服务、定时任务或行情数据库。字段、维护步骤及待开市资格见[持续日线手册](../runbooks/continuous-native-day.md)，合同沿[CNH-R6](../specs/collected-native-history.md#cnh-r6-原生日线持续落盘与指数动态尾部)。

沿[WT历史服务手册](../runbooks/source-market-app.md)绑定新的源码组件、配置SHA和外部storage_root，旧导入库作为base。凭据仍在服务环境，源配置只有数据身份，不开启QMT下载、账户或交易。组件更新不复制或覆盖外部采集历史。

独立补齐根的选择、导入和后继配置操作见[采集历史补齐手册](../runbooks/collected-history-supplements.md)。来源延迟、实时tick接收与最终归档缺口分别取证；缺少原tick留痕时保留触发原因未知。

当前正常整链使用真实上午/下午副本验证同实例3→120→122根，以及自然15:05归档的三证券240根→原Reader→统一SDK；独立审查、最终161文件安装和普通App a19/35发行完整接口链已通过；真实整库335分钟store+1日线store和今日采集同实例三样本241根保持1+240分段原值。详见[CNH证据](../evidence/2026-10-29-collected-native-history.md)。实际浏览器绘制与最终统一发行资格沿[CNH验收要求](../specs/collected-native-history.md)分别登记。完整全市场覆盖、原厂分钟对照、自动长期运行与生产另行验收。
