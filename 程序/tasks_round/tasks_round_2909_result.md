# R2909 修复轮结果：pet_ui_stages.py 超行数上限修复
<!-- round-evidence: {"commit_base": "e196b527", "credential_hits": 0, "evidence_sha256": "edb59e2be97e4a58", "exit": 0, "failed": 0, "passed": 737, "round": 2909, "tests": "run_selftests.py -k pet_ui test_skills module_size"} -->

- 轮次类型：修复轮（§3.2）。根因：R2905 给 `pet_ui_stages.py` 新增勾选门禁代码后文件达 1209 行，超过 `test_module_size_ratchet` 冻结上限 1202（合并轮静态门禁实测失败：`pet_ui_stages.py: 1209 行 > 上限 1202`）。
- 分支：`codex/wip-R2909`（R2909 已领号，基于 R2905 提交 `e196b527`）。
- 三个基线：冒烟 8/8 ✔；架构门禁当轮实测见下；全量未跑（分支不累计欠账，合并轮按 §5 判定）。

## 改动（只动根因所在模块）

### `pet_ui_stages.py`（1209 → 1183 行）
- `run_skill()` 勾选块改用 `stage_flow.selected_skills(project, stage)`——与 `stage_handler_registry`/`stage_exec` 同一读取口，删掉内联 `stage_config.get` 与无用的 `chosen_set`，顺带移除不再使用的局部 `import stage_config`。
- `template_choice()`／`recovery_choice()` 下沉到 `PetPopupMixin`（`pet_ui_popup.py`）：两者同为「向用户弹窗要决定」的询问助手，行为、文案、异常兜底原样保留；`Pet` 经 MRO 解析不变，`self.pet.template_choice = ...` 实例注入不受影响。
- `from ui_widgets import ask_string` 随迁出改为只引 `ask_confirmation`。

### `pet_ui_popup.py`（104 → 128 行）
- 新增 `from ui_widgets import ask_string`；`PetPopupMixin` 收纳上述两个方法；模块 docstring 补记本轮职责扩展。

### 未动
- 行数上限 1202 未改；断言未动；`Pet` 基类顺序、方法解析、`recovery_asker` 注入点均未动。

## 测试证据

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 行数棘轮 | `run_selftests.py -k module_size` | 2/2 ✔（改动前：1209 > 1202 红） |
| Pet＋技能定向 | `run_selftests.py -k pet_ui test_skills` | 735/735 ✔，0 文件红 |
| 冒烟 | `smoke_test.py` | 8/8 ✔ |

Tk teardown 的 `invalid command name "...run"` 为既有并行拆卸噪音，非失败。
