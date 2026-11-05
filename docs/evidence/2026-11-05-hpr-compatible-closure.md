# 2026-11-05 HPR控制拒绝兼容闭包

类型：验证记录。结果：pass（构建、普通安装、原材料配对及隔离主链）；线上采用not-run。关联[HPR3-R1/HPR4-R1](../specs/qmt-history-preparation.md#hpr4-r1-固定来源兼容发行)。

## 输入身份

永久源码：[固定兼容闭包](../../compat/market-python/hpr-control-rejection001/README.md)，Host 63个模块和原Agent 60个模块。`SOURCE-IDENTITY.json` SHA256为`da7cef6ef0943c6cf8d86bb9651383fbd38385b6fa664a74fc4f445aba7b4a18`。原Host wheel为`0.1.0a22+mdphttp.2`，现场原pair固定的`paired_control.py/read_service.py`诊断overlay随实际基线保留。

实际原基线为`E:/workspace/wondertrader-data/wt-control-20261105-001/hpr-runtime001/Lib/site-packages/guanheng_qmt_shm`。63个模块均与原pair登记SHA一致；相对该基线只有`control.py/runtime.py/read_service.py/bulk_host_control.py`四个行为模块改变，`__init__.py`只更新发行版本。其余58个模块原字节保持。control只合入已审拒绝处理、持久交接、运输退休及关闭核查的直接前置，保留旧claim/等待时钟；主干交易/UC/SDKReturn未进入该闭包。

固定Host为`0.1.0a22+mdphttp.2.hprreject.1`，精确依赖原Agent `0.1.0a12+marketdaily.4`。原Agent wheel SHA为`18144e421db9fe5857acdbce420b5735a6f40d74e1614be4dfe53a6eaf9b10f3`；源码重建wheel所有成员内容（含METADATA/RECORD）与原wheel一致，ZIP容器SHA另列。Host直接第三方依赖保留原固定版本；15包依赖锁及全部wheel在以下QA根保存。

环境：`E:/workspace/wondertrader-qa/hpr-control-rejection-20261105-001`，新普通`environment002`，固定CPython3.12.13，`-I -B`导入实际site-packages；没有源码路径注入、旧venv的.pth或来源服务启动。原测试类SHA为`cac77cb26b4ff324d56a6a047e34b04a8b5d5ff7bfe6dd0f758ac4b93475d15b`。

## 步骤与观察

| 步骤 | 退出码/观察 | 结论 |
|---|---|---|
| `python -B compat/market-python/hpr-control-rejection001/build.py --out-dir <QA>/rebuild-wheels002`，随后独立输出到`rebuild-wheels003` | 0；两个普通Flit wheel，两次各自字节相同 | 固定源码离线构建可重复 |
| `uv venv --offline --python <固定3.12.13>/python.exe <QA>/environment002`；`uv pip install --python <新Python> --offline --no-index --find-links <QA>/wheels --require-hashes -r <QA>/requirements.lock.txt` | 0；15个精确锁定wheel正常安装 | Agent/Host版本闭包成立 |
| `uv pip check --python <新Python>` | 0；15包compatible | 实际普通安装依赖成立 |
| `<新Python> -I -B compat/market-python/hpr-control-rejection001/verify.py --original-pair <D>/hpr-pair001 --candidate-pair <QA>/pair002 --report <QA>/INSTALLATION-VERIFICATION002.json` | 0；正常产品create/verify；原五件材料及原manifest前后不变；配置/路由/权限/额度/凭据/Journal定位保持，仅policy路径重定位 | 实际原pair材料支持新正常安装；QMT正文逐字节相同 |
| 同一verify入口在实际安装类中运行原ControlRejectionTests，移除的仅为测试文件原sys.path源码注入 | 11项通过，包含真实HostControlLoop/ControlPeer/SQLite Journal的拒绝→后继成功→关闭，以及持久失败/恢复/协议损坏/原生终态保持 | 原拒绝根因与受影响关闭链通过；来源SDK为明确替身 |
| `python -B scripts/project.py check` | 0 | 文档导航及已配置静态检查通过 |

## 冻结制品

QA的`wheels/`及`rebuild-wheels003/`包含以下两个普通发行：

| 制品 | SHA256 |
|---|---|
| `guanheng_qmt_shm_host-0.1.0a22+mdphttp.2.hprreject.1-py3-none-any.whl` | `05635fe24927d3d101eb510c517ba031ce6af10dbb7e3ed91117327a6b0c51f6` |
| `guanheng_qmt_shm_agent-0.1.0a12+marketdaily.4-py3-none-any.whl` | `15e20ad75997d95531e1e0326b23df46b6c5d06e098ff4b0947e3e2ef84a8422` |
| `requirements.lock.txt` | `59a6be4bb5caf54736e13f1aff236d896547cdff6f3a93162aff416fad248a79` |
| `INSTALLATION-VERIFICATION002.json` | `c3ab56a8d81a97bfe27e67b2b3d4ff20bace9925e1204db68699dc8ea47f852a` |

原pair manifest：`c63712e4c577de37d52b4e325675ea31489864a8d576f9755442a98aa6d4db91`。新`pair002` manifest：`cef019e06eaa6b8f0d17739a54a3efaa83f5982d294b1f4a95317f62ee9a070f`。两者QMT正文SHA同为`0657ae143dab867d8c99224e99b6166ea3f01a2b6f9c76113eca38cc3a26d22f`。报告只保存SHA、版本和布尔资格，原私有配置/正文保持在受控材料目录。

QA另存`BUILD-VERIFICATION.json`（各源码/构建入口SHA及重复构建结果）、`COMPATIBLE-DELTA.patch`（对实际旧Host五模块的源码差异）、`WHEELS.json`（15个wheel身份）。构建入口SHA为`5e1e36ac43a84a9ad7c263f62a1520ebe4f8bd1d934369ee9e04769729bd3994`，验证入口SHA为`fe4fb4aab95da7fdbe6508a126bb437746c782228406d912eafb2432d6894c8c`。

## 证明范围

工程闭包覆盖实际原Host来源、原Agent、正常离线wheel安装、原真实pair材料的后继配对、相同QMT正文及安装后真实类调用链。新配对绑定`environment002`绝对安装位置；生成新Host身份符合原产品工厂合同，原manifest保持原值。

## 限制与后继

本次没有启动/停止任何线上服务、构造真实来源runtime、打开现场Journal、发送QMT请求或修改金融文件。当前HPR保持运行原代；真实Agent的8014项补齐未介入。线上采用与请求接续由Root统一完成。本QA配对属于工程验收；若Root选择新的正式安装位置，使用同一锁定wheel普通安装，再以原材料生成和verify新的后继pair，随后沿原受管入口采用。来源实际结果与在线持续运行资格需另行验真。
