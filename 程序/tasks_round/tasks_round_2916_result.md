# 任务结果 R2916
<!-- round-evidence: {"commit_base": "64f7546d", "credential_hits": 0, "evidence_sha256": "7150da784588581e", "exit": 0, "failed": 0, "passed": 375, "round": 2916, "tests": "run_selftests.py -k test_idea_chat test_ui_edges_pages test_skills test_manual_plan test_skill_panel_dropdown_layout test_complexity_ratchet"} -->

**三问速答**：
- 本轮类型：**修复轮**（§3.2：共享输入框 UI 缺陷修复与交互重设计，按用户验收反馈执行；契约有意变更已同步测试）。
- 测试：默认冒烟 **8/8**；定向 `test_idea_chat` 162 条 0 红、`test_ui_edges_pages` 40 条 0 红、`skill_panel` 18 条 0 红、`test_skills` 127 条 0 红、`test_manual_plan` 30 条 0 红；架构门禁 `--architecture` 复跑见下（修复 5 项失败后全绿）。
- 欠账：未新增欠账；顺带修掉两个既有缺陷（共享栏 `<Destroy>` 回调 TypeError、`skill_panel.Panel` 复杂度登记 683→646）。

## 用户验收反馈与根因（诊断过程）

用隐藏桌面真实构建 Desktop + 控件几何测量，定位四个反馈的根因：

1. **「输入框全部不可用，无法输入」**：剧本准备页有两个 Text——聊天记录框（`idea_log`，状态 normal 但靠 `<KeyPress>` 绑定只读，看起来像输入框）与底部共享栏输入框。用户往聊天记录框里打字当然无效；原 composer 输入框被轮 4 移到了底部共享栏，页面原有输入位留空。
2. **「剧本准备页面有 2 个输入框」**：轮 4 把 composer 输入框复用为共享 Text，页面同时出现聊天记录框＋共享栏输入框，观感上是两个输入框。
3. **「模型下拉选择器没有放入输入框右下角」**：共享栏 `right` 帧在 expand 输入框之后打包，被 pack 压缩成 **1×1 不可见**（实测 `w=1 h=1`）；模型选择器是带外框的文字按钮，不符合"去外框只留文字"。
4. **「技能按钮没有放入输入框」**：技能入口是文字按钮「技能」，非 Devin 风格图标＋技能列表浮层。

## 修复内容

| 文件 | 改动 |
|------|------|
| `desktop_writing_page.py` | 剧本准备页恢复自己的 composer 输入框（撤销轮 4 的共享复用）；输入提示标签挂回 composer 卡片；`_composer_dispatch` 按方法签名容错（修 `<Destroy>` → `stop_input_hint` TypeError，此前每次建页/销毁都抛一次） |
| `desktop_page_nav.py` | `_sync_shared_input`：剧本准备页（stage='script'）隐藏共享栏，其余 12 个阶段页照常显示 |
| `desktop_shared_input.py` | ① 重排打包顺序：发送图标先占右侧、输入盒后 expand（修 1×1 塌缩）；② 输入盒内部下一行：左下角技能图标（✦）＋附件图标、右下角**无边框模型名文字**（点击换模型，仿 DeepSeek 桌面）；③ 新增 `open_skill_list`：Devin 风格技能列表浮层（当前阶段技能在前，悬停右侧出说明卡片复用 `skill_note_render`，点击条目写入 `/技能名`，底部保留「从仓库导入／本地安装 skill」两条，走 `skill_import_service` 同一管线）；④ 浮层与悬停卡片改用 `BaseDialog(chrome=False, modal=False)`（架构门禁禁生产代码直接 `tk.Toplevel`）；⑤ 卡片尺寸用模块常量 `SKILL_CARD_ROWS/CHARS`（避免内联字面量触碰视觉 token 棘轮） |
| `skill_panel.py` | `build_notes` 改为空实现：面板内联「技能说明」区删除（说明改由悬停卡片提供）；`refresh_notes`/`show_note` 对空句柄自守卫 |
| `ui_tokens.py` | 新增 `ICON_SKILL = "\u2726"`（技能星形图标，Segoe UI Symbol 字形，非彩色表情） |
| 测试同步 | `test_idea_chat`（3 处：输入框回到页面自身实例、共享栏在剧本页隐藏、行数断言改 `COMPOSER_MIN_LINES`）、`test_ui_edges_pages`（2 处同口径）、`test_skills`（2 处说明区删除）、`test_manual_plan`（1 处）、`test_skill_panel_dropdown_layout`（1 处）、`test_complexity_ratchet`（Panel 登记 683→646）——全部是契约有意变更，断言按新行为改写，未删测试文件、未跳过 |

## 验证

- 默认冒烟：`python -B smoke_test.py` → **8/8 通过**。
- 定向（全部 0 红）：`test_idea_chat`（162）、`test_ui_edges_pages`（40）、`skill_panel`（18）、`test_skills`（127）、`test_manual_plan`（30）。
- 架构门禁：`smoke_test.py --architecture` 首跑 5 项失败（工具提示边界×2、数字布局棘轮、复杂度棘轮、轮次连续性），修复后复跑 **全绿（470 条）**；轮次连续性一项为上一批轮次遗留的状态页漂移（当前轮次 2872 vs 最新结果 2909），本结果文件与状态页轮次头同步后消除。
- 未跑全量（`--all --safe`）：分支不累计欠账；改动为 L4 UI 修复轮，受影响消费者已全覆盖。

## 状态与提交

- 状态页轮次头已同步为最新结果轮次加一（project_status.md 改动留工作树，按 §2.6 由 master 合并轮提交）。
- 提交范围：`ui_tokens.py`、`desktop_page_nav.py`、`desktop_writing_page.py`、`desktop_shared_input.py`、`skill_panel.py` 与 6 个测试文件＋本结果文件；不含 `project_status.md`。
- 提交信息：`R2916: 共享输入框修复——剧本页恢复原输入框、模型名无边框入框右下角、技能图标+列表浮层+悬停卡片（含仓库/本地安装）`。
