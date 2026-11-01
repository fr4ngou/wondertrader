# 独立市场更新角色的行情连接

类型：功能规格。状态：accepted。范围：维护入口部署材料和启动环境，复用已安装观察监督者、子服务及原窗口/发布协议。

## 目标与职责

市场观察的更新角色独立于观衡Web运行。Web的连接环境与更新角色的连接环境分别准备；更新角色通过原MarketClient读取WT公开行情，WT继续负责来源、通信和采集。该配置不启动WT、Host或QMT，不改变账户、策略或委托权限。

## 配置及启动

维护模板位于`scripts/runtime_templates/observation-update-owner.py`，部署时复制到控制材料目录，与`PREPARED.json`同目录。沿原start/status/stop及live/validation入口运行；它执行维护后退出，持续生命周期仍由原`guanheng_app.observation_supervisor`及其Job拥有。

`PREPARED.json`各profile可选声明：

```json
{
  "market_environment": {
    "path": "E:/managed/observation/market.private.json",
    "sha256": "<该私有文件的实际SHA256>"
  }
}
```

示例只展示profile内字段。path为绝对路径；私有文件最多16KiB，摘要绑定本次完整字节。内容为JSON对象，URL和TOKEN为必需非空字符串，可选连接IP及超时也使用字符串：`GUANHENG_MARKET_URL`、`GUANHENG_MARKET_TOKEN`、`GUANHENG_MARKET_CONNECT_IP`、`GUANHENG_MARKET_TIMEOUT_SECONDS`。具体连接、超时和HTTP校验由原设置及SDK拥有。

部署者创建当前用户受控权限的私有文件，凭据不进入Git、代码ZIP、控制收据或日志。每个角色保留自己的固定配置身份。更改私有文件时同步准备新绑定及明确的重启配置，避免混用旧摘要。

## 行为与恢复

启动清理继承的全部`GUANHENG_*`环境，再仅加入该profile显式绑定的行情连接字段。缺省沿原清理行为；Web配置不会隐式获得更新角色授权。普通系统环境保留，调用者环境保持原状。原固定sources/service/deployment校验保持。

私有文件及必需连接在创建运行身份、写控制收据和启动进程前校验。缺失、摘要不匹配、超容量、非法JSON、未知字段及无效类型均报固定错误，不输出凭据正文，也不留下新运行身份。status和stop不读取该文件，凭据损坏仍可沿原身份停止。已有停止截止、OS退出确认、父子join、窗口与尝试记录均保持。

连接成功和来源数据合格分别核实：原客户端返回数据后，来源适配器继续核单位、时间及实际覆盖。连接配置不能把缺数据或未知单位变成可发布数据；对应来源失败继续保留上一业务快照。

## 验收

同一模板生成的环境传入真实隐藏子进程，通过原SDK查询已运行WT；账户和执行环境不传入。回归覆盖默认清理、显式连接、私有文件变化/容量、字段和类型、失败前无运行身份、凭据缺失仍可停止。原维护生命周期与审定基线除环境装配外保持执行逻辑等价；角色实际部署后再核启动、源查询、状态及正常关闭。组件就绪、连接成功、完整发布分别登记资格。
