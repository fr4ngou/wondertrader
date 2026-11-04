# WT独立运行包

类型：模块说明。状态：开发及隔离验收中。适用规格：[WRI](../../docs/specs/independent-wt-runtime.md)。

`guanheng-wt-runtime`为独立的普通Python wheel，拥有QMT共享内存Host、原生历史服务、采集及执行的进程生命周期。WT原Runner/CTA、Reader/Writer和Parser/Trader继续承担行情、策略与交易算法。观衡独立部署，只读消费WT接口；该包不导入观衡Web包、FastAPI或SPA。

## 公开入口

```powershell
# 示例：路径、摘要和UUID均由本实例安装及配置资料提供。
E:/quant/wt/venv/Scripts/pythonw.exe -I -B -m guanheng_wt_runtime `
  --config E:/quant/wt/instance/runtime.json `
  --config-sha256 <runtime.json原字节SHA256> `
  --control-directory E:/quant/wt/control/<本代UUID> `
  --control-id <本代UUID>
```

`RuntimeConfig.from_path`、`Runtime.start/status/check/request_close/wait_close_request/close`及配置字段以[最终规格](../../docs/specs/independent-wt-runtime.md#wt运行配置及公开接缝)为准。全部组件先完成配置验证，再按Host→可选交易Host→可选账户Host→可选账户结果更新→历史→采集→执行启动，逆序关闭。省略组件表示该实例未装配它，运行ready只表示已声明组件的基础就绪；策略/账户/来源资格须查相应原接口。

以下为配置结构示例，UUID、路径及全零摘要均为虚构值，实际配置由对应组件安装资料提供；执行模块未交付或描述文件不完整时启动失败。

```json
{
  "schema": "guanheng.wt-runtime.v1",
  "instance_id": "d140bbde-bba4-48f0-90a1-c239ec682589",
  "startup_seconds": 180,
  "stop_seconds": 90,
  "components": {
    "host": {
      "kind": "qmt_read",
      "descriptor": "E:/quant/wt/instance/host.json",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    "history": {
      "kind": "source_market",
      "descriptor": "E:/quant/wt/instance/history.json",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    "collection": {
      "kind": "quote_collection",
      "descriptor": "E:/quant/wt/instance/collection.json",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    "execution": {
      "kind": "execution",
      "descriptor": "E:/quant/wt/instance/execution.json",
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    }
  }
}
```

## 复用及职责

可选`trade_host`组件使用`kind=qmt_trade`及原交易部署descriptor/SHA，沿固定交易进程工厂，保留现有host的只读/HPR功能。可选`account_host`使用`kind=qmt_read`和原只读Host descriptor/SHA，复用`QmtHostProcess`。它让已有v3账户观察连接与HPR、v4交易Host同时归同一WT管理；原生Scan/金融mapper和各自配对、凭据、Journal保持。可选`account_observation`固定`kind=native_account_observation`，要求本实例配置account_host，沿[NAP-v1](../../docs/migration/native-account-publication-proposal.md#nap-v1冻结合同)固定工厂运行原生单轮并发布原帧。观衡仅消费已发布数据和状态。完整顺序为host→trade_host→account_host→account_observation→history→collection→execution，逆序关闭；旧配置省略新增项时原相对顺序保持。完整组合及源端同正文共存分别验收，已有数据实例保持原配置。

| 源码 | 职责 |
|---|---|
| `runtime.py`、`__main__.py` | 固定工厂、依赖顺序、唯一运行身份、共享截止及原子状态 |
| `managed_local_process.py`、`thread_owner.py`、`strategy_job.py` | 原组件监督、创建期Windows Job、管道/线程及实际退出确认 |
| `qmt_host_process.py`、`history_preparation_process.py` | 原只读Host或HPR进程；来源晚到和重连沿Host协议，不重发旧业务命令 |
| `account_observation_process.py` | WT持有的原生账户单轮及原帧发布，观衡读取沿冻结NAP-v1定位 |
| `source_market_process.py` | 原Reader历史服务进程；数据和证券范围由来源契约决定 |
| `quote_collection_process.py`、`collection_observation.py` | 原采集进程及安全只读投影，保留Writer格式和算法 |
| `execution_process.py` | 执行模块交付的原执行owner，统一工厂`create_process(path, sha256)` |

QMT终端内的策略正文和内存共享协议保持其原无文件/网络访问约束。本运行包处于QMT外部，负责配置、制品和进程管理。Host依赖安装在独立的Host环境；基础运行监督不导入Host的实现包或金融SDK。

选择持续策略分析数据时，另安装与WT版本匹配的`guanheng-analysis-window-producer[bound]`，并声明`analysis_host`及`analysis_window`，按[WRI装配](../../docs/specs/independent-wt-runtime.md#持续策略分析数据装配)启动。此可选发布者在WT侧复用Host包的只读协议及原签名客户端，HTTP服务仍由WT管理的Host进程承担；基础装配保持原依赖。原SDK调用只在QMT原策略线程执行，观衡不参与启动与刷新。

## 安装及验证

发行安装器负责从已固定wheel及其摘要离线安装。基础运行依赖只有独立`guanheng-market-client==0.15.0`。显式安装`guanheng-wt-runtime[execution]`时，由本包元数据声明唯一策略v1及原生数量模型依赖，并传递选择原core和tzdata；普通角色安装器按该声明组成六发行闭包，不向WT安装观衡App/Web。该安装选项只提供代码依赖，策略与执行开关仍由原运行配置决定。源码工作目录和`sys.path`注入不属于产品运行方式。

当前Root接收角色`0.1.0a12+integrated.2.market.35.3.service.7`使用[最终固定源码闭包](source_closures/0.1.0a12+integrated.2.market.35.3.service.7/README.md)重建；[service.5闭包](source_closures/0.1.0a12+integrated.2.market.35.3.service.5/README.md)保留为谱系前代。两个闭包均按对应角色的43个Python模块摘要验收；后继主干修复继续由当前源码维护。

验收入口为`tests/integration/wt_runtime/main_installed.py`，从普通无Web安装环境调用真实CLI，以原Host两代SDK替身、原Reader真实历史和采集协议替身验证运行装配。该范围不授真实券商交易、原Writer本轮运行或完整策略执行资格。最终组合验收需包含唯一1.1.2策略及原执行器。操作见[独立WT运行手册](../../docs/runbooks/wt-independent-runtime.md)。
