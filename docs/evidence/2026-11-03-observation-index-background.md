# 指数观察背景更新主链

类型：真实只读来源及隔离交付记录。状态：development-qualified，现场接收由Root执行。范围沿[指数背景模块](../modules/observation-index-background.md)及[OBI5](../specs/independent-market-observation.md#obi5-独立采集与来源)。本轮保持现场current、WT/QMT/Host/Web及其它来源运行实例。

## 根因及实现

原`market.sh000001`既是来源表名，也是广度页只读指标名。采集按全局datasets是否存在来选择旧输入、拒绝替换及决定写入目标，使实际来源表在完整覆盖时仍被拒绝。改为按来源配置的tables/datasets声明选择事实所有者，先更新原源表，再沿原最终化生成只读投影。

第二个实际缺口为`source.csi_all`的2018-06-18：原观察表保有官方真实close=4380.58，原WT OHLC接口不返回该日。它只供债券模型消费同日收盘，完整OHLC要求超过消费字段。来源适配器仅投影date/close/available_at，按日期接纳实际返回并保留已核旧行及谱系；成功回执retained_dates明确列示该保留日期。其余七张OHLC/量表继续完整覆盖和单位准入，unknown量活跃度保持为空。

## 真实主链及结果

本批QA位于`E:/workspace/wondertrader-qa/observation-indices-20261103-001`，数据/源码制品位于`E:/workspace/wondertrader-data/observation-indices-20261103-001`。18148经原SDK按729自然日/最多2000根实际查询，前7表与原日期覆盖一致，中证全指2874条对原2875条仅缺上述close-only日；原响应逐件保存，不补造OHLC或改写unknown量额。

当前72组快照`d0115604a5ee80535f9a7eee402dc5c2f21ca5e14a31ad24c81b496491a8d5a8`以SQLite只读备份及18622份不可变对象物理复制到E盘。第一次原入口仍在同名投影判断处失败，原失败保留；职责修正后实际`refresh(source_ids=['wondertrader.indices'])`在52.313秒成功发布`e93f26ba537dc378e3f3605318fdafea2d6c1e9e18d712ab8e8988c63e5613db`。读取真实接口、归一化、原计算、资产登记、准入及CAS完整运行。

原Source CSI收盘中219条获得实际接口三位小数修订，日期和其它字段保持；债券模型218条csi_all_reference按原模型接续，主指标和方法不变。2018-06-18官方收盘原字节内容继续保留。其它源表原值全部保持，上证及其它7张原表日期不减少，不更改历史方法或推定首次可知时刻。

按Root追加要求，在同一隔离根只调用已修好的`chinamoney.repo`来源，20.719秒实际POST成功，接收至2026-11-02，末FR007=1.38%、FDR007=1.36%。最终候选为`5a94e1ea15f7eabce05419e94f11d665d723cdd1431a4ed651413de8b116d79b`。Root拥有回购代码及其规格差异，本模块只合并该路数据；没有重复复制72组或操作现场目录。

## 安装及页面/数据验证

固定Flit3.12.0普通wheel构建与pip无依赖目标安装完成，最终采用revision-002。发行版本保留Root现行0.1.0a94+shared.1，本候选不切换安装角色；Root后继a95沿原独立构建接收源码。最终两文件与wheel/目标安装的摘要一致，构建闭包及Root回购依赖随Source CAS分别登记。

普通wheel的App TestClient通过真实ASGI读取接口核72组目录、18个上证背景页的series与JSON导出，逐值等于源表的同日收盘；周线按source_sse_date匹配，历史覆盖外保留原记录。18项包括12个期货/基差/估值参考、3个利率/市值GDP背景及3个System C日/周背景。原广度共享基准继续沿market.sh000001读取。测试应用正常关闭；本轮没有新增常驻服务、前端改动或浏览器截图资格。

72组所有旧日期及definition_version保持。除Root回购主值和债券参考列外，指标数值分区不变；股票PB分区与其它源表保持。结果见SOURCE-DIAGNOSIS.json、MAIN-RESULT.json、REPO-RESULT.json及VERIFY-RESULT.json。

## 回归、限制及接收

实际主链之后新增4项根因回归，包含同名源表/投影、保留官方close-only日与修订、OHLC表缺日仍拒绝、收盘消费不要求量字段。普通安装定向回归11项通过。扩大到既有参考测试共15通过/1失败：原if-sh000300夹具缺少csi300_daily.reference定义，触发未修改refresh_models的KeyError；本轮保留该失败及原夹具，不修改无关公共模型。静态文档检查与精确文件结果随交付记录。

Root接收前核现场expected-current；已变化时在最新快照重放指数和回购两路，保持财务、T2108等后继事实。来源成功、当前完整日线、历史close-only缺口分别登记；此候选不授WT原生缺日补齐、自然开市持续运行、现场切换或实际浏览器渲染资格。新增模块和本证据的精确索引行随交付提供，索引及CURRENT/NOW由Root维护。
