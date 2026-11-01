# R2188 结果：open_https 跨来源跳转去凭据、手动制作摘要只算一次（缺陷轮）

## 三问
- 轮次类型：缺陷轮（§3）。用户要求整理 /code-review 全项目扫描清单的后 5 条（第 6～10 条）。本轮修第 6 条的根因和第 7 条；第 10 条接下来按结构治理轮做；第 8、9 条本轮不动，理由见「未做」。
- 来源条目（本会话 /code-review 清单原文摘录，清单未落盘）：
  - 第 6 条（`platform_tools.py:345`）：「open_https 自称『唯一出站 HTTP(S) 入口』，却用默认 urlopen 跟随重定向并转发全部请求头……account_client.request 经 open_https 带 Bearer 令牌访问账号服务，服务端或中间设备返回跳转（含 https→http 降级）时令牌会被转发到新地址。」
  - 第 7 条（`stage_flow.py:316`）：「summary_lines(project=None)（stage_models.py:241 的调用方式）先调 step_summary，step_summary 内部又以 project 调一遍 summary_lines……打开一次手动制作弹窗，会在 Tk 线程上执行 stage_parallel.evaluate 3 次。」
- 轮次号：开工不领号，提交前一刻领 R2188。
- 测试和三个基线：在 worktree `happy-jennings-48da69`（分支 `codex/wip-R2175`，基于 `68bd1c84`）上运行，经 gui_hidden。
  - `run_selftests.py -k open_https_redirect stage_flow_summary test_stage_flow test_stage_parallel test_core test_execution_deadline account_offline master_skill_update pet_llm api_cache_usage manual_plan model_pool_redirects latent_defects_r2175 test_api`：14 个文件 439 条全过。
  - `smoke_test.py --affected platform_tools stage_flow`：9 项全过（含默认冒烟 8 项），其中定向自检 33 个文件 1243 条，0 个文件有红。
  - `smoke_test.py --architecture`：411 条红 1 条，即 `test_round_baselines.test_round_number_continuous`（运行时报 2153 != 2176；本报告入库后同理为 2153 != 2189）。本分支新增了结果报告，按规定不写状态页，合并轮登记后转绿。
  - 全量 `--all --safe` 本轮未手动运行，由提交后钩子后台补跑。
  - 真机未手动核对。
- `project_status.md` 欠账：没有减少，也没有新增（本分支不写状态页，合并轮登记）。

## 根因
1. 跳转带走凭据：`open_https` 调 `urllib.request.urlopen`。默认 `HTTPRedirectHandler.redirect_request` 构造下一跳请求时，把原请求头原样复制过去（只去掉 Content-Length／Content-Type），不看目标是不是同一来源；301／302／303／307／308 都跟。`account_client.request` 经这条入口带 `Authorization: Bearer <令牌>` 访问账号服务，`agent/core.request`、`master_skill_update._fetch` 也走它。只要回一个跳到别的主机、端口或 https→http 的跳转，Authorization／Cookie 就发给了跳转目标。
2. 摘要互相调用：`summary_lines` 不带项目时转去 `step_summary`，`step_summary` 拼 `lines` 时又带同一个项目调回 `summary_lines`，两边各算一遍 `selected_skills`／`paid_count`／`blockers`／`model_label`。
   - 打开了项目：`summary_lines` 跑 3 遍 `stage_parallel.evaluate`（两次 `blockers`、一次 `gate_text`），`stage_models.plan_window` 随后再调一次 `blockers`，共 4 遍。每遍都按门禁读资产索引、台账与批次，全在 Tk 线程上。
   - 没打开项目：`project_of` 返回 None，两边以 None 互相调用。无门禁的 8 个阶段一直递归到 RecursionError；有门禁的 5 个阶段（animatic、assets、keyframe、previs、video）先在门禁检查里拿 None 当路径，抛 TypeError。`stage_models.plan()` 把异常收成「未能打开操作确认窗口，请稍后重试。」，看不出真正原因。

## 改动
- `platform_tools.py`（L0）：
  - `open_https` 不再调 `urlopen`，改用 `build_opener` 建的 opener，把默认重定向处理器换成 `CredentialSafeRedirect`（`HTTPRedirectHandler` 子类）。重定向照常跟随；跳到另一来源（协议、主机、端口任一不同，端口写坏按不同来源）时，从下一跳请求里去掉 Authorization、Proxy-Authorization、Cookie。同一来源（含相对地址、主机大小写不同、写明默认端口）照旧带上。
  - 不带 `context` 时 opener 只建一次、之后复用，与 `urlopen` 的全局 opener 相同（每建一个都要重装一遍系统根证书，本机实测约 20 ms）；带 `context` 时每次新建，与 `urlopen(context=…)` 相同。代理、超时和 `current_execution()` 截止时间的处理不变。程序里没有 `install_opener`，不经全局 opener 不影响别处。
