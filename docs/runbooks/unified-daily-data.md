# WT统一日线角色安装、更新和回退

类型：运行手册。适用范围：独立WT数据程序、原SMP组合及外部数据根。状态：离线制品、安装及七指标整链验收通过；当前正式入口及回退保留。完整数据/身份要求见[规格](../specs/qmt-source-daily-history.md)，模块资源边界见[说明](../modules/unified-daily-data.md)。

## 构建与离线安装

永久声明`config/unified-daily-data-source.json`固定共享原模块、角色项目、工具、原生身份及基础解释器清单。构建从永久源码生成Core与SDK轮子，沿固定registry收集完整第三方wheel；原件数据和凭据保持在运行数据根。参数均使用受控绝对路径，以下变量表示调用方已核SHA的工具和输入。

```powershell
& $sourcePython -I -B scripts/unified_daily_source.py --work $newBuild --python $sourcePython --backend $flitWheel --wheelhouse $fixedWheels --native-directory $verifiedNative --seconds 600
& $sourcePython -I -B $installer --artifact $artifact --manifest-sha256 $manifestSha --destination $newProgram --python $sourcePython --seconds 600
```

`$newBuild`及`$newProgram`须不存在。安装前核对交付ZIP及ARTIFACT清单SHA；安装器校验所有成员、完整固定CPython文件清单、离线wheel哈希和依赖闭包，再确认永久原模块字节。成功安装产生INSTALLATION.json，记录实际python/pythonw、入口SHA、完整依赖和Native身份。安装操作不启动来源、WT或观衡，不修改外部数据。

固定CPython为3.12.13 x64，原文件Reader/Helper/Storage及Windows依赖沿该次制品资格。失败根及日志保留；后继安装选择另一全新程序目录。Source SDK版本与协议版本分别核对，SDK0.16支持统一日线、批量、快照、定日事实及证券资料。

## 固定外部数据配置

数据配置使用`guanheng.daily-data-service.v1`，详细字段以UDI表为准：directory拥有持久INDEX/任务；raw_store拥有原件和回执；template固定原基准、资料、事实、Native、受保护slot和publication_directory；inputs复用原HPR/批读声明，凭据来自原环境引用。cache_seed和prepared_native只复用日期/股票池/原件身份匹配的完成结果。

来源连接、Native路径及其他配置身份在持久根中固定。普通程序重装沿用同一数据配置及数据根；配置引用的旧Native程序/固定资产仍是有效依赖，回收任务须计入引用。改变来源或归档政策时按原槽/配置身份做显式迁移，保留原根和保护引用。新程序先通过真实读取、更新和关闭验收，再由Root统一采用。

首次切换保留已成功数据。先用固定的已完成版本初始化新CURRENT，再用独立入口按实际目标日接续；单轮成功要求原始缓存、事实、Native及快照身份一致，调用返回和完整覆盖分别登记。命令形状如下，日期为示例：

```text
pythonw -I -B daily_data_service.py --config <daily.json> --config-sha256 <sha256> --control-directory <root/uuid> --control-id <uuid> --once --as-of 2026-11-03
```

同任务恢复沿原目录、capture_id、slot、截止事实和已完成阶段。已有来源责任暂不可续核时保留原ID与保护区间，其他计划及新缓存继续核查。当前未出现的旧价格键保留原DSB和复权参考；来源截短旧日期时拒绝本候选，当前成功数据继续可读。

## 原WT托管组合

Root沿原SourceMarketProcess创建描述符，pythonw/entry来自安装收据，control_root为新的E盘受控目录。SMP主配置增加可选daily_update固定引用，原监听/认证合同保持。下面是虚构路径示意，SHA在准备时计算：

```json
{
  "schema": "guanheng.source-market-service.v1",
  "source_configuration": {"path": "E:/example/data/read.json", "sha256": "<read-sha256>"},
  "daily_update": {"path": "E:/example/data/daily.json", "sha256": "<daily-sha256>"},
  "listen": {"host": "127.0.0.1", "port": 18100},
  "token_env": "EXAMPLE_MARKET_TOKEN",
  "socket_timeout": 6
}
```

read.json使用source-market-current，current_file与daily.template.publication_directory/CURRENT.json相同。ready要求生产者实际取得租约；HTTP和生产各用自己的线程/资源。日常09:00处理前日最近闭合交易日，全天固定同一日目标；显式手动as-of另行选择日期。未配置daily_update时沿原读服务。

停止使用原SMP stop.json及原单调截止，父WT owner确认进程树、EOF和线程关闭。数据线程独有closed证明其owner退出，SMP成功closed还要求Reader及数据线程均关闭。父Job处理不可协作硬阻塞，Source/QMT外部业务责任继续保持原身份。

## 验收与回退

安装后检查沪深北股票、ETF、指数的实际首尾、数值、单位和价格口径；单/批量绑定同一snapshot_id。新价只从同一WT入口读取，原生归档及历史来源分别保持。观衡采用新wt_breadth/wt_t2108来源配置后，生成最新可用交易日七项结果，并通过独立只读API逐项核同同一观察快照。

程序更新先部署新目录，保留旧程序、原数据和运行描述符。数据回退沿原GenerationPublisher锁和expected_current_sha256采用已保留不可变配置；重新启动原入口后核对其数据日期、Source版本和实际查询。程序切换、数据采用和生产发布分别登记。来源价格冲突、未知单位/因子、覆盖不足和未执行自然新日的范围沿交付HANDOFF明确记录。
