# WT统一日线130项缺口补齐与恢复修正

状态：verified（数据角色）。目标：本机18136。授权：用户要求查清130项并继续补齐，Root分配数据角色正式构建、正常切换和验收；Source、账户、通信Host及页面消费者保持各自owner。操作者：开发者2。时间：2026-11-04北京时间。

## 发布身份

主干 `58d26e55de6cb279f2aebd77a0eb57853b8ca045`，注释标签 `guanheng-daily-data/0.2.0a1+unified.7`。CPython3.12.13，SDK0.17.0。离线制品role-build019，清单SHA256 `d58c4ee7d08a5722ee990a67895e4d30caefdcedf8629ebab34e332b0880d73c`，176源码输入和157安装成员已核。Reader/Helper/Storage沿既有逐文件发行身份，ABI和原生格式保持。详见[正式证据](../evidence/2026-11-04-daily-gap130-release.md)及其固定路径。

## 预检、切换与状态保护

.6按正常服务入口启动后，原native阶段因旧预生成候选capture失配而失败，成功CURRENT继续可读；原42 HPR、完成回读及原请求保持。.7只更换程序，复用同daily配置及原任务根，不重派这些请求、不重新读取整股票池。实际新回读正常转换并完成原价格、补充原价和快照发布。

程序：`E:/workspace/wondertrader-data/unified-daily-20261104-001/program-gap130-20261104-013`。服务配置：同受控根`private-gap130-recovery-20261104-012/service.json`。数据配置：`private-gap130-20261104-011/daily.json`；任务根：`data-gap130-20261104-011/tasks`；CURRENT：`data/publication/CURRENT.json`。凭据继续由原私有环境提供，文档不保存值。

正常服务命令为固定runtime-service-20261104-004解释器的 `-I -B -m guanheng_wt_runtime.service_control start|stop|status --service-config <上述服务配置>`。先停本数据角色旧代，再启动新代；发布及正常重启均通过原管理入口。通信Host、Source和账户运行未切换。

## 发布后验真

53个指数已从统一正式入口逐项回读，原4636档案及6255旧任务文件保持。七指标经239次HTTP、0次SDK调用完成，业务值和旧历史保持；T2108接收时刻沿新原件更新。重启7257文件保持，CSI/CNI/Qmt样本成功，维护owner等待次日调度，本轮没有活动v8/HPR。原两项未知HPR继续以原slot及身份保护。

## 回滚与结论

程序.6具备相同SDK0.17/原生格式，可在停止.7后读取已发布结果并沿原配置恢复；其旧hint问题仍属于已知限制。.5使用SDK0.16，对CNI新元数据需要先沿原发布器CAS重新采用保留的旧成功配置，再启动其原服务，避免直接让旧程序消费新CNI档。原版本、配置、原任务、档案及发布记录保留，当前无需回滚。

两国证页面端SDK0.17接收由Root独立维护，首次自然新日及09:00调度待验。数据角色发布完成，整体页面完成资格不由本记录扩大。
