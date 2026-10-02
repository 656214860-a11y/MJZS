# R520 修复轮：剧本整理自然剧本目录遗漏

## 轮次自检

1. 本轮是功能轮还是整理轮？修复轮；仅修复剧本整理页的自然剧本发现与其受影响的 SKILL 审计兼容性。
2. 测试跑了吗？三个基线过了吗？已跑。剧本契约/结构/工作区定向 73/73；受影响门禁 0 个失败文件；默认冒烟 8/8，均通过。
3. `project_status.md` 欠账少了吗？是；本轮已闭合“项目剧本分类目录中文件名不含剧本标记时在剧本整理页遗漏”的缺陷，并同步轮次至 R521 待执行。

## 复现与根因

“剧本整理 → 自然剧本目录”使用 `script_contract.natural_script_paths()`。它此前只按文件名含“剧本 / script / EP 集数”纳入来源，故剧本准备页已归类到 `创意_*/项目剧本/`、但被用户改为普通文件名的 Markdown 被错误过滤。

## 修复

- `script_contract.py`：将受控 `项目剧本` 目录作为自然剧本来源的同等命名证据；仍要求文件非空、正文通过自然剧本校验，并继续排除结构剧本和内部 `script_raw.md`。
- `tests/test_script_structure.py`：新增普通文件名位于 `项目剧本/` 时可发现、可成为结构阶段来源的回归。
- `script_skill_report.py`：阶段目录分类后，排除 `pipeline-*` 编排 SKILL，避免其混入剧本内容产物审计。
- `script_contract.py` / `tests/test_script_contract.py`：合并体检改经 `skill_registry` 查找归属 SKILL，不再硬编码已不存在的 `skills/` 根目录；阶段断言保留对内容 SKILL 的归属校验，不再依赖总数。

## 验证

```text
python -B -m unittest tests.test_script_contract tests.test_script_structure tests.test_script_workspace_service -v
73 tests: OK

python -B smoke_test.py --affected script_contract script_skill_report script_workspace_service desktop
受影响门禁：0 个文件有红

python -B smoke_test.py
默认冒烟：8/8
```

## 范围与风险

- 未改动任何用户项目文件、剧本正文或阶段配置面板。
- `项目剧本` 仍须位于当前项目的剧本准备阶段目录，且正文必须是自然剧本文本；同名新旧目录副本仍按既有优先级和正文指纹去重。
