# R1723：可靠性轮——smoke_test --affected 按真实 import 选中消费者测试

- 本轮类型：任务书指定的修复轮；测试运行：部分通过，指定运行器命令未形成成功退出凭据；三条基线：默认冒烟未单跑、架构门禁未完成、全量不在本任务范围内；`project_status.md` 欠账：未读取/未修改。
- 状态：`[TASK_BLOCKED]`。实现和专项回归已完成，但任务书指定的运行器/GUI 验收在允许修改范围外退出，不能如实标为完成。

## 改前红

先新增 `tests/test_smoke_affected_consumers.py`，再运行：

```text
AttributeError: module 'smoke_test' has no attribute 'affected_test_modules'
```

说明旧实现没有按直接 import 查找测试消费者的入口；`test_animatic_scope.py` 虽 `import stage_layout`，文件名并不含 `stage_layout`。

## 改动

- `smoke_test.py`：仅在 `--affected` 运行时递归读取 `tests/**/test_*.py`，用 AST 收集 `import X`、`import X as y` 与 `from X import y` 的直接导入；将对应测试模块名追加到传给 `run_selftests.py -k` 的筛选词。
- 既有 `_AFFECTED_TEST_ALIASES` 和 `affected_test_filters()` 的输出保持不变；只由 `check_the_gate()` 使用增强后的计划，现有调用方式不变。
- `--affected` 现在打印实际选中的测试文件数及前八个模块名。
- 新增专项测试：独立 AST 扫描验证所有直接导入 `stage_layout` 的测试模块均在选中集合中，并锁定一个无模块名的真实消费者 `test_animatic_scope`；同时验证 `skill_registry -> skills` 别名仍保留。

## 实测

| 命令 | 结果 |
| --- | --- |
| `python -B -m unittest tests.test_smoke_affected_consumers`（`PYTHONPATH=tests`） | 2/2 通过，5.909 秒 |
| `python -B run_selftests.py -k selftests smoke_affected` | 运行器汇总 61 条、0 红（3.9 秒），但汇总后进程以 `-1` 退出，未产生成功退出凭据 |
| 旧筛选基线：`python -B run_selftests.py --serial -k stage_layout` | 1 个测试文件、21 条、3.4 秒、0 红；汇总后同样以 `-1` 退出 |
| `python -B smoke_test.py --affected stage_layout` | 正确打印 25 个选中模块及前八个名称；在申请跨树 GUI 令牌后于 109 秒以 `4294967295`（Windows `-1`）退出，未执行选中测试 |
| `python -B smoke_test.py --architecture` | 已输出连续通过项，但在完成前以 `-1` 退出，未形成架构门禁成功凭据 |

性能口径：旧筛选的实际执行为 1 个文件/3.4 秒；增强后已确认选中 25 个文件，但因 GUI 令牌/运行器退出未执行完，不能捏造“改后总耗时”或声称未变慢。扫描仅发生在 `--affected`，不在导入或普通启动路径发生。

## 需决事项

请由负责 `run_selftests.py`/跨树 GUI 令牌的任务先解决上述 `-1` 退出与令牌持有问题，随后重跑任务书的三条运行器命令。该文件不改动 `run_selftests.py`，以遵守本任务允许文件范围。

## 独立验收（Claude，隔离验证工作树 HEAD＋车道 lane_affect 文件）

- `tests.test_smoke_affected_consumers` OK；`-k selftests smoke_affected` 0 红。
- `smoke_test.py --affected stage_layout`：选中 25 个测试文件，50 秒，0 个文件有红（改前只选中 1 个文件、3.4 秒）。执行方在 Codex 沙箱里跑到这里退出码 -1，隔离树外复跑正常，属沙箱限制。
- `smoke_test.py --architecture`：首跑 1 红，`test_unification_ratchet` 第四项 `smoke_test.py:114→115` 纯行号平移；Claude 同步 `维护记录/架构统一基数.json` 该条 point，单跑 OK，其余 367 条 OK。
- `review_batch.py --lane affect`：0 失败、0 告警。执行模型：Codex gpt-5.6-terra（首次试用）。
