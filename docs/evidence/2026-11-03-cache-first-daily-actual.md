# 缓存优先日线补齐真实小量主链

类型：实际QMT来源验证。状态：三证券主链完成，全市场运行材料准备中。接口沿[MDP6](../specs/qmt-market-daily-preparation.md#mdp6-缓存优先与缺口准备)，字段及生命周期沿[模块说明](../modules/qmt-market-daily-preparation.md)。本轮仅行情缓存准备及读取，无终端界面、账户、委托、撤单或WT框架操作。

原MDP编排在实读前为全池逐证券准备。显式v2在同一owner中先用原v8读取，按原T2108/2实际尾日和40期正前复权收盘生成有限缺口PLAN，再复用原HPR，最后v8实读核资格。v1目录和旧349个slot身份保持。新字段逐项中文注释，注释版与前代候选Python AST一致。

源码CAS002为`c77e42a044bb47c42064466a819b86a47d15de0a673c1b7535ea3141de709dbc`，本仓六文件匹配；原CAS及候选在frozen001保留。旧期待绑定换代后，原材料预检拒绝进入SDK；随后对未启动的新v2另建small003，固定本代完整v8/HPR元数据、Source profile/route/limits，未放宽原匹配。三股票材料CAS为`6212924bb4b4bcd997c7d44b4cb5a348c64793c92d8ab0d53f403b950a75009b`。

2026-11-03 10:26实际执行`cache-first-small003/owner001/run.py`，使用原coordinator、native.run和Job监督，作业约6.4秒exit0。600000.SH、600036.SH、601318.SH初读各82条、末日10月30日；PLAN仅三项10月31日至11月2日tail区间，没有重复下载7月至10月窗口。三份原HPR确认后，原v8回读每只83条、末日11月2日、最后40条正收盘且共同basis为11月2日，eligible=3/3、coverage_qualified=true。真实front_ratio回执实收为02:26:25Z，保留实际Source和捕获摘要，无因子独立验证或历史首次可知资格扩张。

原CLI的completed结果与实际QUALITY一致；监督核exit0、root_reaped/tree_zero、双管道EOF、线程join及resources_closed全部为真。单次SDK/票据/吞吐/绑定限制保持，业务120秒及监督180秒分别记录。没有自动重试、复用已消费owner、启动全A或写正式T2108 ready。

原件根`E:/workspace/wondertrader-qa/retained-quote-preparation-20261102-001`：small003的SOURCE-CAS、签名preflight、private/workflow/cache、PLAN、preparation、capture、QUALITY、RESULT及owner001/TERMINAL；模块原件与逐字段索引在cache-first-module001/HANDOFF-002.json和ANNOTATIONS-002.md。全A需另核5576股票池、实际缺口/新股暖机与可用范围，沿原封存/ready发布及观衡消费接收；三证券结果保持其准确范围。
