# R529 修复轮：窄窗口保留剧本附件入口

## 轮次自检

1. 本轮是功能轮还是整理轮？修复轮；修复剧本准备输入行在窄窗口中遮挡右侧文件上传图标的问题。
2. 测试跑了吗？三个基线过了吗？窄窗口及提示层定向 Tk 回归 2/2、默认冒烟 8/8、架构门禁 93/93 通过；历史全量安全基线仍为 3,230 条，未将其伪造为本轮结果。
3. `project_status.md` 欠账少了吗？已关闭本轮输入框挤出附件入口的布局缺陷；R182 结构专项与白模真机授权不在本轮范围。

## 根因与修复

输入框先以 `pack(side='left', fill='x', expand=True)` 参与布局，附件按钮随后才加入右侧。在可用宽度不足时，先扩展的输入框可占满输入行，使后加入的按钮没有可见空间。

- 将附件按钮的右侧 `pack` 调整到输入框之前；按钮先取得固定宽度，输入框仅填充余下空间。
- 新增 360px 窄窗口回归：验证附件图标仍映射、有实际宽度、位于输入行右边界内，且输入框已经缩短。

## 修改范围

- `desktop.py`
- `tests/test_idea_chat.py`
- `project_status.md`

未修改用户项目数据、模型配置、密钥、阶段语义或后台任务逻辑。

## 验证

- `D:\漫剧制作助手\运行环境\Python\python.exe -m unittest -v tests.test_idea_chat.SendMessageTests.test_narrow_composer_keeps_the_attachment_button_visible tests.test_idea_chat.SendMessageTests.test_clicking_the_composer_hint_focuses_the_real_input_and_hides_the_static_hint`：2/2 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py`：8/8 通过。
- `D:\漫剧制作助手\运行环境\Python\python.exe smoke_test.py --architecture`：93/93 通过。

## 自检复核

本轮只调整输入行的现有布局顺序，文件选择行为、输入框编辑行为及附件限制均未改变。同类右侧固定操作应先布局、可伸缩文本区后布局；本轮已为当前输入行加入窄宽自动回归。界面改动需重启应用后生效。
