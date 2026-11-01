# 独立市场更新行情连接的部署验收

类型：维护角色安装、真实SDK及正常停止恢复记录。日期：2026-11-02。状态：已部署，原App/WT与业务数据保持；来源覆盖单独继续。

## 实现与接线

后继于[源码接收](2026-11-02-observation-source-connection.md)。已审模板固定源码`00714f24f2df4beef6de0e90f1f265035d5440a3`，SHA256为`85a965704339e5673e6ff3f3248b7cf1e2547b38322b7ae62f63409344e30f7f`。它只增加profile显式私有行情环境装配，继续使用已安装`0.1.0a82+history.1`的原监督者、子服务和Job；App安装没有重建或修改，WT18136与页面18140没有重启。

新控制材料根为`C:/Users/frangou/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Guanheng/observation-update/a82-market-20261102-001`。26来源配置逐字不变，SHA256仍为`7147112119393e35cc81a1315e45ed9567304b0690dd7fdb1b92ba19b186d5fd`；北京时间09:00、start_date、原请求/字节及600秒预算保持。新deployment SHA256为`505f63170d56edb38e76b6ff87c73dae65bd9faaa8adf719b11f89c945b4d894`。私有凭据仅在外部受控文件，profile绑定完整摘要，控制与公开材料不含令牌正文。

## 实际结果

旧a82 owner正常停止，真实监督者OS exit0、父子closed/join及原停止截止成立。新角色实际启动、正常停止并再次恢复；首次新监督者也记录OS exit0及完整关闭。最终监督者26188、子服务69500存续，running/waiting。原业务current仍`fd94eef74e0f3be00cc625bd53ed216eb0b65f5ee227e5c51a783e6a65c8f69d`，同根窗口和尝试记录逐项相同。

最终模板生成的环境已在独立隐藏子进程中，沿原MarketClient实际读取WT18136的沪深300日线，返回Ok及12根；账户和执行环境未传入。监督者子进程沿原CreateProcessW继承启动环境。该SDK主链与监督服务生命周期分别验收，当前服务等待下一窗口，未宣称本次已执行全部来源刷新或完成未来自然09:00。

真实来源探针的6项指数Unavailable及2项unknown量单位继续保持，未将未知量标成股/手。当前主链的连接配置已接通；指数数据补齐及T2108持续生产/选择由相应来源模块继续。已合入T2108重建日期定义修正仍待后继App角色安装，本次只部署维护入口，不授该修正的上线资格。

## 制品及原件

独立维护包为`E:/workspace/wondertrader-qa/observation-update-market-20261102-001/observation-update-market-20261102.1-windows-x64.zip`，SHA256 `93cf10df8ad55ac221ca97247b85add06f81c407d1aedf2699824325417bd57b`。包内保留仓库相对布局、维护模板、唯一规格和合成回归；无私有连接配置。PACKAGE.json SHA256 `95ef8908a79aaaa8b795342a86f789576b28df6e499bba42615ce4a62ac11733`。

同目录`DELIVERY-002.json` SHA256为`2277a683f04260ae317d825486c770d142bf116e9e9e3e881d8dab46c3181b3f`，绑定当前模板的LIFECYCLE-EQUIVALENCE-002、两轴审查、实际SDK、角色准备及停止恢复。初始DELIVERY及初稿生命周期摘要保留，002明确对应NUL修正后的最终源码；旧记录不授新摘要资格。

现有页面、账户最后成功结果、59日历史及独立WT保持。本轮没有操作QMT/SHM、交易、数据库或WT框架。资金取数的管理员只读检查仍待用户确认。维护和回退入口见[交付手册](../releases/2026-11-02-observation-update-connection.md)。
