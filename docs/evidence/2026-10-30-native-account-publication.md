# 独立WT发布原生账户四组事实

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块B开发证据。状态：固定生产者及原C投影主链已验证，统一WT装配、C实际HTTP/页面和真实组合继续。要求沿[NAP-P1..P6及冻结合同](../migration/native-account-publication-proposal.md)，职责沿[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)。本轮全部新增安装、临时文件、缓存和制品位于E盘。

## 缺口与实现

R20由策略调度发布策略观察，首次接管尚需实际周期与WT初值。账户查看需要策略尚未接管时也能读到券商资金、持仓/可卖、委托及成交。现有Scan已经提供原生四查询与v2事实帧，原C已经提供字段校验和中文投影；新增内容是独立WT的生命周期与原帧发布。

新增四个WT模块：[account_protocol.py](../../apps/wt_runtime/guanheng_wt_runtime/account_protocol.py)迁移原严格JSON与配置对象，[account_scan_config.py](../../apps/wt_runtime/guanheng_wt_runtime/account_scan_config.py)迁移原纯配置准入，[account_scan_runtime.py](../../apps/wt_runtime/guanheng_wt_runtime/account_scan_runtime.py)迁移原schema2单轮Job/线程监督并返回原始帧，[固定工厂](../../apps/wt_runtime/guanheng_wt_runtime/account_observation_process.py)顺序运行原单轮、发布最新观察和原关闭事实。迁移原件摘要沿MIGRATION-INPUTS-001.json。原C产品文件由C继续维护，本轮未修改；金融字段验证与投影仍唯一调用原validate_observation/project_account。

工厂是guanheng_wt_runtime.account_observation_process.create_process。locator沿原六字段身份，完整账号和原四组只在受控观察材料，status没有账号、URL、凭据或启动命令。每轮沿原总D和创建期Job；新轮从前轮收口后按间隔启动。源失败保留成功原帧与原时间，成功空批清除旧行；停止关新轮准入，当前轮排空，真实join/reap后释放原WT OS租约。

独审发现两项同一停止期限缺口：close较短调用D未锁存、运行异常直接set停止事件。已在唯一request_close及close的min锁存处统一；两个回归分别证明后续close和异常后的迟到close均保持首D。另将busy/unknown关闭resources统一固定六项False，消费者可用同一字段集合解释未确认状态。原WT框架、账本、绩效和Trader算法改动均为0。

## 最终普通安装与实际主链

根为build/native-account-publication-001，最终installation005，六发行/736条hashed RECORD，无App/Web包、无pth。使用原精度Scan和TraderQMTReadOnly两个制品，原生源码及二进制本轮均未修改。A公共runtime正在单独接入新组件；本安装快照及其范围按实际文件身份保留。

| 身份 | SHA256 |
| --- | --- |
| INSTALLATION-005.json | 954324eb091c3a3d9b31f4f0a60fa0a6650ed3fdc7a3e329c27ba5f98b883298 |
| Scan | 5dae69603377ef7d88dde3e2d82dbc4e111c5b3002b10a456c07c528a700ad44 |
| TraderQMTReadOnly | 27e92a99437771432e5d0af97731dc80b94b445a5a47e1fc70bf9a696a095c42 |

最终main009使用主链夹具（外部历史/待归仓路径：`../../tests/integration/native_account_publication/main.py`），原Host/SHM及三参数SDK为显式替身，独立无App生产者在另一个受管Job内通过实际固定工厂运行。C消费只读取原子文件并调用原validator/projector，没有从页面启动Host或Scan。主链共13查询，真实下单/撤单0：

| 阶段 | 可观察结果 |
| --- | --- |
| 首轮成功 | 2持仓/1委托/1成交/1资金；资金available82000，全部50项可对应源原值的facts一致，浮点逐位比较 |
| 次轮更新 | 新scan_id及revision，available82100，50项facts再核一致；两轮各4查询 |
| 第三轮失败 | SDK替身在首项查询抛错，新增1查询；degraded保留次轮成功原帧、scan_id和last_success_at，attempt保留本轮失败与回收事实 |
| 第四轮恢复 | 4查询成功，持仓/委托/成交为已知空，原旧行清空，资金available82200；成功时间推进且错误清空 |
| 同根竞争 | 第二固定工厂在OS租约处拒绝、未新增原生查询，关闭第二owner后原owner仍ready |
| 正常关闭 | 原completion、exit0、创建期成员、整树wait、两pipe EOF/readers join及资源关闭成立；外层producer/Host/Agent/HTTP关闭全部通过 |

MAIN-INPUTS-009.json绑定229项实际QA/通信/C输入，运行后0drift；RESULT、PRODUCER-CLOSE、ROOT-EXCLUSION及两代PUBLICATION/PROJECTED、FAILED-REFRESH、RECOVERED-REFRESH分别保留原件。原金融投影公开输出不含完整合成账号。该QA的Host由外层夹具持有，故完整WRI生产装配、生产C HTTP和浏览器范围仍为gap。

admission002使用同一005安装：十种坏descriptor/预算/身份拒绝、busy固定六False、两个首停D回归通过，原生及SDK调用均为0。安装001/003/004及main004/006/007/008保留此前输入范围。main001为QA缺SDK路径，002为QA Journal联合预算无效，003/005为QA读取未处理原子换名的短暂2/32错误；均保留失败，不授通过。安装002为夹具基线误指不存在的R25安装，构建后在轮子数核查处停止；没有运行账户。

## 资格与交接

| 要求 | 当前证据及剩余范围 |
| --- | --- |
| NAP-P1 | 无App固定生产者→原C投影通过；A公共runtime/原account_host同候选及实际C页面继续 |
| NAP-P2 | 两成功轮各50项facts原值及浮点逐位，原四组/来源/未知由C原validator核；真实四组精度沿既有SUCCESSOR002复用，本生产者真实组合另验 |
| NAP-P3 | 两轮更新、源失败保旧、成功空批恢复通过；认证换代、原请求未知恢复及实际超时/父死亡矩阵继续 |
| NAP-P4 | 成功轮与失败轮物理回收、停止及同根竞争通过；正常退出不覆盖实际强杀与未确认回收矩阵 |
| NAP-P5 | 固定错配置/预算/身份及busy已验；R20并列消费、完整错绑定/容量/重解析点读取矩阵由最终C入口继续 |
| NAP-P6 | 固定源码、普通安装及独立审查/开发包交付；统一候选、真实QMT和C HTTP/中文页面继续由A/B/C组合验收 |

工厂、descriptor字段、安装依赖及可复用SDK夹具沿同根HANDOFF.md交接。A负责公共组件注册/依赖与统一安装，C负责读取定位、原投影及HTTP/页面。源凭据沿原Scan环境变量注入WT进程，内容不进入descriptor/status；原Host Journal保持原owner。R20策略视图保持原职责。

独立执行/事实审查与协议/生命周期审查位于同根REVIEW-EXECUTION-001.json、REVIEW-PROTOCOL-001.json，绑定最终安装/主链及源码。包与最终校验沿同根DELIVERY-001.json、PACKAGE-MANIFEST-001.json及FINALPOSTFLIGHT-001.json登记。当前证据授固定生产者开发范围，完整模块与生产继续in-progress。
