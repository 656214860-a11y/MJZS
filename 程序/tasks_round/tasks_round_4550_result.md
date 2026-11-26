# R4550 S04-V2-ENGINES-MOTION：S04 分镜预演 V2 草图引擎、暂存烧录、2D 动效与对白秒数落盘
<!-- round-evidence: {"commit_base": "0e50966e6", "credential_hits": 0, "evidence_sha256": "659af77a67de04d3", "exit": 0, "failed": 0, "passed": 84, "round": 4550, "tests": "run_selftests.py -k animatic_sketch_backends animatic_service animatic_timeline copy_rules"} -->

## 三问

1. **本轮类型（§3）**：§3.1 功能轮（任务卡 `S04-V2-ENGINES-MOTION`，对应 `REQ-S04-100..105/111/112`、`DES-S04-30..32` 与 `REQ-S04-83` 单镜重做 Comfy 探测补齐）。
2. **测试与三个基线**：
   - 默认冒烟（`smoke_test.py`）：9/9 通过（隐藏桌面 `--probe` + 8/8 检查项），退出码 `0`。
   - 架构门禁（`smoke_test.py --architecture`）：711/711 全绿，0 红，退出码 `0`（含 `LR-03` 零新增 L2 同层边、`test_layers`、`test_complexity_ratchet`、`test_function_size_ratchet`、`test_module_size_ratchet`、`test_unification_ratchet`、`test_http_boundary`、`test_import_error_boundaries`、`test_copy_rules` 等；初跑曾命中 `test_import_error_boundaries` 1 红，改为 `importlib.util.find_spec` 惰性探测后 711/711 全绿）。
   - 定向自检（`run_selftests.py -k animatic_sketch_backends animatic_service animatic_timeline copy_rules`）：84/84 全绿，0 红，0 跳过，退出码 `0`。
   - 实机 FFmpeg 动效冒烟：用随包 `运行环境/ffmpeg/bin/ffmpeg.exe` 实测 `text_card_render` → `render_overlay_frame` → `segment_filter` 全部 5 种运镜（`static`/`zoom_in`/`zoom_out`/`pan_left`/`pan_right`）均编码成功。
   - 全量安全回归（`--all --safe`）：未运行（功能分支开发轮，按约定由合并轮结算）。
3. **欠账变化**：本轮未新增欠账；顺带闭环 R4544 记录的卡外欠账（`regenerate_animatic_shot` 单镜重做复用 `_ensure_comfy_ready`），并保持与 Codex `codex/flow-model-pool` 零文件冲突。

## 改动摘要

- `程序/domain/animatic_sketch_backends.py`（纯 L2，零同层 `domain/*` import，323 行）：
  - 新增并默认注册免费后端 `text_card`（`paid=False`，`label='文字分镜卡（零成本）'`）：基于 Pillow 按 `spec` 尺寸（默认 1280×720）生成含镜号、时长、景别/场景、自动换行画面描述与可选对白的 PNG 到 `workspace/<shot_id>_card.png`；字体依次尝试 `msyh.ttc`、`simhei.ttf` 与 Pillow 默认字体。
  - 新增并默认注册免费后端 `gflow_cli`（`paid=False`，`label='Google Flow（gflow-cli 免费）'`）：纯注入执行 `settings['gflow_generate'](config, prompt, references, destination, stop)`，落盘 `workspace/<shot_id>_gflow.png`；缺注入器或配置报中文错。
  - 新增纯函数 `render_overlay_frame(image_path, destination, *, shot_id, seconds, start_seconds, dialogue='') -> Path`：在暂存目标上叠加半透明顶栏（`SH001 · 5s · 00:05`）与对白底栏，绝不修改原图。
  - 新增纯函数 `infer_motion(shot) -> str`：按 `camera_movement`/`camera`/`movement`/`description`/`video_prompt` 顺序映射 `zoom_in`/`zoom_out`/`pan_left`/`pan_right`/`static`。
- `程序/domain/edit_service.py`（L2，172 行）：
  - 新增纯函数 `segment_filter(spec=None, *, seconds=0, motion='static') -> str`，为 4 种 Ken Burns 运镜拼接带 `d=max(1, int(round(seconds * fps)))` 与规格分辨率的 FFmpeg `zoompan` 滤镜，静态或无效时长回退 `preview_filter(spec)`。
  - `assemble_image_timeline` 严格保持既有 9 参数签名不变，仅通过 `spec['shot_motions']` 可选键启用逐镜动效；未传 `shot_motions` 时命令参数零回归。
