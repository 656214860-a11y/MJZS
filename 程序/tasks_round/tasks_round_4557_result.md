# R4557 结果报告：UX-SANHU-FIX 三虎聊天框左下指向、三模式日夜头像换色与右键菜单重构
<!-- round-evidence: {"commit_base": "4bd84e711", "credential_hits": 0, "evidence_sha256": "dcfd0bf89b274afd", "exit": 0, "failed": 0, "passed": 12, "round": 4557, "tests": "run_selftests.py -k sanhu_pointer_avatar_menu"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（三虎视觉交互与右键功能修复/重构，堆叠于 R4555 + R4556 之上）。
- **测试跑了吗、三个基线过了吗**：已跑。独立只读验收复核者（`f1085c14`）复跑定向套件 **931/931** 全绿（含新增 `test_sanhu_pointer_avatar_menu` 12/12）；默认冒烟 **9/9** 通过（含隐藏桌面探针，对应 8/8 登记基线）；架构门禁 **711/711** 全通过（改前后 0 红）；三卡合并堆叠后额外复验跨卡集成测试与结构/覆盖率门禁全绿；未跑 `--all --safe` 全量回归（功能分支不触发全量，合并前按规则评估）。
- **欠账少了吗**：少了。`PetViewMixin` 行数由 731 降至 **721/732**，清理死属性 `menu_mode`/`mode_var` 与失效的 `kick_unattended('pet')` 空转重试，消除暂停双重 `act()` 与恢复遗漏清空 `declined_set` 缺陷，覆盖率模块覆盖数由 149→151。

## 改动摘要
1. **三虎聊天框左下角指向修复（`程序/ui/pet_cloud_place.py`）**：
   - 新增 `_pet_horizontal_anchor` 与 `_pet_docked_left`，三虎位于左下角停靠区（常规窗及最大化窗）时气泡贴合窗口左内边、落在三虎正上方不遮挡三虎，尾巴根部 `root_x` 与尖端 `tip` 同步对准左下三虎视觉中心；经典右侧布局 100% 向后兼容；`pet_cloud.py` 未触碰。
2. **三虎三模式头像换色与日/夜双主题同步（`程序/ui_tokens.py`、`程序/ui/pet_ui_support.py`、`程序/ui/pet_ui_view.py`）**：
   - `PET_PALETTE` 拆为日/夜两套，`set_theme()` 原地刷新并触发 `sync_pet_palette()`，顺修夜间 `caption_ink` 为高对比 `#E8ECF2`（日间 `#0F1419`）；
   - `hint`（只提醒 · 冷石板蓝灰 `#64748B`/`#7C93B0`）、`semi`（半自动 · 暖琥珀橘 `#D97706`/`#F59E0B`）、`auto`（全自动 · 翡翠绿 `#15803D`/`#22C55E`）毛色/描边/星光两两区分，暂停态保持置灰；`canvas`/`paws` 注册 `_refresh_theme_colors` 实时重绘。
3. **三虎右键菜单按频率重构与缺陷修复（新增 `程序/ui/pet_ui_menu.py`，联动 `pet_ui_view.py`/`pet_ui_stages.py`/`pet_ui.py`/`pet_ui_settings.py`/`pet_ui_voice.py`）**：
   - 重排为 4 块 3 分隔线（从高频到低频）：`向三虎提问 → 推进当前阶段 → 进度面板`｜【任务控制】`暂停/继续 → 重试失败项 → 待确认项 → 跳过当前阻塞项`｜【常用工具】`切换模型▸ → 语音识别设置… → 切换日间/夜间主题 → 免打扰 → 今日日报`｜`打开设置… → 退出程序`；删除重复 7 项设置级联与陈旧「一键执行（重试＋补首帧＋日报）」。
   - 修复 `retry_failures()` 真实清失败/阻塞/退避并重启阶段、`pause_action()` 消除双 `act()`、`_click_resume()` 清 `declined_set`、`skip_failure()` 解除 `auto.blocked`、`advance_current_stage()` 覆盖 13 阶段并守住付费确认护栏。
4. 同步测试（新增 `test_sanhu_pointer_avatar_menu.py` 12/12，更新 `test_pet_ui.py`/`test_ui_theme.py`）、分层登记（`_layers.py`）、结构测试归属与哈希（`structure.json`/`structure-baseline.json`，含三卡全部新增测试）、覆盖率基线与 `runbook.md` §11。

## 独立验收结论
- 执行者：独立同模型子代理 `0e42af8d`（`codex/ux-sanhu-pointer-avatar-menu`，基于 `162d37b93` 后快进堆叠至 `4bd84e711`）
- 独立验收者：独立只读同模型子代理 `f1085c14` — **VERDICT: PASS**（零阻断，未触碰 `desktop_layout.py` 与主工作树）
- 提交状态：本分支已按 `dev.py commit` 生成 `R4557` 证据提交，完整包含 R4555 + R4556 + R4557 全部 6 项需求，待性能优化会话释放主目录 `D:\漫剧制作助手` 后即可按单条分支快进/合入 `master`。
