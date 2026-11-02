# 观衡a84受管Web与页面后继验收

类型：实际安装和独立运行验收。日期：2026-11-02。状态：只读Web主链通过；资金及模拟交易继续。

## 本次结果

当前受管入口为 `http://127.0.0.1:18143/market?search=300308.SZ`。App保持 `0.1.0a84+market.1`、源码737a0fe；维护入口源码为f8d81ed。新增维护工具沿原Uvicorn及App lifespan运行，正常关闭读取池，不改变WT框架、App wheel、行情算法或账户接口。后续离线构建会将该工具与原安装器一起装入独立交付包。

工具候选的两个独立审查无未闭合问题，未知运行代保护回归已闭合。Root按四文件CAS接收，两个永久回归通过，干净主干文档检查通过。原App构建及203项组合回归输入保持，沿用其有效证据。

Root在实际a84安装上启动18143，读取72组目录及股票60根日线，正常停止后核对解释器、venv启动器退出码均为0、`shutdown_complete=true`、两个读取池线程均为0，再启动新运行代。重启后的日线逐值相同，自选文件逐字保持。原18141及WT18142的OS创建身份和运行状态保持。已有直接启动的18141保留，工具只管理18143的新代。

浏览器使用用户已授权的Playwright回退及本机Edge无头模式，桌面1440×1050和390×1050实际检查通过：简称“中际”、拼音“zjxc”、代码前缀“68817”均无需提交便展示候选；日线默认60日；正式回测净值曲线、400条记录、当日详情和翻页；账户4项持仓、成交页签、唯一1.1.2策略及三实例状态。页面标题和业务内容有效，无框架错误覆盖，脚本与控制台错误为0，390px整页宽度为390。

账户4项持仓仍来自停止前的成功发布，页面保留原来源时间；当前不具备实时账户资格。正式归档仅1份报告，报告比较仍需第二份实际报告。上述浏览器操作只读取WT发布结果，Root没有访问QMT共享内存、下单或撤单。

## 高管来源后继

前次b175高管超时原件保持。本次沿原请求超时和600秒总预算，仅重试 `eastmoney.executive.ashare`，实际成功，业务current成为 `05cd4f8241e77efb777bd230220876dfff36b800735cfe969ac67e3c757ad51a`；沪深北三组高管指标各368个自然日、2025-10-30至2026-11-01。其他69组数值dataset保持。

实际a84 API重新读取72组完整分页，8组JSON导出逐值相同，安装55个观察域模块仍与接收源码逐字相同。单次成功重试证明本次来源业务恢复，持续传输稳定性继续按实际运行记录判断。

## 运行问题与限制

11:02:42发现a84独立市场更新角色已经退出：原监督者4788与子73732均不在，收据为`owner_reported_failure`，`scheduler_closed=false`。业务current、09:00已完成窗口和历史源表保留。已交独立模块定位实际退出触发链；未覆盖失败代、重复启动或把故障状态记为运行。该问题不影响已发布结果和18143/18142只读查询。

部署准备001因保护检查发现上述更新进程已退出，在创建Web前停止；无Web进程产生，目录保留。002只保护实际仍运行的18141/18142，更新故障单独处理。现有QMT、采集策略及其他实例均保持。

资金100万元含现有持仓的完整接线由开发者1继续；模拟下单/查询/成交/撤单由开发者2负责，当前仍受QMT窗口激活失败阻断，尚未取得本轮订单结果。7指数完整源表替换覆盖、T2108新交易日原件及来源权限限制沿[前次证据](2026-11-02-observer-a84-market-installed.md)。

## 原件

- 工具候选：`E:/workspace/wondertrader-qa/observer-web-lifecycle-20261102-001/INTERFACE-001.json`，SHA `bf3742413a25270fd4b59c95579bcf38644fc36c92118be7e69d7fb63a5a2db8`。
- 实际Web部署及运行代：`E:/workspace/wondertrader-data/observer-controlled-web-20261102-a84-002/DEPLOYMENT.json`。
- 维护工具与截图：`E:/workspace/wondertrader-qa/root-observer-a84-web-control-002`；固定工具SHA `1eb517483b02ab56d4119a9279bb3ee387c96adb6196649a0e6e795d85107796`。
- HTTP、来源重试、浏览器及部署脚本：`E:/workspace/wondertrader/build/root-t2108-feed-intake-001` 的 `A84-FINAL-HTTP-SUCCESSOR-003.json`、`EXECUTIVE-SOURCE-RETRY-PROOF-001.json`、`A84-WORKSPACES-BROWSER-003.json` 和 `CONTROLLED-WEB-DEPLOYMENT-001.json`。

启动、查询、正常停止、重启及回退见[本次使用记录](../releases/2026-11-02-observer-a84-web-control.md)；长期契约沿[Web生命周期规格](../specs/observer-web-lifecycle.md)。
