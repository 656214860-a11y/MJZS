# R2307 修复 R2278／R2283 引入的两处自检红（缺陷修复轮）

## 现象
全量验收里有 2 个真实失败（对照 J 路线之前的提交同样红）：
- `test_final_viewer` 3 条：R2278 的两级模型选择器放进阶段配置按钮行，该控件没有 `text` 选项，测试直接 `cget("text")` 抛 `TclError`。
- `test_script_composer::test_message_icons_show_on_hover_and_act_on_the_whole_message`：R2283 在正文与图标行之间加了页脚行（`<name>_time`），旧断言“正文末尾 == 图标行起点”变成 3.0 != 4.0。

## 改动（仅测试）
- `tests/test_final_viewer.py`：新增 `text_of`，读不到文字当空串；3 处 `cget("text")` 改用它。**断言未动。**
- `tests/test_script_composer.py`：布局契约变为“正文 → 页脚 → 图标行”，相邻断言拆成两条（正文末尾==页脚起点、页脚末尾==图标行起点）；其余断言（含 lmargin 对齐）原样保留，未弱化。

## 验证
- 已跑：`run_selftests.py -k final_viewer script_composer`（经 gui_hidden）→ 21 条，0 红。
- 未跑：全量／架构门禁（只改测试文件）。全量里另 5 个红是本工作树环境问题（`剧本锻造` 子模块未初始化、desktop.py 换行符、gitignored `基准历史.json`），与本轮无关。

## 回滚
`git revert` 本轮提交。
