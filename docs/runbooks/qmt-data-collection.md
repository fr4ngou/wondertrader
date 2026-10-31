# QMT持续行情采集

类型：运行手册。适用范围：独立WT管理的终端外全推采集进程。职责沿[WRI](../specs/independent-wt-runtime.md)，组件格式沿[QST](../specs/qmt-quote-stream.md)。隔离验证、真实来源时效和生产资格分别核对。

## 运行结构

独立WT运行入口→隐藏采集进程→WinSHM Receiver→C++ NativeDataKitSession→原生DataKit/Writer。QMT使用已配对内存策略；外部服务读取部署配置。QMT内部无文件及网络访问的边界沿[源端模块](../modules/qmt-quote-stream.md)保持。

WT启动后listener持续等候，操作员无需另开Host窗口或协调60秒窗口。来源断开后Receiver关闭旧连接资源，再建立下一代认证；同一采集子进程保持一个Writer。采集依原Writer分钟和归档能力运行，断线期间缺少的分钟由历史能力补齐，并单独核实来源覆盖。

## 安装与配置

1. 核GuanhengCollection组件安装清单及各文件摘要。原生DLL、运行库、采集Python闭包与许可证由WT发行管理，观衡Web包和SPA独立安装。
2. 准备连接settings JSON，沿[QST2](../specs/qmt-quote-stream.md#qst2-冻结数据合同)与源策略保持route、transport及证券/profile一致，正文不写secret。凭据从受管环境注入；任意bytes秘密采用显式secret_encoding=base64，省略编码沿utf8。保持原配对身份。
3. 准备原生DataKit配置，basefiles、writer.path及非allday的statemonitor使用绝对路径。writer.module明确选择该候选已验组件；需使用关闭修正组件时配置WtDataStorageLifecycle。保持同步Writer（async=false）及原session，日间使用原StateMonitor；allday只用于对应验证范围。
4. 准备qmt.quote-collector.v1子配置和qmt.quote-collector-process.v1部署描述，固定Pythonw、entry、子配置、原生配置及Session DLL摘要，范围沿[QST6.1](../specs/qmt-quote-stream.md#qst61-应用托管与独立进程)。子入口运行pythonw -I -B，不依赖开发目录或PYTHONPATH。
5. 在独立WT的components.collection中选择kind=quote_collection，填写descriptor及sha256；按[WT手册](wt-independent-runtime.md)启动。旧GUANHENG_QMT_COLLECTION_CONFIG等App托管配置已退出观衡入口。

stop_seconds在部署启动前按证券规模和实际归档/回收时间确定，并绑定本次配置。首次关闭使用同一总截止；达到截止仍未归档完时保留失败记录及已生成文件，不宣称正常归档完成。

同一数据根保持单个Writer。采集服务使用byte-range锁，关闭未确认时继续持有。其他原生Writer和导入工具按部署交接同一根；该锁协调采用本入口的实例，外部程序仍由部署流程管理。

## 观察与数据读取

观衡只读GET /v1/ui/wt-runtime展示WT最近发布的组件状态。采集控制目录status.json包含原生投递/处理、最大来源时间、回调观察时间、连接代际、心跳、队列及固定错误。核实际进程、控制身份和配置摘要后使用；ready只表示进程初始化，旧JSON单独不能证明进程存活。

读取JSON使用独立SDK的guanheng_market_client.runtime_status.read_status；Windows句柄共享删除，允许publisher原子替换。同一次读取可得到完整旧快照，再核schema、控制ID、PID和配置摘要。首次文件未生成或取得句柄元数据前的共享冲突返回CollectionStatusPending，沿原业务截止等待；权限、内容和身份错误按实际失败处理。

盘中分别检查来源时间推进、有效/缺失证券、队列和溢出、原生处理及分钟文件回读。连接恢复、全天分钟完整性和行情时效各有证据。Writer真实写入错误会停止流，已部分生效批次按原责任核查。

采集归档由source-collected历史服务读取，旧历史与新DSB按原[归档模块](../modules/collected-native-history.md)合并，观衡通过公开查询连接读取。原Writer新归档无需手工再次导入；盘中DMB与分钟订阅沿原Reader。缓存准备、读取结果与来源完整性分别标明。

## 正常停止与恢复

停止观衡只收回观衡资源，采集继续运行。停止WT时，父运行入口向采集owner交付停止；Receiver结束并join后归档、关闭Native，父owner核实际子树退出、双管道EOF、线程join及句柄释放。closed.json只在原组件成功关闭时发布；生成文件仍由Helper/Reader回读确认。

超时或强制终止保留失败及未知结果，保持原目录。恢复前分别定位写入失败、来源断开或源时间滞后，并确认旧Writer已结束，再按原身份和数据根协议启动。真实交易及生产切换遵循各自授权与验收。


## 全市场显式v2启动

新部署通过正式pair材料显式选择 `profile.schema_version=qmt.quote-stream.v2`、`max_batch=1000`，沿已确认的全市场证券清单、4MiB帧、65536在线队列和原各期限。源与Host均须支持QST9，并重新生成和verify配对；原v1材料不得改写版本后直接复用。Native仍使用原同步Writer和200证券入口。

启动就绪先表示listener可等待来源。冷初始化期间源保存每证券最新值、Host同步初始化原Writer；随后同代收据确认集合、原子切入最新快照与在线FIFO。观察完整快照覆盖、后继心跳、增量与原生实际计数；当前初始分钟、缺失证券和断线历史分别核实。初始化尚未完成时继续展示等待及实际进度，不能以重连前缀或文件总数宣称全市场在线。

默认v1、旧正在运行实例和旧制品保持；切换、源端一次订阅/原timer、日志、停止恢复及发布资格仍沿原受控步骤。初始化期间保存最新值的语义与在线逐更新资格明确区分，在线overflow不隐藏、不绕过。实际候选和现场结果见对应日期证据，SDK压力通过不能替代实际QMT验收。
