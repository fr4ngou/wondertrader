# Native归属接缝验证

先冻结Native候选，构建正常Managed/Standard/Runtime与原WT执行器工厂，再运行本目录。只使用loopback原Host与SDK替身，真实券商调用为0。TEMP/TMP、输出、构建及pytest basetemp显式E/D。

- `run.py --exe .../HookHost.exe --dll .../TraderQMTStandard.dll --factory .../WtExeFact.dll --output <全新E/D目录> --mode allow|event|deny|wait|invalid|legacy|missing`：真实股票执行单元200份裁剪至100份、原UUID/SHA在SDK前确认、查询/实时源事实、原pending拒绝责任与原无回调200份路径。legacy可使用缺少新可选导出的旧Standard DLL；missing显式选择后在API创建前拒绝该旧DLL，SDK调用0。
- `managed_hooks.py <全新E/D目录>`：使用GH_MANAGED_V2_DLL/GH_MANAGED_V2_PROBE/GH_MANAGED_RUNTIME_DLL的真实双ctx Factory/CtaStraContext，完整8/9意图与17次原setter；旧ABI原回归仍由`../qmt_cta_product/test_managed_v2.py`负责。
- `contract_probe.cpp`：独立ABI大小、注册线程/freeze、未明确确认/非法回复、完整字符串复制、2MiB资源边界及原price_text行为。

分层Native验证不授予真实账户执行资格。完整Runtime/ASA协调器、持久分配及恢复沿其所有者的整体验证。测试复用原Host/SHM/线程与关闭工具，不导入或连接旧MiniQMT。构建命令、固定WT overlay身份、具体Source/Native字节与原始输出保存在本次QA目录的source freeze中。
