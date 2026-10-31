# 标准 TraderQMT 在途请求与关闭超时

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证记录。日期：2026-10-24。范围：[STQ-P9](../specs/native-qmt-standard-trader.md#stq-p9-标准插件接线与实施状态)在途HTTP、首次close超时、同实例保留及真实回收。两个新增窗口与原回归通过；完整关闭矩阵、事件/恢复和正式发行未完成，整体目标active。

## 实际行为

关闭期间HTTP尚未完成，release返回只说明本次等待结束。候选保留原worker、API和DLL，Factory拒绝提前删除；重复release继续观察第一次close截止，等待实际drain/join后才允许删除。测试全部通过公开标准接口与[候选工厂](../../src/TraderQMT/StandardFactory.cpp)，没有产品测试hook或WT核心改动。

| 实际窗口 | 根核事实 |
|---|---|
| 下单前prepare回复被门控 | 第3次GET trade-status的原200被保持；首次close611毫秒后worker仍在，重复release/delete为0毫秒且实例保持；放行后实际drain/join/delete。写POST和SDK替身均0 |
| Host已受理后的原202回复被门控 | 第5次状态GET后原POST202/queued被保持；父端已真实推进源SDK替身insert1并核Host为sdk_returned。首次close600毫秒后仍保留，重复release/delete为0毫秒；放行后真实回收，原生pending仍1、交易SPI0 |

第二场景中公开diagnostic_command_id尚未由completion发布，始终为空；父端的真实Host UUID在gate_entered、owner_retained、owner_closed三阶段相同，原命令/结果SHA不变。二者分别验证，不把空诊断字段伪造为已发布ID。Host已保存调用结果与C++本地未决观察分别保留，资源关闭不作交易应用确认。

## 构建、运行与审查

fixed007（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-fixed-007/result.json`）从固定上游08b230dd05facf6d650d949bfe51054115a2ecb1及冻结自有源码编译，包含最终Common切片；未编译工作树的冻结框架差异。首次runtime005只因C2测试错误预期3次状态GET失败：create_insert和submit_once各正常refresh一次，所以实际5次。原件保留。

仅Python oracle改为精确C1=3/C2=5及真实请求序列；复用同一DLL/EXE，在新冻结输入的runtime006（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-006/result.json`）重验15方法16场景全部通过。标准12方法13场景5.939秒，原真实SHM三场景19.077秒。旧丢回复/SDK未知、原Adapter单槽四查询、SPI/线程/原D、detach/stop及容量边界保持并重验。

DLL SHA256为5e676c5fafd7da4101fb9a3345918a21e86d1f9ac34df4709afd03f34e5f2d96，探针375ef78ae4e554f1089b9190f2d306991204e1a4ff4c46b929768a0beab3bbbc。唯一Python修正的冻结身份（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-trader-runtime-006/PYTHON-INPUTS.json`）与编译输入分别登记，未为测试改产品。

独立delta（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-close-review-001/DELTA-001.md`）关闭oracle P2，新增P1/P2=0；16来源根核（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-close-final-001/REVIEW-ROOT-CHECK.json`）一致。Reviewer执行0、动态unknown，根独立执行并逐项核16份原件（外部历史/待归仓路径：`../../build/guanheng-workspace/qmt-standard-close-final-001/CASES.json`）。子进程树、EOF、reader join、API、源线程/共享内存、Host/HTTP及测试事件句柄均实际回收，无成功场景强制退出。真实券商SDK0。

## 剩余范围

Candidate在途退役、队列/收据预算与父死亡等完整Standard矩阵继续；不能用正常关闭或这两窗口替代。实时事件仍未交WT SPI，event_consumption_complete=0。原生pending在release前后保持，不宣称API删除后仍保留同一内存对象；跨进程恢复另验。

生产Factory仍为旧ManagedTrader；完整事件/查询交接、独立安装搬迁、保留策略/观衡入口、真实终端及最终发行分别待验。无新框架修改、无旧终端HTTP、无旧QMT运行/修改、无生产切换。
