# AWP 已确认读取回收消费端

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

范围：AWP6，独立v7与可选HPR按公共RR协议持续读取；AWP a9、core a2、WT a11、Host a13/Agent a10的固定普通安装组合。

实现：连接扩展字段进入原权威配置，剥离后构造原BoundHistorySource；认证能力必须匹配。公共客户端在完整结果落盘后确认消费，AWP保持原slot和时钟，Pending不重造ID。HPR原D/日期计划及原Native/QNA算法保持。首次绑定及所有后继交换共用原RPC总截止和传输异常分类。

最终隔离SDK主链：Host两个Journal及来源Book容量8，24次HPR实际更改缓存与96次v7调用，经原Import/Reader/QNA/R24完成三轮。120个原slot均保存并确认消费，关闭后两库0行，Book高水位1/ACK24。Native三树与外层命令正常关闭；1392运行输入前后相等，42份正式材料身份保持。27项默认、未知/已确认失败映射及慢HTTP头截止回归通过。

原件：固定接口（外部历史/待归仓路径：`../../build/root-analysis-retained-reads-001/INTERFACE-001.json`）、源码与材料清单（外部历史/待归仓路径：`../../build/root-analysis-retained-reads-001/SOURCE-FINAL-001.json`）、最终主链（外部历史/待归仓路径：`../../build/root-analysis-retained-reads-001/final004/RESULT.json`）。独立审查由根会话安排，公共协议及其8/16长跑与重启证据归[已确认只读结果回收](../specs/qmt-read-retirement.md)。

一次先行case的原请求未确认继续保持unknown；其后成功不证明旧故障修复。真实QMT、C++账户四查询、混合v4查询/交易、Writer分钟持久化、整个系统长期及生产资格分别验收。终端外capture档案仍按部署数据保留政策管理。
