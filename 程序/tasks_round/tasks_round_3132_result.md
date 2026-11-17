# R3132 功能轮结果：文件卡片与 HITL·轮 6/8——会话分支/节点树 + checkpoint 树
<!-- round-evidence: {"commit_base": "8a0fdf72", "credential_hits": 0, "evidence_sha256": "02c32f5413326497", "exit": 0, "failed": 0, "passed": 7, "round": 3132, "tests": "run_selftests.py -k checkpoint_tree branch_tree"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.1 功能轮（任务书《文件卡片与 HITL 交互任务书》轮 6/8）。
2. **测试跑了吗、三个基线过了吗？** 跑了：`test_checkpoint_tree.py`（6/6）、`test_branch_tree_ui.py`（1/1）、button/token/dialog/input/icons 边界（43/43）、默认冒烟、架构门禁（见下）。未跑全量 `--all --safe`（非 master 提交点）。
3. **欠账少了吗？** 无新增欠账；append-only checkpoint 树与分支节点树 UI 落地，与轮 2「继续生成」共用同一断点模型。

## 改动

- 新增 `domain/checkpoint_tree.py`（L2，纯内存 + JSON 快照，无 Tk/网络/读写盘）：
  - `CheckpointStore.create/get/children/history/fork/set_current/current/prune/snapshot/restore`；
  - `(thread_id, checkpoint_id, parent_id)` append-only 树；`fork` 从旧节点追加新分支、**原链不覆盖**；
  - `state` 小 JSON + `artifact_refs` 只存引用（存引用不存内容）；
  - `prune(thread_id, keep=)`：保留最近 `keep` 个，被剪父节点改挂根避免悬空；
  - **偏离开销**：随附解释器缺少 `_sqlite3` 扩展，故不用 sqlite3，改以 JSON 快照（由 L3 经既有 JSON 网关落盘），树语义一致。
- 新增 `ui/ui_branch_tree.py`（L4）：`DataTable` 按 `parent_id` 链展平为缩进树 + 当前节点选中 + 「切换到此节点／延续提问／独立提问」三按钮（回调注入；不直造裸 `ttk.Treeview`）。
- 新增测试 `tests/test_checkpoint_tree.py`（6 条，无 Tk）与 `tests/test_branch_tree_ui.py`（1 条，真 Tk）。
- 基线同步：覆盖率基线 540→542；skip 台账 +1；`runbook §11` 同步。

## 测试证据

- `python -B tests/test_checkpoint_tree.py` → `Ran 6 tests ... OK`（append-only、parent 链、fork 不覆盖、切换 current、剪枝改挂根）。
- `python -B tests/test_branch_tree_ui.py` → `Ran 1 test ... OK`（树渲染、子节点、选中切换、延续/独立提问回调）。
- `python -B -m unittest tests.architecture.test_button_boundary ... test_ui_icons_boundary` → 43 tests OK。
- `python -B -m unittest tests.architecture.test_data_table_boundary tests.architecture.test_token_boundary` → 24 tests OK（DataTable 替代裸 Treeview）。
- `python -B smoke_test.py` → `通过：9 项`、`失败：0 项`（退出码 0）。
- `python -B smoke_test.py --architecture` → `Ran 483 tests ... OK`（`✅ 架构治理测试：tests/architecture`；覆盖率基线 542、skip 台账 301 口径同步）。

## 契约变更（§2.4）

- 新增 L2 `domain/checkpoint_tree.py` 与 L4 `ui/ui_branch_tree.py`；不改既有模块签名。
- 零第三方依赖不变（无 sqlite3、无 Tk 外的依赖）。

## 范围外 / 已知缺口

- checkpoint 的落盘（L3 经 `publish_json`/`file_cache.read_json`）与「继续生成从 checkpoint 恢复」的接线留待阶段/对话整合轮；本轮提供树与快照 API。
- 长会话增量索引（A6）当前是线性快照；万级节点再引入分页索引。
- 未跑全量 `--all --safe`（非 master 提交点）。

## 提交

- 分支 `codex/wip-R3132`；commit hash 见回填。
