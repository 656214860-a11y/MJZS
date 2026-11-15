# R2489 结果：/simplify 优化今天提交的全部代码改动（零行为变化）

## 三个必答（§7）

1. **本轮属于 §3 哪种类型？**
   结构治理轮·执行（§3.3），由用户 `/simplify` 指令触发、明确指定「全部今天改动的源码」范围。今天（R2419→R2477，git 区间 `e58deade^..HEAD`）共 54 个源码文件（34 生产模块 + 20 测试），按子系统聚类后由 6 个并行子代理做「审计 → 零风险最小重构 → 定向验证」，最终只落地 5 个文件的纯减法/去重改动（净 −20 行），其余 49 个文件经逐项反例论证判定零改动（已是今天三层收口产物或不足提取阈值）。不新增功能、不改用户数据、不改分层/契约/导入方向、不弱化任何断言。

2. **测试跑了吗、三个基线过了吗？**
   - 定向（子代理各自验证，全部真实通过）：
     - `run_selftests.py --serial -k test_client_profiles test_qwen_adapter test_request_ledger test_model_metering test_pet_llm` → 129 条 0 红
     - `run_selftests.py --serial -k test_model_gateway_robustness test_model_router_parse test_model_router_diagnostics test_adapter_failure_conformance test_model_failure_route` → 38 条 0 红
     - `run_selftests.py --serial -k test_model_manager_actions test_pet_settings test_ui_batch7_settings_models` → 84 条 0 红
     - `run_selftests.py -k aigc_lint model_gateway git_hooks master_import` → 全绿（9+16+14+4）
   - 默认冒烟：**未单独跑**（本轮为纯减法改动，`--affected` 定向门禁已覆盖全部改动模块的消费者；默认冒烟基线 8/8 未在本轮复验）。
   - 架构门禁：`smoke_test.py --architecture` 实跑 **420 条，4 失败**（详见「发现」）——这 4 个失败全部是**今天已提交 HEAD 的预存欠账**，经 `git diff HEAD -- <文件>` 证实本改动未触碰这些文件，非本改动引入。
   - 全量：未跑（分支不累计全量欠账；见 §5）。

3. **`project_status.md` 的欠账少了吗？**
   本轮不直接减少既有欠账条目；**新发现并如实登记 2 个今天提交留下的架构门禁欠账**（见下），由用户决定后续单独一轮处理（用户本轮明确选择「只提交 /simplify 改动，欠账只报告不改」）。

## 改动清单（5 文件，净 −20 行）

| 文件 | 改动 | 依据 |
|---|---|---|
| `程序/model_router.py` | 删死常量 `_REQUIRED_RESPONSE_FIELDS`（0 引用）；提取 `CIRCUIT_RETRY_STATUS = (0, 408, 425, 429, 500, 502, 503, 504)` 替换 3 处内联元组，注释标明与 `model_metering.REPLAYABLE_RETRY_STATUS` 同口径但刻意不含 409 | 死代码删除 + 3 处重复提取 |
| `程序/qwen_adapter.py` | 删死函数 `install_root()`（`command()` 改走 `client_profiles.qwen_command` 后成孤儿，0 引用） | 死代码删除 |
| `程序/pet_models_ui.py` | `_ModelManager.fill` 中 5 个可选字段（context_length/rpm/group/weight/note）的「delete+条件 insert」重复块（14 行）合并为 4 行循环；`note` 无值时的空串写入与「保持清空」等价（注释已说明） | 5 处相同结构重复提取，与同文件 `new_one` 方法口径一致 |
| `程序/tests/test_aigc_lint.py` | 删 3 条未使用 import（tempfile/Path/mock） | 死导入 |
| `程序/tests/test_model_gateway_robustness.py` | 删 2 条方法内冗余 `import urllib.request`（模块顶部已有） | 冗余导入 |

未改动的 49 个文件（含 request_ledger/pet_llm/model_metering/client_profiles 台账簇、writing_api/workflow_settings/skill_tools 等 12 文件簇、aigc_lint/sync_master/round_claim 工具簇、desktop_idea_* / pet_models_ui 其余 UI 簇、tests/architecture 门禁文件）经逐项反例论证：疑似重复点要么是今天三层收口（R2419 简报拆分 / R2443 反向依赖下沉 / R2467 skill 去重）的刻意设计，要么不足 3+ 提取阈值或语义有细微差异，强行提取属负收益或越界。

## 发现（今天提交留下的预存欠账，本轮只报告不改）

架构门禁 420 条中 4 个失败，均非本改动引入（`git diff HEAD -- desktop_idea_chat.py api_endpoints.py` 为空）：

1. **`desktop_idea_chat.py::IdeaChatMixin 765 行 > 上限 748`** — 今天最后提交 R2477 把该类撑过复杂度棘轮；R2477 结果文件自述「架构门禁…均未运行（沙箱限制）」，欠账从未被发现。修复需拆类（结构治理，需单独授权）。
2. **`api_endpoints.py` 2 处裸 `json.loads`（`_http_transport`/`http_stream`）未登记「第四项」台账** — 今天 R2470 新增，同样未跑架构门禁。修复需登记台账或改用正式 JSON 读入口。
3. **`screenplay-gate-engine.md` 缺失（1 条）+ 同源 `sd-decision-engine/SKILL.md` 缺失** — `程序/skills/00全流程SKILL/AIGC创作全流程` 是 **git 子模块**，本工作树未初始化子模块（目录为空），属环境限制，非代码问题。

根因：今天 R2470/R2477 两个提交在沙箱内无法派生子进程跑架构门禁，合入 master 时未复验，留下真实欠账。

## 自检结论

- 5 处改动均为纯减法/去重，逐处行为等价性已论证（见改动清单「依据」列）。
- 定向测试全绿（见上），架构门禁 4 失败已定位为预存欠账。
- 未提交全量；未弱化任何断言；未触碰测试断言值、分层登记表、复杂度棘轮 cap、覆盖率基线。

## 已提交

- 提交方：DeepSeek Assistant（本会话）；领号 R2489（`round_claim.py next`），工作树已切至 `codex/wip-R2489`。
- 待提交：本结果文件 + 5 个改动文件（提交信息 `R2489: 结构治理 /simplify 今天提交代码改动（净-20行零行为变化）`）。
- 合入 master 与 `project_status.md` 轮次头更新由后续合并轮执行（仅 master 可提交 `project_status.md`，规则 41）。
