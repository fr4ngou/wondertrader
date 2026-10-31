# 市场Python组件构建与组装

类型：运行手册。范围：[市场Python来源规格](../specs/market-python-sources.md)中的源码切片及历史发行。

使用已固定身份的CPython 3.12解释器。仓库构建工具的Flit版本和SHA由`config/python-build-dependencies.json`声明。

```text
python -B scripts/market_python_components.py materialize --component qmt_data_v2 --output <新切片目录>
python -B scripts/market_python_components.py materialize --component market/history --output <另一个新切片目录>
python -B scripts/market_python_components.py materialize --component market/hpr --output <新HPR切片目录> --wheel-dir <锁定第三方wheel目录>
python -B scripts/market_python_components.py build-legacy --work <新构建目录> --backend <锁定Flit-wheel>
```

输出`PYTHON-COMPONENT.json`记录切片的准确成员及构建输入；`BUILD.json`记录历史三wheel的版本、SHA、解释器和原发行身份。第三方wheel可从既有HPR依赖锁取得，切片保留各发行原许可证及METADATA。源表中的历史安装路径只作溯源，命令运行不读取该路径。

原生历史查询构建可在原`source_market.py`命令中附加`--python-component market/history`。该选项仅选择Python闭包，沿原原生构建、依赖、许可证和安装逻辑运行。采集所需`qmt_data_v2`切片交由数据组件装配器与匹配的原生库合并；准确成员由切片收据提供。

Python切片自身包含源码和数据契约。HPR切片中的第三方Python文件需要配套原生扩展，因此部署沿固定解释器的普通wheel安装，避免将这个切片直接当作完整site-packages。历史HPR内嵌venv的C盘base路径保留在旧制品中，当前运行角色使用独立固定E盘环境。

复验入口：

```text
python -B tests/integration/market_python_sources/run.py --work <新验证目录> --backend <锁定Flit-wheel> --wheel-dir <锁定第三方wheel目录> --host-pythonw <公开解析所得固定Host角色pythonw>
```

入口组装三个切片、重复构建历史三包，核对输入及wheel一致性，执行纯导入和必要边界验证。它不连接QMT、打开共享内存、查询账户、操作行情库或启动服务。真实链复用范围见对应交付证据；原生组件的完整构建与安装另由所属组件验证。
