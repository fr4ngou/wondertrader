# 日线入口导入遮蔽完整SDK

类型：实际部署故障记录。日期：2026-11-04。状态：失败代已退出，原unified.7服务恢复；责任层修正及后继实际采用继续。

## 触发与影响

unified.8首次切换后，历史服务曾发布ready，随后日线线程发生ModuleNotFoundError，父WT记录component_runtime_history。当日11月4日任务尚未创建，正式行情CURRENT保留11月3日成功版本。金融WT、独立观衡及QMT原通信策略保持，未由本故障重发v8/HPR请求或交易命令。

## 根因

SMP入口按包导入quote_collection_service中的公共读取helper。该模块原来无条件将安装目录下的integrations插入sys.path首位，使guanheng_market_client名称解析到角色内嵌的精简子集，遮蔽已安装的完整SDK。共享日历随后导入guanheng_market_client.exchange_calendar失败。

直接导入日历和调用闭合日计算成功；在全新安装解释器中先以diagnosis_only加载实际SMP脚本，再导入相同日历，稳定复现缺失模块。该对照没有创建服务或调用Source。既有回归预先导入SDK，未覆盖真实入口的首次模块加载顺序，不能替代现场调用链验真。

## 处理与当前状态

正常恢复原unified.7，原逻辑实例a21eb660保持，新控制代f331975e的WT PID76108、历史PID66152；定位仍以实际CURRENT及进程身份为准。失败unified.8控制代746694f0的daily/SMP失败回执及旧文件全部保留，子进程已退出。

后继修正由开发者2在自有quote_collection_service入口负责：独立脚本需要的bootstrap与按包导入的行为明确分开，helper导入保留调用者路径。新增实际SMP首次导入顺序和独立CLI验证；正式采用后继续检验实际11月4日数据更新及原历史/请求保持。分钟包的同名OWNED成员应接收后继修正，防止覆盖回失效实现。本记录不声明修正版已上线。

## 证据与边界

`E:/workspace/wondertrader-data/unified-daily-20261104-001/runtime-natural-day-20261104-013`保存失败WT和history/daily回执。Root的无Source复现存于`E:/workspace/wondertrader-qa/daily-mainline-20261103-001/integration-progress002/INSTALLED-ENTRY-SHADOWING.json`，记录实际安装入口、缺失模块及堆栈位置；`BUSINESS-SNAPSHOT.json`保存金融WT、当前策略及原49命令状态。

修正范围为自有Python入口和制品身份，新增WT框架修改为零。真实当前日覆盖与后继运行资格按后继采用结果补充记录。
