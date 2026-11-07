# 2026-11-08 观衡128 自选恢复

状态 verified。观衡 `0.1.0a128+watchlist.1` 由源码 `e9c723f758f06db6ac713dfaac3b57bc3ac5e743` 构建，发行标签 `deploy/observer128-watchlist-20261108-001`。正式入口沿用 `127.0.0.1:18143/market`。ZIP SHA256 为 `9e1bb5d851b20975933a85b96e79c2dcf21e9f0269a1c1593b2a17b8468163f2`。

## 根因与恢复

策略观察历史沿原自选设置写入 SQLite 数据库及独占锁，破坏了[自选专用目录的准入契约](../specs/personal-watchlist.md)，后继 Web 读取自选返回 503。现使用独立历史配置并在取历史锁之前拒绝路径重叠。正式目录迁移沿[Web 手册](../runbooks/observer-runtime.md#从共用目录迁移策略观察历史)，只停止并启动观衡 Web。自选文档保留原字节，策略历史库和锁原件迁往专用目录，迁移前副本保存在原受控配置目录旁。

## 验证

- 独立 Web 用原数据副本先行验收。正式 Web 正常关闭旧代后再迁移，启动后在原端口读回同一列表 ID、版本 5、原顺序的 4 项，自选可编辑。
- 迁移前后 SQLite 完整性检查通过。3 条日观察、220 条成交逐行等值；新 Web 已持有独立目录历史锁。
- 24 项相关生命周期与观察回归、本地软件 CI、离线制品校验及普通安装依赖检查通过。合入收据在 `D:/wt-build/observer-watchlist-ci-20261108-002/RESULT.json`，正式收据在 `D:/wt-build/observer-watchlist-recovery-20261108-001/FORMAL-RELEASE.json`。
- 回退沿迁移手册保留最新历史库和自选文档。旧版重新共用目录时会重现原自选降级。
