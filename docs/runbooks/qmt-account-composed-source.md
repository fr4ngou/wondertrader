# 生成带只读账户连接的共享内存正文

适用模块：[同一 QMT 正文的只读账户连接](../modules/qmt-account-composed-source.md)。准备工作在终端外使用已安装 Host 解释器完成。配对材料、环境凭据、生成正文保存在本机受控私有目录。

## 准备与核验

1. 沿原只读 Host 手册生成 resident read pair，保留原账户绑定、read v3 policy 和运行额度。它与交易产品使用同一安装及 Host 解释器。
2. 沿交易产品手册准备原交易配置、SDK 元数据、CPython 许可证及 QST/HPR market 配置。各 owner 使用同一个 Windows 登录会话、不同内存名称和不同 IPC 秘密。
3. 使用下面的正式 CLI 生成新配对。路径是示例，替换为该实例的实际受控材料；原凭据通过各配置声明的环境变量提供。

```powershell
& '<Host安装>/venv/Scripts/python.exe' -I -B -m guanheng_qmt_shm.trade_cli pair `
  --config '<私有目录>/trade-config.json' `
  --memory-sdk-manifest '<私有目录>/sdk.json' `
  --stdlib-license '<私有目录>/CPYTHON-LICENSE.txt' `
  --reconnect-seconds 0.2 `
  --market-config '<私有目录>/market.json' `
  --account-read-pair '<私有目录>/read-pair' `
  --output '<私有目录>/combined-pair'
```

4. 用同一安装执行 `trade_cli verify --directory <combined-pair> --installed-agent <实际安装的agent包目录>`。核验成功后，沿原策略更新流程把 `strategy.py` 的完整正文部署到同一个 QMT 策略。策略运行期间全部通过内存加载和共享内存通信。
5. WT 独立运行配置使用原 HPR `host`、新增可选 `trade_host=qmt_trade`、可选 `account_host=qmt_read`。`account_host` descriptor 指向步骤 1 的原 read pair；`trade_host` descriptor 指向完整组合 pair。它们与历史和采集组件由 WT 管理。

## 启动与停止

使用独立 WT 安装入口一次启动配置声明的组件。原只读消费者连接 `account_host` 的只读接口，交易插件沿交易 Host。观衡消费者退出时保留 WT owner。以各原健康/绑定查询确认认证；WT `ready` 本身只证明组件管理入口已启动。

一个策略正文只注册一个 timer 和一个 QST 订阅。只读账户的连接变化由其原重连 owner 处理。正常停止使用原 WT 配置及控制身份，逆依赖关闭各进程；现场更新和 QMT 策略启停由同一操作员协调。

## 升级、故障和回退

升级到新安装后重新生成、核验私有配对，保留原受控材料。配对中的原安装路径、解释器、源码 SHA、依赖闭包、原 settings 和正文必须一致。回退时恢复整套旧安装及配对正文，按原生命周期停止新实例后切换。

交易结果未知时保留原命令身份、Journal 和来源证据。先核查原命令及券商事实，继续沿原恢复规则处理。停止或进程退出属于资源结果，订单结果需单独核实。

出现交易 Host 超时故障时，保留原私有 failure/closed/Journal，并区分已完成、仍在派发和结果未知的原命令。专项 QA 的诊断包装可记录固定异常类别、原源码帧和有限时序，不记录异常正文、凭据或财务值。后继运行成功与原故障定位分别记录。

## 加入分析读取

先沿[QAS 规格](../specs/qmt-analysis-source.md)在同一 Host 安装中生成原 resident v7 pair。保持原两种分析操作、身份和预算。再在上面的交易配对命令增加：

```powershell
  --analysis-read-pair '<私有目录>/analysis-pair' `
  --source-mode strategy_tick
```

用同一安装重新执行 `trade_cli verify`；新组合应为 `qmt.trade-product-pair.v3`。把其完整 `strategy.py` 放入既有同一策略，保留原正文与配对用于回退。WT 的 `analysis_host` 指向原分析 pair，`analysis_window` 沿持续分析发布部署；交易 Host 指向新组合 pair。WT 需支持配对 v3 的正式父端组件。

正文应只有一个100ms timer和一次QST订阅。沿各原绑定确认认证后，再检查分析窗口和原 Native/Reader 消费结果；组件ready只表示托管入口已启动。兼容与权限要求见[分析扩展规格](../specs/qmt-account-composed-source.md#可选分析读取连接)。

## 同时加入批量分析

在同一安装中沿 [QAB](../specs/qmt-analysis-batch-source.md) 生成原 resident v8 pair；保留 v7 pair 供持续日线/因子消费。正式交易配对命令同时增加两个独立参数：

```powershell
  --analysis-read-pair '<私有目录>/v7-analysis-pair' `
  --analysis-batch-read-pair '<私有目录>/v8-batch-pair' `
  --source-mode strategy_tick
```

使用同一安装重新 verify，确认新组合为 `qmt.trade-product-pair.v4`，再沿受控操作流程部署其一份完整正文。各 pair 的 Windows 会话相同，认证映射和 IPC 身份各自独立。原 v7、v8 与 HPR Host 分别由各自运行 owner 管理；观衡继续只读消费。

新安装与父端组件须明确支持 v4 后才能托管该组合。原冻结 v3 配对与其旧安装保留原身份；回退使用整套旧安装及正文。真实 QMT 切换、SDK 替身和生产资格分别登记，读取成功后的日期、复权及闭合资格继续由原数据消费者核实。
