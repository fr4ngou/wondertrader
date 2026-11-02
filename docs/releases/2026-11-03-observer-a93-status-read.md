# 观衡a93：接续短暂状态占用

类型：实际开发环境发布。源码`1f2f554`，版本`0.1.0a93+status.1`，入口仍为 http://127.0.0.1:18143/ 。本次只升级观衡Web读取层，原a92盘后更新、WT、QMT及采集保持运行。

## 已复现根因与修正

实际WT发布状态文件期间，Windows可能短暂占用文件名。原SDK以CollectionStatusPending明确表达此状态；原观衡将其当作本次失败，导致运行正常的数据实例偶发显示“读取失败”，策略投影也可能暂缺。

统一read_runtime_snapshot现沿原2秒总截止接续下一份完整快照，每次等待最多10毫秒。格式、运行身份和其他I/O错误仍沿原失败路径；没有延长总截止、复用旧数据冒充本次成功或推断进程存活。策略与系统状态共用此接缝。

原读取层在真实发布中复现79次成功后CollectionStatusPending。新已提交读取层实际374次SDK读取遇94次真实Pending，得到280次完整业务观察且失败0，未注入替身。安装后连续16个实际HTTP请求均完整读到五实例及策略结果，保留真实执行故障，未再出现本轮短暂读取误报。

## 当前实际部署

- ZIP SHA256：`0e01fdfd2a977c08b0d87c2c781141af1917caf5c0af697358e16f6441158ea7`；制品清单SHA256：`b785bfc4100089f66b7cd5c825c7a721f716e7d252044a4cdd94bf170552c60d`。
- 安装收据SHA256：`973d044913487282a8bba26dfed90260d260cea29c55aad0343bd37ae95d1a34`。
- 稳定维护定位：`E:/workspace/wondertrader-data/observer-current/DEPLOYMENT.json`；实际profile为`observer-controlled-web-20261102-a93-status-001/web-profile.json`，SHA256`5657044a6ceb5e6c81e51c51a88ba759f7f0f9f752d67be4b79f2695b720f5a7`。
- Web控制`f6f4009e-3d37-4407-b865-7f2eb209eb11`，Web PID26824、启动器61152；日常仍核原控制与创建时间。原a92 Web正常关闭exit0、shutdown_complete=true。

新版启动后的业务检查发现正式执行已经再次故障，因此没有沿最初脚本的“必须交易ready”分支登记成功。实际Web已启动；核原工具身份、原资料及真实fault后，单独完成当前维护定位发布。A93-POSTCHECK-INITIAL保留失败触发，A93-DEPLOYED记录真实部署及业务未恢复状态。维护元数据与当前物理运行一致。

## 尚未解决的正式执行故障

12i曾真实就绪，现金/当前可用633,075.20元已在页面显示；随后在2026-11-02 23:54再次component_runtime_execution故障，账户发布被原运行监督链关闭。当前策略显示失败、余额保留633,075.20元、当前可用为空。该故障与本次观衡Pending问题分层记录，开发者2继续定位实际退出。

原报价49922、原采集/18130历史及统一日线18148保持就绪；本次没有发单、撤单、替换正式运行组件或改WT框架。总览精简及原个人观察保持。市场观察仍有T2108等输入缺口，全A最新原件由独立来源模块接续。

实际证据位于`E:/workspace/wondertrader-qa/root-observer-a90-overview-20261102-001`：A92-DATA-READ-DIAG、A93-ACTUAL-STATUS-CONTINUATION、A93-POSTCHECK-INITIAL、A93-DEPLOYED及A93-INSTALLED-READS。后续恢复须接收新的实际运行身份再核账户与策略，不能据此前短时ready宣称持续运行完成。

观衡维护及回退沿[运行手册](../runbooks/observer-runtime.md)。a92原profile保留，正常关闭a93后方可回退；回退读取层不会修复正式执行故障，且原Pending误报可能重新出现。独立盘后更新保持a92，不随Web回退更换。
