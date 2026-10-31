# 健康历史子集读取、首次加载与并行续作

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：开发与实际只读链路取证。日期：2026-10-27。状态：显式排除配置准备与真实首次读取已通过；全库存005仍在运行，尾部及整体迁移未完成。

## 根因与实现

全库存已有三个指数的负量额隔离项；原配置准备仅接受completed，整份目录的三个failed会阻止其余已导入证券生成统一读取配置。自有prepare_source_config新增显式exclude_failed_symbols/CLI重复--exclude-failed-symbol，要求它精确等于终态completed_with_failures目录的全部failed。默认空集合保持原准入，running/failed仍拒绝；imported/empty不能被排除。原收据完整注册集合仍须精确匹配，失败证券藏在原store时拒绝。原目录与失败记录保留，摘要绑定原catalog SHA、原终态、排除集合和pending尾部。配置沿原source-stores，未增加行情存储或修改WT。

首次解码整只证券实测曾需5.66/8.53秒，原观衡配置最多5秒无法覆盖这一实际调用。现有部署字段GUANHENG_MARKET_TIMEOUT_SECONDS上限对齐SDK既有30秒，默认2秒保持；source部署显式选择30秒。主图/基准共享原D、排队扣减、SDK交换及关闭单D和线程join实现保持。没有增加自动重试或后台预热来隐藏首次读取。

## 实际主路径

专用制品：目录（外部历史/待归仓路径：`../../build/qmt-source-config-exclusions-001`）。从004已提交完整批次外部冻结开发子集，覆盖1854 imported、2 empty、3 failed，共1859项；原整库仍运行，冻结文件不代表5342完整终态。目录保留pending_current_qmt_download。实际CLI生成118个原store的统一候选配置，注册1854证券/499543068根，明确排除000001.SH、000300.SH、399001.SZ。原候选与生产实例保持。

- prepare实际exit0/passed；catalog SHA=0333e557d7c5b6290255c8db95255e71c7eb3eba3d137e57e18315cba3970012，config SHA=0755e5edc39163d9efc58fc9773d6a248717fee848b3fc53987776331117f4eb。
- 两个004新转换批次中的000001.SZ/000002.SZ，实际DSB→原Reader→同一HTTP→SDK逐时间与六字段核原CSV尾部；原采集session各自保持，实际注册1854证券。
- 新服务没有preload，首次请求直接来自观衡公开分钟接口，两证券均schema1.5/data_available，源标签仅转UTC、量额unknown；随后SDK读取及交替缓存访问通过。首次App测试采用显式30秒，与真实设置及请求链一致。COLD-APP-HTTP-SDK.json及consume-cold-app.py记录步骤。
- Reader/HTTP拥有线程同owner关闭，App shutdown_complete/读池live_threads=0；真实QMT/券商调用0，生产切换false。
- 首次30秒探测在旧Pydantic上限处失败，保留该次失败控制器状态；修正有效配置范围后的cold-app-002实际通过，失败尝试不算成功。

## 验证与审查

source_market的22项回归全部通过，涵盖显式成功子集、精确排除、终态拒绝、失败证券藏在收据、pending透传、CLI、原写失败/竞争/Reader关闭。公共图表36项全部通过，保留主图基准原截止、排队/容量/恢复/退出，新增默认2及30秒配置范围/SDK透传。

配置准备新准入按full独立静态审查，无实质P1/P2；实现SHA=fb49d17f4194dff2ed46bd24d1d32592f3c06141d3660a06bd9569bf54eaee91。配置预算变更按受影响预算链full审查，未变配置准备实现reuse；静态审查不宣称真实首次读取成功，运行资格来自上述实际链。

## 004停止与005续作

004真实运行在1876 imported/2 empty/3隔离、505765841根时，supervisor替换progress.json遇到Windows共享冲突32并异常退出。根控制器实际child exit1/outer exit2，整树0、双EOF、reader join与资源关闭齐全；原progress的running保留为停止前快照。

005仅修正自有临时进度发布：同目录唯一临时文件先完整写入/fsync/关闭，再对Windows 5/32/33重试同一次原子替换，最多2秒且受原wall/monotonic截止收紧，旧快照保持；其它I/O立即失败，持续共享冲突最终失败。原触发以真实Windows读句柄重现（本次API报5）；释放后成功发布完整新快照、持续锁有界失败并保持旧值三场景通过。第一次测试只接受32而实际返回5，失败尝试保留，后继002才计通过。

从004已终止的登记目录复用全部1876 imported，逐原收据/DSB/metadata SHA确认；独立审查另核125个原store全部1876成员及条数完全覆盖。5342原库存互斥均分，两worker各2671；reuse926/950、fresh1743/1720共3463，三个指数仅各隔离一次。新数据只写E:/workspace/wondertrader-data/qmt-history-20261027-005，原源和旧输出保留；保留原wall截止1793124019.0146115、monotonic截止1194801.437。005独立delta及受影响范围审查无实质P1/P2，实际原触发/恢复及持续锁回归另核通过。

005当前仍在转换/完整回读。进行中数量见本轮NOW快照及受管progress，不能拿它授予全库存结束、尾部齐全或005最终清理成功。后续完成实际全目录、下载尾部、异常指数可信重取、策略/真实常驻与完整恢复、独立发行；当前无新增用户决策，WT新增框架修改0、真实下撤单0。

收尾检查：project.py check实际exit0/passed；本轮10个主验证/旧作业终态均已核整树0、双EOF、reader join及资源关闭，失败身份单列，不算通过。PROCESS-AUDIT.json保留具体范围；005为唯一仍活跃的自有作业，尚无其最终清理成功结论。FINAL-INPUTS.json绑定本轮源码及规格，独立审查结论与实际输入相符。
