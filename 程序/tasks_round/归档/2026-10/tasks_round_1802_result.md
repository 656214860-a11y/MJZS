# R1802：结构治理轮——压平 5 个深嵌套函数（批次 A）＋修复合并留下的冲突标记

1. 本轮类型：§3 结构治理轮（只重构，不改行为）。每处先把旧实现原样内嵌进新测试做对照，再改写，再从 `test_complexity_ratchet.py` 的 `NESTING_CAPS` 删登记。

2. 测试与基线：
   - 等价测试（新增 5 个文件）：`parse_worktree_list`（87 例）、`pet_agent.save_settings`（151 例）、`Pet.click`（10 个意图）、`frames_ready` 逐镜头判定（27 例）、`resume_preview` 逐步处置（768 例全组合）。
   - 相关测试加架构门禁 1187 条：除 `test_round_number_continuous` 外全绿；该条是分支上状态页轮次头只能在 master 更新（钩子规定）所致，合入 master 时三方合并采用 master 的头。
   - 完整安全全量：本轮未跑。

3. project_status.md 欠账：本轮改源码 +1。

## 改了什么
| 位置 | 做法 | 嵌套 |
|---|---|---|
| `workspace_maintenance.parse_worktree_list` | 字段表 `_WORKTREE_FIELDS`／`_WORKTREE_FLAGS` ＋ `_apply_worktree_line`／`_flush_worktree` | 7→登记删除 |
| `pet_agent.save_settings` | 按键查 `_SETTING_NORMALIZERS`，`_SKIP` 表示丢弃 | 7→登记删除 |
| `pet_ui.Pet.click` | `_CLICK_ACTIONS` 分派表（动作在调用时才取 pet 方法，测试替换照样生效） | 10→登记删除 |
| `stage_parallel.frames_ready` | 抽 `_shot_frame_problem`，返回（毛病，首帧是否存在），保留“异常前已存在也计 any_frame” | 7→登记删除 |
| `skill_orchestrator.resume_preview` | 抽 `_step_verdict`（elif 链改早返回；参数收成 `checks` 元组避免超 7 参） | 9→登记删除；`Orchestrator` 类上限 720→719 |

未动：`writing_api._preparation_step`（10 参，换写法收益小）。

## 同轮修复上一提交（R1801 合并）的疏漏
R1801 合并 master 时 `tests/architecture/test_function_size_ratchet.py` 的冲突标记被误提交（导致 3 个架构文件红）。本轮解决：`content_box` 取 master 的 181，`Desktop.__init__` 上限 165（R1786 带入的增长）。
另记一条发现（已在 R1801 处理）：master 的 R1788 误删 `ui_widgets.Splash`，而 `启动漫剧制作助手.pyw` 在 try/except 里引用它，启动画面被静默吞掉；R1801 已恢复 Splash 与 13 个 SPLASH_* 令牌，并把 `ui_widgets.py` 加回 `test_app_metadata.DISPLAY_SOURCES`。建议 master 侧补一条“.pyw 引用的名字不得被死代码清理删除”的守护。
