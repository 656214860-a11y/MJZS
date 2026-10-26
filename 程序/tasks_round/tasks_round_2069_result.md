# R2069 结果（修复轮）

- 轮次类型：修复轮（§3.2）。
- 测试：本轮已运行，三基线结论见下；`--affected` 一项有 1 条红，经单独复跑判定为非本轮引入的间歇失败。
- 欠账：`project_status.md` 欠账未减少（本轮不涉及）。

## 根因

repository-quality-guard 便携试跑指出两处问题：
1. `desktop_login_gate.py:55`（QG183）：登录闸直接读三虎的私有成员 `pet._cloud` 并调用 `.close()`，越过了三虎已有的公开接口 `cloud_visible()`／`close_chat()`（`pet_ui_view.py`、`pet_ui_voice.py`）。三虎内部改了云朵实现，闸门就会悄悄失效。
2. `cloud_assets.py:107`（ruff F401）：`settings()` 导入了 `LineInput` 但没用。

## 复现（先红）

新增 `tests/test_login_gate.py::test_gate_closes_visible_cloud_via_public_pet_api`：用一个只有公开接口、没有 `_cloud` 的三虎桩。改动前：

```
    self.assertEqual(Pet.closed,1)
AssertionError: 0 != 1
```

## 改动

- `desktop_login_gate.py`：改为 `pet.cloud_visible()` 判断，`pet.close_chat()` 收起。
- `cloud_assets.py`：删去未使用的 `LineInput` 导入。
- `tests/test_login_gate.py`：新增上述用例；已有断言未动。

## 验证

| 命令 | 结果 |
|---|---|
| `run_selftests.py -k login_gate cloud_assets`（隐藏桌面） | ALL TESTS PASSED |
| `smoke_test.py --affected desktop_login_gate cloud_assets` | 1 条红：`test_ui_edges.BriefTintTests.test_the_users_own_words_show_up_on_the_display` |
| 该文件撤销本轮改动后单跑 `-k test_ui_edges` | ALL TESTS PASSED |
| 该文件带本轮改动单跑 `-k test_ui_edges` | ALL TESTS PASSED |
| `smoke_test.py`（默认） | 通过 |

上面那条红与本轮改动无关：它测的是创意简报显示，本轮改动前后单跑都通过，判定为批量运行时的间歇失败，留待后续排查。
