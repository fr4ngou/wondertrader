# 原历史Host接入独立WT的装配准备

类型：开发装配及交接准备。结果：离线装配pass，实际交接not-run。对应[WRI](../specs/independent-wt-runtime.md)，后继目标为同一WT拥有HPR Host、历史查询及行情采集。

后继：[实际交接与真实读取](2026-10-30-wt-host-data-handoff.md)已完成，下面保留准备时状态。原61052为外部owner，实际HPR子进程为42648；实际角色和退出事实沿后继记录。

## 已有事实与本次变化

当前实际数据实例仍为WT74964、历史27980、采集30588；历史补齐Host仍为原PID61052。原QMT正文、共享内存名称、凭据、数据目录和下载请求保持。本次没有发停止信号或来源请求。

已找到当前generation-002的原`qmt.history-preparation-process.v1`描述及产品pair。沿同一个配对、Host解释器和通信Journal准备三组件配置，只为新Host owner分配新控制根。历史/采集描述及原120秒初始化、100秒关闭总预算保持；QMT来源常驻等待仍由原HPR服务负责，初始化预算不限制来源必须在该时间内上线。

- 准备根：`build/wt-live-host-data-composition-001`；
- 配置SHA：`a16094bf7df3f985757f5f515b8778edd0916958f4d871df77e01aa4a7c409fa`；
- 新实例：`d836f5f5-6c83-41d5-a93d-0c8cbdf343ec`；新控制ID：`12b10e4e-43ef-404a-a24b-dfb1f042d828`；
- 原pair manifest SHA：`62f99b1c4d4e1bff36293437f163aee2f9067984711b0ea54949c1a5e621dab2`；
- `PREPARED.json`绑定32份原配置、配对材料及解释器摘要，新启动入口只引用原受控凭据文件，不在命令行或输出中出现凭据值。

原通信SQLite保持原址及全部原请求身份，不复制、删除或清空。未来Host运行按原协议更新Journal；“保留Journal”不表示禁止其正常写入或要求数据库文件在运行后摘要不变。

## 实际离线验证

最终普通WT安装通过原RuntimeConfig/Runtime构造host、history、collection三个原owner，随后在未启动状态正常关闭。原HPR安装执行`verify_product_pair`，离线重建正文并核对Host/Agent身份。两项均通过；来源调用、监听启动、共享内存新连接、Journal读取/写入和现场启停均为0。

control412为1.359秒exit0，自有Job树0、stdout/stderr EOF、线程join及句柄回收全部通过。原件为上述准备根的`CONSTRUCT-001.json`、`HOST-VERIFIED-001.json`、`HOST-VERIFY-CONTROL.json`及`control-412`结果。

## 实际交接条件与剩余

《杂役》仍在原Host上推进后续批次。本轮OS已核cohort003的两个Python进程49108/41692实际存在；缺少安全点收据时保持原Host，进程存在本身不代表所有下载已完成。已约定由批次所有者发布无在途/未知请求的交接收据，并暂缓新prepare；转换和查询可继续。

实际交接须沿原owner停止信号及原closed收据，核旧进程物理退出后再启动新实例。保持原pair及Journal，认证恢复后先按原ID读取已有终态，再做只读历史和当前统一目录查询；未知请求不换ID重发。当前三组件仍仅为已准备材料，不宣称已接管或验证新进程。

本次还明确了交易通信的后续完整模块：已有trade_bootstrap/runtime、原SourceTradingService及通信Journal将封装为独立安装、常驻及WT托管入口。原数据HPR的MARKET-only合同保持，交易产品显式选择；WT框架和金融算法保持。正常两代与已执行丢回执的unknown责任分别验收，不扩大既有协议的确认语义。完整交易通信及共存配置继续开发，当前运行及生产未切换。
