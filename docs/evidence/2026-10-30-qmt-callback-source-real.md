# QMT正式回调驱动的真实只读主链

类型：实际终端开发证据。日期：2026-10-30。状态：本次真实只读与原值审计通过，独立full冷核通过并由根限定接收；完整恢复、交易及全系统继续验收。

## 固定候选及范围

普通离线 `build/wt-read-mainpath-repair-001/installation005`：Agent 0.1.0a4、Host 0.1.0a5、WT 0.1.0a4。installation SHA256 `58b5f0a84cc0d261b7563ff3cc95cfb4097d6a1100e47ddb84c62a3b295536cb`。

`FIELD-READY-001.json` SHA256 `7cdced24e97ad0d04aefe4454c464fb6cc16dc138d961b8021d01532ea30f0c3` 的62项材料及2份原生程序身份由根重核。正式四连接正文 SHA256 `585078261e8cc928cdd300ac181d156d7f3edc832f9dbaed636a2b345033a973`，显式 `qmt.source-runtime.v1 / strategy_tick`，同一个原timer配置为 `100nMilliSecond`，没有诊断观察或注入尾段。源端和Host的交易写入均关闭。

原生程序沿已固定的 `GuanhengAccountScan.exe` 和 `TraderQMTReadOnly.dll`，分别 SHA256 `5dae69603377ef7d88dde3e2d82dbc4e111c5b3002b10a456c07c528a700ad44`、`27e92a99437771432e5d0af97731dc80b94b445a5a47e1fc70bf9a696a095c42`。原请求、金融映射、认证和截止保持。

## 实际调用链

根是本轮QMT操作的唯一所有者。普通WT CLI拥有三个Host；QST只读消费者及原生Scan由有界现场协调器管理。观衡没有参与这些进程的启动或停止。

WT在来源启动前持续等待 **77.684秒**。08:09:40，仅启动临时放入正式正文的 `SHM_READ_PROBE`，三条业务连接认证及QST接收成功。原生Scan顺序返回 **4持仓、0委托、0成交、1资金**；随后完成一次HPR `market.full_tick`。本轮没有历史补充、交易命令POST、下单或撤单。

QST接收35个包、6929条快照和34个心跳，无溢出；来源报告53项没有快照。本轮发生在开盘前，结果证明这份配置的全推通信可用，证券全覆盖、盘中时效及原生分钟写入各自保留验收范围；现场只读消费者没有写历史文件。

## 原值、停止与资源证据

- 原只读Journal以 `mode=ro&immutable=1` 核对4个请求的身份、终态、结果摘要、来源binding和执行时间；**67项原事实、39个ABI槽**与原生帧一致，浮点位逐位一致，未重新计算持仓或资金。
- **724项**运行输入前后及根复查时一致。
- 08:10:17停止本次Probe，QMT Formula日志记录停止成功。原探针逐字恢复，SHA256 `35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae`。
- 外层39864运行167.062秒、exit0；WT、QST、Scan和三个Host正常关闭，Job树清空、双管道EOF、reader join及资源释放成立。根OS核查9个本次测试PID均不存在，原数据WT33636/Host46288/历史60964/采集75000仍存活。

原始终态及审计在 `build/wt-read-mainpath-repair-001/final/real/{RESULT,AUDIT,INPUTS-BEFORE,INPUTS-AFTER,PROBE-STOPPED}.json`，外层收据在 `final/control-real/RESULT.json`。根现场材料包 `final/real/root-operations/ROOT-ACTUAL-PACKET-001.json` SHA256 `bbf2391348cfbe1c34e79a76cb2bd1df670348e10208890ec2f29641831a9fb1`；原始终端日志和账户原帧保留在私有运行目录，公开记录只列去敏计数和摘要。

独立full实际证据报告为同根 `review001/REVIEW.json`，SHA256 `744cb24c9ac3b258dc5980b2fd499d568695e7a34840f09c45fd3384575db4f0`，限定范围内P0–P3均0；根重核报告列出的证据摘要并写 `ROOT-ACCEPTANCE-001.json`。审查独立解码13913字节原生两帧、重算三份只读不可变Journal及结果seal，额外逐位比较24个原始浮点事实和31个数值ABI槽。四个旧采集PID属于末次存活观察，不能单凭PID证明整个期间采集业务连续；本次未另授这一范围。

## 解释与后继

原真实失败已证实Host接收期限先到、SDK未进入。此次正式回调驱动在原期限下完成真实主链，并证明Host等待超过60秒后仍可接入。现有证据保持对QMT内部GIL及公平性具体机制的unknown判断。

同安装005的完整SDK组合另有撤单后 `retirement_unconfirmed`，恢复回归还发现已关闭运输的退休分类没有进入重连分支；两项都由通信owner在自有适配层处理，后继安装单独绑定，不修改本次冻结材料。此前installation003/full001的成功结果保留其原身份。

后继006的完整SDK、未知原ID不重发与ZIP搬迁主链已完成，独审收口。根核对005/006的168份冻结源码，仅 `_TickResident._advance`、Agent/Host版本及Agent依赖pin发生变化；该方法外Python AST一致。比较收据 `build/wt-read-mainpath-repair-001/ROOT-005-006-DELTA-001.json` 不转授006真实来源资格，下一组合使用最终006接NAP六组件及独立观衡。

本记录的资格限于一次真实只读、正式完整来源、原生账户与行情主链。独立观衡最终制品、同候选实际账户页面、唯一保留策略的恢复及正常退出，以及完整交易适配仍在推进；真实下撤单、生产切换和本轮新增WT核心修改均为0，完整目标active。
