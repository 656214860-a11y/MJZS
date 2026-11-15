# R2685 结果：定稿快照历史＋右键「历史快照／对比」（REQ-S01-87）
<!-- round-evidence: {"commit_base": "b95dbb8c", "credential_hits": 0, "evidence_sha256": "611c00487506b8c8", "exit": 0, "failed": 0, "passed": 26, "round": 2685, "tests": "run_selftests.py -k test_preparation_confirmation test_writing_edited_restart"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1，文档先行）。任务源：盘点文档优化项 4＋规则 2——
   定稿快照持久化与差异对比入口。分支 `codex/wip-R2685`（R2679–R2684 为
   中央计数器空号/他车道）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **9/9** 通过；`smoke_test.py --affected writing_api
     desktop_writing_page` 自检门禁 **558 条 / 0 个文件有红**。
   - 先红后绿：`test_confirmation_writes_snapshot_and_keeps_history_across_brief_reset`
     改动前 `KeyError: 'snapshots'` 红，实现后绿；15/15。
   - 失败闭环（规则 32）：首轮门禁 4 条红——快照基线误把重写稿（revision）
     前缀算入。显式重写启动时 `_preparation_state` 会把前缀记录重绑到用户
     编辑后正文的新 sha（`document['sha256'] = digest`），取消重写后恢复
     写入被当成新确认补记快照，破坏
     `test_cancel_edited_restart_restores_original_record_before_or_after_generation`
     的逐字恢复契约。最小修复：`_snapshot_basis` 只统计采用稿（顶层
     `documents`）——重写稿确认经提升进采用稿时才打快照，重写启动/取消
     不产生快照。复跑该文件 4/4 子用例绿，门禁复跑全绿。
   - 相关消费者回归：`writing_restart*`／`writing_unconfirm`／
     `preparation_confirmation`／`preparation_monitor`／`idea_send_gate`
     等 144 条全绿（首轮）；门禁覆盖 558 条。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账。盘点队列剩：优化 3（段落级部分采用）、规则 1（并行编辑）。

## 实现

### 定稿快照（REQ-S01-87）

`writing_api.py`：

- `_snapshot_basis(state)`：采用稿（顶层 `documents`）中已确认记录的
  `{(阶段, sha256)}` 集合，作为「新定稿」判据。**不含 revision**——重写
  启动的前缀重绑、重写中途确认都不是定稿事件；提升进采用稿才算。
- `_record_confirmation_snapshots(target, state, publish)`：挂在统一写口
  `_save_preparation_state` 上，覆盖右键「设为定稿」、聊天确认推进、
  重写提升、取消后重确认全部路径。本次写入新增的已确认 `(stage, sha256)`
  把正文快照到 `01剧本准备/确认快照/<阶段>_<时间戳>_<sha前8>.md`，登记
  `{stage, path, sha256, snapshot, confirmed_at}` 入台账 `snapshots[]`；
  同 `(stage, sha256)` 去重。
- `_preparation_state` 简报变化重置分支：保留 `snapshots` 历史，只重置
  确认台账（`documents`）。

### 右键「历史快照／对比」（REQ-S01-87）

`desktop_writing_page.py`：

- 准备稿右键菜单新增「历史快照／对比」。
- `preparation_snapshots(stage)`：台账快照按阶段过滤、新→旧排序。
- `show_preparation_snapshots(stage)`：`BaseDialog` 列表弹窗，两项操作——
  「查看全文」（快照正文只读展示）与「与当前文件对比」（当前选中文件与
  快照的 `difflib.unified_diff`，`fromfile` 定稿快照时间 / `tofile` 当前
  文件名；无差异时明示）。快照文件缺失时按空正文对比/展示。

## 先红后绿证据

```
test_confirmation_writes_snapshot_and_keeps_history_across_brief_reset
  KeyError: 'snapshots'        ← 实现前
  ok                           ← 实现后（15/15 全绿）
```

## 未覆盖

- 快照文件无 UI 删除入口（随项目目录生命周期走）；快照正文不可编辑。
- 对比视图是 unified diff 文本，非并排图形 diff（零依赖口径）。
