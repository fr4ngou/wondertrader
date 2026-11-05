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

## HPR控制拒绝兼容发行

[兼容闭包](../../compat/market-python/hpr-control-rejection001/README.md)内的两个普通Flit项目拥有完整固定源码，`SOURCE-IDENTITY.json`记录原wheel/现场overlay及最终成员SHA。构建入口先核固定源码，再离线调用缓存的Flit3.12.0；输出原Agent及兼容Host wheel，版本和直接依赖从所属pyproject唯一读取。

```powershell
python -B compat/market-python/hpr-control-rejection001/build.py --out-dir <新wheel目录>
```

用新固定Python环境、锁定依赖wheel及散列锁正常安装。Host必须精确配原marketdaily.4 Agent，交易SDK升级独立处理。完整离线安装实例、wheel SHA及命令见[验证记录](../evidence/2026-11-05-hpr-compatible-closure.md)。

```powershell
<新环境Python> -I -B compat/market-python/hpr-control-rejection001/verify.py --original-pair <只读原pair> --candidate-pair <独立新pair> --report <新验证报告>
```

verify核63个已安装Host模块及60个原Agent模块、原材料SHA和原业务配置，沿原产品create/verify生成或核验后继pair，要求QMT正文逐字节相同；再在同一安装环境运行原拒绝回归。该入口只准备和验证，不打开现场Journal、不运行来源Host或发送QMT请求。pair绑定生成时的新安装路径，搬迁或换环境后应通过该入口重新生成新pair。运行owner检查工程资格后沿原受管服务采用；原pair及运行服务在此准备阶段保持。
