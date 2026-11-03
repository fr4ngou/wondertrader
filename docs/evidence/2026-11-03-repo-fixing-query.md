# 回购定盘公开查询根因修正

类型：实际来源验证。状态：适配器主路径通过，普通安装及持续更新采用待后继接收。范围沿[OBI6](../specs/independent-market-observation.md#obi6-调度与发布责任)，实现为`apps/guanheng/guanheng_app/observation/disclosures.py:repo_fixing`。

## 根因与实现

原正式a94适配器对中国货币网FrrHis发GET，请求实际返回403、错误为source_permission_denied。[官方回购定盘页面](https://www.chinamoney.com.cn/chinese/bkfrr/)可读，其公开`frr-fdr-his-cn.html`声明历史查询使用POST和startDate/endDate/lang=CN。沿已有Fetcher.post_readonly发送公开表单，实际一次请求返回200。该查询使用公开数据，无账户认证和交易副作用。

修改统一替换原请求方式，使用原URL、来源配置、HTTP预算、原件、百分比转换及日期过滤。配置原referer可选，实证省略referer也成功；没有增加Cookie交接、浏览器资料、GET回退、时间放宽或独立采集服务。FR007/FDR007、available_at及原失败保旧语义保持。

## 实际验证与范围

使用已安装a94解释器和正式Fetcher/ContentStore，在隔离原件根实际执行原适配器，原GET一次失败403。候选适配器使用同一公开入口执行真实POST，1次请求返回18条实际记录，日期2026-10-09至2026-11-02；末日FR007=1.38%、FDR007=1.36%，首次可知时间为空。日期范围、唯一日期及实际尾值已核。原始JSON保留供应商额外字段，标准输出保持原四字段。

可复现命令位于`E:/workspace/wondertrader-qa/repo-fixing-source-20261103-001/probe_original.py`；不加参数沿原安装复现GET失败，加`--candidate`从本仓源码加载修正函数，沿原安装依赖完成实际抓取。原ORIGINAL.json与后继CANDIDATE.json分别保存，请求原件存于各自独立内容根。候选实际响应SHA256 `5071b5590c56a8a1ebb750d7f94b3ae1f21ae6a36bdabadd65271f5460368a74`，无受控配置或凭据写入仓库。

本轮只证明根因及单来源实际适配。完整72组隔离刷新、计算/发布、数据接收、独立更新安装及页面消费由后继统一批次登记；当前活动更新a94仍使用旧GET。原current、窗口完成、其余来源、Web/WT/QMT与行情采集未因本探针改变。后继包需采用本函数后才具备每日持续读取修正，禁止仅将一次真实读回标成持续部署完成。
