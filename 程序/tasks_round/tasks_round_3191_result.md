# R3191 结果（零依赖边界与媒体预览任务书 M3：阶段文件图标二级图标换 PNG）
<!-- round-evidence: {"commit_base": "e0ddeae7", "credential_hits": 0, "evidence_sha256": "e677983f4a97afa8", "exit": 0, "failed": 0, "passed": 274, "round": 3191, "tests": "run_selftests.py -k test_files_panel test_idea_chat test_ui_icons test_app_icon page_navigation nav_press video_navigation"} -->

- 轮次类型：功能轮（任务书 M3；实现期间领号时 3163–3190 已被其它车道占用，本轮实领 **R3191**，分支 `codex/wip-R3191`；R3168 为同步主干合并轮）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮：阶段文件面板图标列换 PNG 素材＋REQ-S01-94（D11 已确认）切页保持打开的契约变更。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9 通过；定向 `-k test_files_panel`（files_panel＋files_panel_stages）48 条全绿；`-k test_idea_chat test_ui_icons test_app_icon page_navigation nav_press video_navigation` 13 文件 226 条全绿（0 红、0 跳过）。架构门禁随本轮 `-k` 命中的 `architecture.test_ui_icons_boundary`（2 条）通过；完整架构门禁合入 master 前随全量一起验。
3. **欠账少了吗？** 减少：M3 全部落地——13 个阶段文件图标 PNG 化、emoji 兜底保留、图标列可滚动、面板切页不收起；另外修掉一条实际回归：图标列改 `ScrollForm` 后 Tk 画布默认请求宽（约 378px）顶住面板、删长文件名后面板不回缩，已把画布宽度钉到子件内容宽。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `scripts/build_nav_icons.py` | 新增 `render_stage_file_icons()`：以 `STAGE_FILE_BASES` 阶段字形为底、右下角叠「文件」角标，2× 渲染后 LANCZOS 减半、裁透明边，输出 `assets/nav/<stage>_files.png`；`_glyph_layer` 裁边后由调用方定位。Pillow 仍只作开发期依赖，产物随包。 |
| `assets/nav/<stage>_files.png` ×13 | 新生成的阶段文件图标（script/script_structure/storyboard/animatic/assets/continuity/final/keyframe/previs/video/audio/edit/delivery）。 |
| `ui/desktop_files_panel_filters.py` | `_build_stage_rail` 重写：「全部」＋`pet_bus.STAGES` 顺序 13 个阶段钮，经 `IconLoader.nav_icon` 取 `<stage>_files.png`，`compound='image'` 显示（`text` 保留 emoji 作语义标签），缺 PNG 退回 `STAGE_RAIL_ICONS` emoji 文本钮；图标列装进 `ScrollForm` 可竖向滚动；建列后把滚动画布宽钉到子件请求宽，修复面板不能回缩；♻/🗑/🗂 入口与 tooltip 不变。 |
| `ui/desktop_page_nav.py` | `_show_reset_page` 不再对页序号变化调 `files_panel.collapse()`；`project_changed()` 只在项目根变化时收起并复位筛选（REQ-S01-94，D11）。 |
| `tests/test_files_panel_stages.py` | 新增 PNG 图标断言（13 阶段钮挂 `<stage>_files.png`、入口挂 `project_files.png`）、缺 PNG 退回 emoji、图标列可滚动与阶段顺序。 |
| `tests/test_files_panel.py` | `test_page_and_project_switch_reset_panel` 改为 REQ-S01-94 断言：切工作页保持打开、项目根变化收起。 |
| `tests/test_idea_chat.py` | `test_project_files_panel_toggle_and_page_switch` 同步新契约：切工作页保持打开，会员账户页入口隐藏仍收起。 |
| `docs/stages/S01_剧本准备.md` | REQ-S01-90 口径修订（切页不再收起）、新增 REQ-S01-93（阶段文件 PNG 图标）与 REQ-S01-94（切页保持打开），DES-S01-90/93/94 同步实现描述。 |

## 决策与边界

- **PNG 优先、emoji 兜底**：`nav_icon` 取不到 PNG 时按钮退回原 emoji 文本——新装包与旧缓存都可用，不引入运行时解码依赖。
- **`text` 保留 emoji**：`compound='image'` 下不可见，但既有测试与无障碍口径按 text 断言，作为语义标签保留。
- **切页保持打开**：D11 已在任务书确认；REQ-S01-90 原「切换页面或切换项目自动收起」与新契约冲突，本轮同步修订，会员账户/参考网站等入口隐藏页仍收起。
- **ScrollForm 画布宽**：Tk Canvas 默认请求宽约 378px，不受子件宽度约束；显式钉到按钮内容宽，面板才能随最长文件名伸缩。

## 验证

- `smoke_test.py`：9/9 通过。
- `run_selftests.py -k test_files_panel`：48 条，0 红（files_panel 8＋files_panel_stages 40）。
- `run_selftests.py -k test_idea_chat test_ui_icons test_app_icon page_navigation nav_press video_navigation`：226 条，0 红。
- 全量 `--all --safe` 按 §5 攒到合入 master 前发布点统一跑。

## 遗留

- M4–M8 续在后续轮次（视频音频封面/波形、面板缩略图列与文件动作、离线 ASR 可选下载、登录首次配置引导、收尾完成文件）。
