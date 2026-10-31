# 持续分析窗口运行手册

类型：运行手册。状态：开发验收。契约和职责见[模块](../modules/qmt-analysis-window-producer.md)。

部署为 WT 配置一个独占工作目录、一个原子发布文件、固定 Helper/IDataReader/Probe 路径与 SHA。来源连接使用原 `base_url/key_id/secret_env/timeout` 四字段；secret 只由受控环境提供，不写入 argv 或状态。source provenance 单独提供 provider、实例/会话、整数数据代次、SDK 版本、许可及 input_kind；原认证绑定与数据代次分别留证。

通过普通发行安装 `guanheng-analysis-window-producer[bound]`，接口范围为 WT `>=0.1.0a9,<0.2`、Host `>=0.1.0a11,<0.2`；发行 requirements.lock/安装收据仍精确固定 wheel 和 SHA，资格以具体已验组合为准。用 `guanheng-analysis-window --configuration <受控部署配置>` 启动，或由 WT 调用 `create_producer` 后 `start(deadline=...)`。构造和启动不要求来源同时在线；常驻服务等待来源，每轮刷新独立有界。观衡关闭与本 owner 无生命周期关系。

producer 配置键为 directory、publication、artifacts、python、worker_cwd、interval_seconds、refresh_seconds、max_age_seconds、start_date、max_rows_per_symbol。artifacts 精确 helper/reader/probe，每项 path/sha256。refresh_seconds 为一轮绝对预算，interval_seconds 为两轮间隔；max_age_seconds 比较最早真实源实收时点。八证券由原 QNA 唯一策略集合提供。

工作根的 CONFIGURATION.json 是恢复权威，保存完整非秘密配置与 SHA。同一根更换来源声明、发布位置、制品或刷新参数会返回 analysis_configuration_conflict，旧请求与状态保持。部署者应保留旧根，用其原版本/原配置处理未确认请求后再显式部署新根。a4 根缺该身份文件，a5 明确拒绝自动接管；不得手工补造文件或删除旧记录绕过核对。受管 secret_env 指向的秘密可轮换，秘密值本身不进入配置身份。直接 Python owner 调用者须提供明确纯值 source_identity；工厂已自动提供完整来源声明。

观察 STATUS.json 的 published_count、last_success.basis_date、source_received_at、generated_at、publication_sha256 及 phase。`waiting_source` 时旧文件保持；错误码说明缺数据、源过旧或原请求尚未确认。Pending 目录保存请求，保持同 capture；更换来源身份前由集成者明确处理旧未确认读取。`failed` 保留收据，先核原 Native JOB 收据及固定制品，不用成功标签覆盖错误。

Python owner 停止顺序：`request_close(deadline=绝对单调时刻)`，再 `close(剩余秒数)`。CLI 在工作目录收到 STOP.json 后调用相同入口。返回 closed=false 时继续保留 owner 和 OS 租约并续核原资源；正常关闭须有 Job 整树0、双 EOF、join 和句柄关闭。下一次 WT 使用新控制 UUID/控制目录，producer 的工作根、发布路径和配置保持；OS 租约在资源确认关闭后释放，OWNER/status 归档于 owner-records。Pending 沿原 REQUEST 恢复，旧成功窗口及实收时间保持。CLI 重启前由操作方归档自己的 STOP.json 请求文件；WT 控制目录本来按代次独立。

当前 SDK 证据及普通安装验证使用隔离市场值，不启动真实 QMT。真实 v7→Provider→QNA 接入、共享 WRI、生产运行和原生外发依赖资格各自按根验收。

需要自动更新近期日线时，在 configuration 同层显式增加 history_preparation，例如 `{"connection":{"base_url":"http://127.0.0.1:18120","key_id":"example","secret_env":"WT_HPR_HTTP_SECRET","timeout":10},"refresh_interval_seconds":300}`。地址/键为示例，实际选择既有受管 HPR v6；分析 source_connection 继续选择只读 v7。两份连接及准备间隔进入工作根身份，已有无补齐配置根须按原配置完成未确认读取后显式部署新根。

启用后初次只补当前闭合日，后继含上次尾日推进；同日300秒示例间隔内合并请求。原2021年以来暖机缓存继续复用，缺暖机不自动触发五年下载。refresh_seconds 共用 HPR和v7/Native预算：按部署实际往返选择，例如180秒；每个 HPR及RPC仍至多原30秒，来源任务长于 D 时保留原身份。准备后观察实际 basis_date，PREPARATION.json 的 call_returned/coverage unknown 不代表尾日已经具备。源任务/Journal容量按原 HPR运行手册管理，当前模块不删除旧任务或重派未知；容量耗尽属于明确待处理的源边界。

长期读取可为 source_connection 及 history_preparation.connection 各增加 `"read_retention":{"schema":"qmt.read-retention.v1","max_lifetime_ms":300000}`（数值为示例），并选择公共回收能力对应的已验Host/Agent及AWP retained extra。声明必须等于各自来源的认证profile；该字段属于完整配置身份，不能在已有Pending根随意改配。默认省略仍按上面的旧行为运行。

确认消费后，公共Host按原票据到期或epoch结束回收已确定责任；queued/running/unknown继续保留。Host状态 read-retention-status 可区分 queued_or_running/held_unknown/awaiting_consumer/awaiting_ticket_end；来源 HPR retention_status 是纯内存计数。AWP保留完整slot与原received_at，来源或Host重启时只核原ID，保留未知及旧窗口。终端外的capture/Native/发布归档继续沿部署数据保留策略管理，本协议不删除这些文件。

显式回收HPR已确定未执行时，观察原拒绝slot及后继capture；服务自动沿原刷新节奏继续。原ID网络未知或404/410保持等待，保留原slot交后续核查，禁止删slot或改ID。

选择带RR6的已验Hosta14/AWPa11时，新slot每次准入当前认证；capture的BINDING仍保留原值。Host重启后，已确认换代的捕获保留原件及旧窗口，下一业务轮继续；未知旧slot保持原ID。普通发行锁继续固定具体wheel/SHA。
