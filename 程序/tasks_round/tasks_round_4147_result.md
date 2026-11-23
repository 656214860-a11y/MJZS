# R4147 结果：SKILL 改名后半段失败回滚（FIX-AUD-SKILL-RENAME）
<!-- round-evidence: {"commit_base": "3383684c", "credential_hits": 0, "evidence_sha256": "907bd48d949ae9b0", "exit": 0, "failed": 0, "passed": 22, "round": 4147, "tests": "run_selftests.py -k skill_lifecycle"} -->

## 开头三问

（一）本轮类型：修复轮。任务卡 FIX-AUD-SKILL-RENAME（队列 168）；缺陷 AUD-SKILL D8——`apply_rename` 落盘后迁引用／台账／禁用无补偿。车道 `codex/fix-aud-skill-rename`，基准 `3383684c`。

（二）测试与三个基线：`run_selftests.py -k skill_lifecycle` 改前 22 条里 1 条红，改后 22 条全过（原 21 + 新增 1），退出码 0。`smoke_test.py --architecture` 首次因本卡回滚用了 `unlink` 与裸 `except Exception: pass` 红 2 条；改为 `recycle_paths`＋`app_logging.swallowed()` 后 700 条全过，退出码 0。默认冒烟与全量未跑。

（三）欠账：无。回滚尽力而为；若回滚自身再失败只留 swallowed 痕迹。

## 缺陷复现

mock `_migrate_project_refs` 抛 `OSError`：落盘已改名、引用未迁。新用例断言旧清单仍在、新文件不在——改前 `AssertionError: False is not true : 后半段失败后旧清单应仍在原位（或已回滚）`。

## 改了哪些文件

- `ui/skill_lifecycle_service.py`：拆 `_apply_disk_rename`／`_rollback_disk_rename`／`_rollback_rename`；`apply_rename` 后半段失败逆序回滚；新文件经 `recycle_paths` 回收；回滚异常经 `app_logging.swallowed()`。
- `tests/test_skill_lifecycle.py`：新增 `test_apply_rename_rolls_back_when_post_steps_fail`。
- 本结果文件。

## 命令与结果

| 命令 | 结果 |
| --- | --- |
| 开工三查 | 干净；`3383684c`；`codex/fix-aud-skill-rename` |
| `run_selftests.py -k skill_lifecycle`（改产品前） | 退出码 1；22 条，1 红（回滚断言） |
| 同上（改产品后） | 退出码 0；22 条；`ALL TESTS PASSED` |
| `smoke_test.py --architecture`（回滚初版） | 退出码 1；`unlink` 与静默 except 两处 |
| 同上（改后） | 退出码 0；`Ran 700 tests in 235.681s`；`OK` |
| `scripts\dev.py claim` | 领到 4147 |
