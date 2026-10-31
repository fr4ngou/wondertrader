# 普通安装按声明选择依赖

类型：开发验证。日期：2026-10-29。状态：安装模块及根组合验收完成；当前新App的实际运行验收另列。

## 根因与实现

旧工具固定登记历史App包，当前唯一策略依赖已变为五个本地发行，固定名单会遗漏在用的strategy-v1并带入退役策略。安装器现在从App或Host角色入口读取项目声明，沿本地依赖递归选包；显式选择的可选依赖沿同一条路径进入指纹、构建、锁文件及安装。标准公共依赖继续由uv解析。Host补充已有Agent依赖的相对源码声明，版本和运行接口保持。

账户构建也消费同一source_inputs接口，避免安装选择与源码指纹各自维护名单。其实际冻结、回归及独立审查见[账户构建依赖同源](2026-10-29-account-input-closure.md)。

## 实际安装与搬迁

最终工作根为build/guanheng-local-dependency-closure-001。冻结App为0.1.0a26、strategy-v1为0.1.0a6，正式策略为1.1.2。默认App实际普通安装20个发行，包含观察采集的App为29个发行，独立Host为15个发行；host-only输入树不含App源码。旧冻结输入的安装兼容单独通过。

每个环境均核对wheel、METADATA、RECORD及导入归属，并通过pip check。ZIP包含321个固定文件，解压到新根后仅使用包内wheel和锁，离线安装App29发行及Host15发行，唯一正式策略1.1.2可由已安装包读取。Python3.12 x64、固定uv及pip是已登记的外部工具前置。

最终ZIP为guanheng-local-dependency-closure-002.zip，SHA256为d5a334d7b0583c181371472f0176bda23742b6ce3ff676082bf9756d47769abe；MANIFEST为32db1114e789de2b4344db7351c25e2e93a59d9b13b22b3f6dfd6845612f48d3。37项安装边界、独立full及delta审查通过，Standards/Spec complete，剩余发现0。各轮外层均exit0、无强制终止，进程树、读管道、线程和资源完整收束。

## 主会话集成与范围

主会话实际重核交付中的38项源码和原件，摘要全部一致。DELIVERY.json的SHA256为cea346e05303498d14ccf6c0e37296d4a64af166c9d64733f692f7dadf025363；ROOT-INTEGRATION-001.json登记本次限定接受，原交付与历史原件保留。

该候选证明普通安装、依赖选择和搬迁能力。真实OS目录链接创建资格仍unknown，已完成对应路径模型验证。App/Host实际业务运行、完整账户和策略周期、升级回退及生产发布按各模块继续验收。

并行App已更新为a27、strategy-v1为a7。主会话已沿当前五份项目声明离线同步锁，SHA256为0399f35f6492c0090c3dad2639844814f588efd109bc806c3aa0a60c6ee0f6f9，并冻结到build/guanheng-app-a27-install-001/source001；该候选正在重新安装并读取真实历史接口。a26的安装结果只归属其冻结输入。

本次未启动QMT连接、账户或交易请求，未修改WT框架、现有实例或跨夜采集，未切换生产。

## a27实际历史读取后继

build/guanheng-app-a27-install-001已沿冻结245份输入完成全离线普通安装：App29发行、Host15发行，METADATA/RECORD、pip check及唯一正式1.1.2归属通过。该轮只安装Host。

history002实际启动已安装App，沿统一R7历史组件、SDK0.15和HTTP图表入口读取三证券各五根真实分钟及八只正式ETF各五根真实日线；原Helper/来源六字段逐值核对通过。主会话独立重核245份冻结文件无漂移，并重新比较11组共55根SDK与HTTP的上海日期、OHLCV，全部一致。真实源文件保持，未启动补齐、Writer或实时QMT连接。

history002外层36.485秒exit0，无强制终止，进程树、双EOF、读线程及资源完整关闭；App/历史端口关闭，App shutdown完成、Reader线程为0、历史owner为closed。实际加载的原生历史DLL身份已记录。主会话复核固定于build/guanheng-app-a27-root-acceptance-001/RESULT.json；该结果授予本冻结安装与历史HTTP链资格。浏览器页面、完整实时策略、统一升级回退及生产资格分别沿B/C与全系统继续。

主会话随后离线重核全部11组元数据，对照335商店目录中实际选中的四份原导入收据，验证其摘要、原profile、来源四字段、逐证券文件身份及App投影。价格/量额单位、数据集、复权状态、时区、值/时间语义均一致；日线为CNY/lot/unknown，分钟为unknown/unknown/unknown，覆盖保持Unknown。新增METADATA-001.json固定结果，未新增业务请求或改变单位资格。a27候选独立QA/打包审查的四项校验缺口已全部修正并通过delta，原报告保留。

## a27最终交付与根接受

最终SOURCE-FINAL.json固定18份本轮QA/工具源，产品245输入保持。REVIEW-DELTA-001.json的SHA256为78427b87b8edaea131e096e6b800ad22808f7e15655977432e2efb4d0a0ab838，两轴complete、未处理发现0。修正只加强包内精确文件集合、原profile/DSB语义、空/不支持/失败区别及交付审查身份；复用已通过真实业务请求，未重复实机。

最终ZIP为guanheng-app-a27-install-002.zip，60,862,733字节，SHA256为1abb5f0950d7186cc2da7dfd6635fc3ec497c20279004b1c3d275fd412a4e39f；459份受管内容的MANIFEST摘要为f3cee31c392f63750a9492bac8309b3a2a4b4eaa2e80350fa2d6401b546efee0。ZIP新根App29/Host15普通安装与正常关闭通过。

DELIVERY.json的SHA256为f3fc93b82dea2bc9aee7a425171cf66c713474f7b351733013bfac008b4a541f。root实际核49项最终源码/原件及ZIP，全部一致，ROOT-INTEGRATION-001.json登记限定接受；已将完整交付交C用于原页面/配置/升级链。新SRI系统整包安装沿[独立规格](../specs/system-runtime-installation.md)继续，未将本次后端安装结果扩成完整M3或实盘资格。
