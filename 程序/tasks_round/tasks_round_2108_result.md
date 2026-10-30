# R2108 合入 codex/wip-R2106（R2106：模型管理窗口腾出空间给模型列表）到 master（合并轮）

轮次类型：合并轮。日期：2026-10-30。

- 合入：分支 `codex/wip-R2106` 的 R2106（`a72fb4fb`）以 `--no-ff` 合入 master（合并前 master 为 `8a330a78` R2105），无冲突。
- R2106 内容：模型管理窗口说明文字移到标题右侧同一行；表单输入框与下拉框去掉纵向内边距（`CompactLineInput`、`Compact.Tokens.Combobox.TCombobox`），行高约减半；Desktop／CLI 时「模型 ID」一栏改称「程序名」，API 保留；列表可见行数约由 8 行增到 15 行。新增 1 条自检，已有断言未动。详见 `tasks_round/tasks_round_2106_result.md`。
- 主目录工作树里另有他人未提交的 `tests/test_download_inbox.py`、`tests/test_idea_download_import.py` 改动，本轮未暂存、未提交。
- 本轮运行（主目录，合并后工作树）：`run_selftests -k pet_ui pet_settings client_profiles model_probe button_consistency` 1 红：`test_req_s01_56_builtin_catalog_covers_every_known_client` 读到主目录运行数据 `data/客户端档案.json` 里本机新增的 `claude-2`、`claude-3` 档案，用例未隔离本机数据，非本轮引入（worktree 内同组 0 红）；默认 `smoke_test.py` 通过。
- 未运行：`--affected`、架构门禁、`--all --safe`（提交后由后台补跑）、真机目测。未 push。
