# R3282 结果：L2领域服务层优化任务书轮2（功能轮：infra/idempotency 实现＋recon 付费路径幂等收口）
<!-- round-evidence: {"commit_base": "0a0462ea", "credential_hits": 0, "evidence_sha256": "848433536efeecf5", "exit": 0, "failed": 0, "passed": 69, "round": 3282, "tests": "run_selftests.py -k recon"} -->

## 三问

**1. 本轮属于 §3 哪种类型？**
§3.1 功能轮。任务书轮 2 预设「幂等键＋recon 收口」：实现 `infra.idempotency.key_of()`、给 `domain/recon_service.run()` 接幂等判定、把生产工具路径 `skill_tools.call('recon.card')` 收进同一保护入口，并登记 14 个手搓 sha256 模块的迁移清单（只登记、不迁移）。不改变阶段行为契约，无需先改 REQ/DES。

**2. 测试跑了吗、三个基线过了吗？**

| 基线 | 结果 |
| --- | --- |
| 默认冒烟 | **9/9 通过**（`smoke_test.py` 无参，exit 0；含隐藏桌面 `--probe` 自检，8 项本轮检查＋1 项探测全绿） |
| `run_selftests.py -k recon` | **绿**：3 个测试文件 69 条用例 0 红 4.5 秒（test_recon_service 54＋test_ui_writing_recon 2＋test_project_rename_reconcile 13，整轮走隐藏桌面） |
| `smoke_test.py --affected recon_service skill_tools` | **绿**：定向门禁 12 个测试文件 ALL TESTS PASSED（46 秒 0 红）＋冒烟检查 10/10 |
| 架构门禁 `--architecture` | 502 条，FAILED（failures=2）：`test_entry_files_stay_within_budget`（AGENTS.md 16028>16000，本分支存量超支，master 侧已修）、`test_round_number_continuous`（状态页 master 专属冻结 3259，工作树结果文件已到 3276）——**与 R3275 记录的分支固有失败集合完全一致**，失败输入文件本轮均未触碰（`git diff HEAD` 为空），无新增红 |
| 全量回归 `--all --safe` | **未运行**——§3.1 功能轮在功能分支开发，全量按 §5 由合入 master 前触发；如实标注 |

**3. 欠账少了吗？**
减少。`recon_service` 此前是任务书认定的**唯一完全无防护的付费路径**（`save_card` 直接覆盖、`ATTEMPTS=3` 只重试不去重），本轮后同一 project＋target＋material_source＋生效参数第二次进入零付费请求；`infra.idempotency` 由 R3275 空壳转为真实现，幂等键口径有了唯一入口。14 个 sha256 模块的迁移清单已登记待后续轮次。

---

## 幂等键语义（本轮唯一算法口径）

`infra.idempotency.key_of(*parts)`：逐个 `str()` → `\x1f` 连接 → utf-8 → `hashlib.sha256(...).hexdigest()`（64 位十六进制）。哈希不重复实现——`infra.hash_backend.install()` 在 `app.py`/`desktop_launcher.py` 启动时已固定 `hashlib` 到内置后端，本模块只 `import hashlib` 使用。

`recon_service._idempotency_key()` 把业务语义参数规范化为一段 canonical JSON（`json.dumps(sort_keys=True, ensure_ascii=False, default=str)`）后喂给 `key_of`：

| 字段 | 口径 |
| --- | --- |
| `kind` | 固定 `'recon_card'`，与落盘卡片同源 |
| `target` | dict 原样（排序键序列化）；标量归一为 `{'name': str(target or '')}`，与 `collect()` 入参口径一致 |
| `material_source` | `str()` 后原文（`对标爆款`／`热点速成`） |
| `limits` | 生效预算 `dict(LIMITS, **(ports.limits or {}))`，与 `collect()` 同一取值 |
| `official_hosts` | `sorted(str(...))`，影响来源分级故必须进键 |

**不进键的执行细节**：sender、transport、headers、pause、program、时钟、save/save_text 回调——换执行器不换业务语义。

**标记**：`01剧本准备/input/recon_idempotency.json`（与 `recon_request.json`、卡片同目录），内容 `{'kind', 'key', 'written_at'}`；写盘走 `agent.core.save()`（或注入的 `ports.save`），失败只 `app_logging.swallowed` 留痕、不挡主流程。

**命中判定**（全部在 `collect()` 之前）：标记可读且为 dict、`key` 与本次键一致、`load_card()` 返回非空 dict → `_cached_success()` 由卡片字段重建 `success({card, doc, problems, sources, queries, not_found, budget})` 直接返回，**不发任何检索／抓取、不重复写盘**。标记缺失／损坏／非 dict／键不符、或卡片缺失为空，一律按未命中走 `collect()→save_card()→_save_marker()`。

## 验收清单（任务书轮 2）

