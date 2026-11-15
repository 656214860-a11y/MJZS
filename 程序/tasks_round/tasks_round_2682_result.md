# R2682 结果：费用统计模块——用量快照/跨天归档、右上角用量指示器、详情与今日明细弹窗
<!-- round-evidence: {"commit_base": "54561e3d", "credential_hits": 0, "evidence_sha256": "001fe9390f997904", "exit": 0, "failed": 0, "passed": 33, "round": 2682, "tests": "run_selftests.py -k pet_bus"} -->

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   功能轮（§3.1）。任务源：`tasks_round/费用统计模块任务书.md`（用户指定「完整执行任务书要求的费用统计模块」）。
   轮次号说明：本会话先领 R2637；rebase 到 master（落后 25 个提交）后按规则 27
   重新领取改领 R2653；提交被中央计数器拒绝（其他车道已推进）后改领 R2664、
   再改领 R2666 并落下 commit `562154f3`——事后复查发现该提交只含部分文件
   （暂存清单不完整），遂 `reset --soft` 撤回；此后中央计数器被并行车道
   连续推进，本车道多次领号均未赶上提交窗口（含 R2666 曾落下 commit
   `562154f3`，因暂存不全已 `reset --soft` 撤回），最终改领本轮号作为
   唯一完整交付，中间号均成空号（无合入提交、无结果文件），与
   R2634–R2638、R2640–R2642、R2647–R2652 等既有空号同因。分支
   `codex/wip-R2682`（由 `round_claim.py next` 的脏树自动停放创建），
   commit base 为 `54561e3d`（Cascade 快照）。

2. **测试跑了吗、三个基线过了吗？**
   - 默认冒烟 **8/8** 通过（第 10 轮）。
   - `smoke_test.py --architecture`：**466/466 全绿**（含模块行数棘轮、分层登记、
     事件契约、覆盖率基线口径、文档预算等全部架构门禁）。
   - 定向：`run_selftests.py -k usage_snapshot usage_indicator` 17/17；
     `-k preparation writing_unconfirm writing_restart writing_edited_restart
     writing_api writing_quality` 167/167（writing_api 拆分回归）；
     `tests.test_pet_bus` 18/18（契约 fixture 同步后复跑）。
   - `smoke_test.py --affected usage ledger pet_bus desktop`：133 个测试文件
     共 2872 条用例；首跑 2 个文件有红——`test_pet_bus`（契约 fixture 缺
     `project` 键，已修，复跑 18/18 绿）与 `test_skills`（gitlink 技能目录在
     工作树为空，环境性 71≠73，补齐后复跑绿）；其余全绿。
   - 覆盖率基线已按工具重测刷新：生产运行时模块 372 个、61 个有行覆盖、
     9 组定向用例全绿（`维护记录/覆盖率基线.json`，runbook §11 数字已同步）。
   - 全量 `--all --safe`：未跑（功能分支不累计欠账；合入 master 前的全量由主树安排）。

3. **`project_status.md` 的欠账少了吗？**
   未新增欠账；反而消除一笔历史欠账：本分支（R2630＋Cascade 快照）把
   `writing_api.py` 推到 1388 行、超出行数棘轮上限 1372，本轮按 R2400 先例把
   剧本准备台账原语拆入新模块 `writing_preparation_ledger.py`（writing_api 回落到
   1334 行），棘轮恢复全绿。`usage_updated` 为新增事件契约，fixture 已同步。

## 任务书实现范围

- **`usage_snapshot.py`（L1）**：`UsageSnapshot` 按项目缓存单例；`record_call()`
  记今日明细（`deque(maxlen=10000)`，超出弃最旧）＋项目累计
  （`usage_summary.json`，`agent.core.save(durable=False)` 原子替换）＋
  `usage_history.record_today()` 跨天日档（60s 节流）；跨天自动
  `archive_yesterday()` 归档昨日快照；北京时间（UTC+8）日界，与 pet_llm 同口径
  但不反向依赖（避免 pet_llm→request_ledger→本模块成环）。金额全程 `Decimal`，
  序列化为字符串；无价格表时 `money_spent` 不虚构。`_notify()` 经
  `pet_bus.emit_safe` 发 `usage_updated`，总线缺失/契约异常只记日志。
  `bind_bus()` 由界面在换项目重建总线后重新绑定。
