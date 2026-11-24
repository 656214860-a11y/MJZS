# R4248 FIX-NIGHTLY-4209：接管 codex/fix-nightly-4209 既有 7 文件并复验提交（修复轮）
<!-- round-evidence: {"commit_base": "72b61f8b", "credential_hits": 0, "evidence_sha256": "2a01c5a48c137641", "exit": 0, "failed": 0, "passed": 82, "round": 4248, "tests": "run_selftests.py -k test_media voice_emotion_check tests/test_media.py tests/test_voice_emotion_check.py tasks_round/tasks_round_4248_result.md"} -->

## 三问
- 轮次类型：§3.2 修复轮（接管既有修复现场、复验并正式提交；本轮不重做实现）。
- 测试跑了吗、三个基线过了吗：跑了。定向 `run_selftests.py -k voice_emotion_check media asset_detail_service asset_batch` 退出码 0、18 个测试文件 128 条用例 0 红；`smoke_test.py --affected media voice_emotion_check asset_batch_service asset_detail_service` 退出码 0（10/10）；`smoke_test.py --architecture` 退出码 0（700 条）；默认 `smoke_test.py` 退出码 0（9/9）。
- 欠账少了吗：把旧 claim 2fa5f01e 遗留的 7 个未提交修复文件正式入库；无新增欠账。改前红原文未保留，标「未核实」，由验收独立 red-check。

## 范围与基线
- 基准版本：`72b61f8b4d70019618838f9dc33a8534ea9aa6ac`；分支 `codex/fix-nightly-4209`（`git rev-parse --abbrev-ref HEAD` 实测）。
- 源提交：`0909de94`（N476/N479 独立复核认定其三处产品差异合理、源分支定向 119 条 0 红；但源提交未改任何测试，其结果写 25 条旧定向且全量节引用 `a5c4ae35`，与 HEAD `0909de94` 不一致，本轮不照抄、不沿用 25 条或 `a5c4ae35` 作证据）。
- 接管现场：开工 `git status --short` 仅含下列 7 个已修改文件，即旧 claim `2fa5f01e` 的授权现场（+92/-57），不是垃圾，全部保留：
  - `agent/media.py`（+25/-0）
  - `domain/asset_batch_service.py`（+2/-27）
  - `domain/asset_detail_service.py`（+2/-27）
  - `domain/voice_emotion_check.py`（+1/-1）
  - `tests/test_media.py`（+47/-0）
  - `tests/test_voice_emotion_check.py`（+13/-0）
  - `维护记录/分支覆盖率基线.json`（+2/-2）
- 本轮另新增 `tests/test_asset_detail_service.py` 在允许清单内但未改动（`git status` 无该文件）；`tasks_round/tasks_round_4248_result.md` 为本结果文件，`tasks_round/evidence/R4248.json` 由 `scripts\dev.py commit` 生成。

## 三处产品修复复核（与 `git show 0909de94:<路径>` 逐条只读对照）
1. `agent/media.py`：新增 `image_content_ok(path)`（media.py:27-49）。与 `0909de94:程序/agent/media.py` 逐字一致。契约核对：PNG 验签名＋IHDR＋IEND、JPG（含 .jpeg）验 SOI＋EOI、WEBP 验 RIFF＋WEBP；只读头 16 字节与尾 8 字节；`OSError` 返回 False；后缀非三者返回 False；最小长度 PNG≥33／JPG≥4／WEBP≥12。
2. `domain/asset_batch_service.py`、`domain/asset_detail_service.py`：各删除约 26 行私有 `_image_content_ok` 内联验真，改为 `from agent.media import image_content_ok` 单入口调用（asset_batch_service.py:12、118-119；asset_detail_service.py:16、57-58）。两文件与 `0909de94` 对应版本逐字一致；L2→L1 依赖方向合规，未恢复旧内联验真。
3. `domain/voice_emotion_check.py`：`check()` 返回值 `passed` 统计去掉 `or True` 恒真谓词。HEAD 原文为 `u.get("reason") != "缺标注" or True`（恒真，导致 unverifiable 全部被减），现为 `!= "缺标注"`（voice_emotion_check.py:233-234）。与 `0909de94` 逐字一致；只影响返回值 `passed`，不改变 deviations/unverifiable 内容与落盘台账。

