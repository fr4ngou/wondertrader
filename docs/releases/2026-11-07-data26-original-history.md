# Data26原版长历史正式采用

类型：发布记录。状态：Data26 deployed / verified，长历史003 published / verified；原版双策略金融部署仍在验收。核对日期：2026-11-07。界面与D盘归档沿[App125发布](2026-11-07-observer125-data-update-and-d-archive.md)。

## 数据采用和日常入口

源提交`43e5d98bdaa43705393d2051f700db87b583f291`，普通安装`0.2.0a1+unified.26`，SDK20。安装目录为受控`E:/workspace/wondertrader-data/unified-daily-20261104-001/program-history26-20261107-001`；27个轮子、178个声明来源及生成入口已核同，制品清单SHA为`161feaf1a1e31891147203a1acf98f807caa6d446ce914e90f70ce76fd8b8b18`。普通安装主路径56.781秒：原Source→长历史准备→Native原价/前复权→10证券Reader；安装模块来自site-packages，HPR及发布动作均为0。该次为隔离10证券主链，完整目录采用另外核验。

原Data25服务正常停止后，沿原ServiceController adopt-bootstrap采用`daily-service016-history26/service.json`，SHA`d4dc2cf746477c9782b357902ad86e228067dbcf85b178d7e835014ea3c681f7`。稳定CURRENT和原Runtime instance保持；新日常任务目录为`D:/wt-data/daily26-20261107-001/tasks`，保留16个原请求与15个原输入的责任发现。全市场授权起点仍为20260701，原版10证券独立长窗从20190101准备；新增Source阶段共享120秒预算，普通阶段优先。历史补齐、资料、独立批读及日线四角色的后继组状态均ready。

09:00和15:30原服务循环继续负责日更与修订。新INDEX尚无自然任务完成记录；本轮没有观察下一次自然09:00，不把采用ready解释为自然定时验收。进程退出后的拉起责任沿既有服务入口，当前结果不授新的开机调度资格。

## 完整发布003

正式CURRENT字节SHA`79874fb33c816eaf6d7d099e32230749c3adc0db656b1d1e43bd79e38cad6e31`，完整快照`6ec6ab92ba84b8a47b70f7f8f5d72ee36e48a798266c87d93e0f557e11ef97a9`，日期2026-11-06。配置为D盘`resonance-original-warmup-20261107-001/native-candidate003/source.json`，SHA`6adadfc82f8984c707c8d3877dcdeac5a5c03c2667bcb3ab757afc880bd4cdf9`。

完整raw补充档7948证券、front补充档7895证券，保持后继生产者按口径选取完整目录的合同；未选证券原Native文件及元数据按SHA保留。front十个目标文件来自已由原Helper核验的新参考，其余7885个原不可变文件逐SHA复用，没有声称重新编码。旧base及53份选定旧文件前后SHA保持；003正常CAS发布，001/002局部目录和早先完整front超时尝试均保留为原证据。

10证券最后日期均为11月6日。000300/510050/510300/510500各1902行，512100为1901行，515080为1661，588000为1449，589680为408，159780为1295，159352为502。上市较晚者从实际上市日起；512100的2022-09-02份额合并停牌按官方证券例外处理，未制造价格。

## 单位、可买性与金融边界

003真实读取20个price/volume包仍标unknown。根因为原capture profile统一未知声明，数值与单位资格分别处理。固定ContextInfo API、本机包装函数和官方ETF/指数计价证据已核实，SDK21增加显式来源单位解释；Data27归档接线与新完整版本仍在验收，003原档保持原件。金额单位继续unknown。六字段核对的8只ETF完全一致；589680的low浮点尾差及11月5日amount数值差8692登记在受控原件中，旧指数混合来源整档继续保留。

总份额的2个深市缺口、融资供应商日期滞后和官方深市成交额失败仍沿原缺口事实保留。全市场补充事实完整性保持false，不填0或向前填充。

用户已确认原版另分配100万元、零初始持仓，与旧策略并行；原持仓继续归旧策略。旧策略100万元基准及现金锚点已找到，整账户可用现金与策略现金保持独立。当前金融Runtime和Native已退出，独立账户仅读服务保持；本阶段金融委托及撤单为0。

589680有原模拟柜台产品信息不存在、零成交的确定拒单记录，见[原现场](2026-11-05-source-binding-and-afternoon-recovery.md)。它的当前可成交资格尚未确认，不能把QMT有行情或Source允许解释为柜台支持。新策略的成交时点及该证券的现金保留/替代方案等待用户选择；双ctx完整调用链、原账显式扩展恢复和正式金融采用分别验收。

## 受控证据与回退

证据根`E:/workspace/wondertrader-qa/original-live-readiness-20261107-001`：`DATA26-MERGE.json`、`DATA26-INDEPENDENT003.xml`（17通过）、`DATA26-INSTALLED-MAIN001.json`、`DATA26-ADOPT.log`、`DATA26-GROUP-POSTFLIGHT002.json`、`warmup-native003/PUBLISHED.json`、`SUCCESSOR-CATALOG-CLOSURE.json`及`original-published-facts003/DIAGNOSTICS.json`。实际组状态与采用收据共同核验，准备器的production_adopted=false保留其准备时范围。

旧Data25安装、服务配置、原CURRENT发布版本、E盘档案均保留。回退沿原正常停止和显式选择，不覆写旧请求、不重置Source未知责任；数据后继采用须重新核CURRENT CAS及来源责任。D盘归档与本次数据目录继续沿用户盘位约束。
