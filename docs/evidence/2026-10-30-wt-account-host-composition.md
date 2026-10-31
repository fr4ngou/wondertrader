# 独立WT统一管理账户通信、交易与数据

类型：开发安装及SDK主链证据。日期：2026-10-30。范围：WRI可选账户通信装配及观衡只读状态。

## 实现及原能力复用

HPR历史补齐占用原`host`位置、交易使用`trade_host`时，原v3只读账户消费者需要自己的原Host入口。自有WRI增加可选`account_host.kind=qmt_read`，直接使用已有`QmtHostProcess`，由同一个WT启动和关闭；观衡只读状态增加“账户通信”标签。省略新增项时原配置及组件相对顺序保持。没有新增账户计算、交易协议或WT框架修改。最终行为见[WRI规格](../specs/independent-wt-runtime.md)。

## 普通安装及完整业务链

模块根为`build/wt-account-host-composition-001`。原离线安装器从48份冻结输入构建`installation001`，仅安装WT角色及市场客户端，没有App、FastAPI或SPA。实际安装的`runtime.py`与本次冻结源码逐字一致，固定输入在`SOURCE-001.json`和`review001/INPUTS.json`。

`case002/main_installed.py`从普通安装公开CLI启动HPR Host、交易Host、原账户只读Host、历史查询和原生采集五个实际子进程。HPR/交易/QST由正式3.6.8组合正文驱动，原v3账户源由独立3.6.8 SDK进程驱动。本次证明五owner的运行装配；单个正文承载全部通信由QAC专项另验。

- 原生精度修正版Scan完成持仓2、委托1、成交1、资金1，原Journal回读65项事实、30个ABI槽及请求身份/来源绑定/执行区间精确一致。
- SDK完成单笔下单、查单和撤单；真实委托及撤单均为0。
- 原HPR完成补读；QST经原Parser/Writer生成两根标准分钟线并读取；已有真实历史五根在运行前后保持原值。
- 正常停止同一WT，五owner按逆依赖关闭；CLI、两个SDK源、原生Scan及内外Job完整退出，双EOF、reader join和句柄关闭成立，forced=false。

`main002/RESULT.json`及`control-main002/RESULT.json`通过，外层27.006秒exit0，1248份业务输入前后一致，外层工具身份保持。原生严格审计为`read-fixture002/sdk/AUDIT.json`。

## 受影响回归及失败记录

完整主链后补验账户Host启动失败：消费者尚未启动即停止继续启动，原owner仍完成逆序回收，保留`component_start_account_host`，同一实例不会再次启动。`regressions002`安装后10项运行回归及38项观衡HTTP回归通过，外层15.562秒正常关闭。HTTP回归使用已安装的固定策略依赖和当前页面源码，证明只读API行为，不授整套观衡安装资格。

保留两项QA失败：`main001`为Windows读取SDK控制文件时阻止同名替换；`case002`改用每序号不可变文件，产品代码保持。`regressions001`的运行回归通过，HTTP收集因开发环境缺少固定策略安装元数据而失败；后继`regressions002`显式使用已有固定安装依赖，未修改依赖元数据或运行实例。

## 资格与剩余工作

本记录支持独立WT安装及五owner SDK组合、原生数据和账户消费、只读状态及启动失败回收。真实QMT单正文共存、资金中断触发定位、唯一策略/执行完整组合、观衡实际页面消费和生产切换分别保留待验。正在工作的数据WT33636及来源下载保持原实例，本模块没有切换它们。

独立full审查输入冻结为`review001/INPUTS.json`（SHA `9c61de8094c1d2a7c8c8ca1291848511df943b4713e4491e856aef74bbb7adb4`）。规格与开发规范两轴通过，新增P0–P3为0；报告`review001/REVIEW.json` SHA `858d81633e1e929ecd8ae651c7d679f28ce8bfae20639379276ef635ff3bd7ad`。本模块限定资格已接收，整系统目标继续active。