## 回归用例清单（本轮实跑覆盖）
- `tests/test_media.py` 新增 `ImageContentOkTests`（test_media.py:177-221）：合法 PNG、截断/伪造 PNG、合法 JPG、缺 EOI 的 JPG、合法 WEBP、RIFF+WAVE 伪 WEBP、未知后缀 .gif、`OSError` 与缺失文件，共 9 例。
- `tests/test_voice_emotion_check.py` 新增 `test_passed_mixed_unverifiable_reasons`（test_voice_emotion_check.py:61-72）：缺参数＋缺标注混合 unverifiable 时断言 `passed == 2`。
- `tests/test_asset_detail_service.py` 未改：既有 `test_non_image_content_returns_user_error_without_publication`（fake.png/fake.jpg/broken.webp 拒绝且不发布）与 `test_real_jpeg_content_is_accepted` 已覆盖服务层单入口行为。

## 改前红说明
- 未核实：旧 claim `2fa5f01e` 的日志未保留新增测试在产品修复前的改前红原文；本轮接管后直接复跑定向，不冒充改前红，不补造原始输出，由验收独立 red-check。

## 覆盖率基线核对
- `维护记录/分支覆盖率基线.json` 的 diff 仅两处：`points_total` 3088→3092、`media.py` 的 `points` 18→22（`covered`/`percent`/`modules_total`=103 均不变）。系 `image_content_ok` 新增 try＋3 个 if 决策点的机械重计，无语义与阈值改动；`git diff --check` 退出码 0 无输出。

## 验证命令与实际结果（工作目录均为 `程序`，全部 PowerShell 逐条执行）
1. `git status --short` / `git log -1 --format=%h` / `git rev-parse --abbrev-ref HEAD`：退出码均 0；HEAD `72b61f8b`，分支 `codex/fix-nightly-4209`，status 仅上述 7 文件。
2. `git show 0909de94:程序/agent/media.py`、`...:程序/domain/voice_emotion_check.py`、`...:程序/domain/asset_batch_service.py`、`...:程序/domain/asset_detail_service.py`：退出码均 0，只读对照源实现（结论见上「三处复核」）。
3. `git diff -- domain/voice_emotion_check.py`、`git diff -- domain/asset_batch_service.py domain/asset_detail_service.py agent/media.py`、`git diff -- 维护记录/分支覆盖率基线.json`：退出码均 0，差异与上述复核一致。
4. 定向基线（接管后复跑，非改前红）：`..\..\..\..\运行环境\Python\python.exe -B run_selftests.py -k voice_emotion_check media asset_detail_service asset_batch`
   - 第 1–5 次尝试：跨树全量先后占用 `gui-selftest.lock`（PID 31708→59080），本会话 60 秒 GUI 等待上限到点记 `GUI_DEFERRED`，4 个 GUI 文件未执行，退出码 1（每次 112 条 0 红）。
   - 第 6 次：退出码 0。`共 128 条用例，95.2 秒；0 个文件有红`；`ALL TESTS PASSED`。18 个文件含 `test_voice_emotion_check` 9 条、`test_media` 三分片 26 条、`test_asset_detail_service` 11 条、`test_media_import_validation` 12 条及 4 个 GUI 文件（test_media_render 2、test_asset_batch_window 6、test_media_page_buttons 5、test_desktop_media_pages 3）全部执行。
5. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --affected media voice_emotion_check asset_batch_service asset_detail_service`
   - 第 1 次：退出码 2（内层定向 287 条 0 红，但 GUI 锁被 PID 59588 占用，3 个 GUI 文件 `GUI_DEFERRED`）。
   - 第 2 次：退出码 0。输出尾部：`通过：10 项`、`失败：0 项`、`✅ 冒烟测试通过，可以进入下一轮`；内层 `run_selftests.py --serial -k ...` 22 个测试文件 `ALL TESTS PASSED`（约 121 秒）。
6. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py --architecture`：退出码 0。`Ran 700 tests in 279.217s`、`✅ 架构治理测试：tests/architecture`、`OK`。
7. `..\..\..\..\运行环境\Python\python.exe -B smoke_test.py`：退出码 0。`通过：9 项`、`失败：0 项`、`✅ 冒烟测试通过，可以进入下一轮`。
8. `git diff --check`（退出码 0，无输出）、`git diff --name-only`（退出码 0，仍仅上述 7 文件）、`git diff --numstat`（退出码 0，合计 +92/-57）。
9. `..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py claim`：退出码 0，输出 `4248`。

