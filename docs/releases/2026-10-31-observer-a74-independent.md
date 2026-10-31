# 观衡a74独立交付

类型：独立候选交付记录。版本：`0.1.0a74+scalar.1`。状态：安装包已交付并在本机独立离线安装；现有服务未切换，未启用新的生产入口。交付与WT交易开发、整体候选收口分别进行。

## 交付物

稳定交付目录为 `E:/workspace/wondertrader-deliveries/observer/0.1.0a74+scalar.1`。目录包含独立ZIP、SHA256SUMS、已核验解压内容、安装及启动脚本、中文开始说明、已完成的App-only安装及DELIVERY.json。

ZIP为 `observer-0.1.0a74+scalar.1-windows-x64.zip`，56055722字节；SHA256为 `c136090e919b4636775edc69cc225da782218058edbe9ed6f5ff363e4aaea21a`。包清单摘要为 `bb59203b3cdf3aa5c4a8bdde49973b4cf6407cde73d31ff6f7c96746f231a5b3`。

包仅声明app角色及其30份锁定依赖、SPA和安装工具，没有WT/Host角色或交易执行程序。共享的只读协议及报告数据类型作为应用依赖随包安装，不承担WT进程管理。包内保留development标识，当前版本按已验独立候选交付。

## 验证

原独立包的源码构建、安装、实际读取和正常关闭沿 `build/observer-scalar-read-001/FINAL-INTERFACE-001.json`。同字节App/SPA的账户刷新、共振策略展示、原生2000根分钟线、市场观察T2108导航及桌面/手机浏览器结果沿 `E:/workspace/wondertrader-qa/root-final-ui-001/run003`，无JS或控制台报错。账户页面该轮使用封存SDK库存；真实只读账户及行情协议的既有证据保持原范围，不当作本次新查询。

本次从固定ZIP复制至稳定目录，逐字节校验并调用包内公开verify；随后用公开install执行App-only离线安装，30依赖及pip check通过，安装收据为该目录 `installed/OBSERVER-INSTALLATION.json`，摘要为 `c4800f49c058a7b0a2fa631cccc29d4bd71c063e46a0022fd1b63ae03d07f812`。过程不启动WT、Host或交易，不改现有18126服务。

## 使用与数据边界

本机执行交付目录的 `启动观衡.ps1`，默认地址为 `http://127.0.0.1:18120/market`。启动入口只运行独立观衡；其终端按Ctrl+C正常停止。安装到其他目录或机器的方法见交付目录 `开始使用.md` 及[独立安装手册](../runbooks/observer-runtime.md)。

数据来源使用外部WT公开状态、只读行情连接、观察快照和已完成报告归档。ZIP及默认配置不包含账户资料、凭据、SDK演示快照或交易配置。未提供相应数据时，页面显示未连接、缺失或最后来源时间，不用测试数据代替实际账户。WT当前提供的数据范围与WT自身开发状态分别说明。

## 后续

观衡后继版本继续按自身验收独立发布。WT交易恢复、未知委托及活动订单验收由WT模块继续完成；它们不阻塞本版观衡交付。当前没有生产切换或真实下单、撤单。
