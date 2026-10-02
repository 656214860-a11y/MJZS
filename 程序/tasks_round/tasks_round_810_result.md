# R810 结果：SKILL 流水线契约对齐

## 范围

- 对齐 01—12 阶段 pipeline 的输入、输出和上游依赖；资产链改为“自动补全 → 版权过滤”。
- 对白润色迁至剧本整理，音画同步预检迁至后期剪辑；视频链不再依赖音频链。
- 新增注册 SKILL DAG 和 pipeline 阶段 IO／manifest 归属两项架构门禁。

## 验证

- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：177/177 通过。
- `python run_selftests.py -k skill script_contract pipeline dependency`：198 条／0 红。
- 注册表：`problems() == []`，总数 73；script/video/edit 成员探针与迁移后的阶段归属一致。
- 首次 `python run_selftests.py --all --safe`：3,614 条，唯一红项为 `architecture.test_round_baselines`，它在 R809 报告尚未记录安全全量时按轮次纪律拒绝通过。
- R810 报告落盘后重跑 `python run_selftests.py --all --safe`：3,614 条／0 红／882.9 秒，`ALL TESTS PASSED`；`last_full_safe_all_round` 推进至 R810。

## 实测命令原始末尾输出

```text
> python smoke_test.py
通过：8 项
失败：0 项
✅ 冒烟测试通过，可以进入下一轮

> python smoke_test.py --architecture（按 94 个架构测试文件分 5 组执行）
Ran 45 tests in 14.279s  OK
Ran 37 tests in 9.019s   OK
Ran 32 tests in 13.807s  OK
Ran 40 tests in 6.599s   OK
Ran 23 tests in 2.715s   OK

> python run_selftests.py -k skill script_contract pipeline dependency
共 198 条用例，6.4 秒；0 个文件有红
ALL TESTS PASSED

> python -m unittest tests.architecture.test_round_baselines
Ran 4 tests in 0.088s
OK
EXIT=0
```

## worktree 环境缺件记录

worktree 环境曾有三项非代码缺件：外置 SKILL 包未带入、`tasks_round` 被 gitignore 排除、工作路径含 `.codex` 而触发路径断言。本轮已切换主工作区验收；此记录作为后续整改输入。
