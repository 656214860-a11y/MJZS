# R3200 结果（零依赖边界与媒体预览任务书 M5：面板预览列＋打开/在文件夹显示/另存为）
<!-- round-evidence: {"commit_base": "dde3408d", "credential_hits": 0, "evidence_sha256": "c1ae1ad1a8f7d496", "exit": 0, "failed": 0, "passed": 145, "round": 3200, "tests": "run_selftests.py -k test_files_panel test_files_panel_stages test_asset_thumbs test_context"} -->

- 轮次类型：功能轮（任务书 M5，REQ-S01-95 面板侧消费＋REQ-S01-96；实领 **R3200**，分支 `codex/wip-R3200`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮：项目文件面板加预览列（图片缩略图／视频封面／音频波形）与「时长／分辨率」列，行内与右键新增「打开／在文件夹中显示／另存为…」。
2. **测试跑了吗、三个基线过了吗？** 跑了。冒烟 9/9；定向 `run_selftests.py -k files_panel context asset_thumbs` 177 条（首轮我新增 3 条用例红：Tcl show 值对象、`file_cache` 无写口、frozen dataclass 补丁点——改测试后全绿）；复跑 `-k files_panel_stages context` 134 条 0 红。架构门禁随合入前全量统一验。
3. **欠账少了吗？** 减少：M5 全部功能项落地；「按阶段分组（可折叠）」（R3139 登记）按任务书允许转**明确欠账**——阶段图标列＋筛选条已提供等价导航，树分组需节点化列表结构，另立轮次。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `contract/platform_tools.py` | 新增 `reveal_in_folder(path)`：Windows `explorer /select,` 选中文件本身（拉起即返回，不读恒为 1 的退出码）；macOS `open -R`；其他 `xdg-open` 所在目录；无管理器/文件不存在抛可展示 `ValueError`。 |
| `ui/desktop_files_panel.py` | 表格加 `meta`「时长／分辨率」列，`#0` 作预览列（默认 `show='headings'` 隐藏）；索引/素材库行右键给「打开／在文件夹中显示／另存为…」，剧本四类行在原有项后追加「在文件夹中显示／另存为…」；`open_script_file` 修 `library:` 前缀行误拼项目根的既有缺陷（经 `_row_abs_path` 解析素材库根）。 |
| `ui/desktop_files_panel_filters.py` | `_fill_index_list`/`_fill_global_list`：开 `show='tree headings'`，行挂 `_row_preview`（媒体走 `asset_thumbs.media_thumbnail` 占位盒→原位替换；图片走 `asset_thumbs.thumbnail`；缺失行跳过）与 `_row_meta_text`（读 M4 旁路 `media_info`，不动 `FileRow`）；`_schedule_meta_refresh`→`_refresh_media_meta` 延迟 1.5s 补一次空格（不递归排期）；`_row_abs_path`（index 项目相对／`library:` 素材库相对）；`save_as_file`（预填 `项目名_阶段名_原文件名`、`shutil.copy2` 复制不移动原件、存在先 `confirm`、取消零写入、失败抛原因）；`show_in_folder`→`reveal_in_folder`；`script_row_stage` 按行 iid 记录阶段中文名（预填名与 `_SAVE_AS_STAGES` 剧本类别映射）。预览常量 `PANEL_PREVIEW_SIZE/PANEL_PREVIEW_COL_WIDTH/PANEL_META_WIDTH` 放本文件避免环形导入。 |
| `tests/test_files_panel_stages.py` | 新增 `FileActionsTests` 10 条：预览列开/收、占位盒画幅、非媒体无预览、旁路元数据、索引行三项菜单、另存为取消零写入/预填名复制原件不动/覆盖先问（拒写＋同意写）/失败报因、「在文件夹中显示」定位文件本身。 |
| `tests/test_context.py` | 新增 `RevealInFolderTests` 2 条：不存在路径抛错、Windows `explorer /select,` 命令与拉起即返回语义。 |
| `docs/stages/S01_剧本准备.md` | REQ-S01-96 🟡→✅；DES-S01-96 同步为实测实现口径；「按阶段分组」记为明确欠账。 |

## 决策与边界

- **预览列挂 `#0`**：Treeview 唯一可挂图元的列；索引/素材库视图 `tree headings`，剧本四类视图收回 `headings`（文档行无预览）。
- **占位→原位替换**沿用 M4 空盒/常驻图元机制，行本身不重插——500 行滚动性能由既有渐进加载＋同画幅空盒保证（不新增扫描、不阻塞 UI 线程）。
- **删除语义不动**：仍走 `storage_maintenance.recycle_paths()`；索引行菜单只加三项动作。
- **另存为只复制**：`shutil.copy2`，原件不动；取消/拒绝覆盖均零写入；失败 `OSError` 带原因上抛给 `page.safe` 统一弹错。
- **「按阶段分组（可折叠）」转欠账**：任务书允许「完成或明确转欠账」；记欠理由与等价导航写入 DES-S01-96。

## 验证

- `smoke_test.py`：9/9。
- `run_selftests.py -k files_panel context asset_thumbs`：177 条，首轮 3 条新增用例红（断言写法，非产品代码），修正后 0 红。
- `run_selftests.py -k files_panel_stages context`：134 条 0 红（含新 10 条 FileActionsTests＋2 条 RevealInFolderTests）。
- 全量 `--all --safe` 合入 master 前统一跑。

## 遗留

- M6 离线 ASR 默认云端＋可选下载；M7 登录后模型池为空开模型管理；M8 收尾。
- 「按阶段分组（可折叠）」欠账待另立轮次（原 R3139 登记项）。
