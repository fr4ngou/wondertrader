# 2026-10-28 观衡托管行情采集

类型：验证记录。结果：partial。关联规格：QST6、QST6.1、QST7。整体迁移与生产运行资格继续。

## 本轮实现与范围

观衡真实App lifespan通过自有统一ManagedLocalProcess管理独立采集子进程，直接WinSHM Receiver→NativeDataKitSession→原生DataKit/Writer，无原始行情文件中转或第二套聚合。默认采集disabled；原账户Host配置/协议保持，正常关闭顺序为业务消费者→采集→账户Host。

此次新增行为位于自有Session、Python装配、应用接线和构建。已批准Writer两文件覆盖SHA保持`e4a6301b1b6713987862ab792735738117f210d6bd7bfba8b5ebb2f2978aa64c`，原WT框架无新增修改。QMT旧项目只读；本轮未部署诊断正文、未改动GH_WT_MEMORY_VERIFY原源、未真实下单/撤单或切生产。用户确认SHM_READ_PROBE已停止。

## 已取得业务结果

| 实际入口 | 结果 | 证明范围 |
|---|---|---|
| App→独立进程→真实WinSHM→SDK替身→原生Writer | 401证券、1604条、两代、401份DSB；首尾两证券各两根逐字段回读 | 正式托管调用链、单Writer重连及正常关闭 |
| 安装搬迁后401证券，来源晚65秒启动 | 同一子进程两代、文件回读、退出/整树/EOF/join/资源闭合均通过 | 该输入下无需配合60秒窗口；安装闭包可搬迁 |
| 修正包002完整6982证券即时来源 | 27928条、两代、6982DSB；首尾两证券各两分钟逐字段一致；70.485秒 | 完整规模正常主链，独立Job正常关闭 |
| 现有真实QMT源→App托管的搬迁包002 | 21725条、6925有效证券/57缺失，6925份DSB；600000/000001/510300各1根回读；74.953秒正常关闭 | 现有源配对、任意bytes秘密base64传递、真实原生落盘及关闭 |

真实观察的三个样本标签均为13:59，最大源时间13:58:18.918；结束源时间滞后11603645毫秒，约3小时13分钟。源心跳仍有队列11496、溢出0；这些是源端已记录的队列，不覆盖QMT SDK内部排队。量额单位、缺失原因、当日完整分钟和实时性继续未核。初始累计快照形成的一个分钟不能代表该分钟全程成交。

原始真实结果：`build/qmt-collection-real-prep-001/RESULT.json`。安装、搬迁、进程实际退出及后续最终输入汇总见`build/qmt-managed-collection-20261028-001/VERIFIED.json`。受控根均在`build/guanheng-workspace/`，各root保存actual result/stdout/stderr；启动器返回0与测试实际成功分别核实。

## 根因修正与验证

首次独立full审查发现三项并已修正：

1. 原ParserAdapter为void回调，不把writeTick=false交还自有Session。自有ObservedDataManager复用原sink LL_ERROR原子闩锁；push、管理线程闲时健康检查及release后结果均传播真实失败，保留合法时段过滤。C close的+1表示已释放但Writer失败，Python先清句柄再报告业务错误。
2. 关闭未确认时局部目录锁owner可能随函数返回释放。统一服务资源owner共同强引用collection和锁，确认关闭前持续持有。
3. 已校验原生配置后再次从原部署路径读取会脱离校验身份。Native改读本实例私有目录中已校验的字节副本。

真实文件障碍夹具分别触发push映射失败和close阶段后台归档失败，均报告固定Writer错误；重复push不重放，已关闭句柄清空，重复close保留失败。原始根为`qmt-collection-native-failures-20261028-001`。纯Host/App/采集资源57项的最终结果按汇总登记；既有App部分启动与账户能力10项通过。

完整规模延迟启动的两次失败保留：001在首批200交付期间unexpected_exit，原子进程错误未被旧夹具记录，具体原异常未证实；004在就绪阶段control_receipt失败。源码检查发现ready直接创建最终名字暴露半写/独占写窗口，以及普通Windows状态读句柄阻挡publisher原子替换。收据改为私有临时文件完整关闭后rename；状态读取统一为共享删除的有界单句柄，读取旧完整快照仍校验实例身份。实际Windows复现、最终回归及安装包状态以汇总和下方后继登记，不以候选根因覆盖原缺失证据。

Windows实际文件探针已复现普通读取期间`os.replace`失败（PermissionError/winerror5），读句柄关闭后成功。单独增加共享删除/完整共享仍不能让此机`os.replace`替换打开的目标，因此最终接缝采用Windows既有目标`ReplaceFileW`及只读GENERIC_READ/共享READ|WRITE|DELETE，首次仍独占rename。最终正反探针003通过：旧读句柄读完整generation1，新读取获得generation2；未重试、未主动删目标或修改权限。原始debug001/002、probe001/002失败和最终probe003均保留。API契约参考[Microsoft ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)。57项Host/App/资源/发布读取回归最终006通过，10项既有App启动/账户能力通过。

并发、配置身份、Writer失败传播及最终发布/读取变化均经过独立full及适用delta静态审查，最终无P1/P2；审查者将实际运行资格保持unknown，由本记录的真实执行证据单独证明。

