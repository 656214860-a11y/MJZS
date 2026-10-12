# 当前快照

## 2026-10-12：O31 完成（含五轮欠账全量），继续 O32

- 按 R1267 清单 O01→O48 顺序逐个完成。O01—O30 已完成，**O31 已完成（R1356）**，下一项 O32。
- O31（声音角色映射和导入音轨绑定到具体集/用途）：`tts_api.py`（L1）新增 `AUDIO_KINDS`／`AUDIO_KIND_LABELS`（对白/旁白/BGM/音效/整轨）、`audio_kind`／`marked_audio_name`、`voice_for`（稳定角色 ID 优先、显示名兜底，改名不丢映射）、`missing_voices`／`silent_lines`／`voice_snapshot`，`save_key` 音色变化时自增 `voice_version`；`batch_signature`／`resume_folder`／`run_lines` 增至集标识（两集同名台词不共用缓存，旧指纹不变）；`audio_import_service.import_audio(kind=)` 非对白加前缀；`stage_completion_service` 要求对白音轨（导入 BGM 不算对白完成）；`desktop.generate_tts_per_line` 带当前集 token。见 [R1356](../程序/tasks_round/tasks_round_1356_result.md)。
- 验证证据：`tests/test_audio_role_binding.py`（新）18 条；定向 `-k audio_role_binding` 18/18＋关联 427/427、架构 312/312、默认冒烟 8/8，0 红；1356 − 1351 = 5 ≥ 5 **命中五轮欠账**，收口在干净 master 工作树跑 `run_selftests.py --all --safe`。**上次绿全量：1356（tree 006d0295、4749/4749、425.3 秒、0 红），下一五轮欠账点 1361。**
- 工作区：主树另有他人**已暂存**改动（`程序/idea_chat.py`、`程序/idea_attachments.py`、`程序/配置/SKILL/预设.json`）与未跟踪 `outputs/`，不读取、不暂存、不覆盖；提交只点名自己的路径。主树永远“脏”，全量与架构的干净树验证只能在临时 worktree 跑。
- 轮次：中央号靠 `round_claim.py next`；本轮 1356；全量在干净 master 工作树 `run_selftests.py --all --safe`。`project_status.md` 的 `当前轮次` 须＝最新结果报告号＋1（`tests/architecture/test_round_baselines.py` 会校验）。提交后 master 前移会让 `o07-fullsafe-master` 显示为「已暂存改动」，领取／全量前先 `git reset --hard HEAD`。
- 下一步：O32（见 `tasks_round_1267_result.md` O32 条目：剪辑输出规格不能固定替代项目规格；`engine.py:434` 拼接固定 1280×720/30fps；事实项；M）。
- 验证策略（O06—O48）：默认只跑 `run_selftests.py -k <本轮模块>` ＋ 默认冒烟；全量只在收口／合入 master 前跑一次（干净 master 工作树 `--all --safe`）；全量失败先按定位文件定向修绿、只复验一次（报告写“第 N 次全量”，2 次仍不过就升级单独修复轮）；五轮一次的全量欠账由该轮收口补跑。`test_desktop_startup_perf` 属已知阈值抖动，定向复测 3 次取多数，不作为拦截条件（归 O48）。
