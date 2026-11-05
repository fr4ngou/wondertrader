# Fresh cash.4固定源码闭包

类型：固定源码与重建手册。适用范围：本目录cash.4、原V1 a9及QNA resonance121.1。组合要求见[Fresh规格](../../../../docs/specs/etf-role-replacement.md)，报价金额契约见[原价输入边界](../../../../docs/specs/native-quote-money-boundary.md)，缓存生命周期见[服务控制规格](../../../../docs/specs/wt-service-control.md)。

## 唯一产品来源

cash.4包含43个Python模块。仅execution_configured.py、execution_facts.py、execution_recovery.py、service_control.py取自已独审并合入的5e60c96852d82ab3f59990d57ea04f7c4704db1d当前源码；其余39模块逐字沿cash.3角色。

固定Git基线继续为9a0b3f9a36a991a1bfc74af8d1fa315dbf4798b3，27个base模块从该提交读取，16份差异快照位于overlays/guanheng_wt_runtime。canonical另有account_observation_process、backtest_cli、backtest_completion、initial_inventory、runtime五个历史/说明差异；本角色保持cash.3原件，构建不直接Flit canonical整树。

V1 a9的5份产品文件、QNA的12份产品文件及完整元数据保持。QNA四份历史源文件继续在overlays/qna；canonical CNI/SDK17和App110继续由其原项目维护。现金来源、预算、NSQ、策略版本1.2.1、品种与依赖保持。cash.2/cash.3目录均保留历史原件。

## 清单字段

SOURCE-MANIFEST.json沿wt.runtime-source-closure.v1。version为Runtime发行，base_commit为不可变Git基线；modules[].name/source/sha256分别声明包内文件、base/overlay来源和最终原字节SHA256；pyproject_sha256固定本目录发行元数据。

installed_wheel/installed_wheel_sha256沿既有字段名保存本次定版参考wheel名称及SHA，不声明已安装或运行。payload_sha256绑定全部非dist-info产品成员；metadata_sha256绑定完整METADATA。companions.strategy/qna分别拥有其原参考身份及sources映射；路径相对仓库根、成员摘要保持原件。build_tools固定本构建器与原Core打包工具的完整五项源码，构建前后核验。

canonical pyproject保留原四项uv本地项目映射，仅更新Runtime版本；本目录pyproject保持发行元数据，运行依赖market-client 0.15.0及execution V1 a9/native a1保持cash.3原值。

## 单命令重建

使用Python 3.12和显式Flit 3.12后端（SHA e7a0304069ea895172e3c7bb703292e992c5d1555dd1233ab7b5621b5b69e62c）。示例中的work/output须全新且互不嵌套：

```powershell
python -B apps/wt_runtime/source_closures/0.1.0a12+integrated.2.market.35.3.service.9.resonance121.fresh.1.cash.4/build.py `
  --work E:/build/fresh-cash4-work001 `
  --output E:/build/fresh-cash4-wheels001 `
  --backend E:/build/dependencies/flit_core-3.12.0-py3-none-any.whl
```

正式仓库默认读取所在Git对象；私有无.git源码树可显式--base-repository指定固定Git，overlay及伴随包仍从当前闭包所属源码树读取。源路径保持普通文件与Windows重解析点检查，Git换行仅恢复为清单精确原字节。

构建器沿已审cash.3实现，仅更新固定版本及说明：验证/冻结离线后端，完整源码先准入后构建；QNA公开重导出沿原source_packages工具；三包完整载荷/METADATA核对，收尾复核输入，输出REBUILD-RESULT.json。新wheel统一SOURCE_DATE_EPOCH为1980-01-01，定版及正式入口重建须整包SHA相同。构建不取预编译产品wheel或当前安装目录作产品输入，不编Native、不启动服务或访问SDK。

报价金额与缓存修复的行为证据/独审按已合入四模块身份复用。本目录只证明源码与固定制品闭合；Native DLL、同账启停、实际资金/页面和交易资格由Root沿原owner验证。
