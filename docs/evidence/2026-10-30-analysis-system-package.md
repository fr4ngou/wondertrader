# 持续分析、执行与独立观衡的统一候选

类型：验证记录。状态：新候选已装配、ZIP 搬迁、新根离线安装及隔离导入；完整九组件验收进行中。当前候选为开发制品，现场保持原版本。

## 组成与职责

根目录 `build/root-analysis-system-001` 复用原 SRI/ATI，组合真实普通安装的三个独立角色：观衡 a54、Host a12，以及 WT a11 / Agent a9 / 分析发布者 a4 / Native 分析 core a1。各角色保留自己的 wheel、精确锁、RECORD 和原安装来源；组合没有重新编译或替换产品源码。

来源为 `ROLE-ORIGINS-001.json`，分别核实 App 30、Host 15、WT 23 个发行包的原收据及全部成员。三个共同安装工具逐字相同。新组合收据保持各角色的原真实安装根，并另存来源身份；分发阶段只复制 wheel、锁及原安装工具。WT 角色没有安装观衡 App。

历史和采集沿独立 Host 解释器，分析与执行沿 WT 解释器；观衡保持独立只读。原 Native 执行、账户、行情组件来自已验事件续接候选。新增 `native_analysis` 组件显式带入原 helper、Reader DLL、读取 probe 和 VC 运行库；三个入口均从新包解析，不依赖开发目录。probe 作为原 Reader 验证工具交付，它的读取结果与原 CTA 实际策略执行分别验收。

## 已取得的装配结果

原装配器生成 1481 个成员，清单 SHA256 `1e3fa2585532b1a756025cfdf4843ab2e7fb29449d7ec5b022028c85b1c62b17`；ZIP SHA256 `d5d2aa219f4b111c15f0d31c7dbb21ecdb00edd7d8d24dd3dc19899e9c1951b2`。ZIP 已经原 extract 接口搬迁核验。准备、装配阶段各自沿创建期隐藏 Job，实际退出 0、整树清空、管道 EOF、线程 join 与资源关闭成立；未启动业务 owner。

`installed001` 的新根离线安装已经通过，232.594 秒退出 0。原公开 resolve 用 48.672 秒核实三个角色、RECORD 与所有 Native 路径。各角色的实际 `-I` 导入均来自新安装；WT 同时导入发布者及原 QNA 模块、加载同包 helper 和 Reader DLL，通过 1.125 秒检查。五阶段均正常退出、整树为空、管道 EOF、线程 join 与资源关闭，无业务 owner 启动。

最终安装收据 SHA256 `2c29800a61bff2983b1b8bcf1c6cf871ed461c21e295d34310ead44899baf9f3`。新包接口为 `INTERFACE-001.json`，SHA256 `ac436833d35864fbc879725b44acd879b42041c9feff1d2cae096b4b408f9f11`；交付清单 `DELIVERY-001.json`，SHA256 `8a1f84c66d909807c544ee6e74b00052906597b1f430a6ecef8e9d7c3b801a30`。完整九组件 QA 已取得该固定接口，角色及分析 Native 三入口全部沿同包选择。运行中 CTA 日线切换归开发者1；实际 QMT 和模拟账户验收分别记录。模块组成相同、安装通过和业务整链通过各自具有独立证据。

## 独立审查与剩余范围

[分析来源及窗口](2026-10-30-analysis-source-and-window.md)的独立 Spec 审查已完成，固定报告为 `build/root-analysis-bound-main-001/review/FINAL-001.json`，SHA256 `fae27e13c7bcf37c520d30f033688442d6bc951cf4fba594eca16801f657965c`。来源 v7、WRI 装配、QAC 同正文及正常同配置重启已核实。开放一项 P2：同发布根更换来源、发布目的地或 Native 身份时，a4 缺少完整恢复配置比对；维护者在新 a5 候选修正，a4 原件与正常运行资格保留。

本 a4 包用于继续完整装配主路径，配置恢复修正会以新身份进入后继候选。完整九组件同实例、正在运行的唯一策略采用新日线、实际终端以及最终生产发行尚未授予。来源运输时钟、分钟文件完整性及账户业务事实沿原 owner 分别核实。

维护者已交付 a5 新入口 `build/root-analysis-restart-002/INTERFACE-002.json`，SHA256 `9eefcb01c0e87d81049647e32a9db7f4f1a80479194e612fea4f79e6ca346bcb`；完整配置身份先于恢复和来源调用，新的配置冲突及同配置四代主路径已跑通。该后继正在独立 delta 审查，本 a4 ZIP 和安装保持原字节。最终整包将显式选取已经验收的后继输入。

原采集四进程本轮仍存在；采集状态 running/connected、订阅 6982 证券，读取时状态约 0.58 秒前更新。检查记录为 `LIVE-PRESERVATION-001.json`，本轮没有修改、重启或停止这些进程。旧 QMT 项目、终端策略与 WT 框架保持原状，实际委托和撤单均为零。

## 2026-10-30 后继核实

a5 完整配置身份的独立 delta 与 Standards 审查已经完成，开放 P0—P3 均为零；原 FINAL-001 保持，后继为 `root-analysis-bound-main-001/review/FINAL-002.json`。正式 WT a11/Host a12/Agent a9/AWP a5 角色已普通离线安装与原 ATI 提取，接口 `root-analysis-wt-final-role-001/INTERFACE-001.json`，仅一只 AWP wheel 替换，其余22只保持。该角色待进入后继 SRI，本 a4 包保持原字节。

同包九组件 main004 已完成晚来源65.062秒、原1.1.2/八目标/SDK一笔成交、账户发布及独立观衡HTTP，观衡停止期间WT继续；248.688秒正常关闭。原Writer收到942570报价而处理计数0，分钟文件资格继续待核，运行中CTA d1刷新由B负责。固定交付为 `qa-composition-001/DELIVERY-001.json`，不把SDK替身转授实际券商资格。

本包实际 QMT 日线/因子与原生分析主链已实机通过，八ETF在原HPR准备后共同日期到10月30日，详见[实际来源及补齐](2026-10-30-real-analysis-and-daily-refresh.md)。持续自动准备正在自有发布者接入；最终后继组合、完整策略与模拟券商交易继续。

## 九组件 Writer 主路径接收

`qa-writer-002/main001`在隔离SDK装配选择原allday模式后，九组件主链296.235秒正常通过，Native/Writer均56056条，6982DSB和原Reader20946根一致；原1.1.2八目标到SDK卖200一次、账户/独立观衡及App关闭后WT继续均成立。原失败根因是闭市后的回放被会话过滤，产品和框架保持原字节。独立delta `qa-writer-002/review/FINAL-001.json` SHA256 `ced169661d4d1e02e9e65d87922efab7b5e622b6d908a64ac016e151e0b80cf4`，开放P0—P3=0；根重核六原件并写ROOT-INTAKE-001。

Source累计与Native差200、冷初始化缺09:32及连续性Unknown保持；四次发布/128 SDK为实际总数，三轮是选定R24审计。真实自然归档与其缺口见[今日归档](2026-10-30-close-minute-archive.md)，不把SDK结果扩为真实全市场完整。
