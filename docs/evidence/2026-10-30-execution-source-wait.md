# 完整WT等待晚到QMT来源

类型：开发集成证据。日期：2026-10-30。规格：[WRI](../specs/independent-wt-runtime.md)。范围：自有运行装配、普通离线安装及SDK替身；真实QMT和生产切换分别验收。

## 根因与实现

固定A5七组件在没有启动来源的`baseline001`中，执行初始化失败并带动整套WT退出；原始6865输入前后相同、SDK委托0，外层12.625秒exit1且物理资源完整回收。装配直接启动了依赖来源的原生交易初始化，Host本身常驻等待不足以覆盖整个配置。

自有`Runtime`增加显式`components.execution.wait_for_source=true`，默认false保留原执行工厂路径。`SourceWaitingExecution`先持有本地等待线程，只GET原交易Host的认证/通道状态，来源晚到后按原预算只启动一次原执行owner。`execution_ready`和来源等待阶段单独发布；原金融逻辑、Journal、QMT正文及WT框架均保持。读取、启动和关闭分别沿原截止，等待没有60秒配对窗口，故障不自动重启交易进程或重发委托。

独立full审查在A7发现HTTP协议异常被归入暂时断线。已安装A7的真实本地非法HTTP状态行回归实际失败；后继A8仅将异常分类收窄为OSError连接/超时分支，其余HTTP协议异常形成`source_wait_failed`。旧full报告与红例保留，后继delta单列。

## 最终普通安装与实际主链

证据根`build/root-source-wait-001`。A8位于`package003/installation001`，安装manifest SHA `a4ae8ac41236fc74de48dc8b714067eef16fab2d8c12396c058c51c0b720a250`。从固定A5源复制，叠加两份自有模块及唯一发行版本，196源冻结；两模块与实际安装逐字相同。

`late004`通过同一WT七组件→晚于65秒才启动同正文SDK来源→原1.1.2策略八目标→原股票执行器/Trader→WinSHM→SDK单笔卖出→后继NAP→独立a45 HTTP。外层135.531秒exit0，6867输入前后相同，全部Job树0、管道EOF、线程join及资源关闭，无forced。等待时本地WT就绪，原生执行PID为空、`execution_ready=false`；来源接入后才初始化执行。App关闭后WT继续发布，WT关闭后独立App保留最后成功结果。

账户原值沿原`audit.py`在关闭后的immutable Journal只读核对，141项事实、63个ABI槽及浮点位一致，不增券商查询。源码与已安装A8的默认装配、晚来源、认证拒绝、协议错误、等待前停止及启动中停止共19项回归通过。

A7同组合`stop001`在来源完全未启动时正常停止，9.875秒exit0，原生执行PID空、SDK委托/撤单0、全部资源关闭。该正常503等待及关闭路径未受A8协议错误分类影响；A8安装停止回归已重跑，复用资格由后继delta核实。

## 制品与验收边界

后继A8系统ZIP及异根离线安装沿原SRI工具生成，材料和实际结果在`release002`。ZIP为`wt-source-wait-a8.zip`，1390成员，SHA `a3a85004174d9866664f1bbb30417e00de7ea0e787957d6dd134b1e74e625fd5`；manifest SHA `2445bbd22e623f07fe3a94821acaa317a44312ca821793ace187ff4bc914a7f9`。离线安装已成功，安装SHA `8773fb3c228129b220b08bcd91bec3b325eb083858bd43f20603a8f09859f41c`，host/wt两角色、execution/qmt_data_v2两原生组件及无SPA保持。

原300秒打包驱动在安装完成后给resolve仅余37.312秒，该只读检查超时；该批次保持失败结论。核实原解析进程已退出后，在同一已提交安装执行独立240秒只读postflight，40.532秒通过，未重跑安装或启动业务。搬迁后实际导入A8及新配置成功，模块SHA与最终源码一致，环境无观衡/FastAPI。两段证据证明离线安装与独立后检通过，未授原300秒一体预算通过。

原失败的QA准备和release001清单路径错误均在启动业务前拒绝，原记录保持，未覆盖旧候选或活动进程。

本轮策略行情使用原synthetic Parser/Reader feed，QST全市场流在同一WT内并行接收；新分钟持久化和自然归档沿各自证据，本轮不授予该资格。整套重启恢复仍由执行模块继续定位：原`stage=trader`包含就绪后的恢复检查，当前不能仅凭此字段确定具体失败步骤。真实QMT整套、模拟账户真实调用及生产运行继续待验。

完整目标active；本轮没有真实QMT操作、真实委托/撤单或新增WT框架修改。最终独立delta SHA `d8bafdcc06cdffa2b9a4740f3e6372ea1f72daa549f5f92b7ef9552e99b6de0b`，原P2关闭、开放P0–P3为0，原full按未变化范围复用。根核13源码/规则、4安装镜像及原始运行、审计和离线制品后，以`ROOT-ACCEPTANCE-001.json`接收本模块限定范围。
