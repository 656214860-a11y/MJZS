# R4544 FIX-S04-MEDIA-DB-VIEW：S04 分镜预演右侧媒体数据库视图与健壮性修复
<!-- round-evidence: {"commit_base": "3fbb2744f", "credential_hits": 0, "evidence_sha256": "fa7bb13d18bf1cdb", "exit": 0, "failed": 0, "passed": 315, "round": 4544, "tests": "run_selftests.py -k animatic_page animatic_timeline files_panel_stages copy_rules"} -->

## 三问

1. **本轮类型（§3）**：§3.2 修复轮（任务卡 `FIX-S04-MEDIA-DB-VIEW`，涉及 `REQ-S04-06`、`REQ-S04-70~73`、`REQ-S04-83`、`REQ-S04-95~99`、`DES-S04-20/25`）。
2. **测试与三个基线**：
   - 默认冒烟（`smoke_test.py`）：9/9 通过（隐藏桌面 `--probe` + 8/8 检查项），退出码 `0`。
   - 架构门禁（`smoke_test.py --architecture`）：711/711 全绿，0 红，退出码 `0`（含 `_layers`、`test_module_size_ratchet`、`test_complexity_ratchet`、`test_shared_state_ratchet`、`test_http_boundary`、`test_button_boundary`、`test_dialog_boundary` 等；初跑时暴露 `test_http_boundary` 1 红，收敛共用 `_probe_comfy` 后 711/711 全绿）。
   - 定向自检（`run_selftests.py -k animatic_page animatic_timeline files_panel_stages copy_rules`）：315/315 全绿，0 红，0 跳过，退出码 `0`。
   - 全量安全回归（`--all --safe`）：未运行（功能分支开发轮，合入 master 门禁统一结算）。
3. **欠账变化**：本轮未新增欠账；闭环 S04 右侧参考图库不可见、折叠组未收起与缩略图无上限预取、镜头提示词漏读 `image_prompt`、已采用分镜损坏静默吞错及 `run_animatic_timeline` 未探测/拉起 ComfyUI 等 5 项缺陷。

## 改动摘要与行数核验

- `程序/ui/desktop_files_panel_index.py`（597 行）：
  - `load_index(..., stage='animatic')` 在 `not library` 时调用 `stage_execution_service.animatic_reference_library(root)`，将共享及旧参考图库文件就地补齐/转正为 `stage='animatic', kind='资产'` 的 `FileRow`（同 `path` 已存在时就地转正不重复，不写盘、不扫 `.work/`，其余阶段零变化）。
  - 新增 S04 语义分组纯函数 `animatic_bucket` / `animatic_grouped_rows`（参考图库、预演版本、镜头草图、临时声音、其他预演文件）、默认展开判定 `group_default_open`、展开组预取收集 `prefetch_media_paths`（`_MEDIA_PREFETCH_CAP = 40`）、以及折叠组 `<<TreeviewOpen>>` 按需补图 `bind_lazy_group_previews`；折叠组行在初始渲染时跳过同步缩略图与音频封面排队。
- `程序/ui/desktop_files_panel_filters.py`（993 行，< 1000 上限）：
  - `_index_groups` 在 `not library` 且 `group_mode == '阶段'` 且 `stage_filter == 'animatic'` 时委托 `animatic_grouped_rows`。
  - `_stage_view_index_render` 按 `group_default_open` 建树（「参考图库」「预演版本」`open=True`，「镜头草图」「临时声音」「其他预演文件」`open=False`），`_stage_view_request_index` 与 `_prefetch_media_thumbs` 仅预取展开组且限流 40 项。
- `程序/ui/animatic_view_state.py`（288 行）＋ `程序/ui/animatic_page.py`（984 行，< 1000 上限）：
  - `_show_shot_info` 经 `shot_prompt_text` 依次读 `image_prompt` → `prompt` → `video_prompt` → `description`。
  - `show()` 经 `load_timeline_for_show` 载入时间线：未采用分镜继续安静进入引导页；已采用分镜 JSON 损坏等非「未采用分镜」异常写入 ≤45 字中文报错到 `page.status.set(...)` 再显示引导页。
  - `_reclassify` / `_rename_reference` 成功后经 `_refresh_files_panel` 刷新右侧文件面板。
- `程序/orchestrator/stage_animatic_gateways.py`（686 行）：
  - 抽出共用 `_probe_comfy`（保留既有外部依赖清单登记行 `stage_animatic_gateways.py:157`）与 `_ensure_comfy_ready`。
  - `run_animatic_timeline` 仅当后端为默认 `comfy_local`、`settings.get('comfy_client') is None` 且存在缺图镜头时执行 `wait_comfy` → `open_comfy` → `wait_comfy`；全镜已有图、注入桩或非 `comfy_local` 后端直接跳过。

## 先红后绿记录

改产品代码前先向 `test_files_panel_stages.py`、`test_animatic_page.py`、`test_animatic_timeline.py` 补齐 5 类边界用例并执行定向回归：
- 命令：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k animatic_page animatic_timeline files_panel_stages`
- 改前红灯（296 条用例，3 个文件 6 条红，退出码 1）：
  1. `test_animatic_timeline::test_run_animatic_timeline_probes_and_opens_comfy_when_missing_images`：`[] != [('wait', 'http://127.0.0.1:8199', 3), ('open',), ('wait', 'http://127.0.0.1:8199', 12)]`
  2. `test_animatic_page::test_corrupt_adopted_storyboard_sets_status_and_shows_guide`：`[] is not true : 损坏分镜不得静默吞错，应写入状态栏`
  3. `test_animatic_page::test_show_shot_info_reads_image_prompt_and_fallbacks`：`'雨夜红伞特写' not found in '提示词：（分镜未写提示词），参考图：无'`
  4. `test_files_panel_stages::test_load_index_empty_ref_library_and_in_place_promotion`：`0 != 1 : 缺失于索引的参考图应补齐一条`
  5. `test_files_panel_stages::test_animatic_panel_four_groups_collapse_and_prefetch_throttle`：平铺 61 行而非 4 语义分组
  6. `test_files_panel_stages::test_animatic_prefetch_caps_at_40_when_expanded_groups_exceed_limit`：`61 != 40`
- 改后转绿：全部 315 条定向测试 0 红通过，711 条架构门禁 0 红通过。

## 未验证项与卡外发现

- **未验证项**：`run_selftests.py --all --safe` 未在本分支轮执行；真实本机 ComfyUI 进程拉起交互未联调（单测使用 `wait_comfy`/`open_comfy` 桩覆盖调用顺序与跳过条件）。
- **卡外发现**：`orchestrator/stage_animatic_gateways.py::regenerate_animatic_shot()`（单镜重做）同样未在默认 `comfy_local` 无桩时探测/拉起 ComfyUI，因超出本卡契约范围未改动，建议后续按需排卡统一复用 `_ensure_comfy_ready`。
