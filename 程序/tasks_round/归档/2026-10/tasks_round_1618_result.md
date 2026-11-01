# R1618 拆分 script_contract.py：manifest 契约与交付规格各自独立（Q9 第一批）

- 本轮类型：§3.3 结构治理轮·执行（来源 [R1610](tasks_round/tasks_round_1610_result.md) J 第三批 Q9；Q9 共 5 个超大模块 + 打印统一，本轮做第 1 个）。
- 测试：定向 275 项通过（脚本契约/规格/资产契约/取消与关键链路 191，加 contracts 与层级、棘轮、环依赖 80，加覆盖率基线门禁 4）；架构门禁 354/354 通过（174.946 秒）；默认冒烟 0 失败。完整安全全量未跑。
- 欠账：本轮改源码＋新增模块，`project_status.md` 全量欠账计数 +1，未清。

## 改动

| 文件 | 行数 | 说明 |
| --- | --- | --- |
| `script_contract.py` | 1598 → **1113** | 只留自然剧本读写、阶段锁、简报、SKILL 审计表转发 |
| `script_manifest_schema.py` | 新增 **463** | manifest 编号/物理特征/`validate`/JSON Schema/完整性检查 |
| `script_output_spec.py` | 新增 **117** | 正式交付规格、预演预览规格、缩放/音量/字幕滤镜 |

- 两个新模块登记为 **L0**（`tests/architecture/_layers.py`）并在 `architecture.md` §3 L0 行列出。
- `test_module_size_ratchet.py` 中 `script_contract.py` 的 1600 上限**删除**（已降到上限内）；剩余 4 个超大模块仍登记。
- `script_contract` 按原名**转发**搬走的 58 个顶层名（含 `STAGE`），保持 `script_contract.X` 与 `from script_contract import X` 两种既有调用不变。为此把 `STAGE = '00_script'` 一并搬到 manifest 模块并在原处转发——否则新模块要反向 import `script_contract`，形成环依赖（`test_no_circular_import` 会拦）。

## 验证

- **公开面未变**：用 `git show HEAD:程序/script_contract.py` 解析旧文件顶层名（159 个）逐个 `hasattr(script_contract, name)`，缺失 0 个。
- 定向用例覆盖两个新模块的行为（`test_script_contract`、`test_output_spec`、`test_script_contract_production_locks` 等 191+80 项全绿）。
- `test_layers`／`test_no_circular_import`／`test_module_size_ratchet`／`test_coverage_baseline` 均通过；覆盖率基线按新模块口径重跑刷新（272 个生产模块，46 个被 8 个核心目标触及）。

## 环境限制（非本轮引入）

`tests.test_idea_chat`、`tests.test_idea_inline_brief` 本机单跑 **90 秒超时**（Tk `after` 回调报 `invalid command name ...poll`）。已在未含本轮改动的基线工作树 `.wt/architecture-assessment`（R1617）同样单跑两个模块，**同样超时**，故为环境性问题、与本轮拆分无关；这两项未纳入本轮定向范围，其相关问题不计入本轮结论。

## Q9 剩余

`pet_cloud.py` 2137、`desktop.py` 2259、`skill_panel.py` 1886、`stage_execution_service.py` 1677 仍超 1500 行上限；生产根目录 `print(` 计数尚未收敛到 `app_logging`（本轮未动）。下一轮继续。

## 下一项

Q9 第二批（拆 `stage_execution_service.py` 或 `skill_panel.py`）。