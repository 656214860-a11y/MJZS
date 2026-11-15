# R2519 结构治理轮·执行结果

## 本轮三问

- **轮次类型**：结构治理轮·执行（§3.3），来源报告《代码重构可优化清单_20261113.md》B 项「长函数 / 大参数列表收口」，条目：参数个数棘轮收口。
- **测试跑了吗、三个基线过了吗**：跑过了。默认冒烟 8/8；架构门禁 420/420 OK（含 `test_complexity_ratchet` 参数个数棘轮）；定向 `run_selftests.py -k recon_service` 48/48。全量未跑（本轮未命中 §5 全量触发条件，属结构治理常规轮；最近真实全量仍为 R1624）。
- **project_status.md 的欠账少了吗**：参数个数登记表 `PARAM_CAPS` 由 49 项降到 45 项（删除 `recon_service.py` 的 4 项：`run` 13、`collect` 10、`_search_all` 8、`_fetch_all` 8），登记表只降不升，未新增欠账。

## 范围与改动

| 文件 | 改动 |
|---|---|
| `recon_service.py` | 新增 `ReconPorts` frozen dataclass 收拢注入项；`run`(13 参)→`run(project, target, material_source, *, ports)`、`collect`(10 参)→`collect(target, material_source, *, ports)`；内部 `_search_all`/`_fetch_all` 改收 `ports`；新增 `_resolve_ports` 补默认 sender/pause。返回形状不变。 |
| `skill_tools.py` | `_recon_card` 调用点改传 `ports=ReconPorts(...)`，行为不变。 |
| `desktop_idea_chat.py` | 长函数收口（B 项同类）：提取模块级 `_row_signature`/`_visible_rows`/`_brief_field_factory`/`_entry_text`/`_append_in_batches` 五个辅助函数，替换 `IdeaChatMixin` 内嵌闭包，行为不变。 |
| `tests/test_recon_service.py` | 调用点同步改 `ReconPorts(...)`，断言未动、未弱化。 |
| `tests/architecture/test_complexity_ratchet.py` | `PARAM_CAPS` 删除 `recon_service.py` 的 4 项登记（run/collect/_search_all/_fetch_all），其余登记原样保留。 |

## 验证

- 定向：`run_selftests.py -k recon_service` → 48 条用例 0.9 秒，0 红（改前 `recon_service.run` 13 参、`collect` 10 参已在 `PARAM_CAPS` 登记为超线项，本轮收口后从登记表删除，属「先红后绿」：改前 `test_complexity_ratchet.test_parameter_count_does_not_grow` 因登记表存在超线项必然报红，收口并删登记后转绿）。
- 默认冒烟：8/8。
- 架构门禁：420/420 OK，103.9 秒。
- 全量：未跑（不命中 §5 全量触发；如需凭据以 `full-safe-receipts.json` 为准）。

## 收尾

- 队列：无匹配 ID（自启结构治理轮，`maintenance-queue.json` 无对应条目，未冒领）。
- 已提交：见 commit 记录。
