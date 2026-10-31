# 真实国信QMT与观衡受管Host两代读取

类型：现场主路径证据。日期：2026-10-28。状态：真实终端两代认证、十次只读查询、旧终态保留/旧binding拒绝、App与Host关闭通过；交易及完整业务发布继续。

## 实际调用链

当前观衡create_app/lifespan → QmtHostProcess → 独立已安装Host run-pair → Windows命名共享内存 → 国信内置完整内存策略原线程 → get_trade_detail_data/get_full_tick → 原Host终态 → 签名HTTP读取。没有启动旧QMT业务工程或终端内HTTP。终端为3.12:1.2.26.150，配对使用目标CPython3.6.8的既有已核SDK材料。

复用当前未运行的SHM_READ_PROBE，先将原正文逐字存入私有目录，再放入新独立只读v3配对正文；未新建策略。源能力仅account.trade_detail、market.full_tick，order_ready=false。当天GH_WT_MEMORY_VERIFY全推及另外两个已有策略保持运行。

## 结果

同一Host PID42076两次取得新binding。每次position/account/order/deal/market.full_tick均成功：分别4条持仓、1条资金、0条委托、0条成交和一条ETF快照；完整原响应留在私有目录，本文不复制财务值。每次读取前观测到两次递增且新鲜的agent_tick。空委托和空成交是来源成功空批，不是不可用的替代值。

第二代重新认证后，第一代position终态按原request_id读取，与首次收到的完整封装逐字段相同；携带第一代binding提交旧请求返回409。第二代五查询使用新request_id。该实机没有单独统计券商SDK进入次数，不将显式十请求直接等价为SDK全程零重放证明；无自动重发的目标解释器合成证据见[安装组合](2026-10-28-qmt-resident-installed-two-gen.md)。真实下单/撤单均0。

停止/重新运行均在现有探针对应行进行；Formula记录本轮第一代12:23:19.823、第二代12:25:47.340 stop success及对应销毁。未把平台stop文字单独当作所有内核句柄关闭证明。Host自身确认关闭/管理线程join，App shutdown_complete=true；Host最终state=closed、pending=false、forced=false、error=null。受控根qmt-resident-real-two-gen-main-20261028-003实际exit0，约254.25秒，原420秒总预算保持，无强杀，整树0、stdout/stderr EOF、reader join及句柄释放均在原收据确认。

首轮连接在该配对原60秒窗口内到达；本轮证明同一Host的两代业务读取，不扩大为本轮超过60秒首次等待。此前实际425秒首次等待的独立结果保留在[27日记录](2026-10-27-qmt-resident-tail-refresh.md)。

## 制品与恢复

完整现场材料build/qmt-resident-real-two-gen-20261028-002，配对及原始响应保存在其private目录。实际driver SHA fc9a32d6695f9a76f62b3845ebf2435a5a7cd7d6e00e9a4958dea2c885d71b25；配对策略SHA 69369e811e7ecf5dabd01855d08fc9df24475be868decce730b2eef28a85c37b。同一Host连续持有原Journal，未清空既有终态或放宽容量。

第二代停止、Host关闭和外层终态均确认后，SHM_READ_PROBE.py恢复原SHA 35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae。当前全推正文SHA仍b91ada8d10f8c60a9ea0ed1f75c1dd7ca585d7505445569374ff28395cb5c7f2。原件、配对、Journal、失败记录均保留，无WT框架修改或生产配置切换。

## 前序失败与职责修正

第一次配对准备误把IPC bytes填写成hex字符串，被原准入拒绝；在新独占目录按原bytes合同重建，未修改产品准入。首个App描述误用schema_version，原Host入口未启用；新描述按既有schema修正，未增加兼容分支。首轮实际四查询已经成功，第五个行情请求的测试脚本timeout_ms=4000高于该能力声明2000，收到400/invalid_arguments。后继从认证read_profile提取各操作的execution_timeout_ms/policy_id/policy_version，再按该原能力构造请求；原拒绝和成功结果分别归档，不放宽Host/Agent策略。

## 后续边界

此证据覆盖真实终端SHM及受管Host主链，没有执行本轮C++AccountScan/TraderAdapter/业务账户页面；那些消费者及其实际来源资格分别验收。尚未授予完整查询/回报恢复、未知委托跨进程恢复、交易型常驻Host、正式独立发行、登录自动启动或生产切换。分钟采集的下午完整分钟/收盘回读和Writer方案仍独立推进，见[当天采集](2026-10-28-qmt-live-collection-reopened.md)。
