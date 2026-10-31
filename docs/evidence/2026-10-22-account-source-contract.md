# 真实QMT账户读取与范围契约核查

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

类型：真实来源只读开发验证。日期：2026-10-22。状态：现有HTTP四查询基线已读取，显式全账户范围不兼容；原生账户宿主和生产资格待验。

## 方法与隐私

所有客户端来自本仓库已安装QTS签名库及有界只读Reader，未导入或执行旧QMT工程。向现有18010请求的业务方法仅为`account.trade_detail`，账户类型stock，四个datatype为position/order/deal/account；每个操作只POST一次，遇202仅认领原ID。每操作15秒，HTTP最长5秒，响应最多8MiB；前后签名health核来源会话与代际相同。

源签名配置只在内存读取，未落盘或输出秘密。真实响应存于本地受控`build/guanheng-workspace/live-account-read-001/private/`，NTFS权限限当前用户和SYSTEM，Git忽略。公开收据只含数量、字段名、时间及摘要，不包含账户、证券、持仓数量或金额。

## 实际结果

首轮请求显式包含新协议的`scope=account`，四次HTTP200但业务`ok=false`，均为`invalid_arguments`，原因为`unknown arguments for account.trade_detail: scope`。未把HTTP成功状态当成查询成功。原服务错误字段在顶层`error_code/error_message`；首个实验脚本只看嵌套error而登记unclassified，后继诊断按原件更正，原收据与脚本快照保留。

核现有公开方法和磁盘安装适配器后，另以其两个公开参数作明确的legacy基线读取。该轮实际取得：

| datatype | 返回记录数 | 已见字段 |
|---|---:|---|
| position | 4 | m_nVolume、m_nCanUseVolume、昨仓/冻结/在途、原价/市值/盈亏等 |
| order | 0 | 本轮无字段样本 |
| deal | 0 | 本轮无字段样本 |
| account | 1 | m_dBalance、m_dAvailable、m_dCommission、m_dPositionProfit等 |

四组均HTTP200/ok=true、原request_id相符、0次重投，前后health会话/代际相同。空委托/成交只证明本次返回空，不证明全部历史委托成交或其字段兼容。该轮没有原生Adapter、账户页面或新源端策略装载。

## 根因与资格边界

现有服务接受的参数为account_type/datatype，不接受新QTS的scope。磁盘`D:/software/guoxin/python/qmt_agent/broker/adapters.py`声明调用SDK第四参数为`qmt`；新QTS规定全账户三参数调用。线上deployment_commit为空，磁盘实现与运行代码的完整谱系尚未证实，因此本轮只能授legacy字段基线，不能授完整账户范围。

新原生HTTP映射要求明确的账户观察协议及`scope=account`，其合成整链资格继续沿[NAC证据](2026-10-22-native-account-console.md)。后续须在具体安装方案下装载自有只读QTS并核SDK三参、来源身份、四组范围及真实字段；当前开发保留账户范围约束，legacy读取不作为全账户资格替代。终端未安装、重启或切换，未请求委托、撤单、下载或订阅。

后续核[迅投交易查询文档](https://dict.thinktrader.net/innerApi/trading_function.html)（2026-10-22）：三参形式不按策略区分；第四参数strategyName的过滤作用明确限于委托/成交。因此本次0委托/0成交不能推断全账户无记录，也不能反向宣称4条持仓因该参数被策略过滤。运行实现谱系、完整范围和四组真实字段仍分别验收。

[迅投常见问题](https://dict.thinktrader.net/innerApi/question_answer.html)另明确该API读取客户端缓存，缓存经柜台推送刷新。查询执行区间不等于柜台事务时点，health会话稳定不证明缓存与柜台瞬间一致。公开观察继续区分采集时间、源有效时间和未知的新鲜度；无需由本次诊断引入另一账户数据库。

脱敏诊断（外部历史/待归仓路径：`../../build/guanheng-workspace/live-account-read-001/diagnosis.json`）SHA-256为`6ede3ac35db4b11ada299c8c83d844dbf1d6c4474bf736e3221d5997f2ce6ea8`，关联两次原始收据、脚本及安装适配器摘要。原始实际数据始终留在私有目录；来源契约、字段开发验证、原生真实接线与生产分别登记。
