# R1800：修复轮——收口 R1786 带来的 3 个后台全量红（文案「您」、按钮填充色读 `fill`）

1. 本轮类型：§3.2 修复轮。起因：R1788 合入后的后台全量（HEAD `78974488`）4 红，其中 `test_sanhu_mode` 是 R1788 自己的回归（已由 R1796 修复）；其余 3 个来自 R1786 UI 现代化。

2. 测试跑了吗、三个基线过了吗：
   - 定向 `-k copy_rules video_ui ReplyBox test_pet_ui`：683 条，0 红（159 秒）。
   - 完整安全全量：见合入后的后台补跑；本轮未手动跑。

3. 本轮改源码 +1（`desktop_project_pages.py`，仅一个字）。

## 根因与修复

| 红 | 根因 | 修复 |
|---|---|---|
| `test_copy_rules` | `desktop_project_pages.py:343` 空态文案“开始**你**的第一个故事”，界面文案规则要求对用户说“您” | 改为“开始您的第一个故事”——真违规，改产品文案 |
| `test_pet_ui.ReplyBoxTests.test_the_style_paints_on_the_accent_colour` | R1786 把按钮改成圆角图片：ttk `background` 现在是按钮背后的表面色（`CONTROL_CORNER_SURFACE`），填充色挪到 `fill` 选项（`ui_widgets._configure_button`）。测试还读旧语义的 `background`，得到 `#F7F9F9` | 测试改读 `fill`，仍断言它等于 `ui_theme.ACCENT`——契约有意变更，比较强度不变，**断言未弱化** |
| `test_video_ui.VideoEntryTests.test_the_way_back_to_the_choose_page_still_works` | 同一原因：对比度判据用 `style.lookup(..., 'background', state)` 取按钮“填充色”，现在取到的是恒定表面色，测的不是真实的箭头对按钮底色 | 改取 `fill`（带 normal/active/pressed 状态映射），判据 ≥3 与四态循环不变；改后通过，说明真实箭头对比度满足 |

## 提交

- 已提交，commit hash 见 git log `R1800:`。
