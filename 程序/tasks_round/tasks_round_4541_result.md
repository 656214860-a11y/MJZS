# R4541: S04-V2-SPEC 登记 S04 分镜预演 V2 需求与设计
<!-- round-evidence: {"commit_base": "3fbb2744f", "credential_hits": 0, "evidence_sha256": "7434e1029d958a0a", "exit": 0, "failed": 0, "passed": 0, "round": 4541, "tests": "docs-only"} -->

## 三问

1. **本轮属于 §3 哪种类型？**：功能轮（文档先行规格轮，对应卡 `S04-V2-SPEC`，纯文档登记，未修改任何 `.py` 源码或测试文件）。
2. **测试跑了吗、三个基线过了吗？**：
   - 卡面定向验收 `..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k req_s04_anchors animatic_scope`：已运行，29/29 通过（`test_req_s04_anchors` 15 条＋`test_animatic_scope` 14 条，0 红，0 跳过，退出码 0）。
   - 架构门禁 `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：已运行，711/711 通过（0 红，退出码 0，改前后一致）。
   - 默认冒烟（8/8）：未运行（纯文档规格轮，未触及 `.py` 与 Tk 运行路径）。
   - 全量回归（`run_selftests.py --all --safe`）：未运行（功能分支纯文档轮，以 `full-safe-receipts.json` 为准）。
3. **欠账少了吗？**：维持不变。本轮为纯文档先行规格轮，未新增源码欠账；新增 `REQ-S04-100`..`REQ-S04-112` 与 `DES-S04-30`..`DES-S04-35` 均标 `⬜`，待后续实现卡 `S04-V2-ENGINES-MOTION` 与 `S04-V2-UX-PERF` 交付验收后翻 `✅`，不新增未锚定 ✅ 条目。

## 本轮交付

- 卡号：`S04-V2-SPEC`（基线 `3fbb2744f`，分支 `codex/s04-v2-spec`）。
- 修改文件：`程序/docs/stages/S04_分镜预演.md`（仅增量追加，既有 ✅ 条目 `REQ-S04-01..99`、`DES-S04-01..25` 及 `IF-S04-*` / `UX-S04-*` 表格保持原样未删改）。
- 新增需求：在 `## 需求` 末尾新增「2026-11-26 增强：零成本与 gflow-cli 生图、2D 动效字幕、外置播放优先与 Tkinter 性能红线（来源：用户决定 2026-11-26）」，逐条登记 `REQ-S04-100` 至 `REQ-S04-112`（全部标 `⬜`）。
- 新增设计：在 `## 设计` 新增「2026-11-26 增强的设计条目（对应 REQ-S04-100…112，均为 ⬜ 待实现）」，补充模块分工表（`animatic_sketch_backends`、`edit_service`、`animatic_service`、`stage_animatic_gateways`、`animatic_prefs_bar`、`animatic_page`、`desktop_files_panel_index/filters`）与 `DES-S04-30` 至 `DES-S04-35`（全部标 `⬜`），并同步在 `### 测试锚定` 表追加待补用例行。

## 验收与边界核对

- 边界检查：`git diff --numstat` 确认 `程序/docs/stages/S04_分镜预演.md` 为纯新增行（0 行删除），无本机绝对路径、无密钥或私有配置。
- 提交方式：经 `scripts\dev.py commit --agent native:self` 提交至 `codex/s04-v2-spec` 分支，自动生成 `程序/tasks_round/evidence/R4541.json` 并在本文件标题下写入 `round-evidence` 标记；未改队列状态、未执行合并与推送。
- 未验证项：默认冒烟 `smoke_test.py` 与安全全量 `run_selftests.py --all --safe` 未在本轮运行（纯文档规格轮，留待后续实现轮与合入出口验证）。