来源时延诊断正文为可选能力，默认源码身份保持；6项现代与实际国信Python3.6.8纯测试通过。QMT自动化连续两次无法激活窗口，诊断尚未部署；当前没有SDK回调入口/原线程get_full_tick的同次对照，时延根因继续未定位。

## 后继与限制

先完成本轮文件发布/读取根因回归、最终安装搬迁和完整规模延迟来源，再继续来源时延、当天股票分钟/缺口及历史合并、生产时段收盘与长期运行。观衡App独立发行、策略业务同核及完整交易恢复继续总目标。

长期规范与手册已补[采集模块](../modules/qmt-quote-stream.md)、[持续采集手册](../runbooks/qmt-data-collection.md)、[构建入口](../runbooks/build.md)。合成、实际来源、独立安装与生产部署分别登记；当前隔离消费者均沿原截止收束，未启用终端外长期采集服务。

## 后继更正：004实机与来源分工

搬迁包004真实采集26948条、6926份DSB正常关闭；完整规模延迟来源005仍因状态读取短暂共享冲突失败，CollectionStatusPending修正尚未完成当前输入重验。本文前述VERIFIED.json引用为拟定汇总位置，当前文件尚未生成，不能作为通过依据。

来源诊断随后已部署到磁盘并尝试重启原报价行，但新体实际加载尚未证实，见[来源调查](2026-10-28-qmt-source-time-delay.md)。前述“尚未部署”仅对应先前时点。收盘后墙钟年龄包含正常休市时间，前述3小时13分钟属于原始wall age，不能整体当作盘中延迟。多策略交易已交给另一个WT对话，本对话继续来源延迟与采集。

## 最终后继：搬迁包005、完整延迟来源与实机

最终输入与结果汇总现已生成：build/qmt-managed-collection-20261028-002/{INPUTS.json,REVIEW-DELTA.json,VERIFIED.json}。原001的拟定VERIFIED位置继续作为未生成的历史记录保留。

- 安装闭包130文件完成ZIP逐成员SHA与搬迁逐文件SHA核对；build/qmt-collection-install-005.zip。
- 搬迁包005实际App托管→真实WinSHM与明确SDK替身→原生Writer：来源晚65秒接入，同一子进程两代，6982证券/27928条/6982DSB，首尾两证券各两分钟逐字段回读相同；真实正常关闭16.406秒，外层149.656秒exit0/无强制/树0/EOF/join/资源闭。
- 旧006沿启动前固定15秒停止预算，归档尚未完成即到期，最终6742份文件，整体失败。新007在新作业启动前把预算固定为60秒；旧截止未续期，旧输出保留。
- 60项Host/App/采集/状态回归通过；首stat前WinError32 Pending语义及夹具预算经过独立delta静态审查，无P1/P2。
- 最终搬迁包实机源一次90秒观察收到36916条、6926有效/56缺失、6926DSB，三个固定样本各一根14:23标签回读通过，98.187秒正常结束。先前60秒观察只处理到6800份，状态为no-complete-observation，未算完整覆盖成功；两份原结果均保留。

实机源最大时间14:22:28.391，结束私有队列0、溢出0；来源滞后仍未解决，56缺失原因、单位、全天完整分钟、正常生产时段自动收盘、旧历史合并与正式独立发行继续待验。两个实机观察均不要求重启/改变QMT源；诊断正文磁盘身份与实际运行身份仍分开，具体见[来源调查](2026-10-28-qmt-source-time-delay.md)。未真实下撤单、未切生产、无新增WT框架改动。


## 原生StateMonitor自动收盘验收

新增测试入口为tests/integration/qmt_quote_collection/run.py的--automatic-session分支，原默认allday/显式归档分支保持。仅在独占夹具目录生成短交易时段和statemonitor配置，allday=false、archive_session=null；主机时钟、WT框架和真实QMT保持。采用原最终搬迁005的采集入口/原生库与当前源码App托管装配，未授独立新App安装或真实生产时段资格。

实际受控根qmt-collection-auto-close-20261028-011：6982模拟证券/27928报价，真实WinSHM两代在同一子进程/Writer全部处理。模拟报价时间覆盖两分钟，原状态机按实际墙钟到达夹具20:58收盘/处理时刻。App尚未调用关闭且子进程实际仍活着时，观察到6982份DSB和当日SD0930 marker；没有调用归档API或请求显式close归档。AUTOMATIC-BEFORE-CLOSE.json记录20:58:04.201的文件数量、marker与首尾样本SHA。随后关闭耗时4.906秒，Helper对首尾证券各两根逐字段回读通过，关闭前后样本SHA相同。

VERIFIED.json保留完整结果。外层原330秒预算内161.813秒自然exit0，无强制，整树0、stdout/stderr EOF、读线程join及资源关闭全部确认。该证据证明原StateMonitor在本次模拟时段主动触发原生归档，文件由程序运行时产生；真实沪深交易时段/日历、源时效/单位和全天完整分钟继续待验。新增产品代码及WT核心修改0，真实QMT调用/下单/撤单0、生产切换0。

后继兼容：新增自动时段分支后，默认模式以2证券、两代真实WinSHM与原Writer/Helper完整回归通过（qmt-collection-default-regression-20261028-012），实际4.015秒exit0/无强制/树0/EOF/join/资源关闭确认；仍为allday与显式关闭归档。013文档检查通过；前一次012因并行新增状态保存提案尚未挂索引失败，补登记其proposed/待批准状态后通过，未修改提案或框架。
