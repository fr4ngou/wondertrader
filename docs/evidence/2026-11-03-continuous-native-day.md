# 持续日线与50指数离线候选

类型：验证记录。状态：候选隔离主链通过，现场切换与自然开市待Root接收。范围沿[CNH-R6](../specs/collected-native-history.md#cnh-r6-原生日线持续落盘与指数动态尾部)。

当前配置根`E:/workspace/wondertrader-data/continuous-native-day-20261103-001`，隔离原件根`E:/workspace/wondertrader-qa/continuous-native-day-20261103-001`。复用原固定Session SHA256 `6499c6e459495fc8c6c964c3ff697c9b5d4cdfd98d054eef49abe7b4b2194f2a`及原指数历史组件，日线读取源码与固定组件一致。自有运行C++/Python、WT框架源码和实际owner本轮未修改，新增仅离线装配脚本、指数名录、配置及维护材料。

## 实际主链

- `native_probe.py`通过原DataKit加载7032证券，delivered=0、writer_processed=0、健康及正常关闭通过；没有连接QMT、推送行情或写现场存储。
- `dynamic_probe.py`通过固定历史组件及原Reader解码50指数124085行；上证真实QMT日期20261030作后继记录，原20261029及以前记录作隔离前缀。启动一次Reader与空Writer后，用原Helper写入该真实历史日线并推进实际历史日期marker，同Reader读到20261030，六项原值、Mixed分段及unknown量额保持，Writer仍在运行并正常关闭。
- 该文件发布由隔离探针完成，Writer接收行情0；它证明同Reader动态读回，不能证明自然StateMonitor收盘生成。原65→66日保留验证含合成输入，仅复用其文件保留机制范围。
- 原日线归档清单SHA256 `2de53c485e18f6bd1f7d9942d6ad35410fe55d084055e385f03c1d03c77e94d5`保持。原股票/ETF注册逐字段保持，原QST除symbols及其profile摘要外保持。

运行命令在隔离根执行：`E:/workspace/wondertrader/.venv/Scripts/python.exe -I -B native_probe.py`与`dynamic_probe.py`。结果见该根`NATIVE-7032.json`、`DYNAMIC-READ.json`；最终配置、命令语法、固定依赖与精确文件收据随本批交付。主路径完成后只进行本次配置影响的回归和仓库文档检查。

`acceptance.py`实际通过QST完整纯值合同7032证券、原连接其它字段、原股票/ETF注册与品种参数及内层日线配置保持；原6932份种子DSB逐文件SHA通过。候选及回退共六个运行配置均由各自固定安装的`RuntimeConfig.from_path`验证，描述文件SHA相符。三个PowerShell维护入口语法错误0，现场启动/停止命令未执行。最终离线装配源码再次运行于隔离新目录成功。

`python -B scripts/project.py check`退出1，报告31项已有未索引历史文档，涉及2026-10-21证据目录及旧研究文档；本批新增文档无缺索引或链接错误。全仓文档检查保留失败状态，未为本模块改写其它历史资料。

## 未执行范围

Source2完整GH合并与现行未知请求终态、现场owner停止/切换/回退、真实7032订阅回调、自然收盘日线及后继日持续运行由Root统一接收。此批只交准备及隔离证据，不授这些现场资格。原6932证券三日种子保持既有冻结材料，本轮未写入原Writer根。当前持仓和旧交易历史不属于本模块。
