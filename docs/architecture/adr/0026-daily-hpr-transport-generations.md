# 日线计划与HPR通信代分别恢复

状态：accepted。适用范围：WT数据owner持有的缓存缺口计划。

日线补齐计划可以跨越通信Host的正常重启。计划与证券日期区间属于数据owner，某笔已发出请求的UUID、票据、截止和结果属于原SDK槽；整批任务固定到单个Host进程身份会使尚未发出的任务也无法继续。

数据owner保留原计划及认证anchor，只在来源路由、能力、profile、限制等业务身份完全一致时，为新的通信代保存不可变metadata。新槽使用当前认证代，已有槽使用自身原代，已完成观察直接复用。原未知责任继续原ID查询；本决策不授予重发、重置票据或替换旧槽的权限。

实现复用原RetainedReadClient与HPR执行器，恢复记录位于同一任务根。SDK协议、Source、Host与WT框架保持原实现。来源或权限变化继续拒绝，由原业务恢复流程处理。字段与验收规则见[UDI-R48](../../specs/qmt-source-daily-history.md)。
