# R3065 结果 — 死代码清理轮（结构治理·按报告执行）第 3 批
<!-- round-evidence: {"commit_base": "840671b5", "credential_hits": 0, "evidence_sha256": "b2e2e4237de64407", "exit": 0, "failed": 0, "passed": 27, "round": 3065, "tests": "run_selftests.py -k coverage_baseline layers"} -->

## 三问

1. **轮次类型**：§3.3 结构治理轮·子场景「按报告执行」。本批删 2 个模块（≤3 上限）。
2. **测试**：`smoke_test.py` 8/8 通过；`test_coverage_baseline`＋`test_layers` 复跑 11/11 通过。
3. **欠账**：同前轮，状态页仅 master 提交不变。

## 本批变更（任务书 A2·分镜目录兼容簇）

| 动作 | 对象 | 证据 |
|---|---|---|
| 删除 | `orchestrator/storyboard_catalog.py`（17 行）＋`storyboard_catalog.py`（10 行门面） | 任务书 A2：实体 prod_in=1 仅门面；门面 ORPHAN 零消费者；真实现在 `storyboard_catalog_service`／`stage_execution_service`／`storyboard_selection`（均 LIVE） |
| 同步 | `tests/architecture/_layers.py` | L3 移除 `storyboard_catalog` 登记名（`storyboard_catalog_service` 保留） |
| 同步 | `维护记录/覆盖率基线.json` | 文本级移除两模块行，modules_total 545→543（covered=0，不计 covered） |
| 同步 | `runbook.md` §11 | 基线数字 545→543、474→472 |

## 备注

- 同名陷阱已核对：`storyboard_catalog` 作为**函数名**经 `stage_execution_service` 被 `desktop_page_nav.py:344`、`pet_ui_voice.py:423` 等 5 处生产调用——那是 `stage_previs_gateways.storyboard_catalog()` 函数，与本次删除的模块无关，未受影响。
- A1/A2 共 6 个文件清理完毕；余 15 个 T10 死门面分五批（每批 3 个）。
