# R3254：明确分发排除历史代理归档和窗口调试日志
<!-- round-evidence: {"commit_base": "0838f1ed", "credential_hits": 0, "evidence_sha256": "fa9a600a8d89e70f", "exit": 0, "failed": 0, "passed": 13, "round": 3254, "tests": "run_selftests.py -k distribution_build"} -->

## 三问

1. 类型：修复轮（分发边界缺项），不改生产逻辑、不删除历史文件。
2. 测试：新增单项先红；修正真实manifest后distribution_build13/13通过、1.8秒；默认冒烟9/9。主树0838f1ed发布全量仍在执行，已观察分发自检两项/soak性能项失败，不能冒填全量绿。本轮清单修复需合入后定向与发布复验。
3. 欠账：主树两项未分类旧文件已给明确排除规则，保持unknown文件失败闭锁；候选与最终安全全量、完成文件另行收口。

## 根因与改动

主树distribution_build.plan返回undecided2：`.agent-handoff/archive/snapshot-before-o06-pause-20261012.md` 与 `_wm.log`。前者2026-10-13已有归档，后者2026-11-17 14:43已有窗口探针日志，均非运行内容、均不在Git跟踪。不能删除历史证据或用allow-undecided打包。

仅在distribution_manifest.md给`.agent-handoff/**`和`_wm.log`明确排除；修正文档旧“运行时零第三方依赖”残句为requirements白名单，不改变运行源码。

新增test_actual_manifest_excludes_agent_archive_and_window_probe_log在真实manifest+临时source里构造两项，断言excluded/非keep且源字节完全不变。改前1项失败（旧归档未排除），改后模块13/13，原未知文件拒绝与不覆盖非空目录断言保留。

## 任务进度留痕

正式任务书更新已合入R3249主体和R3253安全补丁、实际候选体积、T1/T3/并发评估证据。尚未覆盖/未通过的UI退出维护与发布全量不打勾，尚不输出整体完成声明。

本轮主树实际基线为0838f1ed（R3253；以git log为准），生产requests已2.34.2且依赖15/15。候选独立构建器记录生产路径与HEAD摘要，excluded文档修改不伪称改变产品字节；最终包须含安全补丁并经自身-I验证。

## 提交与后续

按标准dev.py commit记录13条测试机器证据；提交hash由git log/evidence/R3254.json核验。主树全量运行期间不改主树；本补丁经正常合并队列处理。待其结束后读具体失败、soak在低负载定向复验且不放宽阈值，主树最终安全全量通过才能正式收口。
