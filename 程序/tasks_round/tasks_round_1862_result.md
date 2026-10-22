# R1862 修复轮：启动画面尺寸跳变、剧本准备文件栏复原四列、剧本结构改手动保存

## 改动
- `启动漫剧制作助手.pyw`：启动画面尺寸改为直接调用 `ui_theme.main_window_size`。原来写死“可用区 80%、上限 1080×740”，主窗口默认改成 1280×800 后，画面揭开前会跟着主窗口突然变大。
- `desktop_writing_page.py`：剧本准备的四类文件（项目设定／项目大纲／角色卡／项目剧本）从一张整宽单列表复原为四张并排表（R1779 之前的布局），表头即分类名，各自一个勾选列，四张表共用一个当前选中行；右键阶段动作仍按行类别决定。`ui_tokens.SCRIPT_KIND_COLUMN_WIDTH` 已无引用，已删除。
- `script_structure_edit_controller.py`、`desktop_script_pages.py`：取消编辑后自动保存，在「恢复」右侧新增「保存」按钮（无改动时禁用）；编辑与后退都只改内存，点保存才落盘。`ui_tokens.SCRIPT_EDIT_SAVE_DEBOUNCE_MS` 已删除。
- 剧本结构页说明文字从内容框下方挪到页头右上角的 `header_status`，随宽度自动换行，换页时清空（与分镜页的做法一致），为两块内容框让出一行高度。
- 测试：以上三处是有意的契约变更，相关测试同步改到新契约：`test_writing_page_equivalence`、`test_script_structure_page_equivalence` 里的旧实现对照稿，`test_ui_edges`、`test_idea_chat`、`test_desktop_compact_layout`、`test_writing_restart`、`test_ui_batch5_stage_panel_and_script_page`、`test_script_structure_edit`。新契约增加了以下断言：四张表并排、编辑后不落盘、保存在恢复右侧。原有断言目标没有删减。

## 验证（本轮实跑，隐藏桌面）
- 定向 9 个测试文件：297 条，0 红。
- 架构门禁：384 条，0 红。
- 冒烟测试：通过。
- 未做：全量测试；真机界面目视检查，待用户复验。
