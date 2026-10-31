# 普通安装与缓存文件独立性修正

类型：安装器根因修复及隔离验证。范围：[SRI](../specs/system-runtime-installation.md)普通角色prepare和离线制品安装。结果：主路径及根因回归通过；既有冻结安装、运行实例和产品包保持原件。

## 根因及实现

实际交易Host安装发现uv默认把环境中的包文件与私有安装缓存硬链接，`st_nlink=2`。Host正文身份核验要求普通单链接文件，因此在pair生成前拒绝；当时尚未启动Host或共享内存。根因是安装器的文件实体语义与产品核验要求不一致。

`scripts/native_support/account_runtime_install.py`的prepare和install_artifacts两处统一显式使用`uv pip install --link-mode copy`，保留原wheel、hash锁、pip check、RECORD及模块身份核验；不修改Host校验规则，调用方无需环境变量补救。两处命令附中文原因注释，规格与操作手册同步。

## 验证

`build/installer-copy-mode-001/verify.py`在创建期Job内运行原安装器及系统制品两组41项回归，通过；原prepare和离线安装的实际命令派发路径均断言copy模式。

随后使用实际固定uv（SHA256 `6d40479cd1d0d5db7fc0fe68ad703fc8acbd84bba50d864bb97461f6af9d9561`）和实际CPython，在两个新环境中安装同一隔离合成wheel，共用本次私有缓存。即使环境声明`UV_LINK_MODE=hardlink`，命令显式copy仍使两个安装文件均为`st_nlink=1`，与缓存源具有三个不同文件身份。仅修改第一个合成安装文件，第二个安装及缓存原值保持。四个实际命令均exit0；产品包和运行角色修改为0。

control416总计5.140秒exit0，树0、两路EOF、reader join、句柄回收全部通过。原件为上述根`RESULT.json`及`build/guanheng-workspace/wt-data-live-read-control-416/build-wt-data-live-read-control-416/result.json`。源码身份：安装器`3e88126f9fa7ae4fff80cad267243c1bc6669f90dec8bae7c0e6c987adb4e4f7`；prepare测试`3561e15f79f0e5f141f021af5250cc3d2277746b247fb7fcd7e5c28abf3ab63b`；离线安装测试`352ca1c43f0c5d83a485f1e858567b61b65fcad78cf97a3f058df68af37cb665`。

真实交易产品的完整安装、配对、运行与关闭由对应模块继续验收；本次合成wheel验证独立文件语义，不替代整个交易主链。

