# QMT只读HTTP传输

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：模块说明。范围：`GuanhengCommon/QmtReadTransport`及行情兼容包装器。状态：自有源码实现；编译、隔离验证、独立审查与运行资格分别登记。

## 职责与接口

[QmtReadTransport](../../src/GuanhengCommon/QmtReadTransport.h)统一拥有签名、WinHTTP交换、总截止、来源会话核查、单次提交/原ID认领和回调排空。调用者显式选择固定Market或Account域；远端capability只缩小本地准入集合。Common不依赖行情Store、Reader或交易执行器。

Market只接受既有`market.full_tick/market.market_data_ex`及精确参数；QmtHttpClient（外部历史/待归仓路径：`../../src/GuanhengData/QmtHttpClient.h`）保持原行情调用面并委托Market域。Account只接受`account.trade_detail`、stock、四种datatype和显式account范围，准备时核`qmt.account-query.v1`能力。账户选择仍属于源端绑定。金融字段解释、逐批observation完整性、WT回调与交易就绪由领域消费者负责。

## 返回值与时间

`JsonResult`保留status/data_json，附原envelope_json、request_id、operation_id、http_status、terminal和remote_ok。原body受容量限制，可含私有数据，由调用者控制展示与日志。正确关联且终态结构合法的200响应可标terminal；remote_ok仅记录该终态的原ok。成功data还需末次health与截止验证，字段/金融资格继续由消费者核准。

一次read使用同一steady_clock截止。只POST一次；202和网络交付未知时只GET原request_id。已知Content-Length但正文中断属于交付未知；完整非法JSON或明确HTTP拒绝保持失败。取得请求ID后，超时等失败仍保留它，调用者可以准确报告未知结果；本接口尚未提供跨进程ticket恢复。末次health用于筛选来源会话变化，`last_tick_at`只表示源Host回调存活，不能代替券商时刻、交易日或分钟闭合。

## 线程、取消与释放

创建线程独占prepare/read/session/capability/drain。WinHTTP回调按实际同步交接结果，request关闭后仍可能有在途回调；[WinHttpSessionDrain](../../src/GuanhengCommon/WinHttpSessionDrain.h)保持有限session及其关闭事件。read返回不等于可卸载代码，调用者须显式drain成功后再释放客户端/DLL。排空超时保留依赖并由原owner继续处理；析构最后等待不授有界关闭资格。

该边界遵循[Microsoft的CloseHandle契约](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpclosehandle)：关闭返回后仍可能收到通知，关联上下文须存活到HANDLE_CLOSING。原回调已通过互斥区复制/移动结果并持有共享Exchange所有权，session卸载事件另负责全部回调退出后的代码生存期。生产回调应迅速返回；[Microsoft的并发规则](https://learn.microsoft.com/en-us/windows/win32/winhttp/concurrency-in-winhttp)规定请求操作及关闭的同步条件，[安全说明](https://learn.microsoft.com/en-us/windows/win32/winhttp/winhttp-security-considerations)指出阻塞回调会影响同进程其他请求的调度。测试阻塞门控只验证相应窗口，不代表生产回调允许执行阻塞业务。

专用关闭门控只编入测试DLL。生产不含相应导出，也不通过运行环境开关启用它。原ParserQMT通过PollingParser→QmtHttpEndpoint→Market客户端调用本传输；ReaderGuanheng通过StrategyReader→ReaderHttpClient使用独立传输，只共享未修改的排空辅助类。

## 验证入口

最终要求见[QRT规格](../specs/qmt-shared-read-transport.md)。共用域回归（外部历史/待归仓路径：`../../tests/integration/http/test_qmt_read_transport.py`）、原行情协议回归（外部历史/待归仓路径：`../../tests/integration/http/test_qmt_http.py`）与实际回调关闭回归（外部历史/待归仓路径：`../../tests/integration/http/test_qmt_http_drain.py`）覆盖准入、签名、请求关联、原body、错误、截止及排空。测试使用合成回环服务，实际QMT安装和原生账户插件接线分别取得证据。