- **`usage_history.py`（L1）**：`usage_history/YYYY-MM.json` 日档读写；
  `record_today` 同日覆盖更新、`archive_yesterday` 写昨日归档；
  读侧容忍缺失/损坏。
- **`request_ledger.py`（L1）**：`settle_model` 结算成功后调
  `_record_model_usage()` → `get_snapshot(project).record_call(...)`；
  整个挂接 `try/except → app_logging.swallowed()`，记账失败绝不弄断结算与生产调用。
- **`pet_bus.py`（L0）**：`CONTRACT` 新增 `'usage_updated': ('project',)`；
  `request_id`/`seq` 随 payload 透传。
- **`ui_usage_indicator.py`（L4）**：`UsageIndicator`（tk.Frame）三段标签
  Token/¥/余额，`place_in_title_row()` 用 `PATCH_X`/`avatar_size`/`SPACING`/
  `PET_LAYOUT` token 把右沿钉在头像左侧；金额/余额无数据整项隐藏不显 0；
  Token 三档阈值色（≥50 万 warning、≥150 万 danger，取 ui_tokens 语义色）；
  点击开详情。`sync_bus()` 每拍对齐总线并订阅 `usage_updated` → refresh。
- **`ui_usage_detail.py`（L4）**：`UsageDetailDialog`（`BaseDialog` 标准 chrome）
  展示今日/累计/余额与最近明细；`TodayDetailsDialog` 今日明细＋CSV 导出
  （UTF-8-SIG，`csv` 模块 `lineterminator='\n'`）。
- **`desktop.py`（L4）**：标题行挂载指示器；`_tick_stage_model_sync_result`
  每拍 `sync_bus()`（换项目总线重建后自动重订阅），异常吞掉只记日志。
- **`writing_preparation_ledger.py`（L3，新）**：从 `writing_api.py` 原样迁入
  `_save_preparation_state`/`_revoke_natural_script_adoption`/`_confirmed_basis`/
  `_save_preparation_state_guarded`/`_promote_revision` 五个自包含台账原语；
  `writing_api` 同名 import 转发，`writing_unconfirm` 等既有
  `from writing_api import _…` 调用点零改动（已验证对象同一性）。

## 契约变更（§2.4 说明）

- `pet_bus.CONTRACT` 新增事件种类 `usage_updated`（必填 `project`）。
  `tests/test_pet_bus.py::test_every_kind_is_constructible` 的公共 payload
  fixture 同步补 `"project": "demo"`——只加键不改断言，其余 17 条原样通过。

## 环境性修复（不入提交）

- 本工作树缺三份 git-ignored／gitlink 运行内容，补齐后相关架构与技能用例转绿
  （均从主工作区 `D:\漫剧制作助手` 只读复制，不进暂存区）：
  - `维护记录/基准历史.json`（`test_performance_history…` 需要）；
  - `skills/00全流程SKILL/AIGC创作全流程/`（gitlink，`test_script_stages…` 需要）；
  - `skills/01 剧本准备SKILL/剧本锻造/`＋`编剧技能集/`（gitlink，`test_skills`
    技能计数 71→73 需要）。
- `reference/HoLLMwood` gitlink 在工作树同样为空；本轮测试未触及，未复制。

## 未做事项／边界

- 价格表（`cost_profile.json`）与余额来源属外部配置：缺价格表时金额项隐藏、
  余额恒空隐藏，符合任务书「不编造金额」要求；接入真实价格表/余额查询不在本轮。
- 全量 `--all --safe` 未跑（分支欠账规则不要求；结果文件如实标注）。
- Tk 弹窗 `after_idle` 警告：测试 teardown 改用 `dialog.close()`（走
  `BaseDialog.close` 的 `after_cancel`），不再直调 `destroy()`。
