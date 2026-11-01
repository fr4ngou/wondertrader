# 独立更新连接与T2108来源接收

类型：源码接收和实际只读探针。日期：2026-11-02。状态：修正已合入；当前a82安装与更新owner保持，后继来源接线和部署继续。

## 已合入的修正

T2108历史重建点存在`reconstruction_as_of`，原日更重建方法定义时漏登记，严格字段校验以unknown_field拒绝发布。自有方法定义已登记可选日期及历史因果限制，源码`b960d9575df05dee4b16fcca6d73907eb13d5d69`；43项匹配回归及真实冻结包37.11秒完整refresh复用原开发者交付，43日T2108和五组59日广度逐行保持。本次没有采用隔离proof快照。

独立更新维护入口原来清除全部`GUANHENG_*`环境，连行情连接也被移除。该行为使Web已配置WT时，更新角色仍报连接未配置。现将原审定维护工具归入[永久模板](../../scripts/runtime_templates/observation-update-owner.py)，profile可显式绑定私有行情环境文件及摘要，缺省保持原清理行为。凭据在创建运行身份前准入，status/stop保持独立；原生命周期除环境装配外执行AST等价，WT框架修改为0。接口沿[唯一规格](../specs/observation-update-connection.md)。

源码初稿`0df4e3d`的独立审查发现NUL字符串可在运行身份落盘后导致Popen失败。已在环境装配层提前拒绝，固定后继`00714f24f2df4beef6de0e90f1f265035d5440a3`的两轴delta审查均关闭该P2，无开放发现；001失败报告保留。六项标准库测试包含真实隐藏子进程、原默认环境清理、必需字段和NUL失败前零write/零Popen、坏文件及停止不依赖凭据。

Root另以最终模板读取本机私有绑定，真实隐藏子进程沿原MarketClient查询独立WT18136的沪深300日线，status=Ok、12根；源单位仍为unknown，保持原值。该证据证明连接环境及客户端实际主链，不代表全部指数来源合格或整批更新成功。规格审查覆盖固定源码，部署和业务结果的资格由本记录分别说明。

## 指数原件核实

8指数GET探针范围2026-10-01至10-30：6项Unavailable，沪深300返回12根至10-30，上证50返回7根至10-16，两者单位unknown。未改当前服务或用未知单位冒充股/手。

本地86400 DAT实际存在上证、沪深300和上证50；其他五个目标文件不存在。上证文件8751根、首日1990-12-19，其中264根早于现有解码器1992门槛，2010年另有8根原signed负量；沪深300和上证50的10月记录数量与实际接口一致。源文件逐字摘要已固定；没有改变解码、忽略负量或修改缓存。

当前fd94观察原件还保留7指数的真实完整OHLC/来源成交量，范围分别从2020/2022/2023开始；其量单位未登记。000985只有close，不能据此构造OHLC。此前50指数交付属于分钟历史，实际前缀缺口沿[原最终覆盖记录](2026-10-30-qmt-index-50-final-coverage.md)，不授完整日线资格。源模块后继优先复用这些原件并核单位/覆盖，隔离准备WT日线，不切现行18136。

## 原件及剩余

详细固定原件位于`build/root-observation-WT-link-001`：PROBE、FINDINGS、INDEX-CACHE-QUALITY、ARCHIVED-INDEX-TABLES、ENVIRONMENT-PROOF-002、LIFECYCLE-EQUIVALENCE、两轴REVIEW-002及INTEGRATION。T2108接收位于`build/root-t2108-intake-001`；原交付为本机`E:/workspace/wondertrader-qa/observer-acceptance-market-001/DELIVERY-010.json`。

当前运行仍为[已验a82/18140](2026-11-02-observer-ashare-history-installed.md)，快照fd94和26来源owner保持。新模板和T2108修正在干净主干，尚未替换安装；持续T2108的按日包发布/选择及指数来源接收完成后集中安装。完整字段更新、真实新日期生产和自然09:00结果分别核实。

最新策略资金取数方案已准备，管理员只读挂盘/WSL工具环境待用户确认；Docker、PG及旧业务继续关闭。本轮QMT/SHM调用、委托、撤单及WT框架新增修改为0。
