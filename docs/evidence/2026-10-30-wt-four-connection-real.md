# 统一四连接正文的真实只读联调

类型：运行证据。状态：部分读取通过；真实四查询主链失败，根因继续定位。范围：candidate004 普通安装的 WT、三个原 Host、正式四连接正文、包内精度修正版 Scan 与原行情 Receiver。本次未改产品或 WT 框架源码。

## 输入与原生复用

- 安装与既有 SDK 整链沿[统一候选](2026-10-30-wt-communication-candidate.md)及[单正文四连接](2026-10-30-qmt-account-composed-source.md)，本次继续使用原协议、账户 mapper、Adapter、Scan 和 Receiver。
- 准备目录为 `build/wt-real-four-connection-preparation-001`。冻结清单 `FROZEN-HANDOFF-001.json` SHA256 为 `5f33a4bab86dd038fd1548a64042ccd5c329876ad8341ebbb9885e77da98ef0e`，根运行前核对47项全部匹配。真实 READY 摘要为 `2424cf82336e5719ff14f5c0d42a977c3bad20dbbe6657a6b76445b81caf3ecb`。
- 正式正文为私有 `real/private/combined-pair/strategy.py`，1733848字节，SHA256 `2001b9ec2385d611e521eb719d40477c2135552498a4b70c8745d1c3ad255b33`。原真实只读账户、环境和原报价范围保持，配对与内存名为新材料，旧 Journal 保留。
- 原交易配置即使关闭写入仍要求完整 binding。根核对[上交所ETF交易单位说明](https://www.sse.com.cn/assortment/fund/etf/question/c/c_20240118_5734754.shtml)及[现行交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml)，将正常整手规则的来源写入 `RULE-SOURCE-001.json`，仅供关闭写入时的完整初始化。账户读取沿全账户范围；零股及完整交易规则资格单列，未修改原 validator。
- 入口为候选已安装 WT 的 `pythonw.exe -I -B .../run_control.py --mode real`，总预算600秒，创建期 Job/2GiB及原 ThreadOwner。Host、Agent 均关闭写入，协调器交易命令为0。

## 准备和同候选 SDK 主链

独立准备未启动真实 Host、未创建通信 Journal、未部署 QMT 正文。准备、交易输入及最终生成控制器分别以3.270、0.489、2.286秒正常结束，所有资源完整关闭。

`control-sdk001/run/result.json`：15.567秒、exit0，原生账户2P/1O/1D/1A、HPR快照读取、QST Receiver和交易状态读取通过；`sdk/AUDIT.json`核65项事实/30个ABI槽及浮点原位一致。711项输入前后一致，全部子进程/EOF/线程/句柄正常关闭。该结果仅授 SDK 输入范围。

## 真实执行及失败边界

根核对 QMT 仅有原主窗，临时 `SHM_READ_PROBE` 最后停止记录为05:38:04，原文4926字节、SHA256 `35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae`。逐字备份后放入上述完整正文。正式 WT 60320先启动等待，QMT在06:22:52启动临时探针，三个原 Host认证连接及QST连接建立；QST一次实际观察已有8次心跳、28个批次。保留策略 `GH_WT_MEMORY_VERIFY` 及原数据WT均保持。

原 Scan 57932运行19.749秒、exit3，收到原 `source` 失败completion，`closed/joined=true`、`worker_live=false`：

| 原查询顺序 | 实际结果 | 本地完成时间 |
| --- | --- | --- |
| position | 4条持仓，完整交付 | 06:23:00 |
| order | 已知空委托，完整交付 | 06:23:05 |
| deal | 已知空成交，完整交付 | 06:23:11 |
| account | terminal / operation_interrupted，未交付资金 | 06:23:17 |

校验失败位置为原QA `main.py:168` 对原生成功退出及completion的断言。根在06:23:42才停止探针；资金中断发生于停源前25秒，触发原因保持unknown。完整资金读取失败，本次后继HPR快照业务读取未执行，未授真实四组主链成功。QST接通也不代替本次未运行的Writer、历史Reader、策略或页面组合资格。

`real/FAILURE-BOUNDARY-001.json`保存同次终态与时间。根用 `mode=ro&immutable=1`读取已关闭 Journal，`real/PARTIAL-AUDIT-001.json`证明前三组请求/结果摘要/绑定/执行区间与原生帧一致，56项事实、36个ABI槽及16次浮点位比较通过；第四资金保持失败。Journal SHA256 `d62fae893c10e8c5fb750181ce20674ca6fca9e093976d37c7dc4455ce6d332d`在审计前后保持，新增业务查询为0。

## 收尾与当前边界

根确认06:23:42停止成功后逐字恢复原文，并以 `real/PROBE-STOPPED.json`通知协调器。Receiver49232和WT60320均exit0；711项输入前后相同，内层所有树/EOF/join/句柄完整关闭。外层 `control-real/RESULT.json`为95.797秒、业务exit1、forced=false，外层树/EOF/join/句柄也完整关闭；业务失败和正常回收分别保留。

根另核13548/60320/57932/49232均已退出，原数据WT33636、Host46288、历史60964及采集75000均存活。真实下单、撤单、生产切换、旧QMT项目和WT框架改动均为0。

下一步沿本次账户资金中断的原Host/源调度边界定位首故障，不覆盖本次原件、不重开旧Journal、不据后继成功宣称已修复。WT四组发布与观衡只读消费沿[账户发布接线](../migration/native-account-publication-proposal.md)并行；整体目标继续in-progress。
