# R1716：修复轮（源码）——命令行客户端取档案区分 CLI／桌面

## §7 三问

1. **本轮属于 §3 哪种类型？** **修复轮（§3.2）**。只修 R1706b 遗留的档案选择歧义：`workflow_settings.current()` 的 `client-cli` 分支取到共用别名的桌面档案。按任务书只改 `client_profiles.py`、`workflow_settings.py`、`tests/test_client_profiles.py`（只追加）和本结果文件；**未领轮次号、未改 `project_status.md`、未执行任何 git 写命令**（仅只读 `git status`／`git diff`）。
2. **测试跑了吗？三个基线过了吗？** 默认冒烟 **9/9 通过、0 失败**（当前冒烟项为 9 项，不是历史 8 项）；架构只复验与本改动相关的 5 个棘轮文件 **19/19 OK**，**未跑全量 368 条架构门禁**；**未跑** `--all --safe`，无全量凭据。任务书定向命令 **372 条、22.0 秒、1 个文件有红**，唯一红是任务书预先说明的 `test_writing_api` DeepSeek 文件名本机环境项（见 C／D），其余 0 红；`test_client_profiles` **24/24 OK**（既有 23 条＋新增 1 条）。
3. **project_status.md 的欠账少了吗？** 没有。任务书禁止改 `project_status.md`，也未领轮次；本轮不参与状态页欠账记账，由 Claude 验收后处理。

## A 查清结论

### 根因

- `workflow_settings.current()` 在 `explicit_engine == 'client-cli'` 分支先用**与调用模式无关**的 `client_profiles.profile_for_model(selected, item)` 取档案元数据（`client_profile`／`delivery`／`app_name`／`process_names`／`window`）。
- `客户端档案.json` 中 `opencode-desktop` 排在 `opencode-cli` 之前，且桌面档案带 `opencode` 别名；`profile_for_model()` 按 `model_id → model → label → program` 顺序调用 `profile()`，`profile()` 返回加载顺序中第一个命中的档案。
- 因此模型池记录 id 恰为 `opencode`（同时带 CLI 程序路径、`call_mode='CLI'`）时，`current()` 的 `client-cli` 分支拿到 `opencode-desktop`：`client_profile='opencode-desktop'`、`delivery='paste'`，投递方式错误。
- 既有用例没有覆盖 `workflow_settings.current()` 的 `client-cli` 档案选择，所以该问题一直未红。

### 修前复现（红）

新增用例在**未改生产代码**时先跑：

```text
python -B -m unittest tests.test_client_profiles.CliProfileSelectionRegressionTests.test_regression_r1706c_client_cli_branch_selects_cli_profile -v
```

实际结果：

```text
FAIL: test_regression_r1706c_client_cli_branch_selects_cli_profile
  File "...\tests\test_client_profiles.py", line 345, in test_regression_r1706c_client_cli_branch_selects_cli_profile
    self.assertEqual(config['client_profile'], 'opencode-cli')
AssertionError: 'opencode-desktop' != 'opencode-cli'
- opencode-desktop
+ opencode-cli
Ran 1 test in 0.062s
FAILED (failures=1)
```

用例走真实 `workflow_settings.current(临时项目, 'writing', model_snapshot=('opencode', record))`，record 为 `provider='desktop'`、`call_mode='CLI'`、`program='C:/tools/opencode-cli.exe'`；同时断言 `engine == 'client-cli'`、`client_profile == 'opencode-cli'`、`delivery == 'cli_file'`。修前红在档案选择，不是构造错误。

## B 改动

### `程序\client_profiles.py`

- `profile_for_model(model_id='', item=None, *, kind='', refresh=False)`：新增可选 `kind`（`desktop`／`cli`）。指定时逐个候选值改走 `profile_for_mode(value, kind)`，只返回该调用模式的档案；`kind` 为空或非法值时保持原有 `profile()` 首次命中行为，既有调用（如 `engine_for_model()`、`model_pool.provider_name()`）语义不变。
- 只增加过滤分支，未改档案加载顺序、别名规则或其他函数。

### `程序\workflow_settings.py`

- `current()` 的 `desktop-app`／`client-cli` 分支按引擎映射 `wanted = 'desktop' if desktop-app else 'cli'`：
  - `profile_for_model(selected, item, kind=wanted)`；
  - 兜底 `profile_for_mode(selected, wanted)`（不再用与引擎无关的 `model_pool.call_mode(...)` 二次选档）。
- 桌面分支只取桌面档案，命令行分支只取 CLI 档案；未改 `ENGINES`、投递字段名或其他分支。

### `程序\tests\test_client_profiles.py`（只追加）

- 末尾新增 `CliProfileSelectionRegressionTests.test_regression_r1706c_client_cli_branch_selects_cli_profile`，使用空 `tempfile` 项目根与显式 `model_snapshot`，不读用户项目、不发请求。
- 既有 23 条用例与断言未动，未加 skip。

### 明确未改

- `model_pool.py` 未改（行号登记不动）。
- `配置\客户端档案.json` 未改；未调整 `opencode-desktop`／`opencode-cli` 的顺序或别名，避免把修复变成数据顺序依赖。
- UI 批次文件未碰（工作区中原有 UI 批次未提交改动，非本轮产生，见 D）。

