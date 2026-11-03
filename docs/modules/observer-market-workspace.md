# 观衡行情工作区

类型：模块接口正文。职责：消费独立WT行情服务、证券目录与本机自选偏好，提供行情查看；来源采集、交易及WT生命周期由各自模块拥有。

## 用户入口

统一外壳的证券搜索支持简称、拼音和代码前缀，输入后展示目录候选；选择规范身份打开`/market?search=<symbol>`。歧义输入保留候选，不补零猜测证券。`/`聚焦搜索，D/W/M切换日/周/月；输入框、中文输入法及组合快捷键保持原行为。

默认最近60个交易日日线。日/周/月支持5、30、60个交易日及1、2、3个公历年窗口；周/月先选择日线窗口，再按自然周期聚合，首尾不完整周期保留实际覆盖。分钟与日历周期分别绘制分时价及蜡烛图。更新时间使用来源日期或时间，量单位沿metadata；未知单位保持原量值，不推定为股或手。

## 状态所有者与调用链

`SecurityAutocomplete`调用现有证券目录；`MinuteWorkspace`以规范证券、周期和范围为查询身份，调用`fetchMarketChart`及原chart HTTP入口。能力请求完成后再启动主图与自选小图，手动刷新共享门禁和来源预算。刷新失败保留同查询成功数据；更换证券或范围使用独立缓存。

自选沿原`personal-watchlist.v1`持久格式，只保存规范证券和版本。`usePersonalWatchlist`保留唯一QueryClient owner：一次保存拥有完整目标，卸载保持在途结果，迟到GET不回退较新版本，未知保存先GET核实后继续。界面以星标增减，不另建证券表或策略交易清单。

自选名称和类型来自目录，五日小图来自同证券最近五根真实日线。每行独立读取，单行缺数只影响该行；小图不插值或生成点。长名称可悬停查看全文。自选偏好更新不会改变策略交易范围。

## 文件与验证

入口为`apps/guanheng/console/src/workspace/MinuteWorkspace.tsx`、`PersonalWatchlist.tsx`、`usePersonalWatchlist.ts`、`SecurityAutocomplete.tsx`及`components/MarketCandlestickChart.tsx`。API沿[日线合同](../specs/source-daily-chart.md)，来源接线沿[日线与自然周期验收](../evidence/2026-11-02-daily-history-calendar-periods.md)。

验证包含300308.SZ与588170.SH的默认60日、5日、周/月及公历年窗口，规范搜索、自选增减与失败恢复、中文输入法、快捷键、局部失败和桌面/窄屏实际截图。源码、安装和来源数据分别记录资格。


## 保险配置季度来源

独立更新owner沿原`collection.refresh`调用`nfra_source.history`，只生产`holdings_life`及`holdings_property`；详情、列表及XLS原件经原Fetcher归档，原刷新负责合并、来源谱系和CAS发布。官方分组分别为人身险公司、财产险公司；原历史数据ID和字段不变。金额亿元、债券比重百分数，统计范围含独立和非独立账户；保险公司总计另含其他机构，不作为两个分组余额相加的校验值。详细准入及验收沿[IMO-R21](../specs/independent-market-observation.md#imo-r21-寿险与财险季度资金运用持续生产)。

数值读取的采集可选依赖为`xlrd==2.0.2`，用于官方BIFF XLS原文件，BSD许可；来源为[PyPI固定发行](https://pypi.org/project/xlrd/2.0.2/)及[上游读取说明](https://xlrd.readthedocs.io/en/latest/)。依赖只在采集适配中延迟加载，页面只读入口不加载XLS；wheel SHA登记在原`observer-runtime-registry.lock`，完整离线更新角色沿原构建流程获取该依赖。


## SGX A50日频与月报来源

原`providers.sgx`继续拥有CN产品日历史解析，官方全CN合约未平仓/当日成交及异常非整手值规则保持。该路只写`sgx_a50_daily`。同kind下显式datasets选择`sgx_a50_monthly`时进入`sgx_reports.monthly`，以独立source_id和报告游标读取公开appconfig→官网月报目录→原PDF，分别按月末持仓表、整月成交表的A50行及本期月份列取数。报告页码随PDF实际位置登记；原`basis_points`、历史首次可知时间保持未知为空。

两路使用独立游标，原日频最新日不会遮住较早月末；同一原Fetcher、内容归档、批次deadline、collection lease、CAS和调度继续拥有生命周期。月报复用采集闭包已有pypdf，构建/版本/registry保持。原档案中的历史审计与方法定义保留，当前自动生产资格由来源配置及freshness回执说明；来源实际最新期次与本机检查时间分别表达。合同及容量沿[IMO-R22](../specs/independent-market-observation.md#imo-r22-sgx-a50日频与月报持续接续)。
