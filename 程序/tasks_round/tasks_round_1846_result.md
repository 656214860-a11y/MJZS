# R1846 结果：把重构批次 A+B+C+D 分支合并到 master（合并轮）

- 合并：`claude/project-handoff-f6eb50`（R1812–R1845）→ master，合并前 master 为 aa3e2efe（R1844）。
- 合并前验证：分支 `--all --safe`（隐藏桌面）。除常驻红外的失败，与 master 对照后，只在分支红的 4 条已在 R1845 修复；托盘创建失败和其余 13 条在 master 上同样红，属隐藏桌面环境问题，未修。
- 冲突与集成修复：
  - `desktop_script_pages.py`：取分支的类改写，移植 R1842 的 `_install_script_edit_controls`（编辑／后退／恢复＋自动保存），入参从 9 个收成 `(page, controls, box)`
  - `ui_widgets.py`：取分支的 Splash（R1793 计时与 update_idletasks 版），覆盖 R1844 恢复的旧版
  - `pet_ui_voice.py`：R1826 使 `PetVoiceMixin` 超出类上限 1119（1141 行）。把纯逻辑提为模块级函数 `offer_sentence`、`offer_reply`、`offer_backoff`，删去恒真的 `if verdict is False`，回到 1119，行为不变
  - `script_structure_edit_controller`（R1842 新模块）登记为 L2 待审计范围；覆盖率基线重跑工具刷新为 299 个模块，runbook §11 同步
  - `test_script_structure_page_equivalence`：旧实现换成 master aa3e2efe 的闭包版，只把编辑控件的调用适配为新签名；`test_script_structure_edit`：调用点同步。断言未动
  - `project_status.md` 只有表头冲突，取 master 一侧；分支轮次在 R1847 补记
- 合并后验证：`-k script_structure splash app_metadata launcher ui_widgets architecture script_pages reading_density pet_ui pet_offer pet_voice pet_agent pet_chat` 只剩两条红：常驻的 `test_round_number_continuous`，以及全量欠账提示（提交后钩子会在后台补跑全量）。
- 已提交：本合并提交。未 push。
