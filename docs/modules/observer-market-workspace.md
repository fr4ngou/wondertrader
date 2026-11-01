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
