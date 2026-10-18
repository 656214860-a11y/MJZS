# R1722：验证基线轮——S04 分镜预演补 16 条需求测试锚点（REQ-S04）

- 轮次类型：§3.10 验证/基线轮（只补测试锚点、只删基线、同步测试 docstring；未改生产代码）。
- 测试跑了吗 / 三个基线：跑了两条任务书命令，均 0 红（见下）。`smoke_test.py` 默认冒烟 8/8、`run_selftests.py --all --safe` 全量：**未运行**（任务书只要求两条命令）。架构门禁只跑了 `tests.architecture.test_requirement_traceability`（4 条 0 红），未跑 `--architecture` 全量。
- 欠账少了吗：`维护记录/需求锚定基线.json` 的 `untested_done` 由 89 条减到 73 条（删 16 条 S04），其它编号未动。

## 逐条结论（锚定 / 降 🟡）

| 编号 | 锚点测试（文件::测试） | 对应断言 → 需求原文 | 结论 |
| --- | --- | --- | --- |
| REQ-S04-02 | `test_req_s04_anchors.py::test_req_s04_02_requires_adopted_source_reference_and_temporary_sound`（新） | 空/空文件参考图 → `请先准备共享参考图`；无音频且无 TTS 文本 → `请选择临时音频或填写临时 TTS 文本`；来源不在已采用清单 → `请选择已采用的本项目分镜初稿`。=「输入三样：被采用分镜（须在已采用清单）、至少一张非空参考图、导入音频或 TTS 文本」 | 锚定 |
| REQ-S04-06 | `test_req_s04_anchors.py::test_req_s04_06_local_tools_and_comfy_readiness_gate_before_generating`（新） | `tool_path('')` → `请在运行环境配置 ffmpeg` 且无 `animatic_manifest.json`；`tool_path` 兜底可解析后 `wait_comfy` 被调用、未就绪即抛错且无半成品。=「ffmpeg／ffprobe 可解析、本地 ComfyUI 先等待就绪，缺一项直接报错不产生半成品」 | 锚定 |
| REQ-S04-10 | `test_req_s04_anchors.py::test_req_s04_10_reference_import_is_validated_and_content_addressed`（新） | 导入目标 = `shared_reference_dir/<sha256>.png` 且字节一致；同内容复用同名；`.gif` 与 >20 MB 被拒；`prepare_reference` 空描述／空模型报错。=「仅 PNG/JPEG/WebP、≤20 MB、按内容摘要命名去重；本地文字草图需描述与模型名；二者经 L3 发布到共享参考图目录」 | 锚定 |
| REQ-S04-11 | `test_req_s04_anchors.py::test_req_s04_11_reads_new_and_old_reference_dirs_without_duplicates`（新） | 新目录 `_shared/reference_images` 与旧 `04资产管理/参考图` 的图片都在结果里；非图片被过滤；结果无重复路径。=「读取同时覆盖新旧共享参考图目录，按路径去重」 | 锚定 |
| REQ-S04-20 | `test_req_s04_anchors.py::test_req_s04_20_sketch_uses_prompt_all_references_and_fixed_seed`（新） | `reference_graph` 收到的提示词以「只生成分镜预演草图，不是正式资产或首帧」开头且含分镜提示词；images == 全部参考图；图中 `seed`/`noise_seed` 被强制为默认 1（可改成 42）。=「用分镜提示词、全部共享参考图和固定种子（默认 1）生成，提示词前带声明」 | 锚定 |
| REQ-S04-23 | `test_req_s04_anchors.py::test_req_s04_23_uncertain_submission_is_not_resubmitted_and_keeps_run_workspace`（新） | 轮询超时 → `不自动重复提交` 且 `submit_graph` 只调 1 次；`run_animatic` 失败后仍留有 `04分镜预演/.work/run-*` 目录。=「排队或超时不自动重投、报错请人工核查，回执保留在持久工作区 run-*」 | 锚定 |
| REQ-S04-24 | `test_animatic_service.py::test_persistent_previs_reuses_tts_after_later_render_failure`（加 docstring） | 两次 `build_bundle` 中出图失败，`synthesize` 只调 1 次且 `request_id` 以 `tts-previs:` 开头。=「TTS 文件名含脚本签名，已存在且非空则复用，出图失败重跑仍复用」 | 锚定 |
| REQ-S04-25 | `test_animatic_timeline.py::test_timeline_maps_audio_and_decodes_before_success` / `test_missing_audio_and_wrong_duration_are_rejected` / `test_invalid_duration_never_starts_process`（加 docstring） | 拼接命令含 `1:a:0`、末段 `-xerror`；缺音频流或时长差 >1 秒 → `核验失败`；NaN 时长不启动进程。=「叠加声音、含视频与音频流、时长差 ≤1 秒、完整解码核验」 | 锚定 |
| REQ-S04-26 | `test_animatic_service.py::test_formal_assets_require_confirmation_and_online_model`（加 docstring） | 本地模型（`online_model=False`）生成正式资产 → `线上 API`。=「正式资产仍走线上 API 生成」 | 锚定 |
| REQ-S04-30 | `test_req_s04_anchors.py::test_req_s04_30_publishes_all_artifacts_into_the_stage_folder`（新）；`test_animatic_service.py::test_publication_rejects_escape_and_rolls_back_index_failure`、`test_generated_bundle_requires_confirmation_and_detects_source_changes`（加 docstring） | `04分镜预演/` 下存在清单、`assets/animatic.mp4`、`assets/temporary_audio.wav`、`assets/shots/s1.png` 与发布器 `animatic_index.json`；越界路径被拒、索引失败整包回滚（清单恢复旧值、无索引）。=「成果写入阶段目录、暂存后整包原子发布、任一步失败回滚不留半包」 | 锚定 |
| REQ-S04-31 | `test_req_s04_anchors.py::test_req_s04_31_bundle_validation_checks_files_mapping_and_unsigned`（新） | 正常包 True；多出未登记文件 / `confirmed` 被代签 / `video` 不在 `files` / `kind≠animatic` / 空媒体 → False；发布器拒绝 `animatic_index.json`。=「files 一一对应、媒体在 files 内非空、confirmed 全 false、索引只允许发布器写」 | 锚定 |
| REQ-S04-32 | `test_req_s04_anchors.py::test_req_s04_32_source_change_during_generation_blocks_publication`（新）；`test_animatic_service.py::test_generated_bundle_requires_confirmation_and_detects_source_changes`（加 docstring） | 生成期间改写来源 → `生成期间分镜已变化` 且发布器未被调用；发布后改来源使 `evidence` 转 False（清单含 `source` 相对路径与 `source_sha256`）。=「清单记来源相对路径与 SHA-256，生成中来源被改则不发布」 | 锚定 |
| REQ-S04-33 | `test_req_s04_anchors.py::test_req_s04_33_video_path_available_for_complete_unconfirmed_bundle`（新） | 未确认但完整的包 → 返回 `04分镜预演/assets/animatic.mp4`；空项目 → 抛原因。=「只要成果完整（不要求已确认）就返回视频路径」 | 锚定 |
| REQ-S04-40 | `test_req_s04_anchors.py::test_req_s04_40_confirmation_needs_all_three_and_regeneration_resets`（新）；`test_animatic_service.py::test_generated_bundle_requires_confirmation_and_detects_source_changes`（加 docstring） | 三参数缺一 → `全部确认`；成果不完整 → 抛错；全勾后 `confirmed` 全 True 且 `evidence` 通过；重新生成后 `confirmed` 重置全 False。=「三项必须一次全勾选才能确认；不完整不能确认；确认只改 confirmed；重新生成重置」 | 锚定 |
| REQ-S04-42 | `test_req_s04_anchors.py::test_req_s04_42_sg_b_reuses_the_same_completion_verification`（新） | 打桩 `animatic_service.evidence` 返回 `(False,'同一核验')` 时，`stage_parallel.animatic_ready` 与 `stage_completion_service.completion_evidence(root,'animatic')` 都返回该同一结论（同一函数被调用 ≥2 次）。=「SG-B 与阶段完成核验调用同一核验，无第二套判定」 | 锚定 |
| REQ-S04-43 | `test_animatic_service.py::test_evidence_streams_large_media_without_reading_bytes`（加 docstring） | 校验阶段禁用 `Path.read_bytes`（媒体后缀）仍通过 → 走流式摘要。=「大媒体核验用流式摘要，不整段读入内存」 | 锚定 |

