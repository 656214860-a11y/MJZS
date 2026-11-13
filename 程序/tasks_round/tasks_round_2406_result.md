# R2406 文档轮结果：执行方规则由「Claude Code」改为「当前执行 agent」

## 三个必答（§7）

1. **轮次类型**：文档轮（纯 `.md` 改动，不涉及代码；对应 §3 未单列的「文档/状态接续」性质，不跑 smoke/selftest）。
2. **测试跑了吗、三个基线过了吗**：未跑（纯文档改动，按 AGENTS.md §5「文档轮不跑 smoke／selftest」；不改变任何产品行为、分层、契约或测试）。
3. **project_status.md 的欠账少了吗**：不涉及欠账条目。

## 改动

把「执行与提交方」从硬编码的「Claude Code」改为**不绑定具体运行时**的通用表述——当前由哪个 agent 运行时承载任务，该运行时即执行与提交方（含领号、跑测试、提交）。起因：本任务由 DeepSeek Assistant（DSH harness）承载，但规则硬编码「Claude Code 执行」，导致执行方与规则矛盾。

- `程序/AGENTS.md`：
  - §2.1 规则 7「均由 Claude Code 执行」→「均由当前执行 agent 执行」。
  - §2.6「提交与领号由 Claude Code 执行」→「由当前执行 agent 执行」。
  - §4.1 标题「执行与提交方（Claude Code）」→「执行与提交方（当前执行 agent）」；正文「所有任务由 Claude Code 自己完成，不再写任务书派发给 Codex／DSH／opencode／DeepSeek 等其他模型」→「所有任务由当前执行 agent 自己完成……同一时刻由哪个运行时（如 Claude Code、DeepSeek Assistant 等）承载，就以该运行时为执行与提交方」。
- `CLAUDE.md`：工作约定「Claude 的角色」→「执行与提交方」，同步通用表述。
- `程序/HANDOFF_20261022_1830.md`：「所有任务由 Claude Code 亲自完成」→「由当前执行 agent 亲自完成」。

## 有意未改

- `architecture.md` 第 316 行「Claude Code」是出厂模型池的引擎名（产品功能），非执行方规则，保留。
- `tasks_round/归档/…/tasks_round_1837_result.md` 中的「改为 Claude Code 自己完成」是历史事实记录，按「历史条目只读、不追溯」保留。
- `开发者工具/handoff-full-safe.md` 已是「亲自完成、不派发」的通用措辞，无硬编码，不改。

## 提交

- 已提交：见提交记录。
