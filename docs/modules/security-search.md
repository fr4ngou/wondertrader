# 证券目录与检索

类型：模块说明。适用范围：观衡顶部搜索、个人观察及行情证券选择。状态：源码已实现；安装与页面验收按对应交付记录核实。

## 职责与调用链

目录保存证券的规范代码、交易所、名称、种类与拼音。观衡启动时读取一次已生成目录，查询仅访问该内存副本。证券目录用于发现身份；历史行情是否覆盖该证券，由独立WT行情服务返回。

顶部搜索在输入停顿200毫秒后自动显示下拉候选，中文输入法确认后开始查询；与个人观察和行情选择共用 `/v1/ui/securities/search`。候选展示名称、规范代码和种类，点击或上下键加Enter选择后进入对应行情；清空、失焦或Escape收起。换词时中止旧请求并忽略迟到结果，避免候选与当前输入错配。用户沿原个人观察接口保存选中的规范身份，并沿原行情接口读取分钟线。搜索及个人观察操作属于只读展示与用户偏好，不改变策略订阅和交易范围。

自动候选交互由[顶部下拉组件](../../apps/guanheng/console/src/workspace/SecurityAutocomplete.tsx)与原个人观察工作区承接；其[交互回归](../../apps/guanheng/console/src/workspace/SecurityAutocomplete.test.tsx)覆盖自动候选、中文输入、取消迟到请求及键盘选择。

源码入口：[目录读取](../../apps/guanheng/guanheng_app/security_catalog.py)、[HTTP路由](../../apps/guanheng/guanheng_app/security_routes.py)、[公开模型](../../apps/guanheng/guanheng_app/contracts/security_catalog.py)、[前端接口](../../apps/guanheng/console/src/workspace/securitySearchApi.ts)、[个人观察](../../apps/guanheng/console/src/workspace/PersonalWatchlist.tsx)。

## 数据与配置

`GUANHENG_SECURITY_CATALOG_FILE` 指向UTF-8 JSON目录，模式为 `guanheng.security-catalog.v1`。目录含生成时间、来源摘要及按规范代码排序的证券列表。每项包含 `symbol/code/exchange/name/security_type/pinyin_initials/pinyin_full`。`catalog_id` 校验证券列表内容；重复身份、无效字段或摘要不符时，证券检索明确返回不可用，其余工作区保持独立。

当前公开身份支持沪深 `.SH/.SZ`，种类为股票、ETF和指数。北交所身份需扩展目录契约及行情消费者后接入。目录仅代表所加载制品的覆盖范围，新增上市与名称变化通过生成新目录并更新应用生效。

[生成脚本](../../scripts/generate_security_catalog.py)读取已取得的证券身份与名称表，预先计算拼音。`pypinyin` 仅用于终端外生成，Web请求与QMT策略运行均无需加载它。生成命令：`python scripts/generate_security_catalog.py --identity <身份JSON> --names <名称JSON> --output <目录JSON>`；参数均为部署环境提供的本地路径。

## 查询与错误

GET参数为 `query` 和可选 `limit`（默认12，最多30）。支持完整代码、数字前缀、中文名称及简称、拼音首字母和全拼。多个匹配按相关度及规范身份返回候选，用户完成选择；例如五位代码前缀保持前缀查询语义。

响应模式 `guanheng.security-search.v1` 返回原查询、目录身份、生成时间和候选列表。请求词最多64字符且UTF-8最多128字节；单次响应容量通过 `limit` 管理。无匹配返回成功的空列表；输入无效返回422，目录不可用返回503。刷新失败由页面保留已有同条件结果和数据时间。

## 验证入口

[搜索与HTTP测试](../../tests/integration/app_console/test_security_search.py)覆盖名称、拼音、前缀、规范身份与目录错误；[前端接口测试](../../apps/guanheng/console/src/workspace/securitySearchApi.test.ts)及[个人观察测试](../../apps/guanheng/console/src/workspace/PersonalWatchlist.test.tsx)覆盖候选选择和保存链。实际证券分钟覆盖、部署接线与浏览器交互分别核实。
