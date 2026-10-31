# 观衡托管原生执行进程

状态修订：以下为旧App托管入口的操作记录。最终执行进程由WT独立运行包管理，观衡只读观察，见[ADR-0016](../architecture/adr/0016-independent-wt-runtime-and-observer.md)及[WRI](../specs/independent-wt-runtime.md)。新部署按独立WT入口操作；停止观衡只停止观衡自身，以下停止App连带关闭执行的步骤仅适用旧开发候选。

类型：操作手册。适用范围：[EAM](../specs/execution-app-management.md)显式部署与只读观察。实际资格按精确制品和证据登记；隔离SDK、真实来源、恢复及生产启用分别验收。

## 安装与启动

准备已核验的B产品安装目录、execution-install.json、对应原生执行配置及独立控制根。核组件版本、全部文件摘要与原生配置身份；实际账户/来源/交易权限由B原合同拥有。App/SPA和依赖另按固定候选安装。

维护人员准备父部署JSON，字段固定：schema为guanheng.execution-app.v1；installation为B安装目录；installation_manifest_sha256为安装清单原字节SHA；configuration与configuration_sha256绑定原生配置；control_root为预先建立的E盘本地目录。父文件最大16KiB。所有路径使用本地绝对路径；令牌按B原环境变量传递。

给App设置GUANHENG_EXECUTION_CONFIG和GUANHENG_EXECUTION_CONFIG_SHA256，绑定父文档原字节，两项空值保持关闭。沿已安装guanheng-console启动；App先启动已配置数据/账户来源，再启动执行进程。SCW保存版本不会替换该部署或自动生效。

运行固定configured业务核时，使用同一父部署的v2：schema为guanheng.execution-app.v2，追加必填runtime=configured-python。其余六项路径/摘要字段与v1相同。原生exe入口可继续v1，或使用v2且runtime=native；未知值和额外字段拒绝。App沿B已安装的固定模块启动策略，解释器/运行库及七包源码集合由原B入口绑定并重验；父文档不接受模块、脚本或自定义启动命令。

固定业务输入的input_file/input_sha256、主分钟证券和求值预算按[NRT-R11](../specs/native-realtime-strategy.md#nrt-r11-固定业务配置的受管python入口)配置；算法、原生资料、数据口径、理论资金和费用须为同一候选。安装启动成功后仍需核本次策略输入/目标及隔离执行原件。历史快照的实际收到时间保留，日末模型回放须声明模型假设；严格历史可得时间缺项保持待核。

## 观察、停止与故障

打开“系统状态→策略执行进程”。“已启动”表示本实例进程就绪；实际策略目标、账户成交、资金与费用从各自正式接口核实。页面刷新仅读取GET。读取失败时旧状态及PID隐藏；恢复连接后重新读取当前观察。

正常停止App，先收束读取消费者，再关执行进程，随后关历史查询、采集和账户Host。核原生closed收据、进程树、双管道EOF与线程join。任一owner失败会保留App失败结果，CLI归约返回2；正常全部完成返回0。进程PID在退出后可显示未知，以原实例及收据核查。

配置或安装摘要错误时执行能力保持不可用，其他工作区继续可读。核父文件、安装清单、原生配置及路径身份后再由维护人员安排启动；App不会自动换身份重试。

当前B仍拒绝复用已有业务状态根，自动恢复资格为false。保留原状态、原命令及收据，沿B正式恢复流程核查；本手册不提供清空或更换状态目录绕过恢复的操作。升级/回退使用完整匹配App/SPA、B组件及配置组合，统一发行演练沿模块C后续及[发布规范](release.md)。
