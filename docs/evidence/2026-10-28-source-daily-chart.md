# App来源日线图表整链

类型：开发及独立安装验证。状态：done（只读日线切片）；完整模块C继续in-progress，生产发布与真实交易未执行。要求沿[来源日线图表](../specs/source-daily-chart.md)，A来源沿[统一SDK](2026-10-28-source-daily-public-sdk.md)。

## 根因与正确实现

A已提供原生day DSB和SDK0.14公开接口，App旧入口仍对1d返回501，页面也只有分钟周期。Appa7沿原读取池及绝对截止调用source_daily_history_query，复用SDK封闭协议校验和原OHLC模型；schema1.6显式绑定1d/source_date、上海零点日期标签、原值/未知单位及Unknown覆盖。分钟1.4/1.5保持各自语义，来源分钟5m聚合继续等待分钟边界资格。

行情页增加日线选择，复用证券、自选、截止查询、主动刷新及图表组件。日期按上海交易日显示，洛杉矶浏览器也保持同一日期；读取中或失败时隐藏旧图和旧末日期。策略目录继续只读名称、简介与版本。无新增行情缓存、聚合、读取池、配置写或交易动作。

## 固定输入与身份

- App wheel：`build/source-daily-chart-001/app-wheel/guanheng_app-0.1.0a7-py3-none-any.whl`，SHA256 `845f0fd3d56e79336d9e949abd2cef77779ad7f4e5de484679bfa62a16d2d81c`。46个构建输入、源码副本及摘要在同目录app-source/和app-source-sha256.json；随后README作日线操作说明更新，运行代码与pyproject保持构建原字节。
- SDK042：`guanheng_market_client-0.14.0-py3-none-any.whl`，SHA256 `6776ff88339022c5424a182352966f3cd97a654d598ed3243ed04f17cda55e92`。App精确依赖与uv.lock同步，公开依赖按锁导出摘要安装。
- 数据039：`build/source-market-package-039/GuanhengMarket.zip`，SHA256 `42a7ad28d7611998a1f3e8828b85a2dac45098a6889f6f52b16edc2181468824`。解压后逐个核INSTALLATION147文件，受管子进程使用原安装代码；来源注册335分钟store＋1日线store，配置沿A043原收据。
- 纯包采用strategy-configuration-packages-002的corea6/signalsa3/v2a2/variantsa3及固定nativea1，全部安装前核SHA；完整依赖制品清单为dependency-artifacts.json。fresh Python3.12.14环境21包pipcheck通过，运行与SDK模块实际路径均在该新环境，无旧QMT导入。

## 实际主链

原件根`build/source-daily-chart-001`。所有驱动复用native.run，创建期隐藏Job、单一有限截止、输出上限及资源确认；integration-result.json记录总耗时51.469秒，exit0，根/整树/EOF/join正常。

Appa7安装→生产SPA→正式App路由→SMP039→原生Reader/day DSB→SDK042→1.6投影；App统一拥有并关闭来源进程。runtime/VERIFIED.json保存9ETF共7739条全部日期/OHLCV逐值与A043原件一致，content_id、来源单位及覆盖一致；A043已逐行核对直接原生Reader，C复用该固定输入证明。5只股票/ETF分钟样本亦逐字段保持，跨周期读取无串线。

| 证券 | 日线数 | 末来源交易日 |
|---|---:|---|
| 510300.SH | 1205 | 2026-10-23 |
| 515080.SH | 1149 | 2026-10-23 |
| 588000.SH | 937 | 2026-10-26 |
| 589680.SH | 384 | 2026-09-28 |
| 159780.SZ | 783 | 2026-10-23 |
| 510050.SH | 763 | 2026-10-23 |
| 512100.SH | 917 | 2026-10-23 |
| 510500.SH | 1205 | 2026-10-23 |
| 589000.SH | 396 | 2026-10-23 |

## 浏览器与回归

Browser plugin not available，沿已有Playwright和安装Edge验证真实生产SPA。实际URL为本轮随机回环端口63870，结束时已关闭；视口1440×1050与390×844，浏览器时区America/Los_Angeles。

| 检查 | 结果与原件 |
|---|---|
| 页面身份/非空/框架覆盖/控制台 | 正确行情主体和真实图表，四阶段错误数组为空；runtime/*-browser.json |
| 交互 | 系统状态刷新→分钟→日线→9/28截止→清空恢复10/23；全部GET |
| 实际停止 | 来源owner正常关闭后，分钟/日线均隐藏旧图及末日期；stopped/daily-stopped原件 |
| 时间和布局 | 上海来源日期在LA浏览器保持；390px scrollWidth390，无横向溢出；daily-layout.json |
| 截图 | daily-market.png、daily-mobile.png及停止截图，根为本会话visualizations/source-daily-chart-001，桌面/手机均已人工查看 |
| 日线/分钟主组 | build/source-daily-chart-backend-004：66日线＋36分钟，102通过；复用SDK校验、空/错误/恢复、超时/关闭及分钟兼容 |
| 公共App/来源owner | 最终backend.log/pytest.xml为124通过/1跳过，含新增日线及公共App生命周期；与102主组重叠，分别登记 |
| 前端 | 4文件31通过，含日线、日期、自选及独立壳；TypeScript、生产构建和入口可达分块检查通过 |
| 新环境纯包 | 原36项纯包回归通过，模块位置均来自fresh安装；pure-installed.json |
| 安装后原配置P2回归 | 实际CLI两代，65/128个emoji名称经HTTP校验/保存，孤立代理422且store不变，同根重启保留；configuration-installed/VERIFIED.json，参数页面保持卸载 |
| 关闭 | App shutdown_complete，两个读取池线程0，来源owner closed/pendingfalse/forcedfalse，App和来源监听关闭 |

两名独立审查者分别完成规格full和规范full，已核固定wheel/源身份、安装原件及浏览器证据，均无未解决P级问题。源码和审查摘要随本根交付清单冻结。最终文档检查沿project.py check。

## 实际范围与下一步

来源日线读取和资料展示已接通。源单位仍unknown、内部日历覆盖仍Unknown，末日期如表；00:00仅标记来源交易日。闭合知晓、实时来源/辅助事实、合格执行价格和数量模型仍由A/B合同提供，当前证据不提升策略或实盘准入。

完整M1的历史→真实同核BT→正式产品隔离目标/委托/撤单→页面结果仍待B正式桥及来源资格组合；全策略版本、比较报告、独立观察、统一安装/升级回退及操作手册继续。当前未向生产切换或下撤真实委托，模块目标保持active。
