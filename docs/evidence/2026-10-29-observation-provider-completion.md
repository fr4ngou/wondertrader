# 真实供应商与完整观察发布后继

类型：开发验证记录。状态：complete（本次限定工程切片）。对应[独立观察OBI5–8](../specs/independent-market-observation.md)；模块C及完整goal保持active，未发布。

## 根因与实现

固定006的19路HTTP初查发现央行PDF采集闭包缺依赖、申万默认CA链失败。a17可选采集闭包固定pypdf6.14.2，普通只读安装继续延迟导入；HTTP使用系统可信CA，显式SSL_CERT_FILE/SSL_CERT_DIR沿HTTPX，证书/主机名验证和TLS安全参数持续启用。

PDF准入核原表身份、亿元单位、当年12列和两金额行，按原布局列位置映射月份，连续披露月及正分母校验。007首次重放把金额小数识别成日期；008改为唯一“项目 Item”表头。原官方PDF严格重放、实际公开PDF请求及申万安全连接13行通过。库内不可协作解析沿原Job最终回收；字节、页、登记对象及提取文本限制分别描述，未授全部PDF内存分配事前硬上限。

008的首次全部21来源正式CLI已采集实际公开输入，完整发布因basis_ic/if/ih/im缺必需basis_points拒绝，原current保持。零网络重放精确复现4项错误。根因为期货先披露且同日现货缺失时，计算层只在现货存在时写派生列；009统一写明spot_close/basis_points/basis_pct为null，现货后到重算，修订失去现货同步失效。期货原值保持，旧快照完整保留。

009独立规格审查实证Unicode负号、括号金额可被数字子串截成正值（P2）；规范审查提出读取器显式关闭P3。010在金额所在区域验证完整token的ASCII十进制/规则千分位，其他符号/括号/尾注/坏分组固定失败；ASCII负数继续按业务分母规则拒绝。Reader由finally关闭，BytesIO由with关闭，覆盖成功、语义/容量失败及构造失败。两轴已确认源码根因闭合。

010原CLI成功发布后，浏览器原选择器将details中的“技术备注+错误码”误当独立精确文本，保留失败并修正QA；零重采的页面后继又发现真实窄屏问题：质量页覆盖表缺少其他数据表已有的横向滚动容器，在390px撑到728px。SPA011在该表使用同一容器，并补“统一行情指数”中文来源名；保留原排版和全部48行。post-public002的布局、截图及关闭证据固定原条件，post-public003同快照回归页面宽390、原表在容器内滚动，实际GET和状态/错误展开均通过。

## 固定输入与原件

独占根build/observation-provider-completion-001。review-base-006固定原272源码，review-current-009/010及原报告保留；最终review-current-011/SOURCE-SHA256-011.json固定277源码，相对010只新增上述2处前端差异，相对006为9修改/5新增。App0.1.0a17仍为010 wheel SHA `7b6a51eaa266d48a887a1fdb38a0a2037e4d046127b65841c633c24645cc5c5e`，87构建输入/89ZIP成员。新18文件生产SPA ZIP SHA `025ebd950cd1f0b471b9804b5ff1c446688e89a24883460d0022f1b8584503ed`，STATIC-INSTALLATION-011.json核普通31发行4743条RECORD和新SPA全部匹配；测试安装38发行。pypdf6.14.2为BSD-3-Clause、Python>=3.9/OS Independent，来源及wheel SHA沿uv.lock，专用于可选PBC PDF。原006普通环境保持。

最终INSTALLATION-011.json SHA `0dea43c68a79fd30bd404b6f9d19ffb5bb9f9ff6cfe6f67e830c5d691ddf5855`绑定277源码、24 QA、194原件与19截图；独立审查报告单独绑定，避免自引用。三次实际采集全部source_manifest与原对象，以及三项实取探针原件/规范对象均核SHA，见CAPTURES-011.json。

全部实际验证使用本根validate.py及原native.run，隐藏Job、原有限总D/输出、整树/EOF/join收尾；诊断输出只列来源身份、固定错误、字段名和调用位置。旧QMT只读、零真实下撤单、零生产切换和Git集成。

