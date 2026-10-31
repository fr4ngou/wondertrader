# 2026-10-22 WT自有QMT只读连接包

类型：验证记录。结果：pass（隔离开发、独立安装与模拟SDK原生整链）；真实终端装载、真实供应商读取及生产为not-run。关联[QTS-R1–R8](../specs/qmt-terminal-readonly-source.md)。

## 当前身份

源码位于本仓库`connectors/qmt`，测试、工具和制品全部由本仓库拥有。固定旧源码仅作来源追溯，构建及导入均不需要旧工程。包为`guanheng-qmt-connector 0.1.0a1`，Python>=3.6.8，零第三方运行依赖。没有改动当前QMT安装、策略或账户。

汇总原件：`build/guanheng-workspace/qts-qualified-001/receipt.json`，SHA256 `135abcfb76b6beba7d03ecef805cfed910381e319a7da93c9bcdf2a115375adb`。绑定26项产品/测试/构建输入、五份独审报告及实际运行原件。当前分发来源清单SHA为`8f96784ff518675cd467b6f337eb7279049fece7cb730798262d78ed18c076bb`。

正式开发制品位于`build/guanheng-workspace/qts-package-003/artifacts/1bbbd96d1dd64f6e817f88ea947f5c79`：

| 制品 | SHA256 |
|---|---|
| `guanheng_qmt_connector-0.1.0a1-py3-none-any.whl` | `53c31b1bbfb0ffee2d0e084c101cdcf113c0a79a9e1bad9000684ced1a242ad8` |
| `guanheng_qmt_connector-0.1.0a1-source.zip` | `34d38e96785fd166727002cc788730db187825ba21dd22757f0247e9dad8f618` |

003使用最终构建准入逻辑重新构建，wheel与已独立安装/运行的002逐字节相同；来源清单及全部分发文件也相同。源ZIP保留各次归档自身身份，不用相同源内容推断ZIP摘要相同。

## 实际观察

| 层级 | 实际结果与原件 |
|---|---|
| runtime、operations、HTTP | 独立134项通过；含owner/重入/代际、Future原ID、容量/保留/背压、TCP/HMAC/重放/分帧/截止/断连/关闭；独审报告登记实际命令、结果及输入 |
| 最终打包准入 | 独立17项通过；来源漂移、缺项/重复、未声明资源、真实Windows junction、清单reparse读取前拒绝、隔离ZIP导入和入口生命周期；与上述134项合计当前151项要求回归 |
| 原生整链 | `qts-review-runtime-001/native-delta/summary.json`，5/5场景、6个进程：正常、空、源错误、持仓后停止、新实例恢复；实际普通生产DLL→QRT→新源HTTP→原TraderAdapter→v2值；SDK行全部合成 |
| 实际Python3.6.8 | `qts-review-runtime-001/python36-source-delta.json`及`python36-installed-delta.json`；新standalone隔离解释器、源码及安装wheel均通过签名HTTP/owner一次读取/原ID认领/实际关闭。解释器来自国信安装，未操作运行中的QMT进程 |
| 独立安装 | 新环境、无索引/无依赖wheel安装、空工作目录与隔离导入通过；无旧业务模块导入、无导入线程副作用，wheel/ZIP逐项身份相符 |

原生DLL沿既有NQP-018固定来源制品使用，本轮没有重编或修改WT核心，也没有扩大该原生包的发行许可资格。四批分别保留来源、时间和请求ID；合计持仓映射不授精确今昨或执行资格。

## 根因修正与独立审查

- 实际3.6.8复现`concurrent.futures.InvalidStateError`不存在。源端在受理时通过标准Future协议取得结果所有权，取消外部等待不撤销原操作；取消返回False，结果仍按原ID取得，无异常吞掉兼容分支。
- 原HTTP启动在状态锁内调用反向DNS，阻塞时拖住`close(0)`及启动预算。新传输使用回环字面量绑定，移除DNS依赖；bind/listen在状态锁外，取消时关闭已公布socket，阻断迟到监听。新增三项负测在原001 wheel上失败，修正后通过；原样失败保存在`qts-start-repair-001/red.log`。
- Windows junction的`is_symlink=false`使原分发准入漏过外部重定向。构建owner统一检查reparse属性，逐项及项目根/清单正文读取前拒绝；真实junction和清单属性注入回归分别证明目录对象及先准入后读取顺序。测试未提权，真实文件symlink受系统权限限制保留明确范围。

独立报告位于`build/guanheng-workspace/reviews`：`qts-runtime-full-001.md`、`qts-runtime-delta-001.md`、`qts-runtime-delta-002.md`以及`qts-boundary-full-001.md`、`qts-boundary-delta-001.md`。full原件保留当时身份及发现；最终delta复核当前摘要，原P1/P2关闭，开放可复现发现0。最后仅构建准入及其测试变化，未变化HTTP/native/3.6证据由独审明确复用。

## 限制与后继

本包已取得独立开发资格，尚未安装到运行终端；真实QMT调度/停止回调、账户四查询与已下载缓存/快照的实际供应商行为仍须验证。模拟值不能授予真实数据、全市场覆盖、分钟精确股数、交易恢复或生产运行资格。共享内存、交易和push未纳入该只读包。

下一步依[完整业务清单](../migration/business-feature-inventory.md)将账户值接入独立观衡HTTP和中文页面，继续策略、订单/运营及其余全部业务迁入。原生账户接缝调查位于`build/guanheng-workspace/account-contract-001`；产品宿主、业务HTTP和页面尚未实现。
