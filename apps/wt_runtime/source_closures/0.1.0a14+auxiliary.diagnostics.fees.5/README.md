# 股票执行目标修正的同账发行

类型：永久发行源码。版本：0.1.0a14+auxiliary.diagnostics.fees.5。状态：已构建，现场采用待验。

沿[14.4闭包](../0.1.0a14+auxiliary.diagnostics.fees.4/README.md)保留46成员，仅替换版本与execution_recovery.py。前后业务比较只归一化精确股票执行器的严格布尔replace_equal_position_target；原配置、金融基准、纯Core、NSQ及策略数学保持。对应[已批准方案](../../../../docs/migration/native-stock-target-replacement-proposal.md)。

SOURCE-MANIFEST.json固定原Git、全部成员及Flit后端摘要；build.py继续接收repository、backend、work及output四项绝对路径，离线重建并核wheel逐成员字节。该构建读取Git及永久overlay，运行安装作为源码输入为0。

wheel SHA256为34f900cd14b5201dfb5268fc5b38d331e8493caaef722ae05d3e866d02d20b61。实际Native执行器、配置启用、原账恢复与真实业务分别沿发布记录核实；构建通过只授本闭包身份。
