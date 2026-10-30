# R2119 结果：API 用量统计补全、Claude system 拆固定块＋变化块（修复轮）

## 需求
用户原话：“先补全用量统计（OpenAI 嵌套 cached_tokens、流式 include_usage、Claude 的 cache_creation 和总输入口径），再把 Claude 的 system 拆成固定块＋变化块，在固定块上显式加 cache_control。”

## 原因
- Claude 的 `input_tokens` 不含缓存读写，旧代码直接把它当总输入，命中率可算到 8.0（800%），成本也偏低；`cache_creation_input_tokens` 被丢掉。
- OpenAI 兼容接口的命中写在 `usage.prompt_tokens_details.cached_tokens`，Responses 写在 `usage.input_tokens_details.cached_tokens`，旧代码只认顶层字段，所以记成 0。
- 流式请求没带 `stream_options.include_usage`，拿不到用量；最后那个用量分片的 `choices` 是空列表，旧解析会 IndexError 后跳过。
- Claude 的 system 是一整段字符串，只有顶层自动断点，项目上下文一变，整段前缀就不再命中。

## 改动文件
- `token_saver.py`：
  - 新增 `reported_usage(raw)`，作为用量口径的唯一实现：服务端报了哪几格就返回哪几格；Claude 总输入＝input＋cache_read＋cache_creation；嵌套命中和 DeepSeek 命中都计入 `cached_tokens`。
  - `anthropic_usage` 改为四格（多一格 `cache_creation_tokens`）。
  - 新增 `SplitSystem`（str 子类，带 `.fixed`）和 `split_system(fixed, variable)`。
  - `anthropic_payload` 新增 `keep_tail` 参数。拆过的 system 发成块列表，固定块带 `cache_control`；单轮单消息时去掉顶层断点，免得每次都变的用户消息按 1.25 倍写进缓存；带工具或多轮时保留顶层断点。普通字符串 system 的行为不变。
- `pet_llm.py`：`reported_usage` 指向 token_saver 的实现；`usage_of` 始终返回三格，服务端报了非零写入时才带 `cache_creation_tokens`；`Ledger.record` 保存缓存写入数；客户端请求台账改用 `reported_usage`。
- `model_router.py`：`chat` 的 messages 协议不再走单独分支，改用统一的 `usage_of`；`payload` 在有 tools 或多条消息时传 `keep_tail`。
- `model_pool.py`：`http_stream` 请求带 `stream_options={'include_usage': True}`，先读分片里的 `usage`，再取 `choices`，并把用量放进返回的 `data.usage`。
- `model_diagnostics.py`：诊断落盘时保留 `cache_creation_tokens`。
- `writing_api.py`：
  - `_call` 的别名表改用 `token_saver.reported_usage`；没报的格子仍记 None。
  - 写作路径先组固定规则（SKILL、阶段输出契约、文风、编辑习惯；messages 协议下再加上静态的“受控剧本文件工具”段），项目上下文作为变化块：`split_system(fixed, context)`。
  - 准备阶段 system 全是固定规则，整段作为固定块。

## 测试
- 新增 `tests/test_api_cache_usage.py`，15 条，先红后绿。首次运行 14 条红，只有“普通 system 仍是字符串”那条通过。
- 契约有意变更（Claude 总输入口径），同步了 `tests/test_token_saver.py` 的 4 处期望值，仍是精确等值断言，强度未降：
  - `anthropic_usage` 12→25
  - messages 协议 chat 10→18
  - 命中率 0.8→round(80/180, 3)
  - `usage_of` 12→21
  其余断言未动。

## 验证（本轮运行，均经 gui_hidden）
- `run_selftests -k test_api_cache_usage test_token_saver test_pet_llm test_critical_chains test_model_router_diagnostics test_writing_api test_usage_overview test_model_pool_redirects test_model_failure_route test_outbound_request_contract test_idea_chat`：428 条全通过。
- `smoke_test.py --architecture`：本轮引入的超限已压回（`model_pool.py` 回到 1117 行上限内，`_preparation_step` 回到 150 行内）。还剩 3 项红，涉及的文件本轮都没改，是基线 3498aee8 就有的：
  - `test_performance_history_is_declared_as_historical_only`：`维护记录/基准历史.json` 未入库，worktree 里没有这个文件。
  - `desktop_idea_chat.py` 1152 行，超过上限 1148。
  - `codex_paste.py:_run` 的裸 `json.loads` 未登记。

## 未验证与风险
- 没有用真实 Claude 或 OpenAI 接口实测，命中率要等用户实际调用后，在用量页和诊断里看。
- 第三方中转（如 api.supergpt.dev）是否透传块格式 system 和缓存字段未知；如果它只认字符串 system，可能报 400。
- 少数 OpenAI 兼容服务可能拒收 `stream_options`；流式失败会由调用方回退普通请求，但不会自动去掉该字段重发。
- 缓存 TTL 仍默认 5m，本轮没改。
- 后台全量（`scripts/auto_full_safe.py --run`）未跑。
