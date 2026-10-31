# 国信 QMT 本机运行环境核查

类型：安装证据。日期：2026-10-28。范围：本机文件、随安装手册和独立配套解释器；本轮未操作终端界面、运行策略或切换安装。

## 独立版本

| 项目 | 只读取得的值 | 依据与边界 |
| --- | --- | --- |
| 客户端 PE | 1.2.26.150 | D:/software/guoxin/bin.x64/XtItClient.exe 的 FileVersion/ProductVersion；产品显示版本与 PE 映射另核 |
| Python DLL | 3.6.8；ProductVersion 3.6.8.535392 | bin.x64/python36.dll 元数据 |
| 启动器 PE | 3.6.4 | bin.x64/pythonw.exe 的文件元数据，仅描述启动器 |
| 配套解释器实际运行 | CPython 3.6.8，64位；build Dec 19 2022，MSC v.1900 | 独立 pythonw.exe -B 读取 sys.version/version_info/implementation 与指针位数；实际exit0 |
| 当前内置策略的实时 sys.version | 本轮未重采 | 配套解释器和 DLL/手册互相吻合，仍与内置回调实测分别标注 |

隐藏受管入口 qmt-installed-python-version-001 约0.275秒，子进程自然exit0、无控制台、整树/EOF/join/资源关闭确认。未调用行情、账户、委托或撤单。PE 文件时间不充当客户端发布日期。

## 随安装官方手册

| 来源 | SHA256 | 内容依据 |
| --- | --- | --- |
| D:/software/guoxin/HTML/国信iQuant策略交易平台_Python_API_说明文档.pdf | d94ead8f5575596606f5e0a1a68be143535c8132f82cdd2e3041f552f735aaad | 213页；p23明确内置3.6.8/64位，p24要求匹配3.6.8库，p25解释第三方库路径/下载，p40停止线程说明，p79全推订阅 |
| D:/software/guoxin/config/help/python/迅投QMT极速策略交易系统_模型资料_Python_API_说明文档_Python3.pdf | ac1e256f80c5b00c6adf603604cce9e4e3168fad578e186f3e7ce65b96653183 | 171页；封面文档3.3.6、Python3.6.8、更新2021-12-20 |

国信213页手册的 PDF 元数据 CreationDate/ModDate 为2024-09-12，未发现封面正式发行号；这是文档元数据，不能推定客户端发布日期。两文件当前磁盘时间为2025-09，不能用来覆盖正文日期。

148个函数和属性名从国信手册的编号条目标题提取并合并重复页码，见[安装手册 API 索引](../modules/qmt-native-api-index.md)。提取保留名称及页码，未将整本文档纳入源码仓库；目录不宣称覆盖全部API，参数及权限回查官方正文。原始文本、提取器和结果保留 build/qmt-runtime-docs-20261028/{extract-manuals.py,MANUAL-SUMMARY.json,API-HEADINGS.json,API-INDEX.json}，用于更新时再生成核对。提取进程实际exit0，约10.76秒，原件保持。

## 版本可选择性

本机只读配置 xtuserconfig.xml 的 python libs_path 和 customer.lua 的 g_pythonlib_url 与手册p25第三方库功能吻合；后者指向国信 update-python.cfg。配置只证明提供库路径/下载入口，本轮未取得该下载配置正文，未下载或更新。当前目录有python36.dll，未发现可据此认定内置3.12/3.13切换的说明。老 editor.xml 中 Python-2.7.api 是编辑器补全文件引用，不能作为实际2.7解释器可选证据。

国信公开产品V3.13和本机PE号缺少官方对应表，因此本记录不判定两者的先后。公开公告、通用内置/外部 XtQuant 的版本范围与线程说明差异见[官方资料核查](2026-10-28-guosen-qmt-official-runtime.md)。未实施升级。

## 文档验证与实施范围

新增运行手册、148项API索引、行情结构模块及导航/维护/目标回写已完成；project.py check与本轮15份文档的git diff --check均实际exit0。内置策略和WT运行代码修改0，QMT界面操作0，升级/版本切换0，真实下单/撤单0。仅文档变动未触发运行代码独立审查，review范围none；现有真实全推完整采集/停止与历史收尾状态保持，不能以文档门禁授运行完成。安全计数摘要在build/qmt-runtime-docs-20261028/VERIFIED.json，文档SHA清单在同目录DOCUMENTS.json。
