# Native读取来源故障回归

独立合成验收。沿真实Host/HMAC、WinSHM、Standard与Native主入口核故障文件。账户固定为测试SYNTHETIC，三个惰性依赖仅提供普通插件接口，全部场景金融SDK调用为零。生产配置、凭据与账户均不进入本入口。

`run_native_source.py`显式接收`--source`、`--legacy-fixtures`、`--candidate-app`、`--toolchain`、全新`--output`及`--scenario`。候选app为同批构建的`cmake/bin`，八个Native源码成员逐SHA核同输入闭包；工具链沿原TOOLCHAIN。既有本地执行CI统一运行四场景并保留退出/关闭及来源证据。

- `session`：认证身份和Source业务session变化，保原SourceChanged拒绝，实际failure.json的read_source为stage=2、differences=2。
- `authentication`：仅两项认证身份变化，继续完成查询、正常关闭，无failure.json。
- `stable-binding`：稳定route_epoch变化，保原拒绝，落盘stage=2、differences=64。
- `invalid-binding`：错误route_epoch在原Common边界以IoError拒绝；账户或交易读取先到分别保留其原固定错误名，不生成未经发生的Standard差异。

代理仅在Native就绪及初始四查询后改变下一代协议字段；跟进请求沿测试凭据重新认证，原UUID及账户/市场数值保持。回归证明来源比较、原API借用和Native持久链；未知金融责任沿完整执行E2E核实，P33实际截止另验。本入口不会触发生产故障以取得日志。
