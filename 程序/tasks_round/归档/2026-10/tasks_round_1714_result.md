# R1714：修复轮——客户端档案不得改写既有内建路由（OpenCode CLI 回归，R1706b）

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 **修复轮**（任务书 R1706b）。按任务书未领号、未改 `project_status.md`、未执行任何 git 写命令；只改允许文件并在验收后由 Claude 提交。
2. **测试跑了吗？三个基线过了吗？**
   - 默认冒烟：**8/8 通过，0 失败**（本轮实测，exit=0）。
   - 定向引擎／模型路由：任务书命令 `run_selftests.py -k opencode qwen claude engine model_pool workflow desktop_idea_chat client_profiles environment_check codex_paste stage_execution` → **316 条用例、14.9 秒、0 个文件有红、实际跳过 0 条**（ALL TESTS PASSED，exit=0）。
   - 架构门禁：按任务书**未跑** `smoke_test.py --architecture`；只做了 5 个相关子模块的定向复验，14 条中 1 红（`desktop_storyboard_page.py::storyboard 324>323`，UI 批次未提交改动，非本轮）。
   - 全量回归：按任务书**未跑** `--all --safe`，未写入或冒用全量凭据；全量欠账状态不变。
3. **project_status.md 的欠账少了吗？** 没有。任务书明确禁止改状态页与领号；本轮只交修复、测试与结果文件，验收与提交由 Claude 做。

## A 根因

### 复现（修前）

```powershell
cd D:\漫剧制作助手\程序
& '..\运行环境\Python\python.exe' -B -m unittest tests.test_opencode_engine.SettingsAndRoutingTests.test_opencode_is_a_cli_engine_not_a_desktop_model -v
```

修前输出：

```
FAIL: test_opencode_is_a_cli_engine_not_a_desktop_model
  File "tests\test_opencode_engine.py", line 230
    self.assertEqual(model_pool.call_mode({'provider': 'desktop', 'model': 'opencode'}), 'CLI')
AssertionError: 'Desktop' != 'CLI'
```

### 真正根因（不是「档案数据写错」一条）

1. `model_pool.call_mode()` 在无显式 `call_mode`、`provider == 'desktop'` 时取
   `engine = desktop_engine(model_id) or desktop_engine(value['model']) or value['model']`。
2. R1706 把 `desktop_engine()` 的兜底改为 `client_profiles.engine_for_model(name)`。
3. `engine_for_model → profile_for_model → profile()` 按 `load_profiles()` 的**档案文件顺序**逐个匹配
   id／display／aliases／exe 主名；`配置/客户端档案.json` 中 `opencode-desktop` 在前（第 98 行），
   且其 `aliases` 含 `opencode`；`opencode-cli` 在后（第 116 行）。
4. 于是 `profile('opencode')` 命中 **opencode-desktop** → `engine_for_model` 返回 `desktop-app`
   → `call_mode` 的 CLI 集合不含 `desktop-app` → 返回 **Desktop**。

同一机制还造成两条 R1706 新红／新偏差：

| 名称 | R1706 之前 | R1706 之后（修前） | 原因 |
| --- | --- | --- | --- |
| `opencode` | `''` → `call_mode` 用字面名判 **CLI** | `desktop-app` → **Desktop** | `opencode-desktop` 的 `opencode` 别名抢先 |
| `claude` | `''` → 字面名判 **CLI** | `desktop-app` → **Desktop** | `claude-desktop` 的 `claude` 别名／`claude.exe` 主名抢先 |
| `gemini`（模型池记录显式 `call_mode: API`） | `''` → 尊重记录为 **API** | `desktop-app` → 被当成桌面 | `gemini-desktop` 的 `gemini` 别名抢先 |

`gemini` 那条正是 `tests.test_writing_api.test_desktop_routing_honors_explicit_mode_and_legacy_provider`
在 R1706 后新红的根因（用 R1706 版 `desktop_engine` 做变异探针可稳定复现，见 C）。

