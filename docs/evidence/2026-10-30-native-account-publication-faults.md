# WT账户发布的重连、超时和父退出恢复

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B后继验证证据。状态：NAP-P3/P4所列四条隔离生命周期链已验证；完整统一候选、C HTTP/页面和真实QMT组合继续。合同沿[NAP-v1](../migration/native-account-publication-proposal.md)，生产者基线沿[原开发交付](2026-10-30-native-account-publication.md)。所有新增文件、缓存及制品位于E盘。

## 输入与本轮变化

根build/native-account-publication-faults-001。继续使用原installation005/a2：六发行736 RECORD，原精度Scan及只读DLL。四份account_*.py与原HANDOFF-001、安装wheel和安装源码保持同SHA，本轮生产者/WT框架修改均为0。A正在组合的a3统一候选单独验证，当前报告保持a2输入范围。

本轮只扩展主链QA（外部历史/待归仓路径：`../../tests/integration/native_account_publication/main.py`）与独立生产者QA入口（外部历史/待归仓路径：`../../tests/integration/native_account_publication/producer.py`），使用原Host、原SHM、原三参SDK替身及C唯一validator/projector。四个最终003案例共用229份实际输入，原件/物理副本/四案INPUTS均一致，FROZEN-INPUTS-003.json记录各SHA；当前main仅追加两行进程角色与采证时点注释，QA-ANNOTATION-001.json证明AST相等。实际运行输入仍以冻结003为准。

## 四条实际链路

| 案例 | 行为与证据 | SDK替身查询 |
| --- | --- | --- |
| reconnect003 | 原build_read_service与ReconnectingReadAgent完成两轮成功后关闭旧Agent、同凭据重新认证；新transport_generation及binding摘要进入原四组，四批source一致，原Journal文件身份保持；随后失败保旧及成功空P/O/D恢复，最终正常关闭 | 17 |
| timeout003 | 两轮成功后，QA以NtSuspendProcess暂停本轮已归Job的实际Native25360；原总D5000ms/工作D4000ms到期，父监督终止并回收该轮，attempt为forced/collection_timeout、exit1、completion缺失且原Native closed/joined为false；六项外部资源证明均true，旧成功帧保持，后继空P/O/D及资金恢复，最终正常关闭 | 12 |
| stop003 | 第三轮SDK读取内写QA stop信号，WT停止新轮准入；当前完整四查询继续排空，发布新成功帧后stopped，整次三轮且无第四轮，原关闭与外部回收成立 | 12 |
| death003 | 第三轮SDK在途时，记录实际WT Python69076及活Native14684/创建期Job成员，QA在该WT Python执行os._exit(7)；原Native随owner异常退出回收，旧成功五字段逐对象保留。外层launcher57516退出7、整树零及EOF/join后，同控制根新UUID重新启动，取得当前资金后正常关闭 | 13 |

总计54次模型查询，真实下单/撤单0；四案均有首次等待原件、两轮完整原事实/投影与最终RESULT。首次等待未授账户数据，成功空批是已知空集合。重连的运输认证与券商登录分别表达：broker_session继续unknown，Journal代际/observation_identity沿来源原值，当前证据不授券商登录会话换代。文件inode保持证明沿同一原文件运行，旧未知请求逐ID恢复仍由原Host另验。

death的回收时序需要明确：finish_producer先取得root退出7、Job整树零、pipe EOF及reader join，至该采证点尚未调用外层close_job；随后close_reaped按原实现仍对已确认空的Job调用close_job/TerminateJobObject并释放句柄。故证据证明死亡回收不依赖外层强杀。RESULT中的outer_job_terminated=false描述前述采证点，不能解释成全程API零调用。实际WT Python、venv launcher和Native分别保留身份，退出7没有被写成正常业务关闭；异常父没有PRODUCER-CLOSE，恢复代才有正常关闭证明。

timeout只在专属QA暂停本Job拥有的原生进程，生产模块保持原样。失败轮没有正常Native完成帧，外部物理回收成功与Native正常关闭分别记录。该用例验证运行侧截止和回收，真实QMT SDK超时及源端不可抢占窗口继续保持各自范围。

## C原发布投影消费

以当前C的project_publication消费九份实际模型原件：首次等待、成功、运输换代、失败保旧、空批恢复、Native超时、超时后恢复、stopped和父死亡后的新代成功。c-projection002全部产生schema4.0、正确publication状态/原成功时间/原行数和掩码，原金融validator保持；新增SDK及Native/Host进程均为0。输入源码摘要沿C-PROJECTION-INPUTS-002.json，九份DTO与RESULT逐份保留。

该验证调用真实C纯投影，runtime_state显式为unknown，未构造WRI状态或HTTP实例；账户页面的最终定位与HTTP/浏览器资格由同候选整链证明。C产品文件本轮只读。

## 失败原件、独审及交付

reconnect001使用单代Host入口，退出旧Agent后无法重连；reconnect002已换常驻Host，但单代Agent失败后没有重试，两案仅前两轮8次SDK，失败原件及资源回收保留。最终003复用两侧现有常驻入口通过，产品未改。timeout001以1000ms配置尝试原四查询，首轮持续source失败，未产生计划的父总截止超时；该次源失败具体类别unknown，不能替代timeout003的暂停/kill证明。stop001/death001保留此前输入的成功范围，最终报告使用同一冻结003四案。

两份独立delta/reuse报告位于同根REVIEW-EXECUTION-001.json、REVIEW-PROTOCOL-001.json，分别核事实/规格及IPC/回收时序，绑定原产品、安装、实际冻结源、四案及C原投影范围。开发包、逐件清单及最终核查沿同根DELIVERY-001.json、PACKAGE-MANIFEST-001.json和FINALPOSTFLIGHT-001.json登记；原首代开发包与审查保持原身份。

本轮补齐所列重连/父D超时/在途停止/父死亡后重建的隔离证据。完整容量、异常帧、未知请求逐ID核查、同候选WRI/C HTTP/真实QMT、交易恢复和模块B总体资格继续验证。
