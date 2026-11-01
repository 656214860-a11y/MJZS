# R1031 验证/基线轮：剩余 UI 入口覆盖审计

- 整理轮；仅复核优化清单的 UI 覆盖，不修改视觉、行为或生产代码。
- 本轮 UI 定向 67/67（24.721 秒）、默认冒烟 8/8；最近独立架构为 R1028 的 301/301，最近安全全量为 R1029 的 3934/3934、359.139 秒。本轮没有跨层或高风险实现变化，不重复全量；距真实全量 2 轮。
- 欠账：将“覆盖率待审计”分为已扫描、有限保护和明确遗漏；不把审计完成写成全部页面迁移完成。

## 方法与边界

对 git ls-files 列出的 247 个生产 Python 模块作 AST 调用扫描，解析直接 import/from-import 别名；排除 tests、tasks_round、维护记录、private、episode、writing、配置、logs、临时与备份目录；组件实现、主题、测试执行器及对话/通知/快捷键权威模块不作为业务绕过项。此静态扫描不涵盖动态别名、反射或视觉实机结果。

UI/UX 技能仅用于提醒键盘焦点与反馈必须另行实机验证；未采用 Web 专用 CSS 建议，未修改项目设计权威或生成新设计系统。

## 覆盖矩阵

| 对象 | 当前证据 | 限制/结论 |
| --- | --- | --- |
| 弹窗 | test_dialog_boundary.py:16；本轮 AST 业务 Toplevel 为 0 | 原门禁主要扫描根目录，本轮补查已跟踪子模块；不等同于模态/焦点实测 |
| 表格 | test_data_table_boundary.py:15 全目录门禁；原生 Treeview 3 处 | desktop.py:298、3712、3805 是既有导航树例外，不应盲迁为平面表格 |
| 按钮 | test_button_boundary.py 对指定页面检查 ttk.Button | 尚有 tk.Button 4 处：app.py:353、desktop.py:111、112、video_navigation.py:118；现门禁漏检 tk 分支 |
| 文字层级 | test_text_component_boundary.py:13 列出 5 个受保护页面 | 原生带字体/颜色标签 50 处是候选，不是 50 个确定缺陷；asset_batch.py:141 为使用 token 的标题，asset_detail.py:305、309 仍有手写字体/颜色 |
| 下拉框、通知、菜单、文件选择、快捷键、Tooltip、滚动条 | 对应 boundary 测试已有递归扫描，本轮通过 | 规则分别保护样式覆盖、裸入口、Ctrl/Command 注册等；不代表所有交互语义已验收 |
| 忙碌态 | test_busy_state_boundary.py:11、25 保护桌面主链 | 不是全页面 busy 覆盖证明；后台迟到结果另由 R1029 生命周期矩阵验证 |
| 阶段展示 | test_stage_display_boundary.py:14、30 保护主导航与未知阶段回退 | 非所有用户可见文案扫描；13 参考网站是工具页 |
| 输入框、复制、图标 | 已有 R928–R930 审计及专门门禁 | 本轮不重复迁移，不宣称新增完成量 |

## 后续整改边界（未在本轮执行）

1. 按钮按上述 3 个模块一批处理，先核对危险操作按钮、日志工具按钮和带图返回按钮的既有语义；同步补 tk/ttk 与导入别名门禁，禁止改删除语义或弱化原断言。
2. 标签按标题/提示/状态分类后再迁移；50 个候选不能自动替换为 HintLabel。Card/token/焦点/忙碌态仍须逐页验证，不借审计报告伪造视觉验收。
3. 本优化清单中的“剩余 UI 入口审计”已交付；上述实现迁移作为明确后续范围，不在审计轮偷偷扩大修改。

## 验证与提交

定向命令：随附 Python -B -m unittest tests.architecture.test_{dialog,data_table,button,text_component,combobox,notification,busy_state,context_menu,file_dialog,shortcut_registry,tooltip,scrollbar_theme,stage_display}_boundary（逐个模块传参，非字面花括号命令）。默认 smoke_test.py 为 8/8。报告/状态一致性在收尾复核。

仅新增本报告并更新状态页；未改 .py、配置、历史结果、用户数据或密钥，未删除任何文件。文档/轮次回归 15/15（0.318 秒），N=1032/M=1031，git diff --check 通过，自审通过；提交前精确暂存与凭据形态扫描。收尾提交 R1031: 审计剩余UI入口覆盖，提交哈希以 Git 历史及回复为准。

[TASK_COMPLETE] UI 入口审计完成，不等于 UI 全部迁移完成。下一项核对 C4 真实性能凭据与优化清单收尾条件。