- `程序/domain/animatic_service.py`（L2，293 行，保留 L83/L111 外部依赖清单行号）：
  - `build_bundle` 支持可选 `settings['overlay_frame']` 钩子与默认开启的 `animatic_burn_overlay`，经 `_prepare_assemble_frames` 仅对传给 `assemble` 的暂存副本执行烧录，入库 `artifacts` 镜头图仍取干净原图；同时向草图渲染器透传分镜原始元数据与时间线时长。
- `程序/domain/animatic_timeline.py`（L2，161 行）：
  - 新建镜头行补充可选字段 `dialogue_seconds: None`，并在 `_CARRIED` 中加入 `dialogue_seconds`，重建时间线保留已写秒数且兼容旧版缺字段 `timeline.json`。
- `程序/orchestrator/stage_animatic_gateways.py`（L3，803 行，保留 L75/L157 外部依赖清单行号）：
  - `_timeline_render` 适配 `text_card`、`gflow_cli`（经 `importlib.util.find_spec` 惰性加载 `infra.gflow_images.generate`，读取 `infra.model_pool.pool()` 中 `gflow-*` 且 `modality=='image'` 模型并优先匹配 `animatic_gflow_model`，缺失报友好中文错）与 `comfy_local`。
  - `regenerate_animatic_shot` 复用 `_ensure_comfy_ready(settings)` 并透传预览规格与完整镜头信息。
  - `run_animatic_timeline` 注入 `_overlay_frame` 与 `animatic_ken_burns`（默认 `True`）`shot_motions`，并在后台经 `_probe_dialogue_seconds`（优先注入 `probe_duration`，否则复用 L1 `agent.media.probe`）实测各镜对白秒数写入 `_compose_timeline_rows` → `timeline.json` 的 `dialogue_seconds`。

## 先红后绿记录

改产品代码前先向 `tests/test_animatic_sketch_backends.py`、`tests/test_animatic_service.py`、`tests/test_animatic_timeline.py` 补全 5 组边界测试与 `regenerate_animatic_shot` 探测用例：
- 定向命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_sketch_backends animatic_service animatic_timeline copy_rules`
- 改前红灯（退出码 1）：
  1. `test_req_s04_100_text_card_empty_dialogue_and_long_chinese_description`：`AssertionError: 'text_card' not found`
  2. `test_req_s04_100_text_card_falls_back_cleanly_when_fonts_missing`：`ValueError: 未知的草图生成后端：text_card`
  3. `GflowCliBackendTests` 3 项：`gflow_cli` 未注册
  4. `test_req_s04_103_render_overlay_frame_preserves_original_sha256` / `test_req_s04_104_infer_motion_maps_five_motions_and_priority`：`AttributeError`
  5. `test_req_s04_103_build_bundle_burns_overlay_only_on_scratch_copies`：`ImportError: cannot import name 'render_overlay_frame'`
  6. `test_req_s04_104_segment_filter_five_motions_and_zero_regression`：`ImportError: cannot import name 'segment_filter'`
  7. `test_req_s04_105_112_rebuild_preserves_dialogue_seconds_and_legacy_rows`：`KeyError: 'dialogue_seconds'`
  8. `test_req_s04_105_run_animatic_timeline_records_dialogue_seconds_and_motion`：`ValueError: 未知的草图生成后端：text_card`
  9. `test_req_s04_83_regenerate_animatic_shot_reuses_ensure_comfy_ready`：`AssertionError: [] != [('wait', ...), ('open',), ('wait', ...)]`
- 改后转绿：84/84 定向测试全绿（退出码 0），711/711 架构门禁全绿（退出码 0），9/9 默认冒烟全绿（退出码 0）。

## 未验证项与卡外发现

- **未验证项**：`run_selftests.py --all --safe` 未在本功能分支执行；真实 `gflow.exe` 与 Codex `codex/flow-model-pool` 的 `infra/gflow_images.py` 端到端联调待两条车道合并到 master 后验证（本轮按固定 5 参契约单测覆盖 `i2i`/`t2i`、模型池解析与缺失报错）。
- **卡外发现**：当前工作树与后台并发测试共用 `gui-selftest.lock` 期间，`test_animatic_scope`（GUI 类测试）曾被 `[GUI_DEFERRED]` 跳过，但不影响本卡全部非 GUI 定向测试与 711 项架构门禁；后续合入 master 前按常规门禁跑完整回归即可。