- [x] 复现用例：同一镜头同一参数调用两次，第二次必须不发请求——`IdempotencyTests.test_second_run_with_same_params_sends_no_requests`＋`test_tool_path_second_call_sends_no_requests`，改前红改后绿（见下）
- [x] 命中幂等返回 `success(...)` `ServiceResult` 而非 `{'ok': ...}` 形状——`_cached_success()` 与首跑返回字段逐一相同，断言 `second.data == first.data`
- [x] `run_selftests.py -k recon` 绿（69 条 0 红）
- [x] `smoke_test.py --affected recon_service` 绿（另含 `skill_tools` 消费者，共 12 文件全绿）
- [x] 生产付费路径收口：`ui/skill_tools._recon_card()` 原绕过 `run()` 直调 `collect()+save_card()`，本轮改走 `recon_service.run()`，对外返回 dict 形状与错误行为（`ToolError`）保持不变
- [x] 边界用例：标记在卡片丢→重采；换 target→重采；换 material_source→重采；标记 JSON 损坏→重采（宁可重采不拿坏标记挡路）
- [x] `save_card` 的 `artifact_schema.stamp/validate` 行为未动；`{'ok': ...}` 形状清理属轮 8 未触碰

## 先红后绿证据

先写 `IdempotencyTests`（6 条）跑红——当时 `run()` 无幂等分支、`_recon_card` 未接 `run()`：

```
test_corrupt_marker_is_treated_as_miss ... ok          （边界用例天然通过：无标记机制即未命中）
test_different_material_source_reclects ... ok
test_different_target_reclects ... ok
test_marker_without_card_reclects ... ok
test_second_run_with_same_params_sends_no_requests ... FAIL
    AssertionError: 8 != 4   # 第二次 run() 又发出同样 4 个请求，累计 8
test_tool_path_second_call_sends_no_requests ... FAIL
    AssertionError: 8 != 4   # 工具路径同样未幂等
test_recon_service.IdempotencyTests: Ran 6 tests — FAILED (failures=2)
```

接入实现后同 6 条全绿；`tests.test_recon_service` 全文件 54 条 OK（既有断言未动）。

## 变更清单

| 文件 | 变更 |
| --- | --- |
| `infra/idempotency.py` | 空壳→实现：`key_of(*parts)`（`\x1f` 分隔、utf-8、sha256 hexdigest，走 `hash_backend` 既有后端）；docstring 由「R3275 只落签名」更新为真实口径 |
| `domain/recon_service.py` | +`MARKER_NAME`/`marker_path()`；新增 `_idempotency_key`/`_load_marker`/`_cached_success`/`_save_marker`；`run()` 在 `collect()` 前算键查标记、命中短路、成功落卡后写标记（写失败吞掉留痕）；import `infra.app_logging`＋`infra.idempotency`（L2→L1 合法方向） |
| `ui/skill_tools.py` | `_recon_card()` 由直调 `collect()+save_card()` 改走 `recon_service.run()`（`ReconPorts` 透传 transport/headers/pause/program/save/save_text）；返回 dict 字段与 `ToolError` 行为不变 |
| `tests/test_recon_service.py` | +`IdempotencyTests` 6 条（同参二次零请求、卡片缺失重采、异 target 重采、异素材来源重采、坏标记重采、工具路径二次零请求） |
| `tasks_round/tasks_round_3282_result.md` | 本文件 |

## 实测基线

- 默认冒烟：`python -B smoke_test.py` → 通过 9 项 / 失败 0 项（8 项本轮检查＋隐藏桌面探测）。
- 隐藏桌面探针：`python -B scripts/gui_hidden.py --probe` → 「隐藏桌面探测 OK」。
- 定向自检：`python -B run_selftests.py -k recon` → 3 文件 69 条 0 红。
- 受影响门禁：`python -B smoke_test.py --affected recon_service skill_tools` → 定向 12 文件 ALL TESTS PASSED（46s）＋检查 10/10。
- 架构门禁：`python -B smoke_test.py --architecture` → 502 条 / 171s / failures=2。失败集合 `{test_entry_files_stay_within_budget, test_round_number_continuous}` 与 R3275 改后记录的分支固有红完全一致：AGENTS.md 在 HEAD 即 16028 字节（`git show HEAD:程序/AGENTS.md | wc -c` 实测），`project_status.md` 本轮未动且状态页仅 master 合并轮维护；两者失败输入文件 `git diff HEAD` 均为空，证为存量、非本轮引入。与改前（R3275 同树口径 502 条 2F）相比失败集合无扩大。
- 全量回归：未运行（见三问第 2 行）。

## 14 个手搓 sha256 模块迁移清单（只登记、不迁移）

