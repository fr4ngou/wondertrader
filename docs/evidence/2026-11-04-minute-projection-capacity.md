# 2026-11-04 全证券分钟投影容量修正

类型：实际故障后继及验证交付。状态：`pending-verification`，代码与容量/升级材料准入完成；正式采用由Root执行。接续[启动接线修正](2026-11-04-minute-startup-runtime-repair.md)。

## 根因与实现

Root实际program003三组件ready后约106秒，collection以`status_publish/ValueError`退出且`components_closed=true`。现场控制代`configuration003/collection-controls/fa3daf0f-e457-4508-8e4a-2d95b3dddd30`最后维护投影2032914字节、7872行；下一批将超过底层固定2MiB。发布端声明维护16MiB/覆盖8MiB，实际私有创建函数仍硬限2MiB，导致全量扫描推进后失败。

新`collection_projection.py`集中原状态/收据64KiB、覆盖8MiB及维护16MiB预算；发布者与实际覆盖消费者复用同表。原`write_private_new`新增显式`maximum_bytes`，默认2MiB、全局上限16MiB，沿原DACL/独占创建/SecurityResources单一实现。发布继续调用原SDK原子替换，不删字段、不缩证券、不关闭维护。

实际失败代已使用`recovery/configuration.json`绑定原producer，代码换包重生成另一producer会破坏该恢复身份。`prepare-update`只换程序入口、新进程控制根及当前日线接线，保留原producer、worker/维护/Native/基础资料引用和所有原恢复收据。原program003仍是这些Native引用的运行依赖，须保留；没有迁移、改写或复制请求状态。

## 验证

QA根：`E:/workspace/wondertrader-qa/minute-adoption-20261104-001`。全部新产物/临时目录在E盘，0服务/QMT动作、0Source调用。

| 证据 | 实际结果 |
|---|---|
| `PROJECTION-CAPACITY-RED001.json` | 从现场投影行构造7649证券×3日期=22947行，执行原serve.publish AST及原私有写入，7641943字节稳定ValueError，低于声明16MiB |
| `PROJECTION-CAPACITY-GREEN001.json` | 完整字段及24小时范围计数，维护8572015字节、覆盖1608488字节；原有界消费者/原子替换通过 |
| `PROJECTION-CAPACITY-GREEN002.json` | 全集及所有字段保留，uint64/最大有限float宽度的保守上界：维护10637245字节、覆盖1688638字节；低于16/8MiB，22947行均可消费；这是容量替身，非市场完整资格 |
| `PROJECTION-REGRESSION002.json` | 四项实际Win32文件回归通过：跨2MiB、16MiB边界/默认2MiB、越界保旧及打开旧读取句柄时的大文件替换 |
| `CAPACITY-UPDATE-PREPARED001.json` | producer/worker/维护/Native等固定引用逐一保持；原恢复marker SHA与producer SHA同为22933617…，准备前后未变 |
| `CAPACITY-PREFLIGHT001.json` | 原Root013 Runtime工厂构造、history/collector/daily实际解释器入口、完整包及before CAS通过；collector确定加载新release私有写入实现 |
| `CURRENT-ROLLBACK-BASELINE001.json` | Root恢复后的data-rollback-owner002/c8d2b983…/PID76680及quotes-rollback-owner002/1771581c…/PID37772实际ready；原日线新control84294c7d…/PID25376，Source为before4450295… |

同一当前所有者的普通小文件与原子替换后的大投影均保持protected/canonical DACL，权限条目仅当前owner FullControl、非继承；底层ACL与SDK替换实现均复用。配置采用lookback=2个交易日加当天，容量证明覆盖实际三日期全集；字段和证券没有裁剪。原Native/Source166/金融八组件及历史请求边界保持。

## 完整候选及接续

数据根`E:/workspace/wondertrader-data/minute-adoption-20261104-001`：program004清单SHA`05c039c8fa89f3365f098fc2fe8aed41dd6ff5d879e56cafab264ddd24616a4a`，configuration004部署SHA`e2cc8e1354182275a1fb0a15cbaf6b56785b0d9c47faea4092aa4dc915ef8db6`，bindings003清单SHA`41e8e04dee884108cf15e69a00faa210fcdf259cf6af5599dec9ca552e14deef`。原Source before/after CAS保持4450295…/166418…，未重新生成Source或Native。

正式命令为QA根`commands003.ps1`，完整说明`HANDOFF-CAPACITY-001.md`。正常停止对象是当前回退后的两个真实owner002，按OWNER-READY固定摘要核身份，quotes先于data；原已退出owner001不再作为停止入口。Root先完成当前日线轮次/请求责任交接、正常停原日线与GH行，再停两个owner，采用Source和新data-owner003/quotes-new-owner003/新日线。正常回退沿原配置及新rollback-owner003；原失败代均保留。

正式通过须记录稳定运行超过原106秒触发点、一次完整扫描、两公开入口12样本及覆盖分类。若全日缺口仍存在，按原历史准入/未知/未扫/实际缺失分别报告；容量成功不授全市场分钟完整资格。最终独立审查及完整源码/CAS由QA交接清单绑定。
