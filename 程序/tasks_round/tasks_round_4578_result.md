# R4578 轮次结果（PB-B3：解耦 SG-B 对手动 S05 资产管理的硬拦截并回归数据依赖）
<!-- round-evidence: {"commit_base": "c7a23dd40", "credential_hits": 0, "evidence_sha256": "19f20873d547aad3", "exit": 0, "failed": 0, "passed": 242, "round": 4578, "tests": "run_selftests.py -k stage_parallel stage_flow stage_gate_e2e_probe animatic_scope animatic_service assets_scope req_s04_anchors req_s05_anchors copy_rules desktop_shared_input"} -->

- **本轮属于 §3 哪种类型**：3.1 功能轮（将 `stage_flow.DEPENDS['assets']` 回归真实数据依赖 `('storyboard',)`，把 `SG-B` 改为「未开始不拦＋提醒型 `advisory=True`」，解除对手动 `05 资产管理` 与发送链的硬拦截，同时守住线上 API 模型校验、三虎全自动 `PRODUCTION` 门禁与 1000 行模块上限，翻绿 `REQ-S05-53`／`DES-S05-53`）。
- **测试跑了吗、三个基线过了吗**：已运行——13 组定向与核心架构套件 223/223 通过（34.15s）；`test_desktop_shared_input` 32/32 通过（5.78s）；隐藏桌面 `test_shared_input_ui`＋`test_asset_batch_window` 88/88 通过（33.90s）；默认冒烟 `smoke_test.py` 9/9 通过；完整架构门禁 `smoke_test.py --architecture` **711/711** 通过；完整安全全量回归留在紧随其后的任务书收尾轮统一跑完并归档。
- **欠账少了吗**：`REQ-S05-53`／`DES-S05-53` 完整闭环并翻绿为 ✅；3 个高密度文件全部严守 1000 行上限（`stage_parallel.py` 997/1000、`stage_execution_service.py` 980/1000、`desktop_shared_send.py` 994/1000），零新增欠账。

## 改动清单

- `程序/orchestrator/stage_flow.py`（516 行）：
  - `DEPENDS['assets']` 由 `('animatic',)` 改为 `('storyboard',)`（S05 实际消费 S03 已采用分镜，与 `REQ-S07-03` 同一原则）；同步 `blockers` 文档注释。
- `程序/orchestrator/stage_parallel.py`（997/1000 行，精简旧注释保证不越线）：
  - `GATES` 保持 7 门禁连续链路不变，在 `SG-B` 行增加 `'advisory': True`，`_result()` 透传 `'advisory'` 字段。
  - `animatic_ready(project)` 补齐「未开始不拦」语义：仅当阶段机处于 `'running'/'success'/'failed'/'retrying'` 或 `04分镜预演/animatic_manifest.json` 存在时调用 `domain.animatic_service.evidence(project)`；未开始返回 `ok=True, started=False, verdict='upstream-blank'`（保障显式 `skipped` 在 `PRODUCTION` 口径可豁免）。
  - `blocked_stages(project, stage)` 对 `result.get('advisory')` 返回 `()`，不再阻塞「手动制作资产」确认窗；`production_ready(project, 'assets')` 在未开始或未确认时仍返回 `ok=False` 守住全自动门禁。
- `程序/stage_execution_service.py`（980/1000 行）：
  - `require_formal_asset_generation(project, *, online_model) -> str`：仍强制校验 `online_model`（非线上 API 模型照旧抛 `ValueError`，守住 `REQ-S04-26`／`REQ-S05-22`）；未锁预演时不再抛错，改为返回非阻塞状态栏提醒 `'提示：尚未锁定分镜预演，将先按已采用分镜制作资产'`，已锁时返回 `''`。
- `程序/ui/asset_batch.py`（406 行）：
  - `_AssetBatchWindow.start` 接收 `advisory = require_formal_asset_generation(...)`，非空字符串写入 `self.status` 与 `self.app.status`（零弹窗、不拦截启动）。
- `程序/desktop_shared_send.py`（994/1000 行，原地紧缩旧注释实现零净增）：
  - `upstream_send_error(project, stage, status=None)` 遇到 `advisory` 门禁（`assets`）时先校验 S03 已采用分镜（`animatic_input_ready`），未就绪提示 `'请先在 03 初步分镜完成并采用分镜'`；就绪但 `SG-B` 未通过时仅写入状态栏提醒并放行。