## B 改动

只改 3 个允许文件；`配置/客户端档案.json`、`workflow_engines.py`、`workflow_settings.py` 均未改
（根因不在数据，也不在这两个引擎编排模块）。

### 1. `程序/client_profiles.py`（+5 行）

新增内建路由保留名单：

```python
BUILTIN_MODEL_NAMES = ('codex', 'claude', 'qwen', 'opencode',
                       'codex-desktop', 'gemini', 'google-gemini')
```

含义：这些名字在 R1706 之前就有内建路由（内建 CLI 引擎或旧桌面别名），档案只给识别不了的新客户端兜底。

### 2. `程序/model_pool.py`（2 行改，**行数不变**）

`desktop_engine()` 在档案兜底前先查保留名单：

```python
    # 新客户端由档案决定路由，但 R1706 之前就有路由的名字优先，档案只给它们兜底。
    return '' if alias in client_profiles.BUILTIN_MODEL_NAMES else client_profiles.engine_for_model(name)
```

这里返回 `''`（而不是返回 `qwen`／`opencode` 等引擎名）是刻意的：这正是 R1706 之前的结论，
`call_mode` 会继续按字面模型名归为 CLI；`workflow_settings.current` 也继续按模型池记录的
`call_mode`／`provider` 决定，不会被档案提前改判。

### 3. `程序/tests/test_client_profiles.py`（只在末尾追加 2 条，不动既有 21 条）

- `test_regression_r1706b_builtin_cli_models_keep_cli_call_mode`：`opencode`／`qwen`／
  `claude-code`／`claude`／`claude-code-cli` 的 `call_mode` 必须是 `CLI`，且 `desktop_engine`
  不得为 `desktop-app`。
- `test_regression_r1706b_new_clients_still_use_the_profile_fallback`：`gemini`／`google-gemini`／
  `codex-desktop` 不再被档案改判；`profile_for_mode('gemini','Desktop')` 仍能定位
  `gemini-desktop`；新客户端 `deepseek-harness → desktop-app`、`dsh → client-cli` 的兜底仍生效。

### 为什么不改档案别名，而选「内建优先」

- `opencode` 别名必须留在 `opencode-desktop` 上：`profile_for_mode('opencode','Desktop')` 靠它
  找 OpenCode 桌面程序；删别名或改匹配顺序会破坏 Desktop 模式检测。
- 内建优先是单点、与档案数据无关的规则，语义就是任务书第 1 条；档案继续作为新客户端兜底。
- **行号约束**：`维护记录/架构统一基数.json` 为本模块登记了行号型债务点
  `model_pool.py` 547／575／873／919，而任务书允许清单**不含**该台账文件。因此把保留名单放在
  `client_profiles.py`、并让 `model_pool.desktop_engine` 的改动保持净 0 行；复验后上述 4 个
  行号与 `HEAD` 逐行一致（见 C）。

## C 验证（全部本轮实测；未运行项如实标注）

