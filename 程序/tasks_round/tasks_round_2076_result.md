# R2076 合入 claude/agent-learn-user-edits-d32ad8（修改习惯第一期）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。

- 跑了哪些测试与基线：合并后在主目录跑 `--affected`（8 个改动模块，2280 条）、`--architecture`、默认冒烟。默认冒烟 8/8 通过。
- `project_status.md` 欠账：未减少；轮次头同步到 2076。
- 断言未动。

## 合入

- claude/agent-learn-user-edits-d32ad8 的 R2074（53b3be87），`--no-ff`，无冲突。内容见 tasks_round/tasks_round_2074_result.md。
- R2075 由其他会话领取。

## 仍红（均非本轮引入）

- `--affected` 有 5 个文件红。拿合并前 master（47df1bce）的临时 worktree 补上子模块，串行跑同样的 `-k test_core test_idea_chat test_writing_api`（335 条）对比：
  - `test_core#7`（`ProjectList` 无 `exists`）：合并前同样红。
  - `test_idea_chat`：合并前同样红，每次红的条数在 3～4 条之间浮动（「正在读取聊天记录…」等首绘时序）。
  - `test_writing_api::test_api_formal_script_reuses_download_path_and_versions_changed_text`：只在主目录红，原因是读到了主目录本机 `配置/` 的模型池（文件名模型段为「自定义」）。把同一份 `配置/` 复制进合并前的 worktree 后同样红，属于测试隔离问题。
- `--architecture` 有 2 红：`test_full_safe_all_is_required_after_eight_source_rounds`（欠一次 `--all --safe`，提交后由 post-commit 钩子后台补跑）；`test_round_number_continuous`（R2075 的结果不在 master 上）。
- R2074 在 worktree 里因缺子模块出现的 24 个文件红，在主目录已不再出现。

## 未运行

- `--all --safe`（交给后台补跑）、真实界面目测、真实模型归纳。未 push。