## C 验证（本轮实跑，非历史凭据）

| 命令 | 实际结果 |
| --- | --- |
| 修前：`python -B -m unittest tests.test_client_profiles.CliProfileSelectionRegressionTests.test_regression_r1706c_client_cli_branch_selects_cli_profile -v` | **FAIL**，`'opencode-desktop' != 'opencode-cli'`，1 条失败 |
| 修后同一条用例 | **OK**，1 条、0.059 秒 |
| `python -B -m unittest tests.test_client_profiles` | **24/24 OK，0.664 秒**（既有 23＋新增 1） |
| `python -B run_selftests.py -k opencode qwen claude engine model_pool workflow desktop_idea_chat client_profiles environment_check stage_execution writing_api pet_models`（最终代码） | **372 条、22.0 秒、1 个文件有红**：`test_writing_api#1` 的 DeepSeek 文件名环境项；`test_client_profiles` 24 条全绿，其余 0 红；跳过 0 条 |
| `python -B smoke_test.py --affected client_profiles workflow_settings` | 快速检查 **通过 9 项、失败 0 项**；门禁 `run_selftests.py --serial -k client_profiles workflow_settings` **26 条、2.4 秒、0 红**，`ALL TESTS PASSED` |
| `python -B -m unittest tests.architecture.test_function_size_ratchet tests.architecture.test_module_size_ratchet tests.architecture.test_layers tests.architecture.test_unification_ratchet tests.architecture.test_coverage_audit_ratchet`（额外自检） | **19/19 OK，97.027 秒**，改动未引入行号／分层／棘轮新增债务 |
| `git status --porcelain`（只读） | 本轮改动仅 `程序/client_profiles.py`、`程序/workflow_settings.py`、`程序/tests/test_client_profiles.py`（另有 UI 批次既有改动与未跟踪测试，非本轮产生） |

### 唯一红的如实标注

`test_writing_api.WritingApiTests.test_api_formal_script_reuses_download_path_and_versions_changed_text`：

```text
AssertionError: 'DeepSeek' not found in 'proj_自然剧本_自定义_20261019.md'
```

- 该用例不注入模型池，读本机 **gitignored** 的 `配置/宠物/配置.json`；本机池没有该 label，`provider_name` 返回「自定义」。
- 与本轮改动的 `client_profiles`／`workflow_settings` 档案选择无关；`model_pool.py` 的 `provider_name()` 本轮未改。R1714 结果文件已记录同一条红并判定为环境项。
- 按任务书「若仍红，属本机 gitignored 模型池缺 label 的环境项，如实标注」处理，**未修**。

## D 断言未动与需裁决／遗留

1. **断言未动**：既有 23 条 `test_client_profiles` 用例和断言原样通过；本轮测试文件 diff 只有末尾新增 1 条用例，未弱化、删除或跳过任何断言。
2. **`model_pool.py` 未动**：确认未修改，行号登记不受影响。
3. **全量门禁未跑**：任务书只要求两条验证命令，未跑全量架构 368 条与 `--all --safe`；已额外跑 5 个相关架构棘轮文件 19/19 绿，但不能写成「全量架构通过」。
4. **工作区存在 UI 批次既有改动**：`desktop.py`、`pet_models_ui.py` 等与新增 UI 测试文件在开工前已处于修改／未跟踪状态，本轮未碰；全量结果如受其影响应由验收方区分。
5. **边界行为（非新增缺陷）**：若模型池记录 id 为共用别名（如 `opencode`）且既无 CLI 程序路径、也无 CLI 专属 id／label，过滤后无法解析 CLI 档案，`client_profile` 为空、`delivery` 走 `client-cli` 默认 `cli_stdin`；这比修前误取桌面 `paste` 更安全。是否需要为这类「别名 + 无路径」补一条更明确的兜底提示，交裁决。
6. **需裁决**：`test_writing_api` 环境项是否需要在可读本机模型池的会话补 label；不属本轮允许范围。
7. **自审清单**：四条（验收、范围、验证真实、未引入新问题）通过；修复轮追加审「同类 bug 未修」——`profile_for_model` 的另一消费者 `model_pool.provider_name()` 只用于显示名，不参与投递选择，按最小改动未扩范围。

## E 提交

**未提交。** 未执行任何 git 写命令，未领轮次，未改 `project_status.md`；验收与提交由 Claude 完成。

## F 改动文件

- `程序/client_profiles.py`
- `程序/workflow_settings.py`
- `程序/tests/test_client_profiles.py`（仅追加）
- `程序/tasks_round/tasks_round_pending_1706c_result.md`（本文件）

## 独立验收（Claude，隔离验证工作树 HEAD＋本批文件）

- 定向 `-k opencode qwen claude engine model_pool workflow desktop_idea_chat client_profiles …`：379 条 0 红（主树的 `test_writing_api` DeepSeek 文件名红是本机环境项，隔离树绿）。
- `smoke_test.py --affected client_profiles workflow_settings`：9/9 通过。
- `smoke_test.py --architecture`：368/368 OK。
- 先红证据核对：新用例修前 `'opencode-desktop' != 'opencode-cli'`。断言未动。
- 待裁决：别名无 CLI 路径时得空 client_profile、投递 cli_stdin——比修前安全，暂不改。