| 命令 | 实际结果 |
| --- | --- |
| `python -B -m unittest tests.test_opencode_engine.SettingsAndRoutingTests.test_opencode_is_a_cli_engine_not_a_desktop_model` | 修前 FAIL（Desktop != CLI）；修后 **OK** |
| `python -B -m unittest tests.test_client_profiles` | **23/23 OK**（既有 21 ＋ 新增 2） |
| `python -B -m unittest tests.test_model_pool tests.test_opencode_engine` | **73/73 OK** |
| `python -B -m unittest tests.test_writing_api` | **54 条，1 红**：`test_api_formal_script_reuses_download_path_and_versions_changed_text`（`'自定义'` 文件名）。**与 R1706 无关**，见 D.3 |
| `python -B -m unittest tests.test_writing_api.WritingApiTests.test_desktop_routing_honors_explicit_mode_and_legacy_provider` | 修前（R1706 版 `desktop_engine`）红；修后 **OK** |
| `python -B -m unittest tests.test_client_profiles tests.test_model_pool tests.test_opencode_engine tests.test_writing_api.<上条> tests.test_environment_check tests.test_claude_program_detection` | **115/115 OK** |
| `python -B -m unittest tests.test_skill_notes tests.test_idea_attachments tests.test_writer_style_agent_delivery tests.test_request_freeze_entries tests.test_stage_prompt_governance tests.test_req_anchor_s02 tests.test_writing_cancellation tests.test_stage_model_value` | **85/85 OK** |
| `python -B -m unittest tests.test_model_call_error_kind tests.test_model_diagnostics tests.test_model_failure_route tests.test_model_output_contract tests.test_model_pool_redirects tests.test_model_pool_tools tests.test_model_probe_layers tests.test_model_router_diagnostics` | **84/84 OK** |
| `python -B tests\test_pet_ui.py ModelPoolTests`（库内 `call_mode`／`desktop_engine` 断言） | **26/26 OK** |
| `python -B run_selftests.py -k opencode qwen claude engine model_pool workflow desktop_idea_chat client_profiles environment_check codex_paste stage_execution` | **共 316 条用例，14.9 秒；0 个文件有红；实际跳过 0 条；ALL TESTS PASSED（exit=0）** |
| `python -B smoke_test.py` | **通过 8 项，失败 0 项（exit=0）** |
| `python -B -m py_compile model_pool.py client_profiles.py tests\test_client_profiles.py` | **exit=0** |
| 定向架构子集（layers／cycles／module size／function size／unification） | 14 条，**1 红**：`desktop_storyboard_page.py::storyboard 324 行 > 上限 323`（UI 批次未提交改动，非本轮）；`test_unification_ratchet` 已绿 |
| `tests.architecture.test_static_hygiene`（同上定向子集的一次附带运行） | 1 红：`tests/test_ui_batch3_shell.py:1 invalid non-printable character U+FEFF`（UI 批次新增未跟踪测试文件，非本轮） |

### 行号型棘轮复验

用 `git show HEAD:程序/model_pool.py` 与当前文件逐行对比：`model_pool.py` 旧／新均为 1099 行，
登记点 547／575／873／919 四个行号的内容**逐行一致**；`test_unification_ratchet` 由修前红转绿。

### 变异探针（临时脚本在 `%TEMP%`，不在仓库内）

1. 把 `desktop_engine` 换回 R1706 版本后运行新增的 2 条回归用例：**红**（`opencode`、`claude`
   命中 `desktop-app`；`gemini` 也被改判）。`qwen`、`claude-code` 修前修后都绿，说明断言不是空的。
2. 把 `desktop_engine` 换回 R1706 版本运行 `test_writing_api` 的 gemini 显式 API 用例：**红**
   （`False != True`），证明该红确由 R1706 引入、由本轮修复。
3. 把 `desktop_engine` 与 `provider_name` 一起换回 R1706 之前的实现，再跑 DeepSeek 文件名用例：
   **仍然红**（`'自定义'`），证明该红与 R1706 无关（见 D.3）。

## D「断言未动」与需裁决

### D.1 断言未动

**既有断言未动**：没有修改、弱化、删除任何既有测试，也没有加 skip。`tests/test_client_profiles.py`
的 diff 只有末尾新增的 2 条用例；既有 21 条原样通过。

### D.2 需 Claude 裁决

1. **保留名单的归属**：`BUILTIN_MODEL_NAMES` 放在 `client_profiles.py`（L1）是受「行号型架构台账 +
   允许文件清单」约束的折中。若认为「哪些名字算内建路由」应归 `model_pool.py`，需要同轮更新
   `维护记录/架构统一基数.json` 的 4 个行号点（本轮任务书未授权该文件），建议由 Claude 决定是否另开一轮再搬家。
