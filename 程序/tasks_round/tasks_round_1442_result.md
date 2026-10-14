# R1442 结果：清理 HOLLMWOOD 遗留（短剧工业化流水线描述、无调用方的 Claude CLI 适配器）

三个收尾问题：
- 本轮类型：功能轮（R1441 的遗留清理；删除无生产调用方的代码与过期 SKILL 描述）。
- 测试与基线：`test_writing_api`（52）、`test_idea_chat`（120）、`test_cancellation_status`、`test_claude_program_detection` 通过；默认冒烟 8/8。**全量未在本轮产出凭据**：`run_selftests.py --all --safe` 因工作树里另有他人未收口改动（`run_selftests.py`、`scripts/auto_full_safe.py`、`test_round_baselines.py`、`test_selftests.py`、`维护记录/基准脚本/round_claim.py`）拒绝测量，见下。
- 欠账：未减少；新增一个改过源码的轮次。

## 改动

1. `skills/01 剧本准备SKILL/短剧工业化流水线`：删除 `集成HOLLMWOOD框架.txt`；`references/03-script-draft.md` 移除「内嵌 HOLLMWOOD 四步初稿引擎」一节，保留「初稿内容边界」（仅自然语言正文，禁止结构化交付物）。
2. 删除 `workflow_engines.ClaudeWritingAdapter`（R1441 之后无生产调用方）；`writing_api._writing_adapter` 只剩 `PoolAdapter`，`reply()` 去掉不可达的 Claude 桌面分支，`direct_api` 恒为 True。
3. 删除 `desktop._stream_text` 及其「生成中」气泡（流式只服务已移除的演员角色）。
4. 测试：删除 `test_claude_writing_roles.py` 与 `test_claude_program_detection` 中的适配器用例；`test_writing_api` 新增「Claude 桌面模型不是直接 API 模型」用例。其余断言未动。

## 未验证 / 说明

- `自检增量.json` 中的 `hollmwood_roles` 旧条目由下一次全量跑绿后自动重写，本轮不手改。
- 全量回归：工作树含他人未提交改动时 `--all --safe` 拒绝产凭据；需在这些改动收口后，或由 post-commit 钩子在 `.wt/ci` 干净检出上补跑。

## 提交

master，未 push；commit hash 见 `git log`。
