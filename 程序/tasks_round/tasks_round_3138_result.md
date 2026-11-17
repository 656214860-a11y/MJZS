# R3138 功能轮结果：文件卡片与 HITL·轮 8/8——视频/音频卡 + 参数面板 + 多模态参考 + 后台任务
<!-- round-evidence: {"commit_base": "79d44b9c", "credential_hits": 0, "evidence_sha256": "a0a8ff22eaf44987", "exit": 0, "failed": 0, "passed": 6, "round": 3138, "tests": "run_selftests.py -k video_audio_card param_panel multimodal_upload background_task"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 8/8，最后一条实现轮）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`test_video_audio_card.py`（2/2）、`test_param_panel.py`（1/1）、`test_multimodal_upload.py`（2/2）、`test_background_task.py`（1/1）、UI 边界（43/43）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；视频/音频卡、参数微调、多模态参考、长任务进度/转后台/完成回调四块落地，任务书 8 轮实现全部完成。

## 改动

- 新增 `ui/ui_media_player.py`：
  - `build_audio_card`：标题 + 静态波形（Canvas 竖条近似）+ 试听 + 导出 SRT + 确认采用/重新生成；
  - `build_video_card`：封面（`asset_thumbs`）+ 播放（外部播放器回调）+ 确认采用/重新生成；
  - 播放/导出/确认一律经回调注入（调用方接 `platform_tools.open_target` / `subtitle_export`）。
- 新增 `ui/ui_param_panel.py`：温度（0–2）/生图步数（1–60）滑条 + 画面比例 `SelectBox` 下拉；`state['values']()` 读回参数，`on_change` 回调。
- 新增 `ui/ui_multimodal.py`：`classify`/`reference_part`/`attach_references`，把图片/音频参考转成 FILE part（垫图/参考音色），不支持扩展名拒绝。
- 新增 `ui/ui_task_progress.py`：`build_task_progress` **Canvas 自绘进度条**（页面不造 `ttk.Progressbar`）+ 百分比 + 转后台按钮 + 完成回调（通知由调用方接 `notifier`）。
- 新增测试 4 个（`test_video_audio_card`/`test_param_panel`/`test_multimodal_upload`/`test_background_task`）。
- 基线同步：覆盖率基线 544→548；skip 台账 +3；`runbook §11` 同步。

## 测试证据

- `python -B tests/test_video_audio_card.py` → `Ran 2 tests ... OK`。
- `python -B tests/test_param_panel.py` → `Ran 1 test ... OK`。
- `python -B tests/test_multimodal_upload.py` → `Ran 2 tests ... OK`。
- `python -B tests/test_background_task.py` → `Ran 1 test ... OK`。
- `python -B -m unittest tests.architecture.test_button_boundary ... test_ui_icons_boundary` → 43 tests OK。
- `python -B -m unittest tests.architecture.test_busy_state_boundary tests.architecture.test_combobox_boundary tests.architecture.test_complexity_ratchet` → 15 tests OK（Canvas 进度条、SelectBox、hooks 收拢参数）。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；覆盖率基线 548、skip 台账 306 口径同步）。

## 契约变更（§2.4）

- 新增 L4 `ui/ui_media_player.py`、`ui/ui_param_panel.py`、`ui/ui_multimodal.py`、`ui/ui_task_progress.py`；按钮/间距/颜色全部走 `ui_widgets` 与 `ui_tokens`。
- 零第三方依赖不变（波形用 Canvas 静态绘制，播放/通知经回调）。

## 范围外 / 已知缺口

- 视频/音频的「真实内嵌播放」为零依赖硬约束所限不可行，播放走外部播放器（回调位已留）。
- 参数面板的引擎实际支持集、多模态拖拽/粘贴的真实事件绑定、后台任务队列与 `notifier` 的接线留待页面整合轮。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3138`；commit hash 见回填。
