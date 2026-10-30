# R2124 结果：合入 codex/wip-R2119（R2119：API 用量口径补全、Claude system 拆固定块＋变化块）到 master（合并轮）

## 内容
- R2119（68aebfb0）：
  - 用量口径统一由 `token_saver.reported_usage` 实现：OpenAI／Responses 嵌套的 `cached_tokens` 计入命中；Claude 总输入＝input＋cache_read＋cache_creation，并保留 `cache_creation_tokens`。
  - `model_pool.http_stream` 请求带 `stream_options.include_usage`，并读取最后的用量分片。
  - Claude 的 system 用 `split_system` 拆成固定块（SKILL、契约、文风、编辑习惯、工具说明）和变化块（项目上下文），固定块显式打 `cache_control`；单轮请求去掉顶层断点。
- 本轮先领到 R2121。合并时主目录另一会话正在合入 R2117（R2123，有 MERGE_HEAD 和暂存文件），等它提交后重新领号为 R2124，再合并。R2121 未使用。

## 冲突
- 无，自动合并。

## 验证（本轮运行，合并后的主目录）
- `run_selftests -k test_api_cache_usage test_token_saver test_pet_llm test_critical_chains test_model_router_diagnostics test_writing_api test_usage_overview test_model_pool_redirects test_model_failure_route test_outbound_request_contract test_idea_chat`：428 条全通过。
- `smoke_test.py --architecture`：只剩 1 红 `test_full_safe_all_is_required_after_eight_source_rounds`（R2123 欠一次完整安全全量）。R2119 结果文件里记的 3 项基线红，已在 R2123 消除 2 项；`基准历史.json` 在主目录存在，不再报错。
- `--all --safe`：由本次提交的 post-commit 钩子在后台触发，结果见 `logs/auto_full_safe.log` 或 `scripts/auto_full_safe.py --status`。上一次后台全量（HEAD 8a330a7）红在 test_requirement_traceability、test_round_baselines、test_soak_light、test_leak_teardown。

## 未验证
- 没有用真实 Claude 或 OpenAI 接口实测缓存命中；中转站和 `stream_options` 兼容性风险见 tasks_round_2119_result.md。
