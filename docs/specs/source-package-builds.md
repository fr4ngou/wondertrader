# 来源包永久源码与构建

状态：accepted。类型：功能规格。范围：独立 QMT Host、受限 Agent 与可选原生分析 Core 的源码、构建和隔离验收。

## SP1 永久源码与包边界

Host、Agent 的包目录和元数据位于 `connectors/qmt_shm/host`、`connectors/qmt_shm/agent`。Core 独立元数据位于 `packages/native-analysis-core`，其算法继续使用 `integrations/guanheng` 的唯一实现。Core namespace 初始化及实现成员由独立 Core 项目拥有，成员映射由 `config/source-packages.json` 声明。market-client 自身拥有公开回放入口，消费者安装 Core 后可经该入口使用原实现。

源码更新逐文件核实，保留其他职责的改动。新的构建从永久源码获得全部产品成员；历史 wheel、临时源码快照和运行目录不作为产品源码来源。

## SP2 可重复普通构建

构建使用声明的 Flit backend，按依赖锁校验 SHA。Host、Agent 直接普通构建；Core 从声明的永久文件组装其 namespace 并通过 Flit 生成 wheel，market-client 的公开入口由其自身 wheel 安装。构建前后核实完整输入身份，wheel 模块逐字对应源码，元数据版本取自所属 pyproject。固定 SOURCE_DATE_EPOCH 后，相同输入在两个独立输出目录生成相同三 wheel。

构建收据记录解释器、backend、源码和 wheel 身份、实际命令结果及适用范围。旧制品和已运行实例保持其原字节；新输出使用新目录。

## SP3 安装与主链

隔离普通安装使用角色精确 wheel 锁，验证依赖闭合、RECORD、实际导入路径与模块内容。基础 Host 可独立安装；需要 Core 的调用角色显式安装可选能力。用于 SDK 验证的完整客户端角色与生产 WT 角色分别登记。

SDK 短主链使用明确的 Python 3.6.8 替身、正式共享内存/配对代码和单一原策略线程，完成三证券历史准备、两个批量回读、同身份续核、消费确认与正常关闭。真实 QMT、账户及交易资格分别由相应现场验收确认。旧完整规模证据只按未变输入复用，新增构建或元数据资格由新收据证明。

## SP4 必要回归

回归覆盖连接默认行为和显式复用、嵌套预算、服务端关闭、未知结果、Windows 快照提交与失败保留。涉及共用 Journal、Source 调度或组合的源码归仓，还需运行对应原回归。标准与规格分别独立审查最终永久源码及准确构建输入。

## SP5 停止控制快照

自有控制owner在Windows直接取得共享READ/WRITE/DELETE的只读快照句柄，保留原生错误码。合法发布中的共享占用32/33由原监看周期在同一关闭截止内继续观察；真实ACL拒绝、没有明确共享冲突码的EACCES、非法文件、正文及ID继续拒绝。目录和同句柄前后身份核验保持，POSIX沿原读取路径。句柄移交只有一个关闭owner；该接缝不改变交易权限、未知请求、策略线程或WT框架。
