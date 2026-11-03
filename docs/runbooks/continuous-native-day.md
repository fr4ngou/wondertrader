# 持续日线、指数采集与动态历史

类型：运行手册。适用范围：独立WT原采集及统一历史组件。合同沿[CNH-R6](../specs/collected-native-history.md#cnh-r6-原生日线持续落盘与指数动态尾部)，当前候选结果见[隔离证据](../evidence/2026-11-03-continuous-native-day.md)。现场启停及Source2修改由Root统一执行。

## 原生链与配置

完整GH的原QST订阅→Receiver→DataKit→同步Writer→StateMonitor收盘归档→原生DSB→统一日线SDK。Writer已提供day归档，配置`disableday=false`启用；50指数与原证券使用同一Writer，基础资料新增非交易IDX品种。历史`source-daily-overlay`外层为50指数开启动态尾部，内层股票/ETF与原目录保持。首次切换需要启动采用新配置的采集/历史实例，随后新增日期无需重启App或Reader。

离线装配命令在仓库根执行：

```powershell
python -B scripts/prepare_market_collection.py --worker <原worker绝对路径> --worker-sha256 <原字节SHA256> --daily-source <原指数组合配置绝对路径> --daily-source-sha256 <原字节SHA256> --output E:/workspace/wondertrader-data/<全新候选目录>
```

`--indices`默认仓库50指数名录。输出只写全新E盘目录，原worker、基础资料、存储根及运行实例只读。生成`private/connection.json`、`datakit.json`、`worker.json`、基础资料和`source-dynamic.json`，由`PREPARED.json`绑定文件身份。原route、transport、profile版本、批量/队列预算保持，订阅集合及其摘要成对更新。Source2将该增量合并进现行完整GH正文；其它路由、原请求ID、Journal及凭据保持。

外层`snapshots`沿原配置字段：storage_root为唯一Writer根，scratch_root为E盘Reader临时副本目录，session_id为原SD0930收盘marker，source为QMT派生数据集身份，source_license说明原值来源，price_unit/volume_unit/amount_unit保持unknown，symbols仅登记50指数。指数固定历史继续保留原QMT/CSI/BaoStock/Tencent分段。当前结果不证明完整交易日连续覆盖。

## 安全切换及回退

每次交付为当前实际部署准备独立operations材料，固定原/新配置、部署描述、Python及入口摘要、新control目录和原数据根。历史端口和只读App连接保持；控制身份发生改变时由Root同步读取侧的运行状态引用。旧材料的PID和路径随部署变化，执行前核实际进程创建身份、配置摘要和本代收据。

1. Root先接收Source2原MDP/HPR未知请求的终态，确认暂停新请求的安全点。原身份和结果未知时保留原请求，不启动第二源端或Writer。
2. 执行该批`Stop-Previous.ps1`，沿原owner正常停止数据/报价及独立指数历史。原数据owner同时拥有HPR、18130历史与49922报价，维护窗口包含这些服务的短时中断。核原closed、Job子树退出、原owner退出；保留原配对、Journal、数据及锁文件。
3. 已有6932证券/20789行快照日线候选可作为一次性种子，按其Data CAS核身份，只在Writer关闭期间复制到不存在的`his/day`文件。已有day保持原件，新归档继续追加；禁止用旧候选覆盖已有日线。该种子与每日持续运行分别登记。
4. Source2在同一窗口安装完整GH候选，源与新Receiver的QST集合/profile一致。先按固定清单核验，再执行`Start-Roles.ps1 -Mode candidate`，复用原WT CLI启动数据、报价、指数历史三个角色。启动失败执行`Stop-Roles.ps1 -Mode candidate`并核原终态，不自动重启。
5. Root通过原SDK核实际搜索、股票/ETF与指数日线、原分钟及报价，接收新控制身份。ready表示初始化，逐证券来源时间、队列与收盘归档另验。
6. 回退时先执行`Stop-Roles.ps1 -Mode candidate`并确认实际关闭；Source2恢复同批原QST完整正文，再执行`Start-Roles.ps1 -Mode rollback`，使用原配置及全新控制目录。保留已经生成的day文件、全部旧历史和未知责任，不删除或反写历史。回退到`disableday=true`会停止后续day归档，应明确记录该影响。每个控制目录只用于一次运行，回退后再次前进需准备新代际。

维护脚本只调用原CLI和原stop合同，不操作QMT界面，不下撤单，不增加常驻服务。具体当前命令、原部署及文件SHA登记在本批外部`MAINTENANCE.md`、`operations/PLAN.json`、Source/Data CAS；脚本语法核验与现场启停资格分别记录。

## 开市接收标准

Root统一接收：7032集合实际配对；50指数各自真实回调及缺失项；来源时间推进、队列/溢出和原生计数；原StateMonitor自然收盘marker及day文件生成；原Helper与SDK逐值读回；同Reader后继交易日可见且旧历史保持；原股票/ETF和分钟路径正常。休市、未支持代码、未完整接收与单位待定如实记录。隔离验证使用真实历史日期复制证明文件更新可见，不冒充自然开市或当天收盘验收。
