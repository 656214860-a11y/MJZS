# R1651 修复轮：清单 P2-7 收口（迁移校验哈希改走 file_cache 缓存层）

## §7 三问

1. **本轮属于 §3 哪种类型？** §3.2 修复轮。范围＝`tasks_round/tasks_round_1645_result.md` J 节清单 **P2-7**（清单**最后一项**）。
   **指令冲突记录**：本轮会话顶部提示仍为「结构治理轮（子场景：只读诊断）」，与持久目标「按顺序完成 `tasks_round_1645_result.md` J 节清单」不一致。承接 R1646–R1650 的既有判定（R1650 结果文件已记录同一冲突）：以持久目标为准；本项完成后清单全部收口。
2. **测试跑了吗？三个基线过了吗？** 定向 `tests.test_projects` **7/7**（本轮新增 1 条，改前 6）、`tests.test_line_endings` **16/16**、`tests.architecture.test_round_baselines` **5/5**＝**28/28**；默认冒烟 **8/8**；架构门禁 **364/364（298.5 秒，改前 364）并绿**。**未跑全量**；欠账**增加**（见第 3 问）。
3. **project_status.md 的欠账少了吗？** **没有减少，反而增加**：本轮改了产品源码 `程序/projects.py`（`run_selftests.is_source_change()` 口径下 `程序/*.py` 计为改源码）⇒ 欠账 **5/8 → 6/8**。清零仍须后台全量转绿，而后台全量因 D 节遗留红仍未转绿。

## A 改动（2 个文件）

1. `程序/projects.py`
   - `:8` 删除 `from agent.core import file_hash`（迁移校验不再直连 `agent.core`）。
   - `:10` `from file_cache import read_json as cached_read_json` → `from file_cache import file_digest, read_json as cached_read_json`。
   - `:158` 迁移完整性校验 `file_hash(p)!=file_hash(target/...)` → `file_digest(p)!=file_digest(target/...)`。语义等价：`file_cache.file_digest` 是 1 MiB 流式 sha256，并按 `(mtime_ns,size)` 走缓存，重复比对同一文件不重复读盘。
2. `程序/tests/test_projects.py`
   - `:9` 补 `import file_cache`。
   - `:122` 新增 `test_legacy_migration_hashes_through_the_file_cache_layer`：以 `patch('projects.file_digest', side_effect=file_cache.file_digest)` 包住 `Projects(...).migrate()`，断言 `call_count >= 2`（源与目标各经一次缓存层），把「迁移校验经缓存层」变成可执行判据——若有人改回 `agent.core.file_hash`（未打补丁）或改回非缓存实现，该用例会红。

## B 验证（本轮实测命令与结果）

- `python -B -m unittest tests.test_projects` → `Ran 7 tests` **OK**；`tests.test_line_endings` **16/16**；`tests.architecture.test_round_baselines` **5/5**。
- `python -B smoke_test.py` → **通过 8 项 / 失败 0 项**。
- `python -B smoke_test.py --architecture` → `Ran 364 tests in 298.473s` **OK**（改前 364；本轮未增删 `tests/architecture/` 用例，新增用例落在 `tests/test_projects.py`）。
- 运行期间打印 `skills/00全流程SKILL/.../scripts/check_package.py:2239: SyntaxWarning` —— 见 D 节，属跨仓扫描的**预期副产物**，**不**记为本仓红。

## C 完成判据对照

| 清单项 | 判据（原文 `tasks_round_1645_result.md:137`） | 结果 |
| --- | --- | --- |
| P2-7（后半）| 「`file_hash` 调用经缓存层」 | ✅ `projects.py:158` 改走 `file_cache.file_digest`；新增用例断言调用次数 ≥2 |
| P2-7（前半）| 「迁移走后台任务且失败可恢复」 | 🔶 页面层已满足（见 D 节判断依据），L2 `migrate()` 内进度回调判为范围外 |

## D 未做与局限

- **P2-7 前半不在本轮范围（判断依据）**：`desktop_project_pages.py:36` 已在 `threading.Thread(daemon=True)` 里跑 `migrate()`，`:37` 调 `:38` 的轮询，`_poll_legacy_project_migration` 用 `win.after(25, ...)`（`:45`）轮询结果并显示进度文案 ⇒ 该页面**不存在 Tk 冻结**，「可取消的后台任务＋进度」在此入口已满足。`projects.migrate()` 是 L2 同步服务函数（页面与测试直接调用），把后台化下沉到 L2 会把线程语义塞进无编排层服务，超出本项「最小闭环」。真实残余缺口＝`projects.py:~150-160` 的 `_copy_tree` + 哈希循环**没有进度回调**（大素材库上迁移期间文案不推进），建议另立一轮或并入 P1-2 的 asset_batch 批次。
- **权威源核对**：本轮结论以当前代码树、`程序/AGENTS.md` §2.2、`程序/architecture.md` 第 3 节分层表为准，未把历史记录当当前验收。
- **权威更正（修正 R1649 的 P2-2 结论）**：`tests/architecture/test_unification_ratchet.py:22-27` **有意**扫描 `ROOT.glob('skills/**/scripts/*.py')` 与 `ROOT.glob('skills/**/server.py')`，故运行时打印的 `skills/00全流程SKILL/AIGC创作全流程/short-drama-director/scripts/check_package.py:2239: SyntaxWarning` 来自**跨仓扫描**，非本仓文件。R1649 的 P2-2 结论「本仓门禁不编译它、无可验证对象」**不准确**，以此处更正。该目录是 **gitlink 嵌套仓库**（`程序/skills/00全流程SKILL/AIGC创作全流程`，mode 160000，`main`，HEAD `1a43ae5`，无 `.gitmodules`），父仓库无法提交其修改 ⇒ 已登记 `维护记录/优化待办队列.md:72` **U14（上游归属）**。门禁侧可选最小闭环（本轮未做）：在 `test_unification_ratchet` / `test_static_hygiene` 里把「跨仓扫描属有意行为、其时可能打印外部包告警」写成注释或断言，避免该 SyntaxWarning 被误读为本仓问题。
- **遗留红（非本轮引入、非本轮范围）**：`.wt/ci` 全量退出码 1（HEAD `a9a3aa6`，2026-10-17T09:12:19，748 秒），唯一红＝`tests/test_distribution_selfcheck.py::test_manifest_covers_every_file`：`['程序/data_model.md','程序/runbook.md','程序/task_states.md']` 未在 `distribution_manifest.md` 声明保留或排除。三文件由 **R1625** 新增；该测试只在全量跑，故自 R1624 后首次全量才暴露。按 §8.6 只登记不修（属「1 行级」声明补齐，建议由用户裁决是否另立一轮）。
- **P1-2 剩余**：越层豁免 37→35 后仍有 3 条 `asset_batch_service → asset_prompt_rules/asset_reference_prompts/asset_reference_images`，R1647 已记为「下一批应作为一整组的首选」，属 P1-2 后续批次而非未完成项。
- 未更新接力文件（完成／未完成／验证／下一步已写入本文件）。
- 提交：按 §2.6 `git add` + `git commit`，提交信息以 `R1651: ` 开头；hash 见 `git log`（本文写入时尚未提交）。