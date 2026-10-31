# 独立交易记录用户入口

> 源码交付范围：本页标注的外部历史/待归仓路径用于追溯原记录，未随本次源码提交。其旧通过记录不授当前入口可复现资格；当前构建与运行以对应永久源码及正式安装手册为准。

日期：2026-10-22。范围：[NAC-R7](../specs/native-account-console.md)的`/orders`入口。当前状态：新增产品独立full及后继冷加载测试条件修正delta均complete、gap 0。真实账户来源与共享内存账户接线未授。下文初始验证与冻结描述保留当时身份，后继结果见末节。

## 实现与职责

独立应用交易记录路由复用账户页的查询、字段投影、分页、刷新和来源展示组件，默认委托并可切换成交；账户页继续默认持仓和资金。数据来自现有只读账户API，不新增订单/持仓账本、Portfolio资金分配或风险审批队列。删除能力接口中`risk_approval`的“尚未迁入”承诺；交易执行资格保持独立。

## 实际验证

前端相关22项、后端源码33项及新noneditable CPython3.14安装后的33项通过；类型检查、生产构建及分块门禁通过。一次并行构建期间原退役路由用例超过其1秒DOM等待；同一未修改源码在构建结束后完整重跑22项通过，生产浏览器实际路由也通过。未扩大测试等待或修改路由来掩盖该观察。

使用已有Playwright和实际Microsoft Edge验收生产SPA。Browser插件/对应browser技能未提供，因此采用现有Playwright路径，未安装浏览器依赖。1440×1000及390×844检查页面身份、非空、无错误遮罩、键盘切换、来源时间、完整空、部分失败、刷新隐藏旧值及恢复、51条分页和未配置无请求；切换与分页不额外查询。窄屏表格在局部区域横向滚动，页面无水平溢出；截图已人工检查。

另以新安装应用启动实际业务HTTP，注入明确合成Owner，实际Edge读取委托/成交、显式刷新、返回账户及能力接口。该链没有拦截业务HTTP，服务退出码0、shutdown_complete=true、控制线程已结束。它证明安装、HTTP与页面组合，不代表原生四查询或真实账户重新取得资格；未调用终端HTTP、SDK、当前Host或真实交易。

新app wheel SHA为`0c410f5a2dd2c2da753080777ddbe327e9f0e51d62d0193e131cf23767b79d3a`，正式pyproject/锁及固定原生数量/策略依赖保持；1140项安装文件、源码及wheel成员已核。安装收据在`build/guanheng-workspace/trading-records-001/installation.json`，安装测试原件为同目录`installed-pytest.xml`。

浏览器原件按技能保存在仓库外`E:/workspace/wondertrader-ui-qa/trading-records-001`：脚本、结果、桌面/窄屏/异常截图、实际HTTP结果及退出记录。仅含合成数据。首次浏览器脚本对含委托子行的成交单元格使用了过窄的exact文本定位；修正验收locator后7场景通过，产品代码保持，原脚本另存。

## 冻结与后继

审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-001/final-001/review-inputs.json`）SHA为`e5f5f45e2fb6284afa62b0471b001b2a0becd22e385a50aa49f8a90e94a2e948`；1215项及16项仓库外原件清单（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-001/final-001/artifact-manifest.json`）SHA为`d739cafc5caf27f8d82fee67f0ef91fcf7ccc654e97d56e1e0ad12d4c54098b4`。59项最终源码及规格已冻结交另一作者full；当前不宣称独立审查完成、真实数据接通或生产发布。

## 后继：独立full与测试条件修正

完整独立报告（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-review-001/FULL-REVIEW.md`）已封存，SHA为`5426e360455ffd500de37bc5a86c9f8209879ad8cdbe103b1f2530b5c121efcd`；结论为本次新增产品complete、gap 0。审查者使用正式noneditable安装、生产SPA和实际Edge，自行完成13场景、安装后33项HTTP回归、直接相关17项组件/路由及完整类型检查。正常、空、部分失败和429实际经过自有业务HTTP，invalid/503为明确API mock；含105委托/103成交、分页无额外请求、键盘/390px、恢复和写方法拒绝。自有服务退出0、owner已关闭，未访问当前QMT或真实交易。

根任务逐项核243份审查原件、4项只读运行文件及当时59份源码一致，见回核收据（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-001/full-review-integrity.json`）。审查者保留旧退役路由冷运行的19/22和21/22原始结果：先断言URL的1秒等待可能早于首次lazy页面提交；实际生产冷深链及新增入口正常，因此没有将其列为产品缺陷。

full封存后，仅调整`IndependentApp.test.tsx`：在既有15秒case预算内先等待目标页面5秒可见，再同步核URL、导航和无额外读取。产品、路由及HTTP期限保持原字节，其余58份来源一致；4文件22项通过。测试修正审查入口（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-test-002/final-001/review-inputs.json`）SHA为`720a40e57a26368d628efbd26fbc69b77a911ed789da4eabef2b5b0e1327c499`，后继独立delta尚待验收。这项测试修正不改变原产品full的范围，不扩大真实账户、SHM账户或生产资格。

后继独立测试delta（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-test-review-002/DELTA-REVIEW.md`）已complete、gap 0，报告SHA `d29b1e3c8095a97318b7cd9644c1634728dab0944d4599886afbe1cbb3543cc4`。审查者从原full ZIP的59来源及115前端补充输入复制新树，仅替换该测试，空缓存实际22/22通过；首个research冷加载耗1966ms，用户可见目标页等待覆盖原触发条件。原断言均保留，原243原件、1140安装文件及7份dist身份保持。根核137份delta原件相符，见回核收据（外部历史/待归仓路径：`../../build/guanheng-workspace/trading-records-test-002/independent-delta-integrity.json`）。后继V2正在修改当前应用代码，需另行新安装及验收；本结论绑定原产品和单项测试身份。
