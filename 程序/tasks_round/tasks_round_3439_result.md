# R3439 结果文件 — L1 任务书轮 I7：异常迁移第一批（request_ledger／comfy_service／unit_of_work）
<!-- round-evidence: {"commit_base": "73ee249a", "credential_hits": 0, "evidence_sha256": "e449ec899a71a55c", "exit": 0, "failed": 0, "passed": 75, "round": 3439, "tests": "run_selftests.py -k request_ledger comfy_service unit_of_work infra_errors"} -->

## 三问

1. **本轮属于 §3 哪种类型？** §3.3 结构治理轮（任务书明定，3 个模块）；范围限 `infra/request_ledger.py`、`infra/comfy_service.py`、`infra/unit_of_work.py` 及显示其消息的上层位置，`agent.core` 按 §2.4 不在本轮。
2. **测试跑了吗、基线过了吗？** 跑了。任务书定向命令 `run_selftests.py -k request_ledger comfy_service unit_of_work infra_errors` **75 条 0 红**；默认 `smoke_test.py` **9/9 绿**；`smoke_test.py --affected request_ledger comfy_service unit_of_work` 按任务书执行 **3 次**，门禁内唯一红为 `test_batch_frames.test_failure_does_not_stop_batch_and_can_retry`——已查明为**隐藏桌面环境性失败**（ffmpeg.exe 在隐藏桌面返回 0xC0000142），`git stash` 撤掉本轮改动后同环境复跑同败，与本轮 diff 零因果，详见末节归因。
3. **欠账少了吗？** 少了。FL-04 三模块计数 **63 处→0**（request_ledger 34、comfy_service 25、unit_of_work 12 的内置异常中文 raise 全部迁移）；`BUILTIN_CJK_RAISE_BASELINE` 移除三模块条目；LR-07 实测 **257→186**，`层间合规清单.json` violations/baseline 已同步下调。

## 领号说明

- R3439 由本工作树（`devin-l1-enterprise`／`codex/l1-enterprise`）经 `round_claim.py next` 领得（claims 登记 2026-11-18T22:34:02）。
- 同一时段误触 `next` 多领 R3440（登记 22:34:35，无任何结果文件／提交／代码改动）；已从共享 `round-claims.json` 撤回该登记并将 `round-counter.json` 回拨至 3439，序列无实际占用。

## I7-1　FL-04 清零＋棘轮下调 ✅

- `infra/request_ledger.py`：34 处中文 raise 全部改抛 infra_errors 族——校验/前置类 `ConfigError`，台账/凭据/币种损坏类 `CorruptDataError`，预算拒绝 `BudgetRejected`（ConfigError 子类，`code=E-QUOTA-EXCEEDED`），锁超时 `LedgerLockTimeout`（ConfigError 子类，`code=E-UNKNOWN`）。
- `infra/comfy_service.py`：25 处——输入/工作流配置 `ConfigError`，safetensors/返回体/任务编号异常 `CorruptDataError`；自有异常类改挂族：`ComfyGenerationFailed(ProcessError, ValueError)`、`ComfySubmissionUncertain(ProcessError)`、`ComfyRecoveryUnavailable(ProcessError)`。
- `infra/unit_of_work.py`：12 处——路径/状态前置 `ConfigError`，journal 数据 `CorruptDataError`，平台不支持与 `RollbackFailedError` 归 `ProcessError`，登记删除失败 `StorageError`；新增 `_TokenTypeError(InfraError, TypeError)` 兼容 `except TypeError`。
- AST 复核：三模块含 CJK 的 raise 节点异常类型已全部落在 infra_errors 族或其模块自有子类，无内置类型残留。
- `tests/architecture/test_infra_errors_boundary.py` 的 `BUILTIN_CJK_RAISE_BASELINE` 删除 `request_ledger:33`／`comfy_service:20`／`unit_of_work:10` 三条（实测归零，不再登记）；`test_baseline_modules_registered` 仍绿。
- `test_layer_relations.py` LR-07 实测 **186**（原 257，−71），`维护记录/层间合规清单.json` violations/baseline 同步 186 并注明 I8–I11 续迁下调；棘轮提示已执行。

## I7-2　用户可见文案逐字一致 ✅

