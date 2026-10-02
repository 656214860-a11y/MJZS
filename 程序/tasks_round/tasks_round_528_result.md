# R528 修复轮：剧本准备输入提示静态居中

## 轮次自检

1. 本轮是功能轮还是整理轮？修复轮；删除剧本准备输入框的滚动文字效果，并将空框提示改为水平居中静态展示。
2. 测试跑了吗？三个基线过了吗？剧本准备定向 Tk 回归 2/2、架构门禁 93/93、默认冒烟 8/8 通过；历史全量安全基线仍为 3,230 条，未将其伪造为本轮结果。
3. `project_status.md` 欠账少了吗？已关闭本轮输入框滚动提示与由此产生的持续 UI 定时回调；R182 结构专项与白模真机授权不在本轮范围。

## 根因与修复

剧本准备页的空输入提示由 `scroll_input_hint()` 每 35ms 改写横坐标并再次投递 Tk 回调。该动画不符合静态居中展示需求，并持续占用主线程事件循环。

- 删除滚动坐标与定时回调；空框失焦时仅通过 `place(relx=0.5, rely=0.5, anchor='center')` 静态覆盖提示层。
- 保留提示层点击转交真实 `Text` 输入框的行为；获得焦点或开始输入时提示立即隐藏，用户正文的左对齐编辑方式不变。
- 将原本验证“提示持续移动”的 UI 回归改为验证水平居中、静态中心定位，并静态约束不得恢复滚动函数或 35ms 动画回调；这是界面交互契约变更，未弱化测试。

## 修改范围

- `desktop.py`
- `tests/test_idea_chat.py`
- `tests/test_ui_edges.py`
- `project_status.md`

未修改用户项目数据、模型配置、密钥、阶段语义或后台任务逻辑。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest -v tests.test_idea_chat.SendMessageTests.test_clicking_the_composer_hint_focuses_the_real_input_and_hides_the_static_hint tests.test_ui_edges.UiEdgeTests.test_the_writing_page_gives_the_brief_more_room`：2/2 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：93/93 通过。

## 自检复核

本轮只改剧本准备输入提示的显示与其专用回归。提示文字在输入框中水平居中，不再随时间移动；输入框仍可点击、聚焦和正常编辑。界面改动需重启应用后生效。
