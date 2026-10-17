# R1648 验证/基线轮：P1-3 收官（覆盖率审计 19–23 全部入账）

- **本轮类型**：§3.10 验证/基线轮（门禁＋台账＋判据文档；不改产品运行期代码、不改契约、不搬目录、不重命名）。
- **测试与三个基线**：默认冒烟 **8/8**；行尾＋轮次基线 **21/21**；架构门禁 **359/359（288.9 秒，本轮实测，含本轮新增 2 条）**；定向 `tests.architecture.test_coverage_audit_ratchet` **6/6（71.3 秒，含金丝雀 22／23 与双向棘轮）**。**未跑全量**（欠账未到门禁线 8）。
- **欠账**：改程序源码 → 全量欠账 **4/8 → 5/8**。
- **清单依据**：`tasks_round/tasks_round_1645_result.md` J 节 P1-3（覆盖率审计 19–23 未入账；判据＝19–23 每条都有 disposition＋理由，且由棘轮断言）。

## A 改动

1. `程序/tests/architecture/test_coverage_audit_ratchet.py`：
   - 新增 **第 23 项冻结谓词** `_scan23()`：目标事件 `stage.completed`／`script.completed` 的**字面量**发送点（`pet_bus.emit_safe(...,kind,...)` 与 `*._emit(kind)`），且**同一函数内没有核验证据**（`emit_verified_completion`／`_completion_evidence`／`verified_stage_output`，判定＝点号名含 `verif` 或等于 `self._completion_evidence`）才命中；权威白名单 `P23={stage_completion_service, pet_bus}`。
   - `AUDIT_SECTIONS` 纳入 **22、23**，两段进入既有双向棘轮（pending ↔ 冻结谓词实际命中完全相等）。
   - 新增 **第 19 项归并断言** `_audit19_config_writes()`：L2 中「含 `config.json` 字面量且出现写调用」的函数，必须是 `架构统一基数.json.第三项` 已登记项的子集——把「归并第 3 项」变成可执行断言，而不是一句说明。
   - 新增 2 条用例：`test_audit19_is_merged_into_the_third_item_scope`、`test_audit19_to_23_each_record_a_disposition_and_reason`；金丝雀名单补 `23`。
2. 新增金丝雀 `程序/tests/architecture/_canary/audit23_violation.py`（`pet_bus.emit_safe(bus, errors, 'stage.completed', stage='script')`，模块不在白名单且无核验证据）。
3. `程序/维护记录/架构统一基数.json`：新增 `覆盖率审计19`（`disposition=merged`）、`覆盖率审计22`（`reused`）、`覆盖率审计23`（`frozen`），各带理由、`count=0`、`items=[]`；给既有 `覆盖率审计20`／`覆盖率审计21` 补 `disposition=frozen`＋理由（此前只有 count／baseline_pending／items，无法满足「每条都有处置与理由」）。
4. `程序/维护记录/覆盖率审计判据_20261001.md`：文首口径改为「19–27 均已入账」；第 19 项真候选列改为「归并第 3 项扫描器目标集合」；第 23 项三档数字更新为实测（4／4／0，宽口径 37 说明保留在措辞外）；归并映射表 23 行改为「R1648 冻结窄谓词」；「真候选逐条清单与初判」补 19／22／23 三条裁定记录。

## B 实测口径（本轮）

- 第 23 项冻结谓词在生产范围的命中：`pet_ui_stages.py:99`（`emit_verified_completion` 内 lambda）、`pet_ui_stages.py:1131`（`_completion_evidence` 通过后才发）、`skill_orchestrator.py:616/623`（`output_verified` 通过后才发）四处**均带同函数核验证据**⇒真候选 **0**；金丝雀未核验样本命中 ⇒ 谓词不是空集。
- 第 22 项冻结谓词（`os.remove`／`os.unlink`／`shutil.rmtree`，白名单 `storage_maintenance.recycle_paths()` 等）在生产范围命中 **0**，与既有删除权威（第 4 项）同源；金丝雀 `audit22_violation.py` 仍命中。
- 第 19 项：18 条宽口径命中均为文件名／字面量；`_audit19_config_writes()` 的子集断言实测成立（未出现第 3 项之外的 `config.json` 写入点）。

## C 完成判据对照（P1-3 原文）

| 判据 | 结果 |
| --- | --- |
| 19–23 每条都有 disposition＋理由 | ✅ `覆盖率审计19/20/21/22/23` 均有 `disposition`＋`reason`，由 `test_audit19_to_23_each_record_a_disposition_and_reason` 断言 |
| 由棘轮测试断言 | ✅ 22／23 进入 `AUDIT_SECTIONS` 双向棘轮＋判据表数字同源断言；19 由归并子集断言；金丝雀覆盖 22／23 |
| 判据文档三步（先门禁／再逐条复核／最后写入基数） | ✅ 先落冻结谓词＋金丝雀，再逐条复核 4 处发送点与删除面，最后写入台账 19／22／23 |

## D 未做与局限

- 未改产品运行期代码（本轮未发现需要收口的第 19／22／23 项真候选）；第 23 项的核验判定是**同函数内**的静态同现，跨函数核验（例如调用另一模块的核验函数后再发事件）不会被这条谓词覆盖，属已知口径边界，已写在判据文档措辞里。
- 未跑全量；未实机、未联网；未更新接力文件（结果文件已记录完成／未完成／验证／下一步）。
- 提交：按 §2.6 一次性 `git add`＋`git commit`，提交信息以 `R1648: ` 开头；hash 见 `git log`（本文写入时尚未提交）。