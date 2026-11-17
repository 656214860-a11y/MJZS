# R3196 结果（零依赖边界与媒体预览任务书 M4：视频、音频封面与波形预生成）
<!-- round-evidence: {"commit_base": "3320c83b", "credential_hits": 0, "evidence_sha256": "435eacaae2b8b0c5", "exit": 0, "failed": 0, "passed": 95, "round": 3196, "tests": "run_selftests.py -k test_asset_thumbs test_files_panel test_download_inbox"} -->

- 轮次类型：功能轮（任务书 M4，REQ-S01-95；实领 **R3196**，分支 `codex/wip-R3196`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮：`asset_thumbs` 增媒体封面通道（ffmpeg 抽帧／波形、旁路记录、占位图），面板与下载收件箱两个后台补齐触发点。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9；`test_asset_thumbs` 35 条全绿（新增 12 条媒体用例：后缀分流、固定画幅、签名失效、缓存命中、ffmpeg 缺失占位、损坏占位、旁路记录、超时占位＋迟到封面原位替换、预取过滤）；`test_files_panel`/`test_files_panel_stages`/`test_download_inbox` 共 60 条全绿。首轮 1 红（超时用例没模拟活 worker，被 worker-gone 分支正常弹出），补 live-worker 桩后复跑绿——见「验证」。架构门禁随合入前全量统一验。
3. **欠账少了吗？** 减少：视频封面／音频波形零依赖生成链路落地，UI 线程不做 ffmpeg，时长与分辨率走旁路记录不动 `FileRow`/`INDEX_VERSION`。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `asset_thumbs.py` | 新增媒体通道：`media_kind()`（按 `infra.file_index` 后缀表，不重复定义）、`file_stamp()`（`mtime_ns:st_size` 签名）、`media_geometry()`（视频 16:9／音频约 3:1 固定画幅）、`media_thumbnail()`/`request_media()`/`prefetch_media()`/`media_info()`；排队摆同画幅空盒，worker 写回后原地贴图；ffmpeg 缺失／损坏／超时落 `.none` 或灰底占位图（播放三角／波形条，`_media_placeholder`），JOB_DEADLINE 到点先贴占位、封面迟到仍原位替换，worker 真死才弹出任务——界面线程绝不做 ffmpeg。worker 端 `_media_job()`：ffprobe 写 `<键>.info.json` 旁路（duration/width/height），ffmpeg `image2pipe` 出固定画幅 PNG（视频抽帧＋scale/pad 补黑边、音频 `showwavespic`）；工具一律经 `tool_path`（M1 统一：显式有效配置＞随包＞PATH），任务 spec 透传项目显式配置；单 worker 顺序处理＝并发上限天然成立。 |
| `ui/desktop_files_panel_filters.py` | `_prefetch_media_thumbs()` 读项目 `config.json` 的 ffmpeg/ffprobe 显式配置透传；索引视图（`_fill_index_list`）与素材库视图（`_fill_global_list`）填表后 `prefetch_media()` 补齐缺封面；缺失行跳过。 |
| `desktop_auto_flows.py` | `_tick_download_inbox` 收回导入文件后对其中视频／音频 `prefetch_media()`（发布/导入完成时预生成）。 |
| `tests/test_asset_thumbs.py` | 新增 `MediaThumbTests` 12 条：后缀判定、画幅、签名失效、排队与任务 spec（kind/ffmpeg/ffprobe 字段）、空盒原地贴封面、缓存命中不排队、替换文件换新键、ffmpeg 缺失 `.none`＋占位、损坏 `.none`＋占位、封面＋旁路记录落盘、超时占位＋迟到封面原位替换、预取只排媒体。 |
| `docs/stages/S01_剧本准备.md` | REQ-S01-95 🟡→✅（R3196）；DES-S01-95 同步为实测实现口径。 |

## 决策与边界

- **不动 `FileRow`／`INDEX_VERSION`**：时长、分辨率由 ffprobe 写封面同键 `<键>.info.json` 旁路（`media_info()`），L0 契约不改（任务书边界）。
- **媒体任务在界面线程永不回退同步做**：图片的 `_build_here` 回退对媒体禁用；worker 活着只慢时任务保留继续等（封面迟到原位贴上），worker 真死才弹任务给占位图——会话内不重复扫磁盘。
- **并发上限**：单后台进程顺序处理任务即天然串行 ffmpeg；`QUEUE_LIMIT=400` 继续封顶排队。
- **触发口径**：面板打开/筛选重填与下载收回导入时补齐；启动路径零扫描（REQ-S01-95 与本任务书一致）。

## 验证

- `smoke_test.py`：9/9。
- `run_selftests.py -k test_asset_thumbs test_files_panel test_download_inbox`：95 条，首轮 1 红（`test_deadline_lands_placeholder_and_late_cover_still_replaces` 未模拟活 worker，被 worker-gone 弹出的设计行为），修正测试后复跑 `test_asset_thumbs` 35 条全绿。
- 真机 E2E（手动）：bundled LGPL ffmpeg（无 libx264，用 mpeg4/sine 造样例）→ `clip.mp4` 出 72×40 封面 2069B＋`{'width':320,'height':240,'duration':2.0}`，`voice.mp3` 出 72×24 波形＋`{'duration':2.0}`——随包 ffmpeg 足够支撑封面生成。
- 全量 `--all --safe` 合入 master 前统一跑。

## 遗留

- M5 消费本通道：面板缩略图列（图片/视频封面/音频波形）、行内与右键「打开／在文件夹中显示／另存为」、时长分辨率读旁路记录。
- M6–M8 续。
