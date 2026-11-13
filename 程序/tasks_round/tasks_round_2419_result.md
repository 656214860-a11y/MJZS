# R2419 结果：修复剧本准备气泡框显示错误（去描边横线、页脚入框、对齐/截断、选区高亮、留白灰条）

## 三个必答（§7）

- **轮次类型**：修复轮（§3.2）——上轮（R2416）引入的「气泡浅灰外框」在真实渲染下有五处显示缺陷，本轮逐一修复。
- **测试跑了吗、三个基线过了吗**：
  - 定向 `run_selftests.py -k test_idea_chat test_req_s01_anchors test_script_composer`：**169 条，0 红，ALL TESTS PASSED**（含新增 3 条锚点断言）。
  - 默认冒烟 `smoke_test.py`：**8/8 通过**。
  - 架构门禁／全量：未跑（本轮只改气泡渲染的 L4 单模块与对应测试/文档，不命中 §5 触发条件）。
- **project_status.md 的欠账少了吗**：无新增欠账。

## 根因与修复（五个显示缺陷）

1. **外框两条黑色横线**：`relief='solid'` + `borderwidth=1` 在 Tk Text 里按每个显示行各画一圈描边，多行正文行间出现横线。改为不设 `relief`（默认 flat），只保留 `background=BUBBLE_FILL` 淡底。
2. **SKILL 提示文字在框外**：页脚 tag（`bubble_<n>_time`）之前 `lmargin1=left`（贴框左边沿）且无底色。改为与正文同缩进（`body_left`/`body_right`）、同淡底（`background=fill` + `lmargincolor/rmargincolor`），页脚并入同一灰色底框。
3. **SKILL 提示「没对齐、显示不完全」**：`wrap='none'` 超宽被内容框裁掉，改回 `wrap='word'` 自动换行；`justify='left'` 左对齐且缩进与正文一致。
4. **选择文字显示不明显、光标跳动**：新建的气泡淡底 tag 默认优先级高于 `sel`（选区 tag），盖住选中高亮。`add_bubble` 每插一条后 `tag_raise('sel')`，把选区提到最高，选中文字始终显示选区色。
5. **用户气泡左侧灰色满屏长条**（本轮核心）：上一轮把留白区域颜色（`lmargincolor`/`rmargincolor`）也刷成 `BUBBLE_FILL`，右对齐的用户气泡左侧留白宽达大半屏、整块涂灰，文字被挤进窄缝。留白改回内容框底色 `BUBBLE_BACK`（白），灰色只铺正文 `background`——灰框贴着字、按字宽收窄。

## 改动文件

- `desktop_idea_bubbles.py`（去描边、页脚入框、wrap 修复、sel 优先级、留白回白）
- `docs/stages/S01_剧本准备.md`（REQ-S01-65 / DES-S01-65 同步）
- `tests/test_idea_chat.py`（页脚在框内、同缩进、同淡底、wrap=word 断言）
- `tests/test_req_s01_anchors.py`（无 relief 描边断言、sel 优先级高于气泡 tag 断言）
- `tests/test_script_composer.py`（注释措辞同步）

## 提交

- 提交信息：`R2419: 修复气泡框显示错误（去描边横线、页脚入框、留白灰条、选区高亮）`
