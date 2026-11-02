# 观衡首次实际策略资金接入

类型：独立观衡部署记录。日期：2026-11-02。状态：实际资金的只读展示已上线；WT执行进程故障及持续资金更新继续处理。

## 使用入口

打开 <http://127.0.0.1:18143/strategies>。观衡版本为 `0.1.0a87+capital.2`，现有个人观察及行情连接保持，WT、行情采集和市场更新分别维护。此前观衡正常停止，Web及启动器退出码均为0。

稳定维护配置仍为 `E:/workspace/wondertrader-data/observer-current/web-profile.json`。同目录 `DEPLOYMENT.json` 提供本次安装解释器、维护工具、实际profile和控制身份；按照[实际账户交付](2026-11-02-observer-actual-account.md)中的状态命令查询。`start`、`stop`、`restart`只管理观衡Web。

本次实体配置为 `E:/workspace/wondertrader-data/observer-controlled-web-20261102-a87-capital-002/web-profile.json`，原字节SHA256为 `f0e579fa40e17e7e1e5eb6123eabf2173b0a2fcf7ce8e333408c45276990ae85`。前代a86配置及安装保留，可沿原维护工具正常停止本代后切回前代；回退观衡版本与恢复WT运行分别处理。本轮未执行回退。

## 修正与实际结果

首次持仓加载发生在Parser启动前，运行侧使用已声明的原QMT快照估值。读取契约原先仅接受CTA行情来源，会拒绝这份实际发布。本次后端投影和前端类型统一接受两个明确来源，保留原来源标识、金额及时间；观衡继续只读消费WT的计算结果。

本次实际发布的策略总资本100万元包含现有库存。北京时间16:19:15的发布值为：总资产100万元、持仓市值366,924.80元、现金余额633,075.20元、本次运行盈亏0元。旧历史本金及历史收益未导入。策略页面读取到5项持仓，账户仍保留2笔委托、1笔成交及1项资金结果。

Root接收时WT执行子进程已异常退出，WRI为 `faulted / component_runtime_execution`，执行组件为 `unexpected_exit`，其余组件沿原故障流程关闭。因此当前页面明确显示策略运行失败；原账户约束已过期，可用资金显示待更新。其他已发布金额及原时间保留。本记录不授持续运行或自动交易已完成的结论。

安装态实际投影、HTTP与浏览器读取均采用同一份真实资金发布。桌面显示100万元及相应库存、现金；刷新保持原估值时间，390px页面无横向溢出，浏览器未报告脚本或控制台错误。本轮未新增自动化测试，也未调用QMT、下单或撤单。

## 制品与证据

- 源码：`7846ad10901649713d12d89e60b21081f7aa75c7`，限定四个App源码/元数据文件；WT框架差异为0。
- 独立ZIP：`C:/Users/frangou/AppData/Local/Temp/root-observer-a87-capital-build-001/observer-0.1.0a87+capital.2-windows-x64.zip`，SHA256 `9eaff70ba4e913350ba537a5ec76ffd88af908db5442e68e55cd8c0754b117a9`。
- 运行清单SHA256：`d7f7b9cf57f30a57fbf0c79bae9c7ec398d0d0cff67b9aa785ea0cd53126633a`；普通离线安装收据SHA256：`a06f9f28c9af7ca6120ad61ddc6016da9ea1e67f686af6957809f4f7af1b90a3`。
- 本机验收：`E:/workspace/wondertrader-qa/root-observer-a87-capital-20261102-001`中的 `ACTUAL-PROJECTION-001.json`、`ACTUAL-DEPLOYMENT-001.json`、`PAGE-VERIFIED-001.json`、前代关闭回执及桌面/窄屏截图。
- 运行侧交付：`E:/workspace/wondertrader-qa/strategy-capital-handoff-20261102-001/CAPITAL-ACTUAL-HANDOFF-001.json`。其交付时ready与Root后继接收时faulted分别记录，当前运行状态沿原控制身份核实。

## 继续完成

运行侧继续定位实际退出原因，并处理无新K线时资金约束的持续更新；保持原价格、持仓和账户时间。恢复后的新WT身份由观衡只读接收，再核对当前可用资金和持续运行状态。首次已发布资金、模拟成交/撤单证据与整套策略持续可用性分别判断。
