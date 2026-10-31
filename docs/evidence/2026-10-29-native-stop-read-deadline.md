# 模块B：原生停止读取共享冲突贯穿首预算

类型：隔离验证证据。结果：固定安装exe的原生首停止读取预算通过；完整P21和模块B继续in-progress。日期：2026-10-29。关联[P21-C4/C5](../specs/native-qmt-standard-trader.md#stq-p21-原保存加载的产品正常恢复accepted开发中)。原件为`build/ms-recovery-001/lock-through-deadline-002`。新增生产源码/WT核心修改0、真实券商调用0。

## 输入与触发

沿[P21已冻结候选](2026-10-29-native-clean-recovery.md)的安装exe/固定Parser/Reader、真实WinSHM、隔离SDK替身和同一App读取器候选运行。原`CtaProcess.cpp` SHA为`d14329c98d6a53d2b489c86592122ec749e15a5cc3bfa961eff4ea55744a9960`；exe为`5f1731290428b3888708520108bea6cf0fe5c9d6e6e606f056984e4750b85c63`；Runtime为`0f15c702eeb38e80d259543a49ef685c4d9417d8b35a68a98be7b4ed00ac3186`。App公共读取器仍使用隔离候选`338f1d1b9848a4f9a5b04a250fb85d08db5eae4ebb3f051663a5e2f5f76edd88`，C共享源码保持。

新测试`tests/integration/qmt_cta_product/stop_lock_deadline.py` SHA为`3b12513c14e17790f63ad14b747dedcd99aa0167f95d4835efc2a7b8b6fa37a9`。测试在原配置加载前将原生stop_ms设为1000，随后沿原配置身份/安装流程运行；观察父进程使用独立6秒关闭预算，使其能够观察原生失败和完整退出。父预算与原生读取预算分别说明，该实验没有扩大原生首D，也没有将父进程强杀当作原生失败证据。

该父预算同时写入stop.json的deadline字段；若文件可读并成功解码，其6秒余量会超过本例原生`stop_ms+1秒`准入。此次故障发生在仍拒读的stop_read阶段，读取、解析及deadline字段校验尚未完成，故该值不影响首读取预算的观察。本装配只用于读取期限负例，不授予有效stop成功路径或父/原生相同截止资格；既有正常释放前成功用例保持各自证据。

测试发布实际stop.json时持有GENERIC_READ/WRITE、FILE_SHARE_DELETE写句柄，独立CreateFile读取探针真实返回Winerror32。该句柄持续保持，直到原生独立发布failure.json，随后至少持满1.2秒再释放。测试没有替换原生read、时钟、stop检测或关闭实现。

## 实际命令与结果

仓库根执行：

```text
build/ms-recovery-001/runtime-proposal-venv/Scripts/python.exe -B tests/integration/qmt_cta_product/stop_lock_deadline.py --output build/ms-recovery-001/lock-through-deadline-002
```

退出0。原A600+B400组合经原ticker/目标/执行器/Adapter/Host/WinSHM只向SDK替身买1000一次，4次初始查询。持有拒绝读取句柄期间，约1.140秒收到原生`stage=stop_read`失败，1.203秒释放句柄。重复共享冲突继续使用首预算；未等到文件可读，也未反复创建新预算。

`native_error=0`对应原重试预算检查`need(false)`终止；32由独立读取探针证实，原代码仅对32/33续读。该最终诊断字段不保留最后一次瞬时共享冲突值，不能把0解释为没有发生共享冲突。

原生正常完成物理关闭并发布`closed=true, ok=false, recovery_ready=false, error_code=stop_read`；父进程最终`faulted/host_exit`、forced=false、pending=false，表示预期业务失败且没有强制退出。POSTFLIGHT证明原生已回收、双管道EOF/reader join、Host/source关闭及资源释放、server/proxy线程join，first_error/proxy_first_error均空、真实SDK0。

原RESULT复用既有`--expect-stop-read-failure`断言，保留历史字段`expected_old_stop_failure=true`；本例实际运行的是上述010安装exe，通过输入SHA识别。`actual_installed_runtime_dll=false`表示该例直接运行安装exe，没有走Python Runtime DLL入口。

## 失败观察与资格

初次以默认解释器导入该venv包时因pydantic扩展版本不匹配，在创建case前失败；已改用同一venv解释器。001测试错误要求终态native_error=32，在已收到stop_read/native_error0后触发测试断言和父故障收口，原件保留为失败，未授资格。002修正测试对原诊断语义的判断，生产代码保持原字节。

| 原件 | SHA256 |
|---|---|
| STOP-DEADLINE.json | `842b475c6db0594552d452a020eaa36c9f39bbd28dbe8e96285e5af40efb10eb` |
| RESULT.json | `e4eaf0e1e8323b69be2e9d447a4d2be698faf2f8127eddc901a5abd3fd1d0d2c` |
| POSTFLIGHT.json | `1e07d4404fbf27ef57cea58e2f10a65909861d0fe1c9154e3ad581b847706e74` |

本例补齐P21中“实际原生读取共享冲突贯穿首D”的固定条件，和既有150ms释放前成功/格式错误失败分别成立。关闭预算取1000ms，生产者未注入pending；其它预算、pending/父截止、恢复态故障及跨根责任继续逐项验证。公开读取器候选仍须C集成同版核验；原生仓位引用故障沿[独立诊断](2026-10-29-native-position-lifetime.md)处理。