| 模块 | hashlib 用途（一句话） |
| --- | --- |
| `domain/animatic_service.py` | `digest(raw)` 对原始字节取 sha256，作分镜预演 `source_sha256` 清单指纹并与 `file_cache.file_digest` 复核 |
| `domain/asset_reference_prompts.py` | `fingerprint(positive, negative)` 对正负提示词拼接取 sha256，作 `prompt_import_hash` 导入指纹 |
| `domain/audio_import_service.py` | `_sha256(path)` 流式读文件取 sha256，登记导入音频文件的完整性摘要 |
| `domain/confirm_gates.py` | `sha1(text)[:12]` 对 `\x1f` 连接的候选字段取短哈希，作确认门候选指纹（注意是 sha1 非 sha256） |
| `domain/handoff_service.py` | 对打包文件 `data` 取 sha256 写进交接清单，解包侧 `probe()` 复核体积与摘要 |
| `domain/keyframe_evidence.py` | `_digest()` 对 canonical JSON、`_file_hash()`/内联对文件字节取 sha256，作首帧证据 `sha256`＋宽高事实 |
| `domain/recon_service.py` | 对规范化抓取正文取 sha256 作来源 `content_sha256`（幂等键本轮已改走 `infra.idempotency`，此处为内容指纹，仍登记待统一） |
| `domain/script_workspace_service.py` | 对脚本文件字节取 sha256，作结构签名版本列表与采用剧本清单 `sha256` |
| `domain/storyboard_lifecycle.py` | 对原稿文件字节取 sha256 与 `expected` 比对，防生成期间原稿被改（两处） |
| `domain/storyboard_storage.py` | 对 canonical JSON 快照取 sha256，作分镜存储快照摘要 |
| `domain/tts_api.py` | 对 canonical JSON 载荷取 sha256 作 `script_signature`/`batch_signature`，并对已发布语音行文件复核/记录 `sha256`（4 处） |
| `domain/usage_overview.py` | 对 canonical job JSON 取 sha256 作成本请求去重摘要，并比对来源/产物登记的 `sha256` |
| `domain/white_model_service.py` | 对 canonical JSON 载荷取 sha256 作 `shot_digest`/`source_digest`，白模证据的来源身份指纹 |
| `domain/writing_quality.py` | 对剧本正文取 sha256 作 `script_sha256`，对解析后脚本路径取 sha256[:12] 作质量报告 `identity` 定位键 |

口径不一实锤：`confirm_gates` 用 sha1[:12]、`writing_quality`/`script_workspace_service`/`storyboard_lifecycle`/`animatic_service`/`audio_import_service`/`handoff_service` 对原始字节或文件流、`tts_api`/`white_model_service`/`keyframe_evidence`/`storyboard_storage`/`usage_overview` 对 canonical JSON（`sort_keys` 有无、`separators`、`default=str` 各异）——39 处 `hashlib` 调用无统一入口，后续轮次按本表逐个迁往 `infra.idempotency` 或专用摘要口径。

## 偏差与说明

1. **`--affected` 模块名含 `skill_tools`**：任务书只写 `--affected recon_service`，但本轮改了 `ui/skill_tools.py`（`_recon_card` 收口），按 §5「被其它模块 import 的模块必须覆盖全部消费者」补 `skill_tools`，定向 12 文件全绿。
2. **架构门禁 2 红为分支存量**：与 R3275 记录的失败集合逐名一致，输入文件本轮零改动；AGENTS.md 预算与轮次连续性均需 master 侧/合并轮处理，超出本轮文件范围，如实上报不粉饰。
3. **`--tests recon` 提交证据**：`run_selftests.py -k recon` 命中 test_recon_service／test_ui_writing_recon／test_project_rename_reconcile 三文件全绿，不触架构红，无需像 R3275 那样改关键词。
4. **未动**：`L2领域服务层优化任务书.md`（含外来轮次标注改动）、`project_status.md`（仅 master 可提交）、R3276 外来未跟踪三件（诊断报告/结果文件/任务书）一律不入暂存区；临时补丁脚本 `_patch_recon.py`、`tests/_idem_fragment.txt`、`_patch_skilltools.py` 已删除。

## 遗留欠账

- 14 个 sha256 模块迁移：本轮只登记清单，迁移排后续轮次（口径差异需逐模块确认，`confirm_gates` 的 sha1[:12] 是否保留短哈希形态待定）。
- 幂等标记目前单键单槽（`recon_idempotency.json` 只记最近一次成功采风）：同项目换 target 再换回旧 target 会重采一次——任务书口径「同一件事只做一次」按最近一次判定已满足，历史键多槽留待确有需求再扩。
- `run()` 幂等依赖卡片仍在：卡片被用户手动删除后标记仍在，按未命中重采并覆写标记，行为正确。
- 分支侧 2 条架构红为存量结构问题（同 R3275 记录），待 master 合并轮处理。

## 提交

- 分支 `codex/wip-r3282`（领号 R3282，工作树 `dsh-864fd932-4054`）。
- commit：`0a0462ea`（代码＋测试＋结果文件＋轮次证据主提交，6 文件）；本补记行由后续提交写入，不另占轮次。轮次证据以 `tasks_round/evidence/R3282.json` 中 `run_selftests.py -k recon` exit 0 / 69 通过 / 0 失败为准。
- 全量回归：未运行（见三问）；合入 master 前按 §5 触发 `--all --safe`。
