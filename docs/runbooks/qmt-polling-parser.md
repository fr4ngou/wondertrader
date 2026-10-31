# QMT 持续行情插件操作

类型：运行手册。范围：默认 ParserQMT 工厂配置、只读验证与停止。当前实现与限制见[模块说明](../modules/qmt-polling-parser.md)，完整运行器独立验收。

## 配置

在标准 parser 配置中使用 `module: ParserQMT`，用 `code` 限定已加载基础合约，插件参数放在 `qmt` 对象内。以下为合成测试配置示例；端点、环境变量和值的版本由受管配置提供，真实部署须核实来源口径。

```json
{
  "id": "qmt-quotes",
  "active": true,
  "module": "ParserQMT",
  "check_time": true,
  "code": "SSE.600000",
  "qmt": {
    "base_url": "http://127.0.0.1:19010",
    "key_id_env": "QMT_READ_KEY_ID",
    "hmac_secret_env": "QMT_READ_SECRET",
    "timeout_ms": 5000,
    "max_response_bytes": 16777216,
    "poll_interval_ms": 1000,
    "batch_limit": 32,
    "subscription_limit": 200,
    "profile": {
      "version": "example-profile-v1",
      "source_license": "example-only",
      "time_encoding": "epoch_ms",
      "minute_boundary": "right",
      "volume_to_shares": 100,
      "amount_to_yuan": 1,
      "full_tick_cumulative": true
    }
  }
}
```

凭证从启动环境注入；配置只保存合法环境变量名。HTTP 限字面回环，其他允许地址使用正常验证的 HTTPS 根 URL。标准宿主的 id/active/module/check_time/filter/code 保留，插件 qmt 对象字段严格校验。profile 全部必填；量额因子必须有限且大于零。

预算：timeout_ms 为 1..30000，max_response_bytes 为 256..16777216，poll_interval_ms 为 10..60000，batch_limit 和 subscription_limit 为 1..200。未提供预算时采用示例所列默认值。证券仅接受 SSE/SZSE 六位代码及对应 STK/ETF/IDX 标准形式；整批非法或超额订阅保持原目标集合。退订不回收本实例历史水位容量；扩展证券范围需按受管流程重建实例。

## 启动、观察和停止

1. 验证配置、基础合约、凭证引用与宿主准备状态；`init` 不进行网络调用。
2. 对显式 ParserQMTHostV6，宿主先在本次启动总截止内用原认证 GET /internal/v1/read-binding 等待 QMT 连接就绪；Host 进程 ready 只表示外部服务已启动。取得 200 后调用 connect，观察连接/登录事件和 isConnected。其他插件继续各自原启动路径。来源准备、认证、能力或时间口径失败时保持无行情并产生终态关闭诊断。
3. 监测有效行情与来源状态。相同快照重复轮询正常跳过；数据冲突、倒序、会话变化和 HTTP 失败停止该实例。诊断只保留固定原因，凭证和异常原文不进入日志。
4. 外部管理线程调用 stopParser 并确认完成，然后释放 parser、SPI、原 adapter 与引擎依赖。超时保持依赖存活并继续等待；callback 内请求停止随后交外部线程确认。直接从 callback 销毁对象不符合生命周期契约。
5. 停止或失败实例不恢复连接；外部管理者核查状态后新建实例。完整系统恢复资格仍由原业务事实所有者和宿主决定。

## 隔离验证

构建后执行 `ctest --test-dir build/native/cmake -R qmt_polling --output-on-failure`。测试使用合成只读签名 HTTP、默认 DLL、原 ParserAdapter 和原 CTA 的公开 on_tick，包含 pool0/2、重复快照、新快照、来源变化、数据冲突、倒序、认证失败、超时和有界停止。测试不启动 ticker；完整 WtRunner 的准备、分钟事件和退出仍应另验。

开发搬迁包运行同一 polling_flow.py，确认移动后的 DLL 路径与实际工厂。包级通过仅授隔离开发资格；真实终端、常驻运行和业务入口继续按[完整验收地图](../migration/acceptance-map.md)验收。

系统回调退出单独运行 `ctest --test-dir build/native/cmake -R qmt_http_drain --output-on-failure`。专用测试DLL含回调门闩，生产ParserQMT不含该宏和导出；验证同步关闭与回调仍在执行的清理边界，以及确认停止后显式卸载。宿主仍持有tick时必须继续保持其DLL有效。