- 降 🟡：无（16 条新/补测试全部绿，代码满足需求）。
- 需裁决：无。未使用 Tk，故未新增 skip、未改 `维护记录/skip台账.json`。
- 备注：`维护记录/需求锚定基线.json` 的 diff 仅删除 16 行 S04 编号；该文件在 HEAD 中本就无末尾换行，故按“保持原有格式”原样保留（indent=2、ensure_ascii=False）。

## 命令与实际计数

1. `python -B -m unittest tests.test_req_s04_anchors tests.architecture.test_requirement_traceability`（PYTHONPATH 加 `tests`）→ `Ran 16 tests ... OK`（12 新锚点 + 4 门禁），0 红。
2. `python -B run_selftests.py -k animatic test_req_s04` → 4 个文件 `test_animatic_timeline 3` / `test_animatic_scope 12` / `test_animatic_service 13` / `test_req_s04_anchors 12`，共 **40 条用例 / 4.0 秒 / 0 个文件有红**，`ALL TESTS PASSED`，实际跳过 0 条。

摘要：REQ04 完成——S04 的 REQ-S04-02/06/10/11/20/23/24/25/26/30/31/32/33/40/42/43 共 16 条全部锚定（新增 12 条用例 + 5 个既有用例加 docstring），基线 89→73，两条验证命令 0 红，无降 🟡、无 skip、无生产代码改动。

## 独立验收（Claude，隔离验证工作树 HEAD＋车道 lane_req04 文件）

- 定向 `-k test_req_s04 animatic requirement_traceability`：0 红；`test_requirement_traceability` 单跑 OK。
- `smoke_test.py --architecture`：368/368 OK。
- `review_batch.py --lane req04`：0 失败；16 条告警均为基线 JSON 删除已锚定编号，属预期。
- 抽查新测试无源码字符串锚点（read_text 只读 JSON 数据）；不改生产代码，未新增 skip。
- 首个使用独立车道派发的批次。
