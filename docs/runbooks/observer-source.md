# 从永久源码离线构建观衡

类型：构建操作手册。范围：[OSB](../specs/observer-source-build.md)的App及读取侧发行；WT执行、Host和原生Reader各自沿原构建入口。

永久入口为`scripts/observer_source.py`。App位于apps/guanheng，四个读取变体位于packages/observer-read-side；发行名称相同而版本与执行侧不同，各自装入独立角色环境。读取变体作为App已验兼容依赖，WT生产执行继续选择执行侧发行。

准备显式固定CPython3.12 x64、锁定Flit wheel、registry登记的全部第三方Windows wheel、Node/npm及已有npm离线缓存。Flit摘要沿config/python-build-dependencies.json，第三方wheel沿config/observer-runtime-registry.lock，数量随已登记依赖闭包核对；私有wheel全部从这次永久声明源码生成。工具和缓存是构建输入，实际路径与SHA保存在该次记录。全新构建输出与源码/依赖目录分离。

npm缓存须包含本次package-lock声明的依赖；机器默认缓存可能只保存此前下载的部分包。`ENOTCACHED`表示选定缓存缺少依赖，先核对已验证构建记录中的缓存路径，再补齐锁定依赖或选用已有完整缓存。保持package-lock及依赖校验，随后在另一全新输出目录继续离线构建。

```powershell
& $sourcePython -I -B scripts/observer_source.py inputs
& $sourcePython -I -B scripts/observer_source.py build --work $newBuild --python $sourcePython --backend $flitWheel --wheelhouse $thirdPartyWheels --node $nodeExe --npm-cli $npmCli --npm-cache $npmCache --seconds 900
```

各变量为显式绝对路径，$newBuild须不存在。入口在同一总截止内用原隐藏Job执行固定Flit和npm命令，默认用户/全局npm配置由本次空配置替代，项目依赖只按package-lock离线安装。Node/npm和第三方wheel前后摘要固定。失败保留目录和日志，后继选另一新目录。

四个工具文件先经过原绝对路径及逐级链接准入，记录和执行使用同一规范路径，最后一个命令返回后统一重核工具摘要。成功资格同时要求入口exit0、原Job完整关闭及固定收据。最终rename跨截止时入口返回失败，已写收据保留其构建事实，交付方按该次失败处理。

`config/observer-source.json`声明六个项目及前端输入。前端保持原工作区相对布局，包含Vite的generated-storage.ts及回测页面从App读取的唯一v2_package_profiles.json；共享配置按原相对路径读取。构建使用原npm run build及分块检查，记录本次生成的静态资产及逐文件摘要，编译过程不读取历史安装源码。

成功输出SOURCE-BUILD.json、六个新私有wheel、完整App角色制品、独立ZIP与manifest摘要。角色数量为本次私有wheel与固定registry的第三方wheel之和。source-roles记录真实source-build来源及installed=false；roles由现有compose生成，保留各自精确wheel/锁/永久local-projects。不会把来源记录标成已安装。现有account_runtime_install.prepare仍按其文本精确本地版本合同运行。

接收ZIP、解压、核manifest并普通离线安装沿[原观衡安装手册](observer-runtime.md)。运行时外部行情/账户发布、观察数据、报告和个人目录分别配置；构建与安装不启动业务进程，不修改WT或QMT。实际来源继承、新安装验证、完整系统和生产资格沿每次交付记录分别核对。
