# WT管理历史补齐与只读观察

类型：运行手册。适用范围：独立WT与HPR产品的进程接线，以及观衡只读状态。职责依据[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)及[WRI](../specs/independent-wt-runtime.md)；配对、业务请求和缓存副作用沿[HPR手册](qmt-history-preparation.md)。

## 配置与启动

先核HPR完整安装、配对清单和实际运行解释器。维护人员准备原qmt.history-preparation-process.v1部署描述及原字节SHA256，凭据留在原私有配对目录，控制根与业务目录按原产品配置。

在独立WT配置components.host中选择kind=qmt_history_preparation，填写descriptor及sha256。WT复用HistoryPreparationProcess，管理独立隐藏Host进程；同一实例host在qmt_read与qmt_history_preparation两种组合中按实际需要选择。依[独立WT手册](wt-independent-runtime.md)启动，Host先于历史、采集及执行初始化。观衡不启动此Host。

Host常驻等待QMT策略配对，来源晚于60秒仍可连接。每项业务请求继续有自己的队列、执行和往返截止；断线后沿原身份和认证协议恢复。补齐结果未知时读取原请求终态和缓存，保持同一请求ID，操作员不自动换ID重发。

## 只读观察与结果核实

观衡通过GUANHENG_WT_STATUS_FILE及对应控制ID、实例ID、配置摘要读取GET /v1/ui/wt-runtime；参数和状态含义见[WT手册](wt-independent-runtime.md)。旧App的GUANHENG_QMT_HISTORY_PREPARATION_CONFIG等进程托管配置已退出当前入口。

监听就绪表示Host进程的初始化和监听已确认，来源认证、实际缓存覆盖、数据尾部和补齐终态由原接口分别核实。WT声明组件配置错误时保留明确启动错误，观衡可独立启动并显示读取结果。页面不触发下载，补齐由WT业务入口及原HPR请求负责。

## 停止和独立升级

观衡停止仅关闭自己的读取资源。停止WT时按执行、采集、历史和Host逆序关闭；每个原owner沿首次共享截止核实子树、管道、线程和句柄。故障与资源回收分别记录，保留原目录和未决责任。

升级WT或HPR时固定安装与配对身份，在新目录验证并按原状态兼容流程交接；观衡Web包与SPA独立升级。完整组合、真实来源和生产资格分别依据实际交付证据。旧[应用托管规格](../specs/qmt-history-preparation-app.md)保留其历史身份，当前部署目标沿WRI。
