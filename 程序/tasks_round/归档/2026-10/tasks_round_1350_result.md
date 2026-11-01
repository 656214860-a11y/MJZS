# R1350：O25 首帧批量任务统一目标集、重试与替换解释

类型：功能轮（§3.1）。承接 R1267 清单 O25（O01—O24 已完成）。中央轮次 1350。

## 三个必答
- 本轮类型：功能轮（默认）。
- 测试：定向 `-k batch_plan keyframe` 93/93；`-k keyframe previs stage_execution` 全绿；`-k batch_frames todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 27/27（含覆盖率棘轮）；`tests.architecture.test_skip_hygiene` 3/3；架构门禁 312/312；默认冒烟 8/8，全 0 红。
- 欠账：O25 关闭，清单剩 O26—O48；1350 − 1346 = 4 < 5，且未命中 §5 升级条件（非启动路径／Tk 控件生命周期销毁重建／`storage_maintenance` 删除语义／层级登记表；`keyframe_comfy` 是已登记 L4、`keyframe_batch` 是已登记 L2，未新增顶层模块），本轮不跑全量。

## 目标（R1267 清单 O25）
- 依据：`keyframe_comfy.py`、`keyframe_lifecycle_service.py` 已有候选、删除、替换和恢复边界。
- 建议：提交前显示当前集、勾选镜头、跳过原因、实际模型与参考图；区分只补缺失、重试失败、显式替换。删除标记不得被后台补帧复活。
- 验收：切集、删除后迟到回调、已有空文件、用户替换首帧、只选失败镜头分别验证；成功镜头不重付费。依赖 O05/O06（均已完成）。

## 实现（`keyframe_batch.py`，L2 服务层）
- 新增三意图常量 `MODE_MISSING`／`MODE_RETRY`／`MODE_REPLACE`（`BATCH_MODES`／`MODE_LABELS`：只补缺失／重试失败／显式替换）与六态 `STATE_DONE`／`MISSING`／`EMPTY`／`DELETED`／`UNSET`／`OUTSIDE`（`STATE_NOTES` 逐态给原因，`ATTEMPT_NOTES` 给提交中／结果待核实）。
- `frame_state(base, shot)`：与门禁同口径算单镜六态；deleted／unset／outside／empty 优先（删除永不复活）。
- `record_attempts(source)`：读 `<source.parent>/首帧任务/seedream_*.json` 的 shot_id→state；`_attempt_state` 允许注入 dict 或可调用对象（便于测试）。
- `batch_plan(source, *, shot_ids=None, mode=MODE_MISSING, model='', attempts=None, references=None, prompt=None)` → `{source, episode, mode, mode_label, model, targets[], skipped[], counts}`：
  - 只补缺失（missing）：只取「从没提交过」的缺帧镜头；已提交过的（结果待核实）跳过不重复提交；
  - 重试失败（retry）：只取有生成记录仍缺帧的；
  - 显式替换（replace）：只对点名（`shot_ids`）且有可用首帧的镜头，标 `will_replace`；
  - deleted 任何模式都不复活；empty／unset／outside 一律跳过并给原因；
  - 单 `source`＝单集，不跨集（切集＝换 source）。
- `_target` 带 `shot_id/title/intent/intent_label/state/note/references/reference_count/prompt/will_replace`；`plan_summary` 一行说清意图／本集／模型／目标镜头／跳过原因。

## 实现（`keyframe_comfy.py`，L4）
- 弹窗新增只读 `plan_note` 标签与 `mode_var` 下拉（`批次意图`：`['只补缺失','重试失败']`，REPLACE 不在 UI 暴露）；`refresh()` 更新预览（异常容错）。
- `current_mode`／`current_plan`／`log_plan`；`check_values()` 用 `batch_plan` 收窄 `shots`（无目标即 `ValueError` 带跳过原因）；`options()`／start 三条路径（Agent／Seedream／本地）都按目标集提交并记录计划；`auto_batch`（无人值守补帧）固定 `MODE_MISSING` 并记跳过原因。
- `pending_shots` 改用 `frame_state(base, shot) == STATE_MISSING`（行为不变：空文件此前被当作「已有」而不补，现在仍不算 pending）。

## 验证
- `tests/test_keyframe_batch_plan.py`（新）15 条：missing 只取从没提交过的、提交过的跳过不重付费、deleted/empty/unset/outside 跳过并给原因、retry 只取有记录仍缺帧、replace 只对点名且已有可用首帧、切集（换 source）目标集不跨集、`plan_summary` 文案、`pending_shots` 口径、Tk 弹窗显示批次意图与目标集预览（`DialogPlanTests`，复用 `test_keyframe_comfy.StubApp/make_project`）。
- 新增用例含 Tk 平台限制 1 条，同步 `维护记录/skip台账.json`（+1，手写文本插入，不整份重写以免重排全表）。
- 定向 93/93＋`keyframe previs stage_execution` 全绿＋`todo_comment_snapshot unification_ratchet coverage_audit_ratchet` 27/27＋`test_skip_hygiene` 3/3；架构 312/312；默认冒烟 8/8，全 0 红。

## 边界
- 重试集合只看 Seedream 任务记录（`首帧任务/seedream_*.json`）；本地 ComfyUI／Agent 路径的既有尝试不进入 retry 集合——其失败通常表现为仍缺帧，missing 模式下会被当作首次提交。
- 已提交镜头在 missing 模式跳过，避免为「结果待核实（可能已扣费）」的旧任务重复付费。
- 空文件／未配置／越界／已删除一律不进目标集；已删除的任何模式都不复活（后台补帧不复活用户删除）。
- REPLACE 在服务层实现（点名才生效），当前弹窗下拉只暴露 missing／retry；04 首帧管理的删除／导入仍是替换权威入口。
- 未命中 §5：未改启动路径、Tk 控件生命周期销毁重建、删除语义与层级登记表（未新增顶层模块）。
- 未实发模型请求（未调 ComfyUI／Seedream）、未重启、未真实手动点击界面。
- 环境相关（与本改动无关）：主树本地忽略配置 `程序/配置/宠物/配置.json` 使 `test_workflow` 桌面模型用例在主树红，干净工作树绿；不在本轮修复。

[TASK_COMPLETE] O25 首帧批量任务统一目标集、重试与替换解释：`keyframe_batch` 新增 `batch_plan`（三意图 missing／retry／replace ＋ 六态 ＋ 跳过原因 ＋ 实际模型与参考图），missing 只取从没提交过的缺帧镜头、已提交跳过不重付费、deleted 任何模式不复活；`keyframe_comfy` 弹窗新增「批次意图」下拉与目标集预览、三条提交路径与 `auto_batch` 都按统一目标集并记录计划；新增 15 条用例，定向 93/93、关联全绿、架构 312/312、默认冒烟 8/8，0 红；1350−1346=4<5 且未命中 §5，本轮不跑全量。
