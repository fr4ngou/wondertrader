# 2026-11-05 HPR合法控制拒绝与同owner续接

类型：验证记录。结果：partial。关联规格：[HPR3-R1](../specs/qmt-history-preparation.md#hpr3-r1-合法控制拒绝与原请求收束)。隔离主链通过；正式制品及实际来源由集成owner验真。

## 输入身份

永久源码为本仓库自有Host包；QMT Agent、wire、WT框架及现场配置保持原值。执行环境为CPython3.14，`-I -S -B`直接加入已有测试依赖目录，跳过其启动`.pth`；未安装或启动服务。

| 文件（Host包相对路径） | SHA256 |
|---|---|
| `control.py` | `cd848ccda9e558da64a2adcd2eb2f9558392058d10623647a622b72aa75c5769` |
| `runtime.py` | `472a1c496440ab0616d7c9c33b08242c3a3c71b4e3ea29c5ddd03147fc30a862` |
| `read_service.py` | `93678312db70286835e759bca297a4e0f96c23f31cba2160d56fa8b48c50aa9c` |
| `bulk_host_control.py` | `13de369debf83dfeda866bc0095373a3ef8e4bdc829aa87ff5b3ce8868a2aac6` |

测试入口`tests/integration/qmt_shm_reconnect/test_control_rejection.py`，SHA256为`cac77cb26b4ff324d56a6a047e34b04a8b5d5ff7bfe6dd0f758ac4b93475d15b`。

## 步骤与观察

| 步骤 | 观察 | 结论 |
|---|---|---|
| 新入口pytest执行，关闭pytest缓存 | 11项通过，包含固定错误码子用例 | 同owner主链及必要异常通过 |
| 同一HostControlLoop/ControlPeer/AgentControlLoop/真实域线程/SQLite Journal | 首个准入拒绝沿原ID保存preparation_unknown，result_binding为空；第二请求原生结果沿原绑定完整保存；两次ACK退休，域线程关闭 | 单次拒绝不停止后继请求，也不伪造原生结果 |
| 域队列背压、本地not_sent先退休 | 原回复仅take一次，原持久截止及计数不变，未再发送原ID | 运输退休不提前释放持久责任 |
| 拒绝结果提交前/提交后TimeoutError | 原请求仍归原owner；关闭核原Journal完成中断/确认原终态，不补ACK、不重新调用来源 | 恢复与未知责任保持 |
| 待提交拒绝关闭及同根重开 | 第一原ID保持未知终态，下一次领取只选后继请求 | 原未知请求不自动重发 |
| 错正文SHA、已有原生终态、非法wire错误码 | 错身份拒绝；原生终态原值保持；真正协议损坏仍抛ProtocolError | 身份与协议边界保持 |
| Bulk关闭中的普通read回复 | 复用同一拒绝持久入口，未把None当SDK结果 | 共享调用者同步 |
| 原`ReadFinishDeadlineControlTests`类按AST原样单独执行 | 8项通过；原整文件其它类依赖未归仓fixture，没有授整文件通过资格 | 原正常结果、原D、坏载荷及关闭责任回归通过 |
| 四份Host源码AST语法检查 | 通过 | 无语法错误 |

## 证明范围

实际执行了内存packet交换、原peer语法/顺序/ACK、原Host域任务及真实SQLite事务/重开。原下载队列使用明确替身，不调用QMT、不发送网络请求、不修改已有运行实例。最近拒绝诊断是一个有界纯值，字段固定且副本隔离；原公开ready/closed和HTTP/wire保持。

## 限制与后继

尚需独立源码审查、同批SDK制品/配对构建及正式Host采用。真实QMT历史准备、实际长驻来源、跨正式版本身份与现场恢复由Root统一验真。本轮未做发布或线上操作；原失败控制代及未知请求保持。
