# R1796：修复轮——恢复被 R1788 误删的 project_settings.set_auto_submit（全自动模式漏开自动提交）

1. 本轮类型：§3.2 修复轮。起因：R1788 合入后后台全量（HEAD `78974488`，6244 条、1235 秒）红 4 个文件，其中 `test_sanhu_mode.test_auto_mode_enables_every_registered_auto_action` 是 R1788 引入的真回归。

2. 测试跑了吗、三个基线过了吗：
   - 先红后绿：该用例在后台全量里红（`project_settings.get(...)` 对 `DEFAULTS` 里每个键应为 True，`auto_submit` 仍为 False）；恢复后定向 `-k sanhu_mode project_settings unattended pet_ui_stages` 10 条 0 红。
   - 完整安全全量：见合入后的后台补跑；本轮未手动跑。

3. project_settings.py 属源码，本轮改源码 +1。

## 根因

R1788 把 `set_auto_submit` 当成零引用函数删了。它只在 `pet_ui_stages.py:758` 以 `getattr(project_settings, 'set_' + key)` 的**拼接名**被取用：全自动模式对 `DEFAULTS` 的每个键调用 `set_<键>`，缺一个就记为失败，`auto_submit` 不再被打开。前面的只读调查已注明“拼接名无法识别”，我却把它当“高把握零引用”删了——判据错在只做了字面量 `git grep`。

## 修复

- 按原样恢复 `set_auto_submit`（与 R1788 之前逐字一致）。
- 复查 R1788 删除的其余函数（`write_anchors`／`write_triplets`／`asset_deletion_references`／`workspace_settings_path`／`worker_bad`／`rhythm_template_reference`／`duty_rows`／`unit_name`／`Splash`／`ContractExampleAdapter`／`adapter`）：对 `getattr`、`globals()`、`__dict__`、字符串拼接前缀做了全仓检索，无其它动态引用。

## 同一次后台全量里的另外 3 个红（不由本轮或 R1788 引入，未处理）

R1786 UI 现代化带来，需要该轮负责人定夺设计取舍，不在本轮范围：

- `test_copy_rules`：`desktop_project_pages.py:343` 的文案“还没有项目”违反界面文案规则。
- `test_pet_ui.ReplyBoxTests.test_the_style_paints_on_the_accent_colour`：回复框样式期望强调色 `#0F6FC0`，实际 `#F7F9F9`。
- `test_video_ui.VideoEntryTests.test_the_way_back_to_the_choose_page_still_works`：返回箭头对比度 2.54 < 3。

## 提交

- 已提交，commit hash 见 git log `R1796:`。
