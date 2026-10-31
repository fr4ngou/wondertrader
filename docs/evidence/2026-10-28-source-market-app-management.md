# 历史服务App托管与实际页面验证

类型：专项验证记录。日期：2026-10-28。要求：[SMA](../specs/source-market-app-management.md)。状态：正式父管理、真实历史/页面、异常与资源关闭已取得证据；模块C完整目标继续进行。

## 实际实现与主链

App显式加载父部署及SHA，发布SourceMarketProcess后沿原BoundedReader/绝对截止启动。新业务适配只定义部署/argv/ready/closed，ManagedLocalProcess原监督器不变。SDK连接由独立URL/token配置，父端不猜端口。页面独立展示本App持有的历史查询进程；来源数据时点、单位和覆盖由查询结果呈现。关闭沿消费者→历史服务→采集→账户Host，共用原D和各阶段预留。

001：App0.1.0a5普通wheel→搬迁A015→335个真实store→原Reader→SDK0.13→真实App HTTP→生产SPA。五证券600000.SH、000001.SZ、301718.SZ、510300.SH、159919.SZ各尾2根的OHLCV、来源content_id与A直接原生回读证据相符。页面实际绘制2000根ETF分钟线，510300显示2026-10-26 11:30，159919显示2026-10-23 15:00；原来源标签、未知单位/覆盖保留。停止服务后原卡显示已停止，图表无有效旧时点；App及服务端口、读线程与父Job均关闭。

002把来源组件升级为A最终023，147文件及ZIP摘要逐项核实，按同一产品父管理/页面重验通过。002普通wheel SHA为`25cccf2a64e0da00d1175f749c992e4cb34cf0dc54a604da48d5119b18df50db`，原件位于`build/source-market-app-002`。001旧原件保持，不把其015结果写成023验收。

## Appa6组合候选

`build/module-c-app-001`冻结44份App/元数据文件与完整前端运行源；Appa6、SDK0.13、core a6/signals a3/v2 a2/native a1/variants a3，以及uv.lock导出的带摘要public依赖，全部安装到新建Python3.12.14虚拟环境。`uv pip check`核21包通过，无共享开发site或旧QMT路径作为产品依赖。

普通Appwheel SHA为`bdbd1af09eca5987990bcb9ae072d3cc06a457bd0d10fa92dee3505ee22061c7`；完整制品摘要在该根`artifacts.json`。A023 ZIP SHA为`ffcc62a969e9c3a3ef1ed165c8f75d235408605a05e1d5a8f6f68cd1d6e0f06f`。同一App候选的`source-runtime-final/VERIFIED.json`再次证明147文件、335store、五个真实样本、来源值/标签保持、生产SPA读取/刷新/停止和资源关闭。

该候选同时接入SCW，`configuration-runtime/VERIFIED.json`及两次浏览器原件证明已安装CLI实际装配/HTTP/保存/重启及全App关闭；CLI控制QA仅以真实uvicorn.Server显式持有监听句柄来确定性停止。配置与自选在新CLI代际重开相同原根、内容和身份保留，读线程0、端口关闭、退出0。配置保存没有改变历史/回测部署或触发交易。

## 异常及审查

`build/source-market-app-001/pytest-release.log`：73项通过，覆盖默认关闭/配置与身份拒绝、端点校验、启动返回失败/抛错、实际读池排队及在途过D、后续初始化失败、source工厂失败、关闭异常继续收束、单D/各预留窗口、原Host与部分启动回归。`vitest-release.log`39项通过，覆盖状态、独立失败/恢复、未知资格和原路由；TypeScript通过。

两位独立审查者分别按规格和规范执行full/delta；补齐启动/截止行为证据、最终SHA和测试后，SMA原静态与行为缺口关闭。原001安装wheel含旧CLI的边界已明确。后继Appa6把CLI归约进一步收敛为唯一App.shutdown_complete；默认配置也拥有读池，任一owner未确认关闭返回2，全部确认返回0，避免新增owner重复维护配置字段条件。该后继及SCW共享接线按新候选继续独立full审查。

## 保留的尝试与校正

首次前端恢复测试同步取得旧失败卡后立即断言；修为等待新文本。其后一次运行45秒超时、另一次非项目5000ms预算触发懒加载超时均保留原日志；最终按项目既有15000ms测试预算与独占Vite缓存7.43秒全部通过。

Appa6初次来源窄屏检查在ECharts的ResizeObserver完成前观察到390视口/1098旧画布，记录失败，全部子进程清理。后继QA在同次总D内有限等待布局实际收束；`source-final/ready-layout.json`记录初始页面宽1135、画布1098，随后页面宽390；最终移动端截图及完整来源链通过。产品布局代码保持原样，未隐藏溢出或截断画布。

所有外层launcher记录exit0或失败原exit，以及树0/pipe EOF/join；失败未改写成功。原件在上述独占build根。浏览器图像位于会话visualizations下`source-market-app-001`、`source-market-app-002`及`module-c-app-001/source-final`，已实际查看图表及配置窄屏图像。

## 验收边界

完成的是固定A023来源候选与C实际用户入口；真实QMT实时来源、全天完整分钟、合格日线/辅助事实、B策略实时/隔离交易及完整模块C/M3/生产资格继续逐项验收。未真实下撤单、未操作QMT界面、未发布或切生产、未新增WT核心行为。