- `stage_flow.py`（L3）：
  - 新增 `_summary_data`：模型、SKILL、付费、预计秒数、依赖只算一遍。新增 `_lines`：只拼行，内容是原 `summary_lines` 的后半段，未改。
  - `summary_lines`、`step_summary` 都先定项目再调这两个函数，不再互相调用；`step_summary` 返回的键和顺序不变。
  - `blockers` 遇 `project is None` 返回空列表，与 `state_of`／`selected_skills`「读不出来就当空」的口径一致。
  - `evaluate` 次数：`summary_lines` 3 → 1，`step_summary` 3 → 2（另一遍是 `gate_text`），`plan_window` 一路 4 → 2。

## 测试
- 新增 `tests/test_open_https_redirect.py`（3 条）。只换掉贴着网络的 `http_open`／`https_open`，跳转走 urllib 真实机制（同 `test_model_pool_redirects`）：
  - 跳到另一来源：换主机、https→http、换端口、子域、用户名位置伪装主机、端口写坏，各配 301／302／303／307／308，有无 `context` 各一遍。第一跳带凭据，第二跳不带，普通头照带。
  - 同一来源：换路径、相对地址、主机大写加显式 443。第二跳照带凭据。
  - POST 遇 303 跳到另一来源：变成不带正文的 GET，也不带凭据。
- 新增 `tests/test_stage_flow_summary.py`（5 条）：没打开项目时 13 个阶段都出 2～4 行、两个入口一致，`blockers(None, …)` 为空；打开项目时数 `stage_parallel.evaluate` 的调用次数（`summary_lines` 1 遍、`step_summary` 2 遍）；上游失败时两个入口给出相同的依赖警告。
- 修复前红：把 `68bd1c84` 版 `platform_tools.py`、`stage_flow.py`（已与该提交逐字节比对）放在 `sys.path` 最前，用 unittest 跑这两个新文件（不涉及 Tk）：

```text
test_open_https_redirect ran 3 failures 61 errors 0
test_stage_flow_summary ran 5 failures 2 errors 18
FAILED (failures=63, errors=18)

AssertionError: 'Bearer SYNTHETIC' is not None
（同一断言共 61 条：6 个跨来源地址 × 5 种跳转 × 有无 context，加 POST 303 一条）
RecursionError: maximum recursion depth exceeded
（8 条：script、script_structure、storyboard、continuity、final、audio、edit、delivery）
TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'NoneType'
（10 条：animatic、assets、keyframe、previs、video 在两个「没打开项目」用例里各一条）
AssertionError: 3 != 2
AssertionError: 3 != 1
```

- 修复后：8 条全过。
- 已有测试：`tests/test_core.py` 三处、`tests/test_execution_deadline.py` 一处的 mock 目标由 `urllib.request.urlopen` 改为 `urllib.request.OpenerDirector.open`。`open_https` 不再经过 `urlopen`，原目标拦不住真实请求，`assert_not_called` 也会恒真。断言未动。

## 未做
- 第 6 条后半「再让 model_pool、volcengine/wan、qwen_setup 都走 open_https」：
  - `qwen_setup` 已在 R2175 改走 `model_pool.http_transport`（不跟随重定向）；`comfy_service` 只连本机，不带凭据。
  - `model_pool`、`agent/volcengine`（`wan` 复用）、`local_video`、`seedream_api`、`tts_api` 各自带一份不跟随重定向的处理器（另有独立工具 `batch_frames_tool` 一份），本来就不会把凭据转给跳转目标。把它们收成一处属于结构治理，约 7 个模块，按每轮不超过 3 个模块至少 3 轮，单独提出。
- 第 8 条（回收清单每移一项就整份重写）：与 O38 写前计划的逐项落盘契约冲突。`tests/test_recycle_write_ahead.py:59` 要求每移一项都已记进清单，中途断电能按清单恢复。改不改要用户定。本机临时目录、每项 1 字节文件的实测：

  | 项数 | 现状耗时 | 清单写入 | 写入字节 | 只写计划和提交 |
  | ---: | ---: | ---: | ---: | ---: |
  | 1 | 14.8 ms | 3 次 | 1120 | 19.5 ms |
  | 20 | 81.7 ms | 22 次 | 118958 | 24.3 ms |
  | 100 | 404.9 ms | 102 次 | 2713918 | 101.2 ms |
  | 300 | 1338.1 ms | 302 次 | 24041318 | 261.2 ms |

- 第 9 条（`_project_root`／`_require_gateway` 各复制 8～9 份）：`architecture.md` 维护边界（R1327、R1313 两条）把「各 L2 模块各自持有 ProjectContext 校验」写成惯例。改成共享函数要先改这条约定，再按每轮不超过 3 个服务分至少 3 轮，单独提出。

## 用户需做
重启应用后生效。
