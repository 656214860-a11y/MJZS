# R1356：O31 声音角色映射与音轨用途绑定到具体集/用途

类型：功能轮（§3.1；本项为「建议」→ 实现＋回归）。承接 R1267 清单 O31（O01—O30 已完成）。中央轮次 1356。**本轮为五轮全量欠账点（上次绿全量 1351），收口在干净 master 工作树跑一次 `run_selftests.py --all --safe`。**

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k audio_role_binding` 18/18；关联 `-k tts audio stage_completion media_import ui_edges skill stage_execution` 427/427；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O31 关闭，清单剩 O32—O48；1356 − 1351 = 5 ≥ 5 **命中五轮全量欠账**。收口全量结果见文末「收口全量」。

## 目标（R1267 清单 O31）
- 依据：`tts_api.py` 支持说话人、voice、speed；`audio_import_service.py` 有音频归档但通用完成判断不足。
- 建议：同一角色保存选定音色及版本；区分对白、旁白、BGM、音效、整轨；显示缺配角色、静音台词、音量与峰值检查。音轨应说明对应哪集哪版台词。
- 验收：角色重命名不丢配音映射；两集同名文件不串；换音色后的续跑遵循 O12；导入 BGM 不能被算作对白已完成。

## 实现（`tts_api.py`，L1）
- 新增 `AUDIO_KINDS`（dialogue／narration／bgm／sfx／full）与 `AUDIO_KIND_LABELS`（对白／旁白／BGM／音效／整轨）；`audio_kind(name)` 从文件名前缀反推用途（认不出按对白，兼容旧文件），`marked_audio_name(stem, kind)` 给非对白加前缀（对白保持原名）。
- 新增 `voice_for(voices, speaker, name='')`：**按稳定角色 ID 优先、显示名兜底**（`build_lines` 改用它）——角色改名不影响映射。
- 新增 `missing_voices(entries, assets, voices)`（有台词但没配音色的角色，按 ID 去重）、`silent_lines(entries)`（文本空白的静音台词行）。
- 新增 `voice_snapshot(settings)`：逐角色音色／语速＋映射版本；`save_key` 在 `voices` 变化时自增 `voice_version`（「同一角色保存选定音色及版本」）。
- `batch_signature(lines, episode=None)`／`resume_folder(root, lines, episode=None)`／`run_lines(..., episode=None)` 增至集标识：给了集就纳入批次指纹，**两集同名台词／音色不再共用缓存目录**；不给集时指纹与旧口径逐字节一致，老缓存仍可续用。

## 实现（`audio_import_service.py`，L2）
- `import_audio(..., kind='dialogue')`：按用途给非对白音轨加可识别前缀（对白保持原名，不破坏既有命名）；非法用途报 `ValueError`。

## 实现（`stage_completion_service.py`，L2）
- `prepare_media_completion` 对 `stage=='audio'` 增加对白音轨要求：所选成果里若没有对白音轨（只有 BGM／音效／旁白）则拒绝，**导入 BGM 不能算作对白已完成**。已确认的旧清单（`_validate_media_completion`）不变，避免历史项目回退。

## 实现（`stage_execution_service.py` L3／`desktop.py` L4）
- `run_tts_lines(..., episode=None)` 透传；`generate_tts_per_line` 取当前集的 `episode_id`／`id` 作为批次指纹 token，`resume_folder`／`run_tts_lines` 都带上，切集不会沿用别集音频。

## 验证
- `tests/test_audio_role_binding.py`（新）18 条：ID 优先／名字兜底／改名不丢映射；缺配角色列表；静音台词；音色快照与 `voice_version` 只在变化时自增；音轨用途前缀往返；对白保持原名；未知用途默认对白；`batch_signature` 无 episode 时与旧公式逐字节相同、带 episode 时区分；两集在不同目录不互相命中且不带 episode 不命中；BGM 导入加前缀、对白导入保持原名；非法用途报错；完成核验对 BGM-only 拒绝、对白音轨接受。
- 定向 `-k audio_role_binding` 18/18；关联 `-k tts audio stage_completion media_import ui_edges skill stage_execution` 427/427；架构门禁 312/312；默认冒烟 8/8；全 0 红。
- 台账：未新增裸 `json.loads`／L2 直写／未登记动态导入／顶层模块；未新增 `skipTest`；`desktop.py` 唯一 TODO 仍在 2753（改动在 7000+ 行）。

## 边界
- 音轨用途靠**文件名前缀**识别（`marked_audio_name`）：只有经 `import_audio(kind=...)` 导入的音轨才带前缀；手工直接落盘／旧文件名的音轨按「对白」处理（兼容），完成核验只在**能确定全是非对白**时拒绝——不误伤历史与直接落盘成果。UI 的「导入配音／音乐」按钮目前仍按对白导入（`kind` 参数已就绪，供后续 BGM／音效专用入口）。
- 音量与峰值检查本轮**未做**（需 ffmpeg `volumedetect`，环境依赖重），只做缺配角色与静音台词。
- 「音轨说明对应哪集哪版」沿用既有 `成果确认` 清单的 `scope`（集 id＋采用分镜摘要）＋本轮批次指纹的集标识；未改清单结构。
- 给 `episode` 后重新计算批次指纹：同一集的**旧**逐句配音批次（无集标识）不会被新指纹命中，首次会重合成一次（不误用别集），之后恢复正常续跑——这是一次性代价，换取「两集不串」。
- 未实发模型请求、未真实点界面（Tk 用例经 `-k ui_edges` 通过）；未改启动路径／Tk 控件生命周期销毁重建／删除语义／层级登记表（`tts_api` L1、`audio_import_service`／`stage_completion_service` L2、`stage_execution_service` L3、`desktop` L4 均在表内）。

## 收口全量
- _（本轮五轮欠账，收口在干净 master 工作树跑 `run_selftests.py --all --safe`；结果待回填）_
