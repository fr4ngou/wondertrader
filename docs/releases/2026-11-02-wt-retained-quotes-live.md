# WT报价回收接入与原采集恢复

类型：开发环境实际接入。2026-11-02晚间正常切换GH数据策略行与数据owner，独立金融策略文件及交易权限保持。WT框架、DataKit算法、原存储和原QST流配置保持。

## 根因及正确路径

旧HPR已累计1024条完成记录，旧配对未启用消费回收，导致新报价准入失败。后继沿已有retained协议：Native校验并持有完整快照后确认consumed，Host在原票据结束后回收确定完成责任。unknown/running继续保留。本轮没有增加容量或清理旧Journal；原Journal完整保留，新配对按原生成器初始化独立Journal，额度仍1024条/30670848逻辑字节。

实际同owner连续三次quotes.query均取得QMT原值。第三次读取前后，旧request_id退出原Journal，新request_id完成且consumed=1，记录数保持1。证据证明真实消费与回收主路径；连续跨1024次的长时间验证尚未执行，按主路径优先不作为本次接通的额外门槛。

## 运行身份与实际业务

- 维护根：`E:/workspace/wondertrader-data/wt-retained-quote-prepared-20261102-001`；`ACTUAL-DEPLOYMENT.json`固定实际记录，`owner001/control.py status|stop`为当前维护入口。
- 单个独立隐藏owner PID29056，创建FILETIME`134381058923749559`。它持有自身生命周期Job，再以原native.run管理data与quotes两个普通WT CLI，继续独立于观衡运行。
- data控制`02427072-153e-4282-a710-86b698185cfe`，实例`6e0b9d4f-f9cd-4bf1-b5c7-5e4fb9cf6804`，配置SHA256`5cf423b7928bb9e07b75a8f0a6c993a2623fa21752c7cdaab785460f5d078b60`。包含RR HPR50885、原历史18130和原采集。
- quotes控制`a648f7d2-98b6-4114-843e-8e26dd7ae717`，实例`b11edf13-ad9b-4c75-8e06-44018e960f09`，配置SHA256`66164d1b422a83dc8005f03f70a83795318bea9c17896035a41de4c6ce91e577`，报价入口 http://127.0.0.1:49922 。凭据保存在原私有环境文件，文档不携带凭据。
- PLAN摘要`2259f62c009be2cc9c26657e2c2de1b6f221da8e6ad5758f54326f0b9a8f5b21`；59项启动输入冻结于owner001/INPUTS.json。Native报价库SHA256`cf07a3b82d39911a517a64a4b42217f66d4f040e053f2d1ee96c634485889729`。
- 开发者2操作GH数据行一次正常停/换/启，实际Source SHA256`4450295ed1a4d39504e447380cac1543c0340292ab4af85132b92e02ddf9c34b`，保留v7/v8及原QST；独立金融Source文件摘要保持，金融命令0。

实际MarketClient读取510300=4.085、588170=0.617、300308=550，来源instance/session/generation随结果保留。来源时间为闭市16:27附近，接收完成时间与来源时间分开；这次恢复不能作为盘中报价时延验收。

原18130来源分钟入口实际读取588170的2026-11-02 14:51至15:00共10根，价格量额原值保留。该后端直接读既有Store/catalog，没有旧HPR依赖。原采集实际connected=true、received/pushed=6930、overflow=0、error=null，仍处闭市等待；新交易日持续分钟写入另按真实数据验收。原writer.disableday语义保持，本轮未接入已准备的原生日线开关与历史回填。

## 关闭收据与维护脚本修正

旧data三组件均正常closed、forced=false，WT closed的components_closed=true、error=null，旧owner与组件物理退出。旧外层维护脚本在reader.join时传入一年剩余秒数，超过Windows线程等待参数范围，导致其终端passed=false；该失败原件保留，不改写为成功。精确恢复接收材料绑定旧终端摘要、产品closed、tree_zero、exit0、pipeEOF及原PID退出。

新自有监督副本把Windows等待拆为最多60秒一段，沿原绝对总截止；保留全年监督预算及原有限关闭预算。实际独立隐藏owner并发两无业务子进程正常结束，两个均exit0且资源/读线程/Job树完成。该修正属于自有维护脚本，未改WT框架。当前新生产owner保持运行，本代完整业务正常停止尚未另做破坏性重启验收。

本次唯一启动器已消费，维护时沿README正常stop、有限截止、closed和物理退出，再准备新控制代。禁止重跑已消费launch、清锁、清Journal或重新提交未知请求。观衡历史18148与Web18143分别管理，当前账户/策略故障恢复仍由正式执行接续处理。

实际证据位于`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`的RR-ACTUAL-QUOTES-001/002/003及RR-ACTUAL-CUTOVER-001；脚本等待修正和旧代接收材料见运行根owner001。原报价与回收设计见[共享内存报价模块](../modules/qmt-shm-quotes.md)。
