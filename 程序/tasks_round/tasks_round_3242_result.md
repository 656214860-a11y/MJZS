# R3242：主干同步后修正跨盘闭包负例夹具
<!-- round-evidence: {"commit_base": "2930fbd1", "credential_hits": 0, "evidence_sha256": "5d1d4ab8df80e049", "exit": 0, "failed": 0, "passed": 62, "round": 3242, "tests": "run_selftests.py -k stdlib_closure http_client execution_deadline dependency_whitelist"} -->

## 三问

1. 类型：修复轮，测试夹具跨盘路径根因，不改生产逻辑。
2. 验证：改前stdlib13条1红，C盘temp/D盘ROOT导致relpath ValueError；补ROOT=root后与HTTP/deadline/依赖锁共62条全绿，3.1秒。之前架构502/502见R3227；发布全量尚未绿，不冒填。
3. 欠账：闭包负例在系统temp/跨盘环境可靠，无弱化缺包/用户site/ImportError断言。完整发布验收仍未完成。

## 改动

tests/test_stdlib_closure.py：仅在test_closure_does_not_use_user_site_or_ignore_importerror既有patch.multiple中增加ROOT=root，和HERE/ENTRY同指临时夹具；保留assertIn entry与missing精确断言。

## 主干同步

本树已rebase master49da616（R3240）。保留主干R3232完整runtime必需项测试和本树白名单/缺包/用户site负例，实际stdlib13项通过。现映射：R3218 de013e2f、R3220 d5979be7、R3224 74fadd65、R3227 0e0bfc1b、R3234 2930fbd1。旧报告hash是原始真实凭据，rebase后以当前git log为准。

## 正式命令

工作目录本树程序；PYTHONUTF8=1、PYTHONIOENCODING=utf-8、PYTHONHOME=本树运行环境/Python；主树python.exe启动，生产依赖仍本树六包：

`run_selftests.py -k stdlib_closure http_client execution_deadline dependency_whitelist`：4文件/5单元/62条/0红/0skip。

此组合绕开已对照确认的复制exe MSYS初始化限制，不更改共享runtime文件或ACL。新工作树技能资料已只读复用主树两包，注册恢复73；round_gate/release_bindings等11条对照绿，见R3234后续证据。

提交由标准dev.py commit生成62条机器证据；任务整体仍执行中。下一步迁正工作树位置、在一致环境最终完整安全回归、按合入入口处理、更新任务完成文件。候选不是正式发布版，不将旧8483条28红无效回归记为绿色。
