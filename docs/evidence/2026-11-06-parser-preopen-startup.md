# Retained行情开盘前启动与持续轮询修复

类型：根因修复与隔离C++重放。状态：源码、完整SDK替身主链及正式工厂DLL构建通过；实际安装与真实运行恢复 pending-verification。

## 根因与正确实现

原 retained v6 的完整快照映射把当日尚未形成OHLC的真实开盘前报价交给通用OHLC强校验；InvalidInput经HostEndpoint→MarketParser.pump触发disconnect，外层worker终止。冻结09:19八ETF原结果全部open=0、volume/amount=0、high=low=昨收、lastPrice为正竞价参考值，原严格映射可确定重现此失败。09:00失败代的首个真实错误没有保存原原因，因此本重放证明该触发链存在，09:00实际首错仍为unknown。

另一处根因在准备阶段：read-binding已对固定来源未就绪进行同截止GET等待，预算耗尽可返回专属reconnect_deadline，也可由末次GET返回普通http_deadline。旧worker把两者都作为单次永久失败。新逻辑仅在首次prepare未发布来源绑定、未发SDK请求时，按规格固定超时/运输原因沿原轮询等待；真实身份、坏结构和未知效果保持终止。

开盘前特定完整原值在映射层跳过投递；原始字段、原请求、完整结果、消费确认、线程owner和每次请求截止保持。后继同worker收到已形成OHLC时，按原映射和WT SPI投递。日志对快照非法、绑定/能力非法、换代、冲突和下游未知输出固定安全类别。

## 固定输入与实际证据

冻结输入位于受控QA根 `preopen-quote-flow-20261106-001`：current-slot.json SHA256 `138bf32fb972d685828fad82e1687de8d32520f61c751c2c51ab28561de76618`；native-source-slot.json SHA256 `242381ecfdc59ff5d1cf5479b8e45789a586d7a5c98beb46bea603caf37f4c53`。仓库不保存完整私有原件。

实际入口为 [重放driver](../../tests/integration/qmt_parser_startup/run.py)，参数为独立新work、冻结fixtures目录及已有native deps目录。driver冻结自有源码及原WT头文件，MSVC C++17隔离编译原映射、HostEndpoint、MarketParser和PollingParser；仅QmtHostReadClient为无网络SDK替身。随后以原工厂和完整Common闭包单独链接正式DLL，替身对象不进入DLL。未启动服务、终端、正式安装或账户动作。

最终运行根为 `E:/workspace/wondertrader-qa/parser-startup-replay-20261106-008`，RESULT.json含全源码SHA及构建命令。实际结果：原严格映射拒绝09:19原值；新持续映射产生0条WT tick；同worker后继真实有效原值产生8条；准备五种固定错误后第6次成功；reads=2、原ACK=2、resume=0；主动stop后唯一Close=1。三类非法输入、五类硬准备失败、等待期间100ms预算stop和固定快照错误日志均通过。

正式工厂DLL独立链接通过，SHA256 `d325cc74b8b4b62dfbd797679d78b44e754cf1cac5b66186a1b27677c13b6225`。此DLL属于隔离构建证据，正式交付仍通过原reader_product构建/安装入口及config/native-data-sources.json精确文件清单生成。

## 自查、审查与边界

独立delta审查先发现末次GET普通截止遗漏，修复后复核通过；复核QmtPollingParser.cpp SHA256 `fb8d5b8989710a9944454e08cdd1ef44907616d06a1ee9b058267e5ed9f69a83`。最终测试补齐五类准备回放、等待stop和固定日志断言。project.py check通过；CRLF原字节文件沿既有格式保留，diff检查以cr-at-eol规则执行。

实际BoundCore/WinHTTP的网络故障窗口未通过本次无服务替身注入；其现有分类按源码核实。正式QMT/Host/金融运行、安装切换和发布后真实调用链由唯一现场owner继续核验。执行器和WT框架源码保持原样。当前状态属于已开发、主链隔离重放及构建通过，真实运行恢复资格待集成。
