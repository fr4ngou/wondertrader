# QMT真实只读通信中断的同代核证

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：验证证据。日期：2026-10-30。状态：最早中断点已确认；通信未能及时完成的更深原因及修复资格继续。

## 入口及现场

同candidate004固定普通安装，沿[逐代诊断准备](2026-10-30-read-transport-interruption.md)的final2执行一次真实只读联调。根重核FINAL-READY-002的67项；该准备材料独立full及delta无确认P0–P3。原文、QA尾段、配对摘要及版本均固定，产品/WT核心/原预算保持。

临时SHM_READ_PROBE于07:25:53启动、07:26:39停止；实际诊断正文SHA9c040643b445c225afb4d2ac4cfd1adc82acf5422f877e7757a76e6d1410a23b。原文35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae已逐字恢复。其他策略保持。

## 严格同一请求及代际

独立因果核证（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final2/real/root-operations/CAUSAL-REVIEW-001.md`）将唯一position请求的request摘要9d6e685a…、受理/派发binding99592ff5…、transport generation6eb5b07e…与Host run1和来源run1完全配对。根重核（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final2/real/root-operations/ROOT-CAUSAL-ACCEPTANCE-001.json`）的16份证据身份一致。

| 北京时间 | 已确认事件 |
| --- | --- |
| 07:25:58.186145 | 原Journal受理请求 |
| 07:25:59.014230 | 原Journal记录派发及绑定 |
| 07:26:00.007222 | Host首次观察到原active请求 |
| 07:26:02.008519 | Host在原builtin_shm.receive → _wait的2秒接收等待中先发生TimeoutError；当时本端stop、对端close均false |
| 07:26:02.012528 | 原Journal终结operation_interrupted，无原生结果绑定 |
| 07:26:03.001173 | 来源同代读取到peer_close=true，产生OSError |
| 07:26:03.007179 | 来源原reconnecting owner随后退休旧代并请求close |
| 07:26:18.186145 | 该请求原20秒业务截止；Host首异常时尚余16.1776秒 |
| 07:26:39.668957 | 操作员停止探针 |

来源原日志提取18条从序号1连续开始的冻结事件，operator_stop存在、capture_failed=false。native_execute、SDK调用与Context guard异常均0。首次source主动close来自故障后的退休流程，人工停止前的业务中断已与后续空请求代际及人工停止异常分开。

## 可证明范围及未知

此次券商SDK尚未调用，失败发生在其前面的共享内存通信周期。具体未完成的包/控制阶段，以及QMT调度、GIL、等待或锁的关系仍unknown；全局首OSError、每秒回调及单次超时分别不足以归因。

[官方内置使用须知](https://dict.thinktrader.net/innerApi/user_attention.html#关于线程和进程)于本日复核：其内置模式给出Python线程/进程限制，并要求回调及时返回。该运行模型与普通pythonw SDK替身分别看待；源运输修复正在使用可控稀疏调度repro核对原后台I/O假设，显式回调驱动的新模式先收敛契约再实现。旧thread配置、原wire/MAC/seq/ACK/Journal、业务截止及未知不重发保持；新模式资格按后续实际证据登记。常规使用边界已补入[内置Python手册](../runbooks/guosen-qmt-python.md)。

## 回收及剩余

实际结果（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final2/real/RESULT.json`）：原生3915ms、exit3/source；WT/QST均exit0。外层（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final2/control-real/RESULT.json`）104.125秒业务exit1、无强制、树0/EOF/线程join/句柄释放完整。717输入前后及核证时当前摘要保持，原Journal只读immutable审计前后SHA b20df25e…一致。

物理核对（外部历史/待归仓路径：`../../build/wt-read-transport-rootcause-001/final2/real/root-operations/PHYSICAL-PIDS-001.json`）确认现场数据WT33636、Host46288、history60964、collection75000仍存活；本次所核诊断PID均已退出/不可再打开，内层Job树正常回收。真实下单、撤单和历史下载0。

完整目标active。下一项为通信责任层确定性repro和修复、普通发行验证及根单一现场复验；六组件SDK联合/账户恢复已另行独审通过，独立观衡账户页及唯一策略执行仍按各自范围继续。无需用户处理本次来源启停或恢复。