## 提交（未完成：被车道重叠门禁拒绝）
- 提交命令（已执行）：`..\..\..\..\运行环境\Python\python.exe -B scripts\dev.py commit -m "R4248: FIX-NIGHTLY-4209 接管复验 R4209 修复" --tests voice_emotion_check media asset_detail_service asset_batch --agent "Devin SWE-2 Flash High" agent/media.py domain/asset_batch_service.py domain/asset_detail_service.py domain/voice_emotion_check.py tests/test_media.py tests/test_voice_emotion_check.py 维护记录/分支覆盖率基线.json tasks_round/tasks_round_4248_result.md`（路径相对 `程序` 目录）。
- 结果：退出码非 0（工具报告 1），未产生提交。stderr 原文：
  - `提示：路径 程序/agent/media.py 与活跃分支 codex/nightly-review-2026-11-23 的未合入改动重叠，试合并可以自动合并，不拦截`（asset_batch_service.py／asset_detail_service.py／voice_emotion_check.py 同此提示）
  - `拒绝提交：路径 程序/维护记录/分支覆盖率基线.json 与活跃分支 codex/nightly-review-2026-11-23 的未合入改动重叠，试合并有真实冲突（合入将冲突；请错开改动位置，或待对方合入后再提交）`
- 机制出处：`scripts/commit_round.py:67-84`（`check_scope_overlap`）→ `维护记录/基准脚本/branch_scope.py:440-512`（`commit_gate_report`）；该门禁无旁路参数，`commit_round.py` 全文无绕过开关；卡面禁止手写 `git commit`/`git add`，故按失败升级停下，现场保留。
- 判断：4 个 .py 与活跃车道试合并可自动合并（疑为同一 R4209 修复的平行实现），唯独 `分支覆盖率基线.json` 双方各自重算了同一区域（`points_total` 与 `media.py` 的 `points`）且数值不同，三方试合并产生真实冲突段；「错开改动位置」在同一 JSON 字段上不可行，合入后正确基线值取决于合并顺序，超出本卡授权。
- `tasks_round/evidence/R4248.json` 未生成（commit 在证据阶段之前被拒）；提交哈希不存在。

## 未验证项
- 改前红原文未核实（见上），由验收独立 red-check。
- 提交未完成：R4248 无 commit hash，`git status --short`／`git log -1 --oneline` 的提交后核对未执行（无提交可核对）。
- 未跑全量 `run_selftests.py --all --safe`（卡面未要求；GUI 锁期间多次被跨树全量占用）。
- 未合入、未 cherry-pick 源分支 `0909de94`；其结果文件与 evidence 未复制，本轮证据全部来自本工作树实跑。
- `tests/test_asset_detail_service.py` 本轮未改动，其用例在定向中实跑通过（`test_asset_detail_service` 11 条 0 红）。

## 合入接管会话代提交（2026-11-24，原执行者中断）
- 由合入接管会话代提交，原执行者中断；R 号沿用本文件已领的 R4248（`round-claims.json` 归属 `codex/fix-nightly-4209`）。
- 比对 master 现状（`git diff master -- <改动文件>`）：4 个产品文件（`agent/media.py`、`domain/asset_batch_service.py`、`domain/asset_detail_service.py`、`domain/voice_emotion_check.py`）与 master 逐字无差异——同一修复已随 `codex/nightly-review-2026-11-23` 的 R4209（`bfb4505c`）经合并轮 R4268 合入；`维护记录/分支覆盖率基线.json` master 已是更新的重算值（本车道为旧值），不提交。
- 独立价值：R4209 未改任何测试；本车道的 `tests/test_media.py`（`ImageContentOkTests` 8 条）与 `tests/test_voice_emotion_check.py`（`test_passed_mixed_unverifiable_reasons` 1 条）是 master 没有的回归用例，因此本次只提交这 2 个测试文件与本结果文件。
- 本次实跑（车道 `程序` 下）：`run_selftests.py -k test_media voice_emotion_check asset_detail_service asset_batch_service` 退出码 0，`共 93 条用例，30.4 秒；0 个文件有红`、`ALL TESTS PASSED`。
