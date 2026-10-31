# 2026-10-22 独立客户端网络截止与业务恢复

类型：开发隔离验证记录。状态：后继SDK及业务切片独立审查通过，严格发行继续；生产未发布。最终要求见[CTD规格](../specs/client-transport-deadline.md)与观衡仓库的`wondertrader-market-chart`规格。完整移植目标保持active。

## 根因与实现

图表独立审查在SDK0.11.0复现：配置30ms超时，合成DNS解析等待300ms，实际调用耗时320.5ms；Console外层等待结束后工作线程仍存活，随后owner关闭又等待258.5ms。网络阻塞发生在自有Python客户端，不能靠Future取消证明结束。

SDK0.12.0在共用网络owner修正：数值socket直接连接，HTTPS域名使用部署配置的connect_ip，原域名继续用于Host、SNI和证书校验；缺失映射在网络前拒绝。TCP、显式TLS握手、每次部分发送及读取共用绝对剩余预算；已获得的raw/TLS socket与响应在finally释放。没有新增解析线程、进程或DNS缓存。同步本地信任材料和CPU工作的非抢占边界按CTD如实保留。WT框架及原生二进制没有因此修改。

旧数值回环配置兼容；旧HTTPS域名配置需要补显式连接IP。MarketClient、ReaderClient及适用工厂同步映射，wire协议保持不变。其他独立传输owner的资格不由本次转授。

## SDK验证

`build/native/client-deadline/final-inputs.json`绑定30项输入，主任务重新计算后漂移为0，wheel与构建收据一致。独立安装包网络测试12/12、0skip、最终残留线程0；Reader/工厂28/28，构建范围7/7。原服务测试37通过、6项因原生环境缺失跳过，未提高这些原生路径资格。

唯一wheel：`build/native/client-deadline/client-sdk/guanheng_market_client-0.12.0-py3-none-any.whl`，SHA256 `5314dcb38353b50f63a69a9de97c42c8df900317bac3c01d78de45c0185e2e4e`。验证覆盖真实合成本地TLS的Host/SNI/证书、错证书不发凭据、IPv4/IPv6、DNS零调用、连接/握手/发送累计预算及异常socket释放。原生完整新包尚未生成。

## 实际业务链

业务候选位于`E:/workspace/qmt-worktrees/wondertrader-service-adapters`。独立安装该wheel，原生服务只使用两证券428根冻结的真实来源输入；没有调用运行中的QMT、下载或账户接口。新的整链37项全部通过，源码/测试/规格与原始数据前后摘要一致，原生owner正常关闭。

两组各两次Console子进程完整ASGI启动和正常退出：正常分钟主图/基准、空/失败/恢复，以及HTTPS域名缺映射连续失败→同端口正常数值来源恢复。四次均DNS调用0、最终非daemon/读池/日志线程0、HTTP客户端关闭及端口释放；旧MarketData、数据库、NATS连接0。ASGI卸载即时线程与最终进程线程分别记录，不授同进程热卸载资格。

实跑材料：`E:/workspace/qmt-storage/wt-chart-dns-integration/run-8bc92640b1c948a6854df15316482e0c/`，包含result、JUnit、两组lifecycle及稳定日志。

浏览器复用实际MarketPage组件与本轮Console payload，1m/5m、来源资格、空和失败均通过，页面及console错误0；相关输入前后摘要一致，且浏览器运行前核对payload生成链的source_inputs与当前源码匹配。收据为观衡generated目录`validation/wondertrader-market-chart/browser-final/run-ce24c75e655b4d62a9499179ee243721/receipt.json`。该证据属于隔离组件入口，完整受管生产SPA入口尚未验收。

## 剩余边界

正式准备与SDK/业务独立复审继续。旧策略制品源码漂移保持真实记录；完整发行门禁、原生搬迁包和生产切换各自验收。真实QMT的[分钟量额精度](2026-10-22-qmt-cache-volume-precision.md)、长历史补齐、原CTA真实盘中闭合分钟、研究日线/复权及交易恢复仍按完整目标推进。未操作数据库、真实订单、生产配置或运行终端。

