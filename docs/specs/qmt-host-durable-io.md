# QMT Host 通信记录的持久 I/O

类型：唯一最终规格。适用范围：自有 Host 的原通信 Journal。本文补充[QST](qmt-shm-trading.md)与[读责任回收](qmt-read-retirement.md)的存储执行，不改变其业务和 wire。

## DIO1 同一 owner 的持久存储

原 OS 文件 owner 与原事务锁共同拥有一个 SQLite 连接。该连接在 owner 生命周期内复用；所有线程仍沿原锁串行使用，事务结束后不关闭连接。关闭先等待原事务，再实际关闭连接并释放原 owner。任何连接/提交/回滚/关闭失败向原调用者传播，保持原未确认责任。

连接使用 SQLite WAL 日志与 synchronous=FULL；逐事务成功必须等待原 COMMIT 返回。WAL 只改变物理日志组织，原 queued、dispatching、结果、消费和事件前沿的 SQL 及提交边界保持。默认自动 checkpoint 保持1000页，正常最后连接关闭由 SQLite 完成其收尾；不新增线程、定时任务、另一个库或业务缓存。运行中的数据库及其 `-wal`/`-shm` 共同属于原通信资料，备份须沿 SQLite 一致快照或先正常关闭；不得只复制活动主文件。

旧 rollback 数据库在取得原独占 owner 后由 SQLite 正式切换日志模式，表、原记录及身份保留。日志模式或 FULL 设置无法确认时初始化失败；没有静默降同步或内存代替。旧 Host 的表/身份与未知处理合同保持，回退按固定制品和完整数据库资料验证。

## DIO2 原截止与持久性

原锁等待、SQLite busy 等待、SQL 与 COMMIT 共用调用者首次绝对截止；每次事务只按剩余时间设置 busy_timeout，最大仍为原1秒。提交前超期回滚；提交已开始后超期保留实际提交结果及原 owner/未知事实，上层不授源ACK或成功应答。正常读取的原同锁快照和全部大小/条数准入保持。

受理持久化先于来源派发与受理成功应答；dispatching 持久化先于外发；完整原结果持久先于源ACK；consumed 先持久化再成功应答，责任释放继续同时要求原票据结束及原业务证据准入。重复ID、同源原字节、查不到不等于未执行、unknown不重发、命令/事件不删除的合同保持。

## DIO3 验收

以原成功/失败字节核 POST→原ID GET→consumed，48查询负载保持数量与全部字段；核原同一目录重开、提交前/后失败、突发退出与未知保留、容量及有界关闭。再沿 B 原非空库存、三轮目标/现金、SDK实际成交和同根恢复主链，保持65/120/70/600及所有原期限。微基准、普通安装、完整SDK、真实QMT及生产资格分别记录。

官方语义依据：[SQLite WAL](https://www.sqlite.org/wal.html)、[synchronous](https://www.sqlite.org/pragma.html#pragma_synchronous)。FULL WAL逐事务同步，默认checkpoint与最后连接关闭仍有额外I/O；本模块不承诺任意磁盘负载下固定时延。
