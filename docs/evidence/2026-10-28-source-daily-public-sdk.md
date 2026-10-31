# 统一源日线SDK及混合周期服务

日期：2026-10-28。范围：[DSH4](../specs/qmt-source-daily-history.md#dsh4-统一公开查询与目录)。首策略9ETF真实原生日线已验，本轮完成独立SDK/HTTP公开读取和原分钟兼容。

## 实现与职责

SDK0.14.0新增history.source-daily-query和source_daily_history_query。请求为有效YYYYMMDD日期闭区间；成功响应以date表示交易日期并携带period1d/source_date。原分钟请求/响应形状保持。显式source-catalog模式在同一Reader/LRU注册证券+周期，允许不同QMT来源实例；能力页使用确定性目录身份，查询逐次核原收据SHA、实际Reader source和period。旧source-store(s)继续仅schema2和原同实例限制。

服务与SMP继续创建线程独占，沿原控制/Job生命周期；没有新增读取池、数据库、QMT终端文件/网络调用或交易行为。日线源日期不提升为闭合/可获知资格，量价原单位unknown保持。

## 固定制品

- GuanhengMarket：build/source-market-package-039/GuanhengMarket.zip，147文件，SHA256 42a7ad28d7611998a1f3e8828b85a2dac45098a6889f6f52b16edc2181468824；INPUTS SHA256 3b39194842bb7b50100f10d6cbe2d1d650fc6bb30fb6a05a42bd8acdec6c6463。原生二进制沿029复用且逐文件保持，没有框架源码修改。
- 独立wheel：build/daily-sdk-wheel-042/guanheng_market_client-0.14.0-py3-none-any.whl，SHA256 6776ff88339022c5424a182352966f3cd97a654d598ed3243ed04f17cda55e92。离线固定Flit构建，源码前后/元数据/许可证完整校验，基础运行依赖为空。该wheel全部SDK源码SHA与039安装目录一致。

## 真实主链

043原件在build/guanheng-workspace/daily-wheel-real-main-20261028-043，业务结果build/daily-wheel-real-main-043/VERIFIED.json。原固定240秒总预算，实际20.422秒exit0，非强停、整树/EOF/线程join/资源关闭均确认；监听端口关闭。测试先逐文件核ZIP并搬迁，再从固定SHA的实际wheel导入客户端（核模块路径），SMP子进程-S禁用site-packages。

同一服务注册原335分钟store及1个真实日线store，5个股票/ETF分钟样本与9ETF7739日线均取得。全部日线日期/OHLC/volume/amount既与原来源JSON一致，也逐行与同一DSB的直接NativeHistory回读一致，来源身份及单位/语义/版本一致；510300同服务两周期读取，日线后重新读分钟的bars和metadata不变。分钟样本亦和原Reader逐字段一致。返回日期/量价/未知状态保持，无数据补造。

040使用组件内SDK的初次同服务主链20.578秒exit0；其日线数值与source JSON对照，直接Reader只核metadata。独审指出该范围不足后，043补全部日期/值的直接Reader对照、同ETF交集与跨周期重读，并改用独立wheel，原040保留原资格。

044受影响服务/SDK回归73项，通过67、原生环境依赖缺失跳过6；已另有043真实原生主链。包括旧分钟注册、精确目录生成、重复键、日线协议/非法日期、跨周期LRU和HTTP/TLS截止，4.984秒exit0，全部资源关闭。首次041的51项包含被导入的fixture TestCase重复发现，已收敛模块别名；正式044没有该重复。独立full/delta源码审查无未解决P1/P2，QA遗漏已补齐，审查和实际运行资格分别记录。

## 继续与边界

统一组件及SDK作为固定候选交接记录在[模块A](../migration/module-a-delivery.md)。App依赖/锁及产品页面由C拥有；实际App与B业务核组合仍须同候选验收。当前没有活动测试监听器或长期生产切换；真实盘中时效、完整分钟、ETF尾部/内部日历、原API填充语义和单位/可获知时刻、按需补齐仍在模块A待验项。源数据读取和存储通过不等于实盘就绪。
