# R2966 结果：修复轮——master 全量回归既有红三处根因修复
<!-- round-evidence: {"commit_base": "a1027c6d", "credential_hits": 0, "evidence_sha256": "f90d968f6336f959", "exit": 0, "failed": 0, "passed": 388, "round": 2966, "tests": "run_selftests.py -k video_navigation desktop_layout ui_edges inline_brief video_ui idea_chat"} -->

## 三问

1. **轮次类型**：修复轮（§3.2）。目标会话「测试全部通过」要求下，处理 R2963 合并轮全量 `--all --safe` 暴露的 18 条 master 既有红中可复现的代码缺陷；纯环境性缺口（干净工作树技能子仓未物化）以同步方式闭环。
2. **测试跑了吗、三个基线过了吗**：跑了。改前红证据：`test_video_ui` 10 红＋`test_ui_edges_autopilot` 1 红＋`test_ui_edges_tables` 2 红＋`test_ui_edges_pages` 2 红＋`test_idea_inline_brief` 1 红（合计 16 条，同因归并 3 处）；改后 `-k video_ui ui_edges inline_brief` 215 条 0 红、`--affected video_navigation desktop_layout` 9 项门禁 275 条 0 红、默认冒烟 8/8。`--architecture` 与全量回归见「验证记录」。
3. **欠账少了吗**：是。R2960 导航图标轨改版引入的三处回归全部根因修复并复测转绿；master 全量红集合从 20 收敛（剩余为环境性/待核项，见下）。

## 根因与修复（先红后绿）

| 失败簇 | 根因 | 修复 |
|---|---|---|
| `video_navigation.show_back` TclError `can't pack ... inside ".!frame.!canvas.!frame"`（14 条：test_video_ui×10、ui_edges_autopilot×1、ui_edges_tables×2、ui_edges_pages×1） | R2946/R2950 把 `desktop.title` 从 `title_row` 搬进侧栏 `scroll.form`，`show_back` 仍 `box.pack(before=desktop.title)` 跨父级引用 → TclError，整个视频工作区页打不开 | `video_navigation.py`：`before` 锚改 `desktop.usage_indicator`（同 master `title_row` 的左侧常驻件），返回钮仍居页头最左；注释注明 R2966 口径 |
| `test_the_way_back_to_the_choose_page_still_works` `button.winfo_height()=20 < image.height()=32`（test_video_ui 余 1 红） | R2950 `align_header` 重写后 `title_row` 高度只量 `usage_indicator/header_info/header_stage_button`（单行 ~22px），返回钮设计高 56px 被 pack 纵轴压到 20px | `desktop_layout.py`：测量名单补 `video_back` 并加 `winfo_manager()` 守卫（`hide_back` pack_forget 后不再撑高行）；视频子页标题行收到钮高，其余页不变 |
| `test_script_structure_page_...` `justify 'left' != 'right'`（ui_edges_pages×1） | R2950 页头改单行设计「状态居左可伸展、模型名贴右」把 `header_status` 由 `anchor='e',justify='right'` 改为 `anchor='w',justify='left'`，测试断言停留在两行右对齐时代 | 测试契约同步（§2.4，有意变更）：断言改 `'left'` 并注 R2950 口径；行为断言（label 即 header_status、文案）原样未动 |
| `test_api_stage_confirmation_...` `preparation_continuation Called 2 times`（inline_brief×1） | R2663 发送门禁 250ms 防抖 `_idea_live_missing` 与 `send_message` 共用 `writing_api.preparation_continuation`；send 内部 update 落进防抖后以清空后草稿 `''` 再调一次，mock 计数被污染（与 R2947 test_script_composer 同类 flake 的另一形态） | 测试隔离：with 块补 `patch.object(d,'_idea_live_missing',return_value=())`，门禁判据不参与本断言，`assert_called_once_with` 严格度保留 |
| `test_rejected_response...`/`test_tabular_attachment...` SKILL 引用缺失（干净工作树 2 红） | 四个 gitlink 技能子仓（`reference/HoLLMwood`、`AIGC创作全流程`、`编剧技能集` 等）在新工作树不自动物化 | 环境修复：自主工作区整目录同步（含 `.git`，供 skill_package_pins 哈希核验）；`01 剧本准备SKILL/剧本制作` 主工作区本就为空，属既有状态非本轮问题 |

## 测试与契约变更（如实，§2.4）

- 生产代码改动 2 文件：`video_navigation.py`（pack 锚点）、`desktop_layout.py`（align_header 测量名单＋manager 守卫）。无接口/行为契约变更——修复的是 R2946/R2950 改版未同步的既有调用点。
- 测试改动 2 文件：`test_ui_edges_pages.py` 一处断言值 `'right'→'left'`（R2950 有意设计同步）；`test_idea_inline_brief.py` 一处 mock 隔离（防抖门禁不属本测试面）。断言强度未降：justify 仍断言具体值、continuation 仍 `assert_called_once_with`。

## 验证记录

- 改前红（master `a1027c6d` 定向复现）：16 条红，堆栈均指 `video_navigation.py:127`／`desktop.py:285 justify`／`desktop_idea_send_gate.py:55`。
- 改后：`run_selftests.py -k video_navigation video_ui ui_edges script_structure inline_brief` 215 条 0 红；`smoke_test.py --affected video_navigation desktop_layout` 9 项门禁 275 条 0 红；`smoke_test.py` 8/8。
- `--architecture`：见提交证据（本轮触及 desktop_layout 测量逻辑，合入前以 local_ci 出口为准）。
- 全量 `--all --safe`：合入 master 后按累计源码轮次判定执行，结果以 `full-safe-receipts.json` 真实凭据为准。

## 范围外记录（不代修）

- 干净工作树技能子仓需手工同步属环境基线问题（主工作区已物化），建议后续轮次在 worktree 引导或文档中固化；本轮以同步闭环。
- 全量剩余红的最终清单以合入后全量复跑为准；本轮已覆盖可复现的全部代码缺陷簇。
