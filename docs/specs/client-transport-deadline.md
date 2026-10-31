# 独立客户端网络截止

类型：功能最终规格。状态：accepted。前缀 CTD。所有者：独立 Python 行情 SDK；适用 MarketClient 与 ReaderClient 共用网络传输。依据：单次有界行情交换、异常恢复及业务进程正常退出要求。

## CTD-R1 显式地址与网络边界

公开构造增加关键字 `connect_ip=None`。URL为数值IP时直接连接该地址；HTTPS域名必须显式给单个数值connect_ip，缺失、非法、带zone/interface或非数值地址在构造时拒绝，构造不访问DNS/socket、不启动线程或进程。HTTP仅数值回环；数值URL同时提供connect_ip时要求地址一致，禁止通过映射改变HTTP回环路由。IPv4/IPv6均采用明确地址族和数值socket.connect，所有路径不调用getaddrinfo/create_connection，不添加代理、重定向、自动重试或后台缓存。部署所有者更新地址映射。

## CTD-R2 TLS身份与凭据

HTTPS始终保留原URL主机名作为HTTP Host、TLS server_hostname/SNI及证书校验身份，使用默认可信证书链；数值IP按证书IP身份验证。连接IP只选择网络地址。TLS握手成功且预算仍有效后才能发送Bearer凭据；错误证书、主机名或信任链拒绝，错误信息去敏。不得关闭CERT_REQUIRED或check_hostname。HTTP非默认端口/IPv6 Host沿标准http.client序列化。

## CTD-R3 单次绝对截止

交换以monotonic绝对deadline覆盖连接、TLS握手、每次发送、响应头/体读取及响应校验后检查。每一阻塞网络阶段使用当时剩余时间，<=0立即拒绝；TCP耗时不得重置TLS上限，多次/部分发送不得重复消费原超时，不得用最小正值给已到期请求续时。TLS采用显式握手；请求仅有界字节，发送循环拥有partial send进度。保留原请求/响应容量、JSON严格验证与无重试规则。

SSL信任材料加载、JSON及证书校验包含同步本地文件/CPU工作，前后检查剩余预算且异常去敏；socket超时不能抢占任意OS初始化、调度暂停或本地CPU工作。这里承诺网络阻塞受剩余预算约束及同步工作后判超时，资格不扩为硬实时进程取消。

## CTD-R4 资源、异常及恢复

每次调用独占raw/TLS socket与HTTP响应，获取后立即建立finally所有权；连接、握手、发送、读取、验证和初始化失败均关闭已获得资源。SDK不创建后台线程/进程，Future取消不作为底层操作完成证据。失败后下一次调用能独立恢复；Reader实例身份仅在完整及时成功响应后绑定，线程独占规则保持。有限次故障后调用者线程可返回并正常退出；完整业务Console退出由业务规格验收。

## CTD-R5 兼容、安装与验证

包版本0.12.0，wire协议保持guanheng.market.v1。旧HTTPS域名配置必须补connect_ip；数字回环调用兼容。Reader公开签名、history_factory.market和minute_factory.sources[]的可选字段同步，构造零网络保持。其他暂停的Operations/Calendar/MinuteOwner/MinIO传输有独立owner，本次不授予其DNS/截止资格。

验收：未配/坏地址及HTTP改路由拒绝；DNS哨兵零调用；真实隔离TLS正确Host/SNI/证书成功、错证书不发凭据；IPv4/IPv6；TCP+握手+多段发送共享预算；失败/超时socket关闭、连续故障后恢复与线程退出；原慢头/慢体/协议拒绝和Reader/factory回归。生成离线独立wheel，安装到隔离目录，用该安装包执行网络验证，绑定源码/规格/测试/wheel摘要。测试来源和证书均合成，禁止外网/账户/真实行情/数据库/生产调用。WT核心与原生二进制资格保持原范围。
