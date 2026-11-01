# R689 结果｜阶段配置 SKILL 中文显示

## A. 轮次类型与目标

- 类型：修复轮。
- 目标：阶段配置页面的 SKILL 用户可见名称只保留中文，不显示英文名称或内部标识。

## B. 改动

- `skill_panel.py`：新增 `chinese_skill_display()`；面板勾选项、悬停全文、说明目录及保存结果提示统一经该函数渲染。
- 英文只从 UI 显示层移除；注册表 ID、工作流路径、勾选框内部索引与配置落盘均不变。纯英文自定义名显示为“自定义技能”。
- `tests/test_skills.py`：新增中英混合显示名、带 `SKILL.md` 的自定义路径和纯英文名称的回归。

## C. 验证

- 新增专项：`tests.test_skills.PanelTests.test_stage_panel_skill_display_only_keeps_chinese`，1/1 通过。
- 默认冒烟：`smoke_test.py`，8/8 通过。

## D. 自审

- 通过：改动仅限阶段配置页面的用户可见文本；未修改 SKILL 文件、注册表、项目配置或执行路径。
- 同类风险：说明正文仍按原 SKILL Markdown 显示，属于内容说明而非名称标签，未被篡改。

## E. 结论

`[TASK_COMPLETE]`：阶段配置页的 SKILL 名称已统一只显示中文，且保留内部引用兼容性。
