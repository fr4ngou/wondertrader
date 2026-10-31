# QMT 全推共享内存与原生 DataKit 接线

类型：开发验证证据。日期：2026-10-28。状态：合成主链 passed；真实全市场完整采集 pending-verification。

## 原生职责与实现

原 DataKit ParserAdapter/DataManager/StateMonitor/WtDataStorage 负责原生分钟聚合、文件及收盘。自有 QuoteStreamAgent 通过内置 ContextInfo.subscribe_whole_quote 接收全推，只在内存缓存纯值；独立 QuoteStreamReceiver 复用 LocalTransport/Session 的 Windows 共享内存认证运输，随后调用自有 GuanhengDataKitSession 薄 C++ ABI。原公开组件装配并正常 stop/release，不修改原框架。本链不用 HTTP、命令 Journal、数据库或 wtpy；原轮询插件保留原契约。

原 WtDtPorter 虽提供外部 parser C 接口，其导出缺少整体 close，本切片采用原公开 C++ 组件组合。自有归档完成查询读取 Writer 在队列末尾写出的 marker；isSessionProceeded 的初始化缓存不作为本轮新任务完成依据。文件字段仍独立回读。

## 真实终端能力

同一 GH_WT_MEMORY_VERIFY 条目的纯内置探针实际调用 get_full_tick(6982) 返回 6938 有效报价，subscribe_whole_quote 接收两次回调/51156 行，stop 退订返回。输出 build/qmt-native-quote-capability-001/RESULT-LINES.txt；44 只缺报价未伪造。终端外 xtquant 失败不代表内置全推不可用。探针停止后恢复原正文 SHA e40f946960b04d967de20b593314ad07ce35c8937aa0842066c868958a6816af。

## 合成运输与原生落盘

SDK 替身、真实 Windows 共享内存、同一新合同及原生 DLL：401 只证券、1604 行通过 Writer；生成 401 份 DSB，抽选两根分钟的日期、时间、OHLC、量额逐项通过；Source/Receiver/Native 关闭均返回。build/qmt-quote-datakit-main-002/VERIFIED.json；控制器 qmt-quote-datakit-native-main-002 实际 exit0，约5.22秒。原生输入固定上游 08b230dd05facf6d650d949bfe51054115a2ecb1，无框架覆盖。

## 真实接入的限定结果

真实正文 SHA b91ada8d10f8c60a9ea0ed1f75c1dd7ca585d7505445569374ff28395cb5c7f2。build/qmt-quote-stream-real-002 实际启动同一只读条目，Receiver 取得15批/3000行，原生 delivered/writer_processed 均3000。本轮没有完整快照/心跳资格，在原210秒采集观察截止结束；控制器实际211.015秒、子进程exit1、整树归零/EOF/join/资源关闭均确认，无强制终止。FAILURE.json 记录 connection_ended，尚未确认其触发原因；本轮点击停止策略与中断的因果关系仍需核时间链，不能据此宣布传输自身故障。

当前仅发现 native/storage/cache.dmb，未取得该真实根的分钟 DSB，不能将 Writer 计数当作分钟落盘。场外旧快照、量额原始单位均明示，未授完整分钟、标准单位、盘中连续或自动收盘资格。真实策略已请求停止，最终停止确认及正文恢复另见后继记录；不能以停止请求等同资源退出。首个 real-001 在部署前观察超时，记录保留，未延长其截止。

## 历史与剩余

005 已终结：5337成功证券/1388404040根，2空、3原始负量额指数隔离、remaining0；状态 completed_with_failures，控制器实际完成且整树/EOF/join/关闭确认。已有行情正常转换，未删改源 DAT。1877成员整批尾部刷新继续，另28批446成员待刷新；最终统一目录须完整旧批替换，不能依靠配置顺序覆盖重叠证券。

下一步确认源/接收中断时间链、真实全推完整快照及分钟文件，完成受管常驻及原生 session 收盘装配；历史继续尾部及最终目录。误建定时任务已删除，不能用对话唤醒代替原生采集。真实下单/撤单0、未切生产、无新增框架修改或用户必需决策。

## 终端停止观察后继

原生日志于01:34:36.543记录本次request 000300427 stop success，随后unsubscribeQuote提示formula instance not found；界面仍显示停止中。当前仅确认终端接收停止，不授Source I/O线程退出资格，未覆盖/恢复正在停止中的正文，未重启QMT。真实外部接收进程已按原截止退出；后续先核停止与回调职责，再继续部署。

文档门禁：qmt-quote-stream-doc-check-001 实际exit0，3.527秒，local document navigation and skill manifest integrity通过；不代表应用运行或发布验收。
