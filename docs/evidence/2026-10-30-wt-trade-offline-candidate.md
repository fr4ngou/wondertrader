# WT交易与数据离线候选安装

类型：系统候选打包、搬迁安装及主链证据。日期：2026-10-30。适用规格：[SRI](../specs/system-runtime-installation.md)、[WRI](../specs/independent-wt-runtime.md)。本候选只含WT与Host角色，观衡按独立发行维护。

## 交付及实际入口

候选使用现有system-runtime安装器，完整链为create → ZIP → 新目录解压 → 离线install → resolve → 两角色实际CLI及WT隔离检查。安装阶段不编译源码，不启动业务进程，不请求QMT来源。运行侧继续复用原生Reader/DataKit/Writer及既有已批准覆盖。

最终制品位于build/wt-trade-system-candidate-003/wt-trade-runtime001.zip，共1200个制品文件，archive SHA256为b9f3170521d4a3e5e87541aa25f05f190817a9e560fbbbcf21a3fb2860ba1527；manifest SHA256为1ed016f38b6997e324bce1fa37c90d7e83a403fd134a6b623ac8447f37db2771。交易来源为THP installation009。搬迁安装installed001的系统收据SHA256为cec6b90108e877ccbe8eb5da596a184b099648b635c357ec71fcde045e3473b9，SYSTEM-PATHS-001.json SHA256为212901f947c1e081b687430f304bf7530542af4cc2a0d405470c217dbf6ed32b。

Control422实际257.250秒exit0，无强杀；整树0、两路EOF、reader join及资源关闭，外层真实解释器、python312.dll、owner和控制器7项身份前后一致。安装120.687秒、resolve33.016秒。WT只安装运行包与市场客户端，未安装观衡、FastAPI、Uvicorn或SPA；Host的trade_cli帮助正常。

随后直接使用installed001/roles的普通安装和同候选payload/market/components运行[联合主链](2026-10-30-wt-trade-data-composition.md)main006。该实际运行覆盖Windows SHM、3.6.8正式三owner正文、SDK替身交易、HPR、原生采集和历史读取，17.532秒正常退出及完整回收。打包帮助检查与业务整链资格据不同原件分别授予。

## 原件与边界

SYSTEM-CREATE-001.json、SYSTEM-INSTALL-001.json、SYSTEM-PATHS-001.json、SYSTEM-INPUTS-001.json、SYSTEM-RESULT.json及control422原件保留；精确摘要汇总于本目录DELIVERY-001.json。先前007来源的candidate002已完成独立安装，但其业务资格受到旧main003未知异常限制，最终候选使用009，两个制品各自保留。

早期control419因QA路径替换不完整而失败，尚未生成有效候选；control420使用90秒总预算，打包超时且当次回收收据不完整，后续OS检查父子均不存在。它们保留失败资格。实际完整安装/校验耗时超过90秒，后继按整链工作量给360秒一次总预算并预留15秒回收，420失败没有被覆盖成成功。

本候选没有配置唯一策略/原生execution，没有接管现场QMT、采集或下载实例，没有真实下单/撤单或生产切换。完整观衡+WT独立升级/回退、实际账户及生产运行仍继续；该开发候选不表示系统已发布。

后继独立增量审查：build/wt-trade-data-composition-review-001/REVIEW-003.json，SHA256为0cebe6c8d09c122bb694ab4f879f2c46878f89fc017fa262825cf37db4da0419，P0–P3新增发现均0。接受本次离线安装和SDK替身联合主链开发资格；根精确接收另见候选003的ROOT-ACCEPTANCE-001.json。真实账户、唯一策略和生产资格仍未授予。
