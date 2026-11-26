# R4572 轮次结果（PB-B1-L0：清理 S03 L0 分镜契约历史资产前置文案）
<!-- round-evidence: {"commit_base": "2beced341", "credential_hits": 0, "evidence_sha256": "c77203073a2583e2", "exit": 0, "failed": 0, "passed": 60, "round": 4572, "tests": "run_selftests.py -k storyboard_scope shot_field_specs golden_outputs copy_rules"} -->

- **本轮属于 §3 哪种类型**：3.4 契约轮（仅改 L0 `contract/storyboard_contract.py`、配套文档/任务书、黄金基线与定向测试，不动 L1 及以上源码）。
- **测试跑了吗、三个基线过了吗**：已运行——默认冒烟 9/9 通过（含隐藏桌面探针）、`--affected storyboard_contract` 0 失败、完整架构门禁 711/711 通过（0 失败）；全量安全回归留待四卡收口统一执行（当前分支在功能分支，合入 master 前按 §5 补齐）。
- **欠账少了吗**：消除 L0 分镜契约中旧 3 步流程遗留的资产前置假设（`REQ-S03-56` L0 部分落地），未新增欠账。

## 改动清单

- `程序/contract/storyboard_contract.py`：
  - 第 38 行：`沿用已完成剧本、已确认角色固定外观和资产编号；仅补齐当前剧本缺少的场景、临时角色及关键道具。` → `以已确认的结构剧本（角色／场景／道具档案与分场）为唯一依据；本阶段先制作分镜初稿，不要求资产库已出图或已锁锚点；角色／场景／关键道具可写名称或可选延续已有编号，正式资产正典与编号对齐归第 05／07 阶段。`
  - 第 65 行：`它记录来源剧本、角色／场景／道具编号…` → `它记录来源剧本、出场角色／场景／关键道具…`。
  - 全部 `episode_contract.SHOT_FIELD_SPECS` 派生字段与 `prompt_lines()` 保持不变。
- `程序/tests/fixtures/golden/storyboard_contract_rules.txt`：按 `tests/test_golden_outputs.py` 规程以 `GOLDEN_UPDATE=1` 刷新（原因：有意更新上述两处旧 3 步流程措辞，落实用户 2026-11-27 拍板的 `REQ-S03-56`）。
- `程序/tests/test_storyboard_scope.py`：新增 `test_req_s03_56_l0_rules_do_not_require_prior_assets_or_anchors` 锚定 `REQ-S03-56`。
- 配套需求／设计文档先行落盘：`程序/docs/stages/S03_初步分镜.md`（`REQ/DES-S03-56`）、`程序/docs/stages/S04_分镜预演.md`（`REQ-S04-113` / `DES-S04-36`）、`程序/docs/stages/S05_资产管理.md`（`REQ/DES-S05-53`）、`程序/docs/records/对话需求追溯.md`、`程序/tasks_round/分镜预演与资产管理解耦及S03提示词清理任务书.md`。

## 先红后绿证据

改动前运行 `tests.test_storyboard_scope.StoryboardScopeTests.test_req_s03_56_l0_rules_do_not_require_prior_assets_or_anchors` 实测失败：

```text
FAIL: test_req_s03_56_l0_rules_do_not_require_prior_assets_or_anchors
AssertionError: '已确认角色固定外观和资产编号' unexpectedly found in '【制作 JSON 必须通过助手校验】沿用已完成剧本、已确认角色固定外观和资产编号；...'
```

改动并刷新黄金基线后复跑全部通过：
- 定向套件（`test_storyboard_scope` + `test_shot_field_specs` + `test_golden_outputs` + `test_copy_rules` + `test_requirement_traceability`）：全部通过
- `smoke_test.py`：9/9 通过（含隐藏桌面探针）
- `smoke_test.py --affected storyboard_contract`：4 秒，0 失败
- `smoke_test.py --architecture`：711/711 通过

## 提交状态

- 分支：`codex/pb-s04-s05-decouple`（从 `master` `2beced341` 切出）
- 提交方式：经 `scripts/dev.py commit` 提交（含证据文件 `tasks_round/evidence/R4572.json`）。
