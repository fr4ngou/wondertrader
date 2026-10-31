# 独立WT托管真实只读账户后继

类型：真实QMT部分主链证据。日期：2026-10-30。状态：pending-verification，持仓和资金成功，其余三项与正常Host关闭尚未完成。

## 触发链与结果

直接使用最终系统候选003搬迁安装的WT与Host角色，公开WT CLI管理原qmt_read常驻Host，无观衡运行owner。复用[此前已验账户只读配置](2026-10-28-qmt-resident-real-two-gen.md)，以同一Host解释器冻结新v3配对；只声明account.trade_detail和market.full_tick，order_ready=false。临时使用原SHM_READ_PROBE，没有新建策略。

run002实际完成原Windows SHM认证，按原health.last_tick观察到两次新回调，再沿认证profile原policy_id/version/execution_timeout_ms分别提交一次读取。持仓返回4行、资金返回1行，原请求、终态及完整响应保存在私有目录。随后查询委托期间Host异常结束，HTTP连接拒绝；没有取得本轮委托、成交和行情的成功证据，不将前两项扩大为五项完整验收。

Host原closed收据error_code=runtime_failed、runtime_closed=false、monitor_joined=true；WT报告host unexpected_exit，components_closed=false。WT CLI退出2，外层及全部子树最终均已回收，EOF、线程join和句柄关闭；物理回收与业务正常关闭分开记录。现有封装没有保存具体异常类型，退出根因尚待捕获。该实际失败与旧SDK联合main003是否同因仍unknown。

## 恢复与原件

本轮仅停止/启动SHM_READ_PROBE，其他策略保持原操作状态。结束后通过QMT界面和Formula stop success确认探针停止，磁盘正文逐字恢复原SHA256 35d020b67dc1b0fb1d6880d7bd4f04cfd7c8a915df0172dd51090542ea9546ae。没有真实下单、撤单、账户权限调整或WT核心修改。

原件位于build/wt-real-account-preparation-004：PREPARED-001.json、run002/RESULT.json、run002/STATUS.json、run002/wt-control、private原Journal/请求/终态/响应及RESTORED-001.json。原控制器为control428，输入身份前后保持。配对凭据和财务值保持私有，文档只列来源、计数与固定状态。

前轮run001的健康字段误用已在测试脚本修正为原last_tick；它没有发出账户请求，保留独立失败记录。静态准备阶段的命名/解释器错误属于QA材料准备，未修改产品准入或原协议，原记录保存在各build目录。

下一步由通信模块所有者沿这次实际失败捕获首个有限分类/源码位置，建立定向回归后修正自有责任层；必要现场复现由根统一操作。完整真实账户消费者和业务观衡页面继续沿原生执行/账户模块验收。

后继：新配对005的诊断运行以及006无诊断普通入口均完成真实五类读取及正常关闭，见[普通真实主链](2026-10-30-wt-real-readonly-main.md)。原004失败和其恢复资格继续unknown，本文原件保留。
