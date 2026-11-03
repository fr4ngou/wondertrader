# 寿险、财险资金配置持续生产隔离验收

类型：验证记录。日期：2026-11-03。范围：两组原口径的数字来源接续；状态：开发与隔离安装验收通过，正式角色部署由Root另行接收。

## 根因与实现

原`nfra.disclosures`调用`disclosure_check`，仅读取官网首页并返回空结果，因此官方新表不会进入两组数值序列。原数据本身与官方XLS一致。改用自有`nfra_source.history`沿官网列表954→同身份详情→唯一同名XLS，以固定xlrd读取原账面余额；原Fetcher、deadline、排他刷新、合并、来源登记及CAS负责其余生命周期。来源ID、寿险/财险分组、亿元单位和债券比例公式保持。

## 官方期次与原数值

实际取得官网统计栏目前3页，最新列表截至2026-10-23；资金运用最新是[2026年二季度原表](https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId=1268117&itemId=954)，发布时间2026-08-14 17:46:37。9月人身险/财产险经营表属于月度经营口径。当前列表未披露三季度资金运用表，保持6月30日期次。

| 机构口径 | 资金运用余额（亿元） | 债券余额（亿元） | 债券比例（%） |
|---|---:|---:|---:|
| 人身险公司 | 368690.956069265 | 188800.560366525 | 51.208351400693296 |
| 财产险公司 | 25349.9856317761 | 10268.5874149431 | 40.50727114445173 |

保险公司总计还含其他机构，两个分组之和不要求等于全部保险公司总计。官网原XLS统计范围包含独立账户及非独立账户。

## 主路径与回归证据

所有新材料在`E:/workspace/wondertrader-qa/insurance-allocation-20261103-001`和`E:/workspace/wondertrader-data/insurance-allocation-20261103-001`。真实列表/详情/XLS请求、SHA和逐单元格原数值保留，`REAL-PARSER-RESULT.json`证明两组最新行与原件逐字段精确一致。

`run_main.py`先将只读现场基线680ebf7a…完整验证到E盘隔离根，再经原refresh发布f5f4105b…。两组各6条原历史、原定义版本保持，其余70组完整记录及源表/股票分区保持；本次数字源4次HTTP请求、2条最新期次观察，发布约12.219秒。`check_recovery.py`以错误附件回放实触发nfra_workbook_schema，原current和72组分区保持；随后普通安装沿真实官网重新刷新，零历史修订，最终候选96d360e83d9ec5b8876d0d4c2c3d3206581e909eac3e4abe1cdccb4e55f4913a。

普通非editable wheel及固定XLS依赖在E盘独立安装，`verify_installed.py`通过实际FastAPI catalog、两组series及JSON exports，全部原6条与导出相等，应用正常收尾。最终安装模块、wheel和源码逐字一致；API证据为`INSTALLED-VERIFY.json`。新版本号与现场服务均未操作。

安装代码的定向回归命令为固定E盘解释器`-I -B run_regression.py`，包含NFRA、原配置及HTTP截止/预算，68项通过。合成后继三季度单独标识，验证新标题、期末、发布时间及新金额被消费；该用例不作为实际三季度披露证据。错误单位、机构、比例、非有限值、重复行/附件、外部附件、分页漂移/不足、未来披露、缺依赖及原截止均覆盖。

按规格与规范人工full审查，当前开放发现0；未另派独立审查者。`project.py check`仍报告共享工作区原30份历史未索引文档，本项未新增链接/索引错误。Root统一维护索引和当前状态。

## 交付边界

SOURCE/DATA/CONFIGURATION三份CAS与HANDOFF-001.json在E盘交付目录。配置保留28来源，只将原nfra.disclosures改为数字适配及季度游标；其余来源、模型、计划、预算保持。原基线为680ebf7a86302e8abe501c3a5efbff053ac921d72cb1a64564abffb5f9d78a0e；接收时原current若变化，沿原refresh重放本来源，不强行覆盖。

正式独立更新角色需在同一固定闭包装入xlrd==2.0.2，Root从干净主干建立后继发行并按原流程绑定配置。未来自然三季度披露及自然调度窗口尚未发生；本项证明自动识别与隔离运行能力。现场current写入、WT/QMT动作、真实下撤单、服务重启均为0。

格式检查补充：原collection/config/registry保留既有CRLF字节；默认git diff --check将新增行CR报告为行尾空白，使用`git -c core.whitespace=cr-at-eol diff --check`核查通过。未对共享文件整文件换行重写。