- 阶段规格文档：
  - `程序/docs/stages/S05_资产管理.md`：`REQ-S05-53`／`DES-S05-53` 翻绿为 ✅，同步更新 `REQ-S05-02`／`DES-S05-02` 及 `测试锚定`。
  - `程序/docs/stages/S04_分镜预演.md`：在 `REQ-S04-01`／`REQ-S04-42` 交叉注明 `REQ-S05-53` 修订口径。

## 契约变更同步的既有测试断言（按 `AGENTS.md` §2.4 逐条说明）

以下改动均由用户 2026-11-27 拍板的方案 B（`REQ-S05-53`）有意变更契约所致，未删除或弱化任何无关断言：

1. `tests/test_animatic_scope.py` L32：`DEPENDS['assets']` 由 `('animatic',)` 改为 `('storyboard',)`（`REQ-S05-53` ①）。
2. `tests/test_assets_scope.py` L27–30：`DEPENDS['assets']` 改为 `('storyboard',)` 并补充断言 `SG-B` 的 `advisory=True`（`REQ-S05-53` ①②）。
3. `tests/test_stage_flow.py` L254–256：空项目 `blockers(proj, 'assets')` 由 `['animatic']` 改为 `[]`（`REQ-S05-53` ②，`SG-B` 不阻断手动入口）。
4. `tests/test_stage_parallel.py` L368：空项目评估中仅 `animatic`（`SG-A`）为 `ok=False, started=True`，`assets`（`SG-B`）改为与其他 5 条门禁一致的 `ok=True, started=False`（`REQ-S05-53` ②）。
5. `tests/test_stage_gate_e2e_probe.py` L28–41：空项目探针中 `SG-B` 从「必须有上游成果」组移入「上游没做就别拦」组，运行期 7 门禁真实证据全通断言完全保留（`REQ-S05-53` ②）。
6. `tests/test_animatic_service.py` L22–31：`require_formal_asset_generation(temporary, online_model=True)` 未锁预演由抛 `ValueError` 改为返回非空提醒文案；`online_model=False` 抛 `ValueError('线上 API')` 断言保持不变（`REQ-S05-53` ③）。
7. `tests/test_req_s04_anchors.py` L336–344：`test_req_s04_42_sg_b_reuses_the_same_completion_verification` 在调用 `animatic_ready(root)` 前先创建占位 `animatic_manifest.json` 标记 S04 已开始，继续验证已开始时与 `completion_evidence` 共用同一 `animatic_service.evidence`（`REQ-S05-53` ②）。
8. `tests/test_shared_input_ui.py` L536–550：`test_gated_stage_upstream_ready_passes`／`test_gated_stage_blocked_reports_reason` 改用硬门禁阶段 `'continuity'`（`SG-01`）继续覆盖通用硬门禁路径，同时新增 `test_req_s05_53_assets_send_requires_storyboard_and_warns_without_sg_b` 专门覆盖 `'assets'` 提醒型路径（`REQ-S05-53` ④）。

## 先红后绿证据

改动产品代码前先新增 3 条 `REQ-S05-53` 锚定测试并运行，实测全部失败：

```text
FAIL: test_req_s05_53_sg_b_advisory_allows_manual_assets_and_keeps_guards (tests.test_req_s05_anchors.ReqS05AnchorTests)
AssertionError: Tuples differ: ('animatic',) != ('storyboard',)

FAIL: test_req_s05_53_assets_send_requires_storyboard_and_warns_without_sg_b (tests.test_shared_input_ui.UpstreamGateTests)
AssertionError: '03 初步分镜' not found in '分镜预演 还没做完：分镜预演未就绪、源文件已变化，或节奏／时长／对白同步尚未确认。先完成分镜预演并确认三项检查'

FAIL: test_req_s05_53_start_writes_sg_b_advisory_to_status_bar (tests.test_asset_batch_window.AssetBatchFinishStaysOnPageTests)
AssertionError: set('提示：尚未锁定分镜预演，将先按已采用分镜制作资产') call not found
```

改动后全部通过：
- 13 组定向与核心架构测试（含 3 条新增用例所在非 GUI 套件）：223/223 通过（34.15s）
- `tests.test_desktop_shared_input`：32/32 通过（5.78s）
- 隐藏桌面 `tests.test_shared_input_ui`＋`tests.test_asset_batch_window`：88/88 通过（33.90s）
- `smoke_test.py`：9/9 通过（含隐藏桌面探针）
- `smoke_test.py --architecture`：**711/711** 通过

## 提交状态

- 分支：`codex/pb-s04-s05-decouple`
- 提交方式：经 `scripts/dev.py commit` 提交（含证据文件 `tasks_round/evidence/R4578.json`）。
