# R4209 轮次结果
<!-- round-evidence: {"commit_base": "af94e648", "credential_hits": 0, "evidence_sha256": "0906dc04049a097a", "exit": 0, "failed": 0, "passed": 25, "round": 4209, "tests": "run_selftests.py -k voice_emotion_check asset_image_import asset_detail_service"} -->

## 开头三问

1. **轮次类型（AGENTS §3）**：修复轮（§3.2）＋同范围结构治理（§3.3，3 个模块）。
   - 修复：`domain/voice_emotion_check.py` 的 `passed` 统计恒真谓词（`or True` 残留）。
   - 结构治理：`agent/media.py`、`domain/asset_batch_service.py`、`domain/asset_detail_service.py` 三模块——两处同构的私有 `_image_content_ok` 收敛为 L1 `agent.media.image_content_ok` 单入口。
2. **测试跑了吗、三个基线过了吗**：
   - 定向：`run_selftests.py -k voice_emotion_check asset_image_import asset_detail_service` → 25 条 0 红。
   - 受影响：`smoke_test.py --affected media.py asset_batch_service.py asset_detail_service.py voice_emotion_check.py` → 0 文件有红。
   - 架构门禁：`smoke_test.py --architecture` → 700 条全绿。
   - 默认冒烟：9/9 通过。
   - 全量：`--all --safe` 9998 条 1 个环境性红（`test_perf_baseline` CPU 比率，master 同红，详见「全量」节）→ **不合入**，停于分支。
3. **欠账少了吗**：少了。`image_content_ok` 双份实现收敛为单份；分支覆盖率基线按官方流程真实重测（102 目标 2003 条全绿，103 实体 3092 决策点／1769 覆盖，`media.py` 18→22 决策点），下限表未动（`media.py` 下限 0.0）。

## 改动说明

### BUG 修复：voice_emotion_check passed 统计

- 根因：`check()` 返回 `passed` 的推导式 `u.get("reason") != "缺标注" or True` 中 `or True` 恒真，等于把所有 `unverifiable` 都计入扣减——`缺标注`（无法核验）行也被当作失败行扣掉，`passed` 系统性偏低（如 2 条剧本 2 条缺标注时报 0 而非 2）。
- 修复：删除 `or True`，恢复谓词原意「只扣非缺标注的无法核验项」。`deviations` 与 `unverifiable` 生成逻辑未动。
- 断言未动：`tests/test_voice_emotion_check.py` 未改；该测试不断言 `passed`，行为修正不破坏既有断言。

### 结构治理：图片内容验真单入口

- 问题：`domain/asset_batch_service.py` 与 `domain/asset_detail_service.py` 各持一份逐字相同的 `_image_content_ok`（PNG 签名＋IHDR＋IEND、JPG SOI＋EOI、WEBP RIFF＋WEBP，头 16 尾 8 字节），两份私有副本会漂移。
- 方案：函数下沉为 `agent/media.py`（L1）的公共 `image_content_ok`；`contract/media_signature` 的 docstring 已裁定「完整探测、尺寸解析与导入校验在 agent.media」。L2→L1 下行依赖合法，两域服务改为 `from agent.media import image_content_ok`。
- 曾试放 `contract/media_signature`（L0）：contract 纯度台账拒绝新增 `open`/`stat` 调用，已改落 L1。
- 零行为变化：实现逐字保留（复用模块内 `PNG_SIGNATURE` 常量），调用点签名不变。
- 断言未动：无测试文件改动。

## 基线刷新说明

- `维护记录/分支覆盖率基线.json` 由 `scripts/branch_coverage_report.py` 对基线原登记的 102 个目标真实重测生成（2003 条全绿，退出码 0）；`media.py` 决策点 18→22（新增 4 个分支点：try＋3 个格式判定）。
- 下限表 `维护记录/分支覆盖率下限.json` 未改：`media.py` 下限 0.0，实测 0/22 仍满足。

## 环境说明

- 首轮基线测量中 `tests.test_script_contract.AuditTests.test_the_audit_covers_every_script_skill` 红：主树 `skills/01 剧本准备SKILL/` 下 `剧本锻造`、`编剧技能集` 是未跟踪的内嵌 git 仓库，worktree 不含这两目录导致注册表少 2 个 skill。将两目录复制进 worktree 后测试转绿；为环境差异非回归，未跟踪文件不入暂存。

## 全量

- `run_selftests.py --all --safe`（提交后执行，隐藏桌面）：9998 条用例、1585.4 秒、**1 个文件有红**。
- 唯一红：`test_perf_baseline.test_the_asset_page_opens_under_the_limit` — 资产页打开 CPU 比率 10.0/11.1 倍 > 10.0 限（墙上耗时正常）。判为**环境性既有红**：master 自身 23:38 自动全量（HEAD `198c033`，不含本改动）同一条红；串行复跑该文件仍红（并发会话同时跑全量、机器负载下 CPU 计时断言失稳）。相关模块本轮未改动。
- 全量红 ⇒ 按规则**不合入 master**，停在 `codex/nightly-review-2026-11-23`（a5c4ae35）；绿凭据未写入，欠账口径不变。
- 外层包装器在打印含 `✗` 的日志时 UnicodeEncodeError（GBK 输出装饰性问题，内层日志完整）。
