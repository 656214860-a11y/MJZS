# R4259 结果：FIX-COMPOSER-DRAFT-KEEP（模型浮层切换后底部输入框草稿保留）
<!-- round-evidence: {"commit_base": "79fa309b", "credential_hits": 0, "evidence_sha256": "da6e2c9aec1c6975", "exit": 0, "failed": 0, "passed": 9, "round": 4259, "tests": "run_selftests.py -k model_picker_draft_keep stage_model_picker ui_popup"} -->

> 本轮落码（产品代码、测试、REQ-S01-117 文档与结构登记）最后一次写入 2026-11-24 07:19。R4259 是本车道 07:02 领到的号（归属登记在 round-claims.json，此前未用于任何提交）。

## 开头三问

- （一）本轮属于哪种类型：修复轮（§3.2）。用户报告「底部输入框在模型下拉切换模型后，之前输入的内容消失」；登记为 REQ-S01-117，只改 `ui/stage_model_picker.py`、`ui/ui_popup.py` 两个根因模块。
- （二）测试跑了吗、三个基线：跑了（由接管会话执行）。默认冒烟 `smoke_test.py` 通过 9 项、失败 0 项；定向 `run_selftests.py -k model_picker_draft_keep stage_model_picker ui_popup` 9 条用例 0 红（只有 1 个匹配测试文件）；架构门禁 `smoke_test.py --architecture` 首跑 700 条，1 失败 1 错误，均为登记类，最小修复后复跑相关 32 条全绿（见下）。全量回归：未跑；凭据以 `full-safe-receipts.json` 为准，本轮未新增。原执行者的「先红后绿」改前失败输出：未留存，本会话未复现改前红灯。
- （三）欠账少了吗：少了。REQ-S01-117 🟡 转「已实现、自动验收通过」；合并后由合并轮推进状态页。

## 改动范围（原执行者落码，接管会话未改产品逻辑）

- `程序/ui/stage_model_picker.py`：`_choose_model`／`choose_reasoning` 在保存配置并触发刷新回调后，若共享输入框被清空则还原原文、插入光标、有效范围内的选区并回焦点；输入框不存在或已销毁时静默跳过；模型浮层改开 `Flyout(win, noactivate=True)`。
- `程序/ui/ui_popup.py`：`Flyout` 新增 `noactivate` 选项，Windows 下给顶层窗口追加 `WS_EX_NOACTIVATE` 并不抢焦点；默认调用方行为不变。
- `程序/docs/stages/S01_剧本准备.md`：登记 REQ-S01-117 与测试锚点。
- `程序/governance/structure.json`：登记 `程序/tests/test_model_picker_draft_keep.py`。
- `程序/tests/test_model_picker_draft_keep.py`（新增）：草稿还原、输入框缺失静默跳过、浮层 noactivate、真实点击路径回归共 9 条。

## 接管会话做的最小修复（登记类，均为让门禁与已落码内容对齐）

1. `程序/governance/structure-baseline.json`：`structure.json` 变更后 `test_structure.test_real_repository_has_no_new_structure_violations` 报 `Directory policy changed without explicit baseline review`。按 R4099 的既有做法只更新三个来源字段（`source_commit`／`inventory_sha256`／`policy_sha256`）；已登记的 1 条违规行原样保留，没有新增违规。
2. `程序/维护记录/skip台账.json`：`test_skip_hygiene` 报 `323 != 331`。新测试文件有 8 个 skip 位点未登记，按源码扫描结果补 8 行（类别与原因常量取自 `tests/skip_reasons.py`，可读原因沿用同常量既有措辞）；没有删改既有行，没有新增 skip。

## 验证记录（接管会话，日志在仓库根 `.agent-tmp/takeover-fix-composer-draft-keep-*.log`）

| 命令 | 结果 |
| --- | --- |
| `python -B smoke_test.py` | 通过 9 项，失败 0 项 |
| `python -B run_selftests.py -k model_picker_draft_keep stage_model_picker ui_popup` | 9 条用例，0 个文件有红，ALL TESTS PASSED |
| `python -B smoke_test.py --architecture`（修复前） | 700 条，失败 1（跳过台账）、错误 1（结构基线） |
| `python -B run_selftests.py -k skip_hygiene test_structure`（修复后） | 32 条用例，0 个文件有红，ALL TESTS PASSED |

架构门禁当轮总数：700；失败集合：修复前 {test_skip_hygiene 双向相等, test_structure 真实仓库无新增违规}，修复后为空（相关 32 条复跑全绿，其余 668 条首跑已通过且本轮修复未触及其被测对象）；合入时出口 CI 会再跑一遍全部架构门禁。

## 提交与合入

- 是否已提交：由 `dev.py commit` 提交到 `codex/fix-composer-draft-keep`，提交号见提交记录；合入 master 走 `dev.py merge` 合并轮。
- 欠账：全量回归本轮未跑（合并后按 §5 口径处理）。
