# 2026-10-21 真实 QMT 分钟数据导入与原生 CTA 验收

类型：验证记录。状态：开发样本链通过，覆盖完整性 unknown。承接[源语义验证](2026-10-21-qmt-minute-source-semantics.md)和[合成输入导入验收](2026-10-21-qmt-minute-import.md)。用户自行重启策略恢复端点，本任务沿现有只读接口获取已下载数据。

## 输入与实现

2026-10-20 的 300308.SZ 为 239 条、688076.SH 为 189 条。原 Bridge → Gateway → market.market_data_ex 使用 subscribe=false、fill_data=false、dividend_type=none；读取前后来源身份相同。原始结果 SHA256 为 `7b9ee0110d36e18e5b57473f57ca19e0ff9cb069cb46ffb6eb0bc7472aff17a1`，保存在 ignored 的 `build/native/live-source-probe/history-f0c812373e6a4484957a181447982650/`。

离线交换适配保留全部 428 条记录，按显式 profile 使用北京时间右端标签、volume×100、amount×1、none 复权。资格为 DevelopmentVerified；时间边界、量额尺度和源精度的依据及限制见源语义记录。源整数手值换算后保持原有精度，无法恢复精确的不足一手成交量。

使用固定上游源码单独构建的原版 WtDtHelper 写入并逐字段回读 DSB；helper SHA256 为 `da75291338ab8f9618ee3befde4c81f98dbdb6047e11d3e2cbc94ca3119bb055`。输出独占新目录 `build/native/live-source-probe/imports/262717530f31448c87fa4278201854b3/`，包含 exchange/manifest.json、storage/qmt-import.json 和各证券 DSB/sidecar。输入和原终端文件保持原样。

## 实际原生策略读取

调用 WtBtPorter 原生 CTA C ABI，直接从 bin-path 读取 DSB，不注册扩展 loader。每只证券在独立子进程和隔离目录运行，以原始 QMT 返回及显式 profile 独立生成期望值，校验预热、闭合回调、每次历史窗口和完整字段。

| 证券 | 原始与导入根数 | 预热 | 闭合回调 / 计算 / 历史窗口 | 错误 |
|---|---:|---:|---:|---:|
| 300308.SZ | 239 | 2 | 237 / 237 / 237 | 0 |
| 688076.SH | 189 | 2 | 187 / 187 / 187 | 0 |

验收入口为 `build/native/live-source-probe/native-acceptance/accept_native.py`，结果位于其 `real-validation/239326a5060f456894f34de8bd2ff789/acceptance.json` 与 input-sha256.json；结果 passed，inputs_unchanged=true。该脚本另已验证合成输入的两种时间编码，以及时间、成交量错误输入拒绝。

WtBtPorter SHA256 为 `483e04c2263e69a14727233772f6265d0a90656c6c3b20d6559d59cbd4a3e77b`，来自现有开发构建，仍包含冻结待审框架差异。原版 helper 的验证与开发版 CTA 的验证分别成立；该结果不授予其余框架差异审批或生产发布资格。

## 边界与后续

本次证明已下载的部分数据可用于开发验收，全市场十年下载完成并非前提。缺分钟原样保留，全天覆盖 unknown；本次没有权威日历及证券例外验证，也未验全市场、所有日期、真实策略业务页面或实盘委托。原始数据、来源身份和完整逐行结果只保留本机 ignored 目录，仓库记录脱敏计数和摘要。

现有实例在外部补齐后读到新数据仍由[历史可见性接线](2026-10-21-reader-visibility.md)继续交付。实时快照、闭合分钟持续消费和独立服务生产接线另行验收。整个移植目标保持 active。
