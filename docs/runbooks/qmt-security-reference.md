# 证券资料共享内存接入

类型：运行手册。适用：独立WT拥有的QMT证券资料连接。模块与字段沿[模块说明](../modules/qmt-security-reference.md)及[唯一规格](../specs/qmt-security-reference.md)。

1. 在终端外准备固定Host/Agent安装、公开SDK3.6.8闭包及独立只读配置。选择v9两操作，沿原30秒retention和共享内存预算；资料使用独立route/SHM和HTTP凭据环境引用。原账户、交易、QST/HPR及v7/v8配置保持其职责。
2. 从真实QMT的`get_sector_list('')`和返回子目录核板块，再用已核node/name填写`source_groups`。目录出现证明映射存在，证券成员与上市资格还需读取。未知组保持unsupported，避免用旧数量或代码前缀补全。
3. 用原`guanheng_qmt_shm pair`生成并verify独立resident-read pair；用原`trade_cli pair`追加`--security-reference-read-pair`生成显式v5完整正文。保持`--source-mode strategy_tick`及原完整产品输入。省略新连接继续生成原版本，不把v9塞入旧schema。
4. WT通过原只读Host进程组件管理资料监听，通过原交易Host组件管理完整产品。启动前核安装/manifest/配置SHA及父端准入；监听ready与QMT业务来源可用分别查看。凭据仅在私有环境，QMT正文不建立网络或读取外部文件。
5. 沿既有QMT策略启停接续流程采用完整正文，保留原文、原请求和通信库。资料调用优先先取一页，按原cursor读完同次catalog，再分批读取details；核各页B、catalog、scope、时刻及计数一致后才声明完成。
6. 统一日线owner记录各类应收、实收、尾日和缺口。断线或响应未知继续原UUID/slot；游标过期明确结束旧捕获后，才新建捕获。资料失败保留价格池和已成功行情，不删除证券或把未知字段填零。

升级先离线生成新材料，再按实际在途与交易责任切换；回退使用原角色、原配置和原文，保留新版本已完成的行情及原始结果。Source原SDK是同步调用，部署时记录批次耗时；在交易时段按实测选小批次，保持既有唯一timer和单重任务调度。

2026-11-04隔离与真实目录证据位于`E:/workspace/wondertrader-qa/daily-mainline-20261103-001`的security-reference独立核验、角色及sector-tree-real001目录。Python3.6.8完整正文、WinSHM/签名HTTP、原ID恢复与slot消费已核；实际新Source读取及全市场完整覆盖另按正式部署结果验真。
