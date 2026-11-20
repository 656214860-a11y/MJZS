# R3987 结果：专题二资产数据盘点（DOC-T2A）
<!-- round-evidence: {"commit_base": "81577d36", "credential_hits": 0, "evidence_sha256": "a0f11ffd4c82685a", "exit": 0, "failed": 0, "passed": 0, "round": 3987, "tests": "docs-only"} -->

## 开头三问

1. **本轮类型**：只读诊断轮（§3.5）。未修改任何 `.py`／`.pyw`，仅新增 `tasks_round/` 下两份文档。
2. **测试与基线**：文档轮按规则不跑默认冒烟与全量；任务卡要求的架构门禁已跑：`python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v` → 54 项全过（OK，EXIT=0）。默认冒烟基线：未运行（只读诊断轮不跑）。全量基线：未运行（不跑 `--all/--safe`）。
3. **欠账**：本轮无新欠账；既有欠账未触碰，不增减。

## 改动文件

- 新增 `tasks_round/专题二资产数据盘点报告.md`（六块结构＋四种形态总表＋35 条事实＋3 条文档差异＋5 个给主控的问题）
- 新增 `tasks_round/tasks_round_3987_result.md`（本文件）

## 验收命令结果

| 命令 | 结果 |
|---|---|
| `python -B -m unittest tests.architecture.test_layers tests.architecture.test_structure -v` | 通过：Ran 54 tests，OK；test_structure 输出 `ok:true`、0 findings |
| `git status --short` / `git diff --stat`（核对改动范围） | 仅上述两个新文件，无 `.py`／`.pyw` 改动 |

## 主要结论（详见报告）

- 资产文字无版本历史：所有字段写入口均原子覆盖，无备份（`asset_plan.update_fields`、`asset_batch_service.rename_asset`、`agent.core.save`）。
- 图片两条入库路语义不一致：生成路已有图则跳过，导入路替换旧图并备份 `历史版本/`。
- 首帧有正式过期判据：`frame_evidence.source_evidence`（分镜 sha＋提示词 sha＋引用资产 {id,digest,图片 sha256}）不一致 → SG-04 报"待重新导入复核"。
- 视频无持久过期标记：仅采用分镜时一次性预告"N 段视频将失效"，不落盘；版本 `signature` 是提交时指纹，事后无人重算。回退靠 `pin_version`。
- 产物来源账本只有剧本→定稿分镜两个写入方，资产图片不入账；artifact_index 只有首帧登记（stage=keyframe），资产图片未登记。
- `deletion_references` 已实现但未接进删图弹窗（REQ-S05-33 文档承诺与 UI 有差距）。

## 未核实事项

- 「资产合并」功能：全仓检索未见程序内实现，不能断言"设计上不需要"。
- `artifact_lineage` 在 02 册等其余规格册中是否有专章：本报告只核了 04 册目录与 README 索引，其他册未逐页翻。
- 报告 F18 中视频提示词历史备份的行号区间（`stage_execution_service.py` 约 :92-103）为检索定位，未逐行精读该函数。

## 提交

- 提交命令：`python -B scripts\dev.py commit -m "R3987: 专题二资产数据盘点报告" --agent Devin tasks_round/专题二资产数据盘点报告.md tasks_round/tasks_round_3987_result.md`
- commit hash：（提交后补记）
