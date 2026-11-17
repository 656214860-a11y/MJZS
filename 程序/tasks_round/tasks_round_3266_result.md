# R3266 结果 · U7 任务书收尾（完成文件＋遗留项登记＋门禁名核对）
<!-- round-evidence: {"commit_base": "1e08035f", "credential_hits": 0, "evidence_sha256": "979fb639547e2fc6", "exit": 0, "failed": 0, "passed": 0, "round": 3266, "tests": "docs-only"} -->

- 轮次类型：文档轮（UI 统一组件标准任务书 U7；任务书 §5 明确 U0/U7 文档轮不跑 smoke 与 selftest）。
- 三问：测试未跑（文档轮）；适用验证为 `test_taskbook_closure` 8/8 绿（含 `test_real_repo_state_is_clean` 对真实仓库状态的全量校验）；欠账口径：本轮把 D16 范围外项与各门禁存量冻结清单登记入 `维护记录/优化待办队列.md`，不产生新欠账。

## 改动

- 新增 `tasks_round/任务完成/UI统一组件标准·任务完成.md`：U0–U6 全部 29 条验收勾选＋U7 自身 2 条收尾勾选共 **31 条逐条对账**，每条给轮次号、结果文件、commit hash 与测试凭据；全部完成、无未完成项、无处置项。
  - 命名说明：任务书 §U7 字面写 `UI统一组件标准任务书·任务完成.md`，与 `taskbook_closure.stem_of` 同名规则（任务书文件名去 `任务书.md` 后缀）冲突会成孤儿文件；按门禁口径命名并在文件头注明。
- `维护记录/优化待办队列.md` 新增「UI 统一组件标准遗留项（R3266 登记）」节：
  - UI-U7-1 键盘焦点覆盖审计（`takefocus` 11 处、含 "focus" 行约 188 处，计数不足以证明覆盖完整；D16 范围外）；
  - UI-U7-2 深色模式／主题切换（D1/D16 范围外）；
  - UI-U7-3 各门禁存量冻结清单指针（测宽 15+2、Box 边框 3、字体 11/6、自配颜色原生控件 63/13、表单 5/5、图标两门禁基线），注明「谁改谁迁，只减不增」。
- 门禁名核对：`ui_components.md` 全部门禁名（`test_text_measure_boundary`／`test_nav_icon_size_boundary`／`test_icon_source_boundary`／`test_box_boundary`／`test_font_boundary`／`test_native_control_boundary`／`test_form_control_boundary`）与 `tests/architecture/` 实际文件名逐一相符；发送键节无独立边界门禁、由 `test_script_composer`／`test_shared_input_ui` 锚定（U0 已定口径）。
- `任务完成/README.md` 已存在（此前任务书建档），无需改动。

## 验证

- `python -B -m unittest tests.architecture.test_taskbook_closure -v` → **8/8 绿**：`test_real_repo_state_is_clean` 对真实仓库校验通过——完成文件与任务书同名对应、31 条勾选全覆盖、证据/处置标记 31+ ≥ 任务条数、无孤儿完成文件、README 在档。
- 门禁名核对为人工逐条比对（文档轮无代码行为变化）；U0–U6 各轮测试凭据见对应结果文件与 `tasks_round/evidence/R<轮次>.json`。
- 未跑：smoke／selftest／`--architecture` 全量（文档轮按 §5 不跑；本轮改动仅 `tasks_round/任务完成/*.md` 与 `维护记录/优化待办队列.md` 两个文档，无 `.py`）。

## 基线与欠账

- 任务书 U0–U6 全部验收勾选完成并留痕；遗留项三项已登记待办队列（焦点审计、深色模式、冻结清单指针），均为任务书明示的范围外或「谁改谁迁」存量。
- `project_status.md` 欠账无变化（仅 master 可提交，合并轮统一补记）。

## 提交

见 git log（`codex/wip-R3241`）。
