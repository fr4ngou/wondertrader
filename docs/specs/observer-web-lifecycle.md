# 独立观衡 Web 生命周期

类型：功能规格。状态：accepted。适用范围：独立观衡 Web 的本机进程维护；已有直接启动实例沿原 Owner 退出。

WEB-R1：一个本机维护入口提供 start/status/stop/restart。Web 隐藏独立运行，仅持有自己的 Uvicorn、App lifespan 和读取线程；不启动或停止 WT、更新角色、Host、QMT。

WEB-R2：配置绑定明确的 App 版本、pythonw 文件摘要、SPA、监听地址和独占控制目录。读取配置从外部环境 JSON 加载；清除调用者继承的 GUANHENG 环境后只采用该文件。个人观察、市场快照和读取连接继续由原 App 配置维护。

WEB-R3：start 在同一有限截止内等待自己的 ready；PID、OS 创建身份、配置摘要和随机控制 ID 共同定位一个 Web 运行代。重复启动返回该代，配置切换须先停旧代。

WEB-R4：stop 只向匹配运行代提交本机停止文件，不提供 HTTP 写入口。Uvicorn 正常停止后执行原 lifespan，核 shutdown_complete、reader/backtest_reader 线程均为零；维护命令持有原 OS 进程句柄，确认 exit0 后才报告 closed。端口关闭或进程消失单独不足以授成功。

WEB-R5：超时、异常退出、PID 创建身份不符、关闭证明不完整时保留现场并报 failed/unknown；不强杀、不终止任意 PID、不自动重复未知启动。停止后重启产生新代，外部配置和个人目录保持。

WEB-R6：控制操作加本机排他锁；文件原子提交。启动借 Windows 自带 PowerShell/CIM 创建唯一 pythonw，调用命令退出后 Web 继续运行，无新增守护进程和第三方依赖。

WEB-R7：用新端口/独占目录及替身只读行情跑启动→实际读取→停止→重启→读取→停止，确认两个 exit0、两次 lifespan 完成/读取线程0、个人数据不变。原18141/18142仅核OS身份，不访问业务或停止。

WEB-R8：主链后验证重复 start/stop、身份篡改拒绝及启动失败保留；不重复全量构建或浏览器资格。Root 按源码 CAS 接收，候选不直接修改共享源码或全局文档。
