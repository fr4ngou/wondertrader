# WT统一日线数据角色

本角色独立安装于CPython3.12 x64，持有缓存优先的日线、证券资料、真实缺口、原生归档和版本发布。观衡通过统一WT接口读取原价/供应商前复权及定日事实，原指标公式保持。独立披露来源沿原所有者运行。

普通命令为`guanheng-daily-data --config ... --config-sha256 ... --control-directory ... --control-id ...`。WT日常运行采用原`SourceMarketProcess`和`source_market_service.py`，通过可选`daily_update`固定描述符组合单个数据生产线程与原HTTP/Reader线程。省略该字段保持原读服务；停止仍使用原SMP控制协议和父Job总截止。读取配置必须为`source-market-current`且指向该生产者的同一CURRENT。

角色发行组合固定原源码，成员和来源摘要见`config/unified-daily-data-source.json`。原公开事实输入、原对象库及Host/Agent协议库复用同一仓库实现，构建时冻结原字节；运行不连接观衡进程。SDK的内部/独立导入布局来自同一19文件声明及同一版本。轮子中的旧函数保留原库行为，当前活动入口仅执行显式数据配置。

安装器只创建全新程序目录，离线校验全部wheel与原生摘要，使用固定基础解释器创建独立环境。来源凭据、原缓存、成功历史、控制目录和CURRENT在外部受控数据根，重装程序和回退不删除或改写这些数据。发行包、安装事实、实际来源与生产切换分别取得资格。

来源价格单位/复权参考、39项T2108资格缺口、来源价格分歧和PIT限制沿每次数据快照及交付证据说明。完整合同见`docs/specs/qmt-source-daily-history.md`，部署操作见`docs/runbooks/unified-daily-data.md`。
