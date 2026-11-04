# 日线批读按请求保存通信身份

状态：accepted。适用范围：日线数据owner的缓存与补齐回读。

闭合日批读可以跨通信Host重启。来源路由、权限、profile和额度属于业务来源身份；Host进程与运输代次属于每笔读取身份。整份未完成捕获固定到旧进程会阻断后续尚未发出的批次。

日线owner显式采用DailyBatchAnalysisSource。原REQUEST、BINDING和slot保持，新槽先认证当前metadata，仅在业务来源身份完全相同时使用当前通信代。每代metadata在原capture/read-generations内不可变保存；已有槽只按自身原binding恢复，未知结果继续原ID。SDK保留原校验、结果落盘和consumed确认，manifest逐批保留真实binding。

通用BatchAnalysisSource维持完整binding匹配的默认合同。日线适配复用其分片、数值验证和manifest，无新增WT框架行为或Source权限。规则见[UDI-R49](../../specs/qmt-source-daily-history.md)。