## 后继候选 repair-001

前述`5314...`是首次冻结的未发布候选。独立审查发现CTD-F001：HTTPResponse已创建文件引用后，响应包装初始化失败，保留异常traceback会继续持有文件；只关闭socket不能立即结束这个引用。修复在包装失败分支显式关闭response并重抛，中文注释说明所有权原因。该修改位于自有SDK；WT核心、API/wire与未发布版本号0.12.0保持原样。

后继wheel为`build/native/client-deadline/repair-001/client-sdk/guanheng_market_client-0.12.0-py3-none-any.whl`，SHA256 `86ca4c90db6db5fd6bf448192e91677b765c0a793814642acbf60a0157179dda`。原wheel及记录保留，当前验证明确选择后继摘要。`repair-001/final-inputs.json`绑定30项输入；主任务核对当前输入、安装文件、wheel内容及日志摘要均一致。保留traceback的真实回环回归原样失败、修复通过；源码与隔离安装网络测试各13/13，消费者28/28，构建7/7，服务38通过/6项原生fixture缺失跳过。

独立delta结果位于`repair-001/independent-delta/review.json`，与最终pack规格/输入/wheel身份相符：CTD-R1–R5均complete、CTD-F001 resolved、开放阻断0。审查者独立运行HTTP/TLS × MemoryError/KeyboardInterrupt四种初始化故障，保留traceback时均文件关闭、描述符-1、对端EOF；同客户端连续故障后恢复、服务端线程退出。该结论只授本SDK切片开发审查资格。

修订包的业务整链重新运行于`E:/workspace/qmt-storage/wt-chart-dns-repair-integration/run-a615067b2aea4bfcaa841f94bb2fdb34/`：37通过、0skip，44.39秒；真实数据与声明输入摘要不变，Gateway调用0、原生owner正常关闭。四次Console进程的DNS调用及最终残留线程均0，旧MarketData/数据库/NATS连接0。浏览器绑定此轮实际payload及当前源摘要通过，收据为观衡generated目录`validation/wondertrader-market-chart/browser-final/run-65c4f9a9bb2446a996e31227bfe4a908/receipt.json`，范围继续为真实页面组件的隔离入口。

业务正式prepare-review五项检查全部通过；当前delta报告为观衡generated目录`validation/wondertrader-market-chart/native-chart-repair-delta/review.json`，R1–R5 complete、开放发现0。审查者核对后继wheel、安装/业务输入、四进程结果及159项页面输入，并独立复验响应包装失败的资源释放。该结论不授予完整SDK、生产或旧策略制品资格。

SDK审查之后，规格索引增加下一[NQB只读初始化](../specs/native-qmt-readonly-bootstrap.md)条目；`repair-001/post-review-document-index.json`核实30项原输入中仅该索引改变，删除新增一行即可恢复原字节摘要，SDK源码/测试/API/配置与wheel均保持原审查输入。未修改冻结清单或覆盖历史资格。

后续再登记[NHP准备分片](../specs/native-history-preparation-shards.md)，第二份`repair-001/post-review-document-index-nhp.json`确认仅索引增加两项下一任务链接，移除两行恢复原摘要；其余29项SDK声明输入保持。两份记录分别保存当时观察。

## 正式审查与严格门禁分界

图表与送审阶段治理两任务的真实独立报告均已由原工具保存为passed、开放发现0，阶段为full_testing。治理复审逐项确认R1–R3，并独立纯规划验证16条完整门禁声明派生22条命令，market五项角色精确匹配；缺项/多项负例被原严格规则拒绝。该调整仅补原market批声明遗漏的storage角色，保留原测试选择和真实资源准入。

两次report导入后的自动严格门禁都在只读doctor阶段停止：`native_fixture_capacity_occupied`，resource=strategy。当前注册环境为running-retained、failure_latched=true；原分钟接纳批22项失败、业务资格false，容器仍运行。未启动新资源、恢复、清理或删除原环境。旧六份策略制品的source_changed也保持原事实，正式开发审查通过不覆盖真实资源、制品、发布或生产资格。