- 全部 raise 的 message 实参原样保留，未做任何改写；`str(exc)` 输出不变（同一字符串实参）。
- 新增 `tests/test_infra_errors_i7_migration.py`（11 条），对代表性显示点逐字断言：
  - `RequestLedger._quantity` 四类非法输入 → `'用量或费率必须是有限非负数'`；
  - `BudgetRejected`／`LedgerLockTimeout` 构造文案与 `code`；
  - `RequestLedger.load()` 损坏台账 → `_corrupt_message` 文案＋`detail={'path','cause'}` 技术载荷（detail 不进用户文案）；
  - `Comfy` 非本机地址 → `'请输入本机ComfyUI地址，例如 http://127.0.0.1:8189'`；`validate_safetensors` → `'不是有效safetensors文件，可能下载到了网页'`；
  - `unit_of_work` 外来令牌 → `'unit_of_work 令牌必须来自 begin()'`、目录登记 → `'事务原语只登记文件，不登记目录'`、回滚后提交 → `'事务已回滚，不能再提交'`。
- 上层既有测试（test_request_ledger 37 条、test_unit_of_work 15 条、test_assets、test_request_recording、test_animatic_service 等）原样通过，构成显示点回归网。

## I7-3　兼容继承 ✅

- 迁移测试逐类断言旧内置 `except` 继续命中：`ConfigError`/`CorruptDataError` 为 `ValueError` 族，`ProcessError`/`QuotaError` 为 `RuntimeError` 族，`StorageError`/`NetworkError` 为 `OSError` 族，`_TokenTypeError` 为 `TypeError` 族；`ComfyGenerationFailed` 双继承 `ProcessError+ValueError` 同时兼容两侧历史 `except`。
- 消费者核对：`orchestrator/asset_batch_execution.py` 的 `isinstance(exc, ComfyGenerationFailed)`／`ComfySubmissionUncertain` 与 `domain/animatic_service.py` 的 `except ComfyGenerationFailed` 按类名命中不受影响；全仓 `except RuntimeError` 消费点（model_pool 等）与 comfy 调用路径无交集，双继承扩展的捕获面无行为改变。
- `record_request` 的 `(OSError, ValueError, TypeError)` 尽力记账降级、`rollback` 的 `BaseException` 透传语义均不变。

## smoke --affected 归因（环境性，非本轮回归）

- 任务书命令执行 3 次均 exit 1，门禁内唯一红：`test_batch_frames.BatchFailureRecoveryTests.test_failure_does_not_stop_batch_and_can_retry`（期望 `SH002：已保存并关联`，实得 `SH002：失败：首帧图片损坏或无法完整解码`）。
- 复现链：`domain/keyframe_evidence.image_facts` 以 ffmpeg `-xerror -err_detect explode` 严格解码 PNG；在 `gui_hidden` 隐藏桌面内直接复跑 ffmpeg 返回 **3221225794（0xC0000142 STATUS_DLL_INIT_FAILED）**，stderr 空——进程在隐藏桌面会话内初始化失败，stderr 为空属典型会话隔离现象。
- 对照实验：同一测试普通桌面单跑 15/15 绿、模块级批次绿；`animatic+assets+batch_frames` 组合绿；**`git stash` 撤掉本轮三个 infra 文件后隐藏桌面复跑同败** → 与本轮 diff 零因果。
- 结论：隐藏桌面环境下 ffmpeg 系子进程不可用，凡经 `image_facts`/`agent.media.probe` 的测试在含 Tk 批次的隐藏桌面轮次中必红；R3407 结果文件归因为「ffmpeg 负载抖动」的同批红项实为同一环境性根因（隔离复跑均在普通桌面）。缺陷面在 `scripts/gui_hidden.py` 与打包 ffmpeg 的会话兼容性，超出 I7 范围，建议后续轮次立项跟踪。
- 本轮不因此让路：I7 全部验收点（FL-04 清零、文案逐字、兼容继承、定向 75 条绿、默认冒烟 9/9 绿）均已满足并留证。

## 验证汇总

| 命令 | 结果 |
| --- | --- |
| `run_selftests.py -k request_ledger comfy_service unit_of_work infra_errors` | 75 条 0 红（含新迁移测试 11 条） |
| `unittest test_request_ledger test_unit_of_work test_request_recording test_assets` | 156 条 OK |
| `architecture.test_infra_errors_boundary` | 3 条 OK（三模块基线条目已移除） |
| `architecture.test_layer_relations` | 5 条 OK（棘轮提示→基线已下调 186） |
| `smoke_test.py` | 9/9 绿 |
| `smoke_test.py --affected request_ledger comfy_service unit_of_work` | 9 项过 1 项红（test_batch_frames 环境性，归因见上） |