2. **残留的档案歧义（无红、未改）**：`workflow_settings.current()` 在 `explicit_engine ==
   'client-cli'` 时仍先用**与模式无关**的 `profile_for_model(selected, item)` 取档案元数据。
   若模型池记录的 id 恰为 `opencode` 且带 CLI 程序路径，该调用仍可能返回 `opencode-desktop`
   的 `delivery`／`app_name`。本轮未改：① 它不是已报告的 `call_mode` 回归；② 没有对应用例；
   ③ 修它要再动 `workflow_settings` 的档案选择语义，超出「最小修复」范围。请裁决是否另立一轮。
3. **断言与真实行为**：`claude-desktop` 记录在 `call_mode` 里仍归 `CLI`（因 `DESKTOP_ENGINES`
   映射到 `'claude'`，而 CLI 集合含 `'claude'`）。这是 R1706 之前就存在的口径，不是本轮引入，
   本轮未动；如要纠正需产品裁决。

### D.3 与 R1706 无关的红（如实记录、不修）

`tests.test_writing_api.test_api_formal_script_reuses_download_path_and_versions_changed_text`
（54 条中唯一红）：

- 现象：`assertIn('DeepSeek', formal.name)` 失败，实际文件名 `proj_自然剧本_自定义_20261019.md`。
- 原因：该用例不注入模型池，读本机 **gitignored** 的 `配置/宠物/配置.json`；
  本机池里没有 `DeepSeek V4 Flash` 这个 label（现有 `deepseek-flash`／`deepseek-v4-pro-0813` 等），
  `id_of_label` 原样返回 label、`records.get()` 落空 → `provider_name` 返回 `自定义`。
- 证据：用 R1706 之前的 `desktop_engine` ＋ `provider_name` 实现重跑该单条，**同样红**。
- 处置：**不修**。它不属 R1706 回归，且修复需要改测试／fixture 或本机模型池配置，均不在本轮允许范围。

### D.4 UI 批次未提交改动造成的红（如实标注、不修）

- `tests/test_pet_ui.py::CaptionTests::test_the_caption_is_black_ink`：`pet_ui_support.py` 本轮工作区
  未提交改动把 `CAPTION_INK` 从 `'#000000'` 改成 `COLORS['text_primary']`（实测 `'#1F2937'`），
  断言仍期望 `'#000000'`。**属 UI 批次**，本轮未改该文件。
- `tests.architecture.test_function_size_ratchet`：`desktop_storyboard_page.py::storyboard 324 > 323`，
  `desktop_storyboard_page.py` 在工作区已被 UI 批次修改。**不修**。
- `tests.architecture.test_static_hygiene`：`tests/test_ui_batch3_shell.py` 带 BOM 导致
  `invalid non-printable character U+FEFF`；该文件是 UI 批次未跟踪新增。**不修**。

## E 提交

**未提交，由 Claude 验收后提交。** 本轮未领轮次号、未改 `project_status.md`、未执行任何 git 写命令。

## F 改动文件

- `程序/client_profiles.py`（＋5 行：`BUILTIN_MODEL_NAMES`）
- `程序/model_pool.py`（净 0 行：`desktop_engine` 内建优先）
- `程序/tests/test_client_profiles.py`（只在末尾追加 2 条，既有断言未动）
- `程序/tasks_round/tasks_round_pending_1706b_result.md`（本文件）

## 验收与提交（Claude，2026-10-19）

轮次号 1714 由 Claude 提交时领取（原名 `tasks_round_pending_1706b_result.md`）。Claude 在隔离验证工作树（HEAD＋本批 3 个文件）复跑：任务书定向＋`writing_api`／`pet_models` 共 378 条 0 红、实际跳过 0 条；`--affected model_pool client_profiles` 冒烟 9/9；架构门禁 368/368 OK。R1706 遗留的 `test_opencode_engine` 回归在本提交转绿。执行者报告的 `workflow_settings` 命令行分支可能取到桌面档案一项，另立 R1706c 处理。断言未动。
