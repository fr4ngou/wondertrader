# 跨日成交与券商查询开仓周期候选

类型：候选与部署记录。时间：2026-11-05北京时间。状态：candidate / pending-live-verification。范围：自有BrokerQueryAdapter及唯一共振策略的开仓来源接线，未新增WT框架修改。

## 实际问题及实现

09:29发现原金融Native47840仅收到9报价后插件关闭，正常停止/同账恢复后，09:35的自然行情驱动1.2.1计算、8目标setter及真实模拟成交。09:36之后原新持仓来源等待：券商完整成交包含多天，自有观察却将日期变化置error3，且本进程flat来源不支持已有新持仓重启接续。

C++观察改按日期及成交ID共同定位，保留跨日原事实、原SPI通知、容量和同日同ID冲突语义。Python正式基准路径从原库存及完整实际成交与当前P一致性核实真实零转正时间；已核原库存持续周期与缺证据分别返回。卖平再买采用已证新周期，同刻混合且可能触零保持待定，同刻后续部分成交保持cycle_id。数量和可卖始终取P，不增设持仓账本或策略归属分摊。旧无基准静态profile保持旧路径。

## 固定输入与候选

- 原生由scripts/execution_product.py及固定上游/已批准覆盖构建，work=build/td2，RESULT.json passed、25安装文件、旧二进制输入0。Standard源码仅更新清单到已提交1896bbb86e1ff7eb8c4e3eec1e4b81f451fa7d55951a711e4a85a2fda5cef573，未修改其源码行为。
- 原正式cash4源码43模块保持，新cash5仅修改execution_configured并新增execution_cycle_source，共44模块；永久入口source_closures/...cash.5/build.py，完整离线重建通过。
- cash5 Runtime wheel SHA bc65abb3cf5bed6f1fecc93f370acdcd8905eb71d5bc2d9e53bae63369dd4d56；新独立解释器runtime-service-20261105-014，原013保留。
- 新native-execution-008安装清单SHA7aac70db6e69a24d157b0d15f878768992d6fc87f08af042a21479452476ed1d；新五运行组件来自同次固定构建，旧Reader、资料、Parser与许可证保留。

## 验证与待验

独立delta审查complete。定向实际形状检查覆盖原库存持续、卖平再买、数量暂不一致、同刻混合顺序未知及同刻50至100份周期身份稳定。既有C++probe已改为同ID跨日完整查询及query/live保持，当前该旧probe引用未归仓的历史fixture，未宣称已编译运行；真实多天查询将由候选线上主链验真。

实际已保存09:35自动订单/成交，包括832806091、832806115、832806612，券商查询和观衡同源页面已见；这些证据证明切换前自然提交链已工作，不代表本候选已解决后继周期问题。

证据根E:/workspace/wondertrader-qa/unified-wt-operator-20261105-001：OPENING-PARSER-RECOVERY001、NATURAL-STRATEGY-OPENING001、NATURAL-FILLS-OPENING002、CASH5-STAGED001、cash5-wheels002/REBUILD-RESULT.json，原生build/td2/RESULT.json。先正常停止处理原活动委托，沿原prepare_transition冻结金融状态，再切新解释器/Native并实读跨日成交、周期、P和页面；原100万元基准及financial-state008保持，禁止通过重置获得就绪。

剩余风险：原行情插件早前停止的具体终态未知，当前恢复后报价与自然调度已连续推进；完整后继调仓、候选线上接续及清理仍待验证。回退保留cash4、Native007、原CURRENT、配置及金融原件，按原关闭/交接协议执行。
