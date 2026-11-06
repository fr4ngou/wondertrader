# 股票绝对目标替换根因回归

类型：隔离验证入口。只构建/加载原公开工厂DLL及自有配置准入代码；Context记录SDK调用，无账户、QMT、Host或金融文件操作。

```text
python -B tests/integration/stock_target_replacement/run.py --work E:/absolute/new-build --toolchain E:/absolute/TOOLCHAIN.json --dependencies E:/absolute/locked-source-dependencies
python -B -m unittest discover -s tests/integration/stock_target_replacement -p test_*.py -v
```

示例路径需替换为本机已核MSVC工具链收据和锁定依赖源码目录；work必须全新。原WT源码从构建清单固定Git对象取出，批准覆盖逐项检查并应用，全部本项目对象/库在该work内重新编译。目录中的SOURCE/COMMANDS/RESULT和逐场景日志记录来源与结果。正式完整执行制品继续使用`scripts/execution_product.py`，此入口只证明工厂与配置接缝。

两种原公开工厂名分别以三种模式重放7组冻结形态：159780旧220700→新22000、512100旧76400→新76200、515080卖100、全新已达目标、在途余量、总量/可卖分离、159780两轮连续调用。true预期禁止旧目标额外买入；缺省/false保留原行为。可卖分离组直接传入显式较低目标，原算法的卖出结果仅属该隔离输入，不构成实际超量持仓的自动卖回功能。

Host准入直接编译实际valid_configuration，核可选bool、坏型和其它算法拒绝。Python比较测试核缺省/false/true、深拷贝不变、坏型/其它算法拒绝，以及账户、资本、现金锚点、策略、账根、scale和整手参数保持严格。独立活动单记录ID4242和剩量，两个cancel重载均记录并改变订单；断言零撤单、原ID保留和剩量连续。原活动单/未知结果仍归原查询与恢复owner；本入口不授实际订单恢复、金融部署或用户页面验收资格。