| 验证 | 当前实际结果 |
|---|---|
| replay-002 | 当前严格PDF解析与原官方表的月份/金额/比值一致，零网络 |
| probe-pbc.large-bank-001 / probe-shenwan.801003-001 | 实际HTTP原件及规范结果保存；PDF1行、申万13行，client关闭 |
| main-001 | 正式008 CLI失败missing_field，原current保留；50 HTTP/2 SDK发送，原件及失败回执保存 |
| diagnostic-001 → diagnostic-002 | 同一真实响应零网络重放，4缺项→48项字段准入零错误，诊断禁止发布 |
| basis-red / basis-green | 原4条件失败；009四产品×新行/旧派生共8场景通过，含邻日禁止匹配、同日晚到及修订清空 |
| backend-001 → backend-002 | PDF合成样本0列边界修为金额两位小数排版；185通过 |
| backend-003 → backend-004 | 原193项中1个正常gzip超过原1秒，保留失败；主链结束后010全组206项通过64.78秒，原时限保持。并发负载是当时观察条件，未将它当作排他根因结论 |
| installed-001 | 实装009、-I关闭源码遮蔽，PDF19/基差8/CA3/原HTTP24共54通过；原请求时限保持 |
| pb-live-001 | 正式安装实际公共PB单日成功：9协议、890411线上字节、1486405展开字节，原字符串和规范结果留存，client关闭 |
| main-002 | 正式009全部21路→48完整校验/partial发布→四指标HTTP/生产SPA宽390→资源关闭通过425.593秒；61发送=50HTTP+11SDK，3实际失败明确保留 |
| replay-publish-001 | 原失败响应完整离线发布达到255秒原Job截止并终止；未授完成，保留原件。后继按实际CLI完整主链核结果 |
| pdf-installed-red009 / pdf-green010 | 新27项在旧安装-I实证9失败（含2关闭断言），010源码27通过；后加成功/语义失败两项关闭回归由206/64覆盖 |
| replay-003 / installed-002 | 010官方原PDF重放通过；同一010安装-I的PDF29/基差8/CA3/原HTTP24共64通过12.22秒 |
| main-003 | 正式010原CLI exit0，21路→48完整partial发布至9168087b…2825f，8指标HTTP核对通过；原wrapper因浏览器选择器exit1，保持原日志，不写成整轮exit0 |
| post-public001/002 | 同一已发布快照零重采；选择器修正后实证质量页全宽728，保留失败/截图/布局；两轮App均正常shutdown、读线程0、HTTP join及监听关闭 |
| frontend/typecheck/spa-build/spa-chunks-011 | 9文件46前端（含策略目录回归）/TypeScript/生产构建/分块均通过；18成员归档核对通过 |
| post-public003 | 010安装+新SPA011+同9168快照，8指标HTTP、4实际数值页面、21来源结果/4目录待解析及3原失败、宽1440与390通过；errors0/warnings0、请求全GET，监听/HTTP/读线程均关闭，原native.run记录8.5秒 |
| 独立审查 | 两轴最终complete，原金额P2/关闭P3及质量表溢出闭合，无新增产品P级；独立核277/24/194/19及31发行4743RECORD/87输入/89ZIP/18SPA，原捕获与PBC/申万/PB算术、分阶段CLI/页面和关闭核同。保留各轴独立核对范围与unknown，不合并放大资格 |

最终报告分别为本根SPEC-FINAL-REVIEW.md SHA `2749fde78b8c84b1e94353f69cda9dd382412faa412108a519fe31635c7960a3`、STANDARDS-FINAL-REVIEW.md SHA `e012a5394e290840c323aa3031048deb244815347c6d768e10fd2eded6a475be`；009 full及010源码delta均保留原字节。最终DELIVERY.json绑定制品、固定输入、全部原件、报告和工程切片/完整模块各自状态，由A沿既有规则唯一组合提交。

## 限制与后继

19路初查中的四个披露目录仅保存页面，新增附件语义仍未接纳；货币网回购/IRS连接失败和A八指数未配置继续列为实际失败。实际PB单日成功、原006受管PB成功与21来源组合的最终结果分别登记。完整21来源、自然09:00、真实M1、全部策略和统一安装升级回退保持未完成。策略页保持名称/简介/版本，回测单独标签页。
