# R4522 设置、技能包与剧本文档编辑器
<!-- round-evidence: {"commit_base": "3339fe8cf", "credential_hits": 0, "evidence_sha256": "b7aced5cfc9067a7", "exit": 0, "failed": 0, "passed": 193, "round": 4522, "tests": "run_selftests.py -k pet_settings pet_skills_manage ui_theme ui_widgets_dialogs ui_batch7_settings_models script_autosave storyboard_page_loading"} -->

## 三问

本轮为界面改进与缺陷修复。设置和模型管理采用主界面的导航图标与选中态，按字段内容限制控件宽度。SKILL 管理以真实技能包为父行展示子技能。结构剧本与初步分镜在正文右上角提供关闭按钮，编辑中先保存，保存失败保留内容。两个编辑器的导航在左侧。用户选择的文件继续由项目文件面板管理。

定向验证覆盖技能包与独立技能、筛选及子技能操作范围、设置键盘导航、模型切换、关闭重开和保存失败、主题切换后的正文/光标/选区、弹窗和上下文菜单。具体定向用例数与返回码以本轮机器凭据为准。使用隔离项目与隐藏桌面实测设置、模型、两种编辑器以及一个包含两个子技能的包。未运行全量用例。

本轮解决设置说明重复、模型管理部分字段溢出、场次目录挤占正文和夜间脚本文字对比度问题。系统文件选择器保留 Windows 外观。未更改用户的项目数据和模型配置格式。
