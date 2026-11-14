# R2481 功能轮：自然剧本质检附块剥离 + 质检报告可定位

## 三个问题

- **轮次类型**：功能轮（§3.1）。扩展阶段 01 剧本准备的辅助质检：附块残留剥离 + 「质检报告」按钮历史报告定位。未改分层、契约或权威源。
- **测试**：定向 `run_selftests.py --serial -k writing_quality stage_execution_service desktop_script_pages script_page_services` 28 条全绿；`-k writing_quality` 17 条全绿（含新增 3 条）；`-k script_page_services` 3 条全绿（含新增 1 条）。默认冒烟 8/8 通过。架构门禁本轮未整跑通过：`test_bare_json_load_debt`（`api_endpoints.py` json.loads 债务）与 `基准历史.json` 缺失为既存环境/债务问题，主工作区同样红，非本轮引入。
- **欠账**：`project_status.md` 欠账未因本轮减少；本轮改源码 +1 轮（全量欠账 +1，符合 §5 触发口径，不命中风险路径，未强制跑全量）。

## 目标

修复三个问题：

1. 自然剧本文件末尾残留 `<script_quality>{JSON}</script_quality>` 附块（附块未闭合/被截断时尤其明显）。
2. 三端（API / CLI / Desktop）都正确拆分附块并产出质检报告；附块损坏时正文仍完整保存、报告如实标「格式或证据错误」，且不残留半截 JSON。
3. 点击「质检报告」能快速定位对应剧本的质检报告，而非打开一串 hash 子目录或只记「最近一次」。

## 根因

- `writing_quality.split_response` 在附块未以 `</script_quality>` 闭合时抛 `ValueError`、返回 `error` 非空；`stage_execution_service.collect_writing_quality` 第 321 行 `if not error` 导致**不写回干净正文**，半截 JSON 残留在剧本文件里。
- 报告落盘到 `quality/<identity>/<digest>/`，目录名全是哈希，用户无法对应到具体剧本；`_script_quality_report` 只存内存、重启丢失、只记当前项目最近一次。

## 改动

### 程序\writing_quality.py（L2）

- 新增 `strip_envelope(text)`：只认最后一次 `<script_quality>` 作为附块起点，之前内容一律为正文；附块未闭合/损坏也照常剥离。
- `split_response` 的 `body` 改用 `strip_envelope`，保证返回的正文永远干净（返回签名不变）。
- `publish_reports` 的 `质检报告.md` 顶部追加「来源剧本：<绝对路径>」行。
- 新增 `list_reports(quality_root)`：扫描 `quality/*/*/质检报告.md`，读 `screenplay_gates.json` 的 `script_path` 字段，把 hash 目录映射回具体剧本，按 mtime 倒序返回。

### 程序\stage_execution_service.py（L3）

- `collect_writing_quality` 写回条件从 `if not error and response.strip() != body.strip()` 改为 `if response.strip() != body.strip()`：只要剥离出附块就写回干净正文，不再因附块损坏而残留。

### 程序\desktop_script_pages.py（L4）

- `open_script_quality` 回退链：内存记录报告 → `list_reports` 定位本项目最新历史报告 → 打开 quality 目录 → 提示尚无报告。

### docs/stages/S01_剧本准备.md

- REQ-S01-76 第 45 行与 DES-S01-76 第 151 行同步「质检报告」按钮的定位回退链描述。

## 测试

- `tests\test_writing_quality.py`：新增 `test_strip_envelope_removes_residual_envelope_in_all_shapes`、`test_list_reports_maps_hash_folders_back_to_scripts`、`test_list_reports_empty_or_missing_dir`；原 `test_incomplete_desktop_envelope_notifies_without_overwriting_source` 改名 `test_incomplete_desktop_envelope_notifies_and_strips_residual_json`，断言从「文件残留原文」改为「文件被剥离附块写回干净正文」（有意契约变更，见 §2.4）。
- `tests\test_script_page_services.py`：新增 `test_fallback_opens_latest_report_matching_current_project`，验证重启后（无内存记录）能定位历史报告。

## 验证

- `run_selftests.py --serial -k writing_quality stage_execution_service desktop_script_pages script_page_services`：28 条，0 红。
- `run_selftests.py -k writing_quality`：17 条，0 红（含新增 3 条）。
- `run_selftests.py -k script_page_services`：3 条，0 红。
- 默认冒烟 8/8。
- `test_writing_api` 的 10+3+10+1 条红为主工作区既存（确认流程/取消/preparation_state），与本轮无关。
- 架构门禁既存红（`api_endpoints` json.loads 债务、`基准历史.json` 缺失）非本轮引入。

## 边界与说明

- 附块完全缺失（无 `<script_quality>`）：`strip_envelope` 原样返回，正文无变化；报告四项标「缺失」（既有行为）。
- 外部工具（如 Gemini desktop）直接产出、绕过漫剧助手的剧本文件，漫剧助手无法实时拦截；用户下次在漫剧助手中触发任意一次自然剧本保存/回收时，`collect_writing_quality` / `_save_formal_script` 会剥离残留附块。
- 并发写保护：`collect_writing_quality` 的「回收期间正文变化」检查保留，避免覆盖用户手改。

## 提交

- 提交信息：`R2481: 自然剧本质检附块剥离 + 质检报告定位`
- 分支：`codex/wip-R2481`
- commit hash：`2598dcb5`
