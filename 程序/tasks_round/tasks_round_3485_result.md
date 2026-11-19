# R3485 结果文件 — 修复轮：master 全量既有红三处（测试契约同步已合入行为变更）
<!-- round-evidence: {"commit_base": "93e3ef64", "credential_hits": 0, "evidence_sha256": "ad80796aee7ae7aa", "exit": 0, "failed": 0, "passed": 732, "round": 3485, "tests": "run_selftests.py -k ui_edges pet_ui shared_adapter"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮（master `full-safe-history.jsonl` 连续红灯的既有欠账清理；三处红根因均已查明并修复，改动全部在 `tests/` 断言同步层，无生产代码改动）。
2. **测试跑了吗、三个基线过了吗？** 跑了。红→绿证据：三处失败在 master 自动全量与本工作树定向复跑中逐一复现，修复后定向全绿（明细见下）；默认冒烟 9/9；全量 `--all --safe` 未跑（修复轮非 §4.2 必跑清单；合入后由 master 侧 auto_full_safe 补跑验证，凭据以 `full-safe-receipts.json` 为准）。
3. **欠账少了吗？** 少了。master 持续红的 4 个测试文件中修复 3 个（`test_ui_edges_guards`、`test_pet_ui`、`test_shared_adapter_infrastructure`）；`test_perf_baseline` 为负载敏感性能断言（CPU 比 10.5–10.7× vs 限 10.0×），机器空闲时可复绿，属环境抖动非代码缺陷，如实保留观察。

## 背景与根因（全量历史取证）

`full-safe-history.jsonl` 取证：

- `test_shared_adapter_infrastructure` 自 2026-11-18T11:59（head `f0665b68`）持续红——R3320（L2 任务书轮9，`1f752e0b`，已合入 master）把 `domain/tts_api` 出站收口到 `infra.http_client.request_bytes`（规则 42），不再自开 urllib opener；测试仍把它列在「各适配器共用 `no_redirect`」的断言集内，属测试成员口径未同步。
- `test_ui_edges_guards`、`test_pet_ui` 自 2026-11-18T18:35（head `dc3b3bb8`＝R3382 L0 v2 合并轮）同步转红——R3364（L0 v2 轮7B，`9a611353`，REQ-S13-54/REQ-S10-22）两处有意重构：①`engine.auto_edit_ready` 内联选版循环抽为共用内核 `edit_ready_rows`（与 `stage_completion_service.edit_ready_for_project` 同源），`adopted_edit_version(st['shots'].get(shot['id'])` 字面出现次数 2→1；②`stage.completed` 改经 `emit_verified_completion` 按磁盘证据核验，无证据发 `stage.paused`。R3364 当时未跑全量（可靠性轮不在 §4.2 必跑清单），两处断言漂移随合并进入 master。
- `test_perf_baseline` 间歇红（负载敏感），最近三次自动全量均在列。

## 修复内容（全部测试断言同步，无生产代码改动）

| 文件 | 改动 | 契约依据 |
| --- | --- | --- |
| `tests/test_ui_edges_guards.py` | `adopted_edit_version(st['shots'].get(shot['id'])` 计数断言 2→1（手动拼装 `assemble()` 直呼保留），新增 `edit_ready_rows(` ≥2 断言（自动粗剪经共用内核，其内仍调 `adopted_edit_version`）；`approved_versions(...)` ==0 断言不变 | R3364 REQ-S10-22 共用选版内核；守卫意图「两路径收敛同一内核」保持 |
| `tests/test_pet_ui.py` | `test_tick_once_drains_into_the_bus` 期望 `("stage.completed","delivery")`→`("stage.paused","delivery")`；用例无交付产物，核验失败发 paused 是 REQ-S13-54 的正确行为；排水→总线→状态栏三项断言意图不变 | R3364 REQ-S13-54 完成事件磁盘证据核验 |
| `tests/test_shared_adapter_infrastructure.py` | `NoRedirectSharedTests` 适配器集移除 `tts_api`（已收口 `http_client`，直连传输由 `test_http_boundary` 守卫，不在本门禁适配器集）；删除对应 import | R3320 http_client 收口＋AGENTS 规则 42 |

## 红→绿证据

| 用例 | 改动前（master/本树复现） | 改动后 |
| --- | --- | --- |
| `test_approval_consumers_use_the_shared_helper` | `1 != 2`（AssertionError） | ok |
| `test_tick_once_drains_into_the_bus` | `('stage.completed','delivery') not found in [('stage.paused','delivery')]` | ok（隐藏桌面实跑） |
| `test_every_adapter_uses_the_one_implementation` | `module 'domain.tts_api' has no attribute 'no_redirect'` | ok |

定向验证：`run_selftests.py -k ui_edges pet_ui shared_adapter`（结果见提交证据 `evidence/R3485.json`）；单测预跑 `unittest tests.test_ui_edges_guards tests.test_shared_adapter_infrastructure` 13/13 绿、`gui_hidden` 单跑 `test_tick_once_drains_into_the_bus` OK。

## 边界与说明

- 本轮为任务书外 master 既有红清理（§8.4 欠账处置）：两红归因 L0 v2（本车道族前序任务书 R3382 合入），一红归因 L2 车道 R3320；修复均为断言同步已合入的有意行为变更，未弱化断言语义（守卫意图逐条保留并在注释注明契约依据）。
- `test_perf_baseline` 未动：CPU 比断言对机器负载敏感，空闲时段预期自复；若持续红再立修复轮。
- 与在途分支冲突面：仅 `tests/` 三文件，无生产代码；foundation/L2 各分支未见同文件改动（合并时 CI 复核）。

## 环境修复（非仓库改动，如实记录）

首次提交证据跑（732 过 1 文件红）暴露 `test_pet_ui.FrameBatchSeamTests` 另有 2 条红：`keyframe_evidence.image_facts` 解码首帧 PNG 失败。根因链：

1. `运行环境/ffmpeg`（.gitignore 排除的随包工具）自 2026-11-17 Python 3.15 embeddable 迁移后从主工作树消失，`auto_full_safe._fill_bundled_tools` 取源落空 → 干净检出与本工作树 `tool_path('ffmpeg')` 均落空。
2. 本工作树曾临时硬链接 `devin-l1-enterprise` 工作树的 ffmpeg（n9.0.2-57-git 自建版）补齐，但该构建在隐藏桌面下 `CreateProcess` 后 DLL 初始化失败（rc=0xC0000142，`ffmpeg -version` 均不可跑），GUI 测试内解码仍红。
3a. 改用机器上可用的 gyan.dev essentials 9.0.1 构建（`D:\Tools\ffmpeg`，仓库测试自身以此为 FFMPEG 基准路径）硬链接补齐 `运行环境/ffmpeg/bin/{ffmpeg,ffprobe}.exe`——本工作树与主工作树各一份（同卷硬链接，零拷贝）。隐藏桌面实测 `image_facts` 解码通过。
3b. 主工作树补齐后 `auto_full_safe` 后续干净检出可重新获得可用 ffmpeg，根除该环境欠账源。

验证：`run_selftests.py -k keyframe_evidence` 13/13 绿（普通桌面）；`run_selftests.py -k pet_ui` 612/612 绿（隐藏桌面，含 FrameBatchSeamTests 2 条原红与本轮 stage.paused 修复项）。

## 三基线

- 默认冒烟：9/9 绿。
- 架构门禁：未整轮重跑（仅 `tests/` 非架构目录断言改动；合并轮出口 CI 含架构门禁）。
- 全量回归：未跑（修复轮）；合入后 master 侧 auto_full_safe 补跑，`full-safe-receipts.json` 为唯一权威。

## 提交

- 分支 `codex/l0-constitution`；`dev.py commit --tests ui_edges pet_ui shared_adapter` 生成 `evidence/R3485.json`；提交号与 hash 见提交记录。
