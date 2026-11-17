# R3150 结果（项目文件图标再右移半步＋与左侧聊天框间距减半）
<!-- round-evidence: {"commit_base": "a1eaba36", "credential_hits": 0, "evidence_sha256": "426f459a78759c71", "exit": 0, "failed": 0, "passed": 44, "round": 3150, "tests": "run_selftests.py -k files_panel compact_layout"} -->

- 轮次类型：功能轮（桌面界面微调；分支 `codex/wip-R3150`，基线 master `a1eaba36`）。
- 用户要求：项目文件图标再右移半步，且与左侧聊天框的距离再缩短 1/2。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（既有入口钮的 padding 微调，不改启动路径、不改契约）。
2. **测试跑了吗、三个基线过了吗？** 跑了。定向 `run_selftests.py -k files_panel compact_layout` **44 条 0 红**（含 files_panel／files_panel_stages／desktop_compact_layout）；默认冒烟 **9/9**。架构门禁未跑（非结构治理／跨层改动）；全量未跑（无触发条件）。
3. **欠账少了吗？** 未产生新欠账；无历史欠账处置。

## 定量依据（改动前实测，隐藏桌面 1008×900）

- 改动前：`rail` w=44、`button` w=38 `padx=(4,2)`；图标字形约 30px 在钮内居中，图标左缘距聊天区（`stage_area`）右缘 **8px**（左 pack padding 4＋按钮内边距 4）；图标右缘距内容区右缘 6px（body padding 4＋右 pack padding 2）。
- 改动后（探针复测）：`rail` w=38、`button` `padx=0`；图标中心 995→997（**右移 2px**，与 R3133「半步」同量）；`stage_area` 右缘 972→978，图标↔聊天框间距 **8→4px（减半）**；面板打开时 rail 仍为内容区最右竖条。

## 本轮改动（相对 master）

| 文件 | 改动 |
| --- | --- |
| `ui/desktop_files_panel.py` | `_pack_button` 的 `padx` 由 `(xs, xs//2)` 改为 `SPACING['none']`（左右收 0）；删除仅服务旧值的 `RAIL_BUTTON_PAD_RIGHT` 常量，注释更新为 R3150 口径。净 −1 行。 |

## 验证

- `run_selftests.py -k files_panel compact_layout`：**44 条 0 红**（GUI 令牌排队后实跑）。
- `smoke_test.py`：**9/9**。
- 几何探针（临时 `tests/test_rail_geom_probe.py`，已删）：改动前后 winfo 实测如上，面板开／合两态均正常。

## 备注

- `docs/stages/S01_剧本准备.md` DES-S01-90 中「入口钮 padding 由 sm 收为 xs」为历史沿革叙述；R3133（xs→xs//2）同口径未改文档，本轮沿用先例，padding 现为 0，如需文档同步可在下一文档轮补一句。
- 提交：本轮收尾提交（证据 `tasks_round/evidence/R3150.json`）。
