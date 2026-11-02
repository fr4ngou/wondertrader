# 观衡a92与独立盘后更新

类型：实际开发环境发布。源码提交`24594a2`，观衡版本`0.1.0a92+postclose.1`，用户入口仍为 http://127.0.0.1:18143/ 。总览入口`/dashboard`仅显示账户资金、记录数量、更新时间及跳转；具体策略保持在策略页。桌面和390px页面已核，无横向溢出及浏览器异常。

## 数据更新职责与实际结果

观衡Web只读取已发布结果。独立更新进程沿原27来源、预算、市场数据根与发布事务工作；计划为北京时间09:00、17:30、21:00。原09窗口记录保留，新进程已实际完成当日17:30和21:00两次窗口，各尝试一次，最后发布快照`9c4a22a450176f4bc07f6edc0759d8bcee212cfce76e10c6b98f51a5f6b17edb`。当前进程回到waiting，心跳正常。该结果由实际常驻服务取得，未复制隔离候选的窗口完成状态。

72组目录中43组最新行到2026-11-02。沪深广度、换手率大于5%占比、独立日频PB和六组高管增减持已更新。高管数据按已披露变动回溯统计，披露可能迟于实际交易日，后续披露也可能改写历史；页面标识“已披露资料，非盘中实时”。年度、季度和月度数据保留实际报告期。

仍有缺口：T2108和部分全A广度停在10月30日，QMT分析窗口输入与外部来源超时继续处理；原月末/最新全A PB停在10月16日，独立日频PB属于另一口径，保持分开。部分官方来源权限拒绝或超时只影响相应数据，保留其原有效版本和真实日期。

更新性能修正复用已验证且不可变的原对象，仍校验变化分区和完整发布CAS。首次导入、恢复和显式完整验证沿原全量路径。本次未改WT框架、分钟算法、持仓、委托或交易权限。

## 制品与维护定位

- ZIP SHA256：`f4549688baabebf5f038e00262b7efd3ae778ee7b02ba1764248e751efc32e2c`。
- 制品清单SHA256：`16c404700e59e5b731aa66def80e77c1f165e0d5431623f607143827349b963e`；安装收据SHA256：`86c4c31c249fbff21173e458c267d8826f18bf2788c1d380958cf4874fbea643`。
- Web稳定定位：`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；本次profile为`observer-controlled-web-20261102-a92-postclose-001/web-profile.json`。Web PID57704仅作本次记录，日常同时核控制身份与创建时间。
- 更新维护目录：`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a92-postclose-20261102-001`。其中PREPARED固定原数据根、27来源、配置摘要、解释器与私有行情环境；`update_owner_control.py status|stop|start`沿原监督协议管理本角色。
- 更新控制`5eecdb69-00af-45c8-a053-2f6e0521a5ed`，监督PID48948、子PID46284；部署SHA256`895da58675f956e6e3523a3cb3451968377d447bd6db96070ef5a2516e8d0a45`，来源SHA256`dc79564526c226179e08ccdb10215a1b50c72d8843afc3fa80b6652751239fcc`。

旧a85更新角色正常关闭，监督和子进程已退出，exit0及原截止/关闭收据齐全。a91 Web正常关闭exit0，新a92读取同一历史18148、原自选文件及原WT绑定；个人观察原件未变。安装构建、TypeScript/Vite、依赖检查及干净主干文档检查通过。

实际证据位于`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：A92-DEPLOYED、A92-PAGE-VERIFIED、A92-ACTUAL-READ、A92-ACTUAL-WINDOWS，以及两代更新维护收据。后续根数据继续更新时，以当前实际API和窗口记录为准。

## 当前交易阻断与后继

本次读取侧仍绑定resume11真实故障状态：策略现金余额633,075.20元保留，当前可用金额为空。后继resume12e也已实际故障，尚未替换为观衡当前绑定；自有交易读连接暂不可用的等待/原请求接续仍在开发。

旧行情HPR的1024条已完成请求未回收，导致报价停更。后继采用已有retained认证、Native持有快照后确认消费、票据结束后回收机制；原Journal保留。Root已请求旧数据owner正常关闭，三业务组件均closed且forced=false、物理退出；旧外层维护脚本收尾因Windows等待参数OverflowError保留原失败记录。新自有owner修正等待切片并取得实际隐藏关闭证据，WT框架保持原状。新GH数据Source由开发者2操作，RR行情与原采集后继尚待启动和真实报价验收。本页不以组件ready替代交易持续运行结果。

## 回退

Web沿[观衡运行手册](../runbooks/observer-runtime.md)正常关闭后才能恢复旧profile。当前市场根已包含新增计划窗口状态，完整更新/读取组合优先采用a92及后继；旧a91回退资格需先核其对当前状态的读取兼容，保留原数据，避免直接回退旧更新器。观衡升级与WT/QMT生命周期分别维护。
