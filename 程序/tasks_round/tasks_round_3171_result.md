# R3171 结果（任务书 P3 收尾：引用到当前项目／添加到全局库）

- 轮次类型：功能轮（任务书《统一项目文件生命周期管理》P3，Q11 收尾；分支 `codex/wip-R3171`）。

## 三问

1. **本轮属于 §3 哪种类型？** 功能轮（补齐 P3 最后两个动作，零 UI 重排、不改启动路径）。
2. **测试跑了吗、三个基线过了吗？** 跑了。默认冒烟 **9/9**；架构门禁 483 条 / **1 红**（`test_round_number_continuous`，分支固有）；定向 37 条 0 红。
3. **欠账少了吗？** 减少：P3 从「索引＋目录登记＋面板视图」补齐到「可引用、可入库」，Q11 全部落地。

## 本轮改动

| 文件 | 改动 |
| --- | --- |
| `domain/global_library_service.py`（新，L1）＋门面 | `copy_to_project()`（全局库→项目 `_shared/全局素材库/`，登记来源到 `素材来源.json`，不移动源）；`copy_to_library()`（项目→全局库，保留相对结构、重名加序号，不移动源）；复制走 `agent.core.save_file`、登记走 `agent.core.save_text` |
| `ui/desktop_files_panel_filters.py` | 新增 `reference_from_library()`：全局库行右键「引用到当前项目」，失败给可读提示 |
| `ui/desktop_files_panel.py` | `script_menu` 对 `library:` 行追加「引用到当前项目」菜单项 |
| `tests/test_global_library_service.py`（新，6 条） | 引用复制＋来源登记＋越界拒绝＋重复登记去重；入库复制＋重名加序号＋越界拒绝 |
| `tests/architecture/_layers.py`、`architecture.md` | 新模块登记 L1（只依赖 L0/L1，不承担 L2 发布债务与返回契约） |
| 两套覆盖率基线、`分支覆盖率下限.json`、`runbook.md` §11 | 新增模块后按纪律重跑工具刷新（行覆盖 708 模块、L0/L1 分支 79 模块），数字同步 |

## 过程中按门禁修正的两处

1. `_copy_file` 初版用 `open(target, 'wb')` 直写，触发 `test_atomic_write_boundary`；改走 `agent.core.save_file`（原子替换＋缓存失效＋大文件按块不进内存）。
2. 初版把该模块登记 L2，触发 L2「范围记录」与「正式发布债务」两条门禁；核实其真实依赖仅 L0/L1（同 `storage_maintenance` 类文件基础设施）后改登记 L1。

## 验证

- `smoke_test.py`：**9/9**。
- `smoke_test.py --architecture`：483 条 / **1 红**＝`test_round_number_continuous`（状态页抬头仅 master 可提交）。
- `run_selftests.py -k test_global_library_service test_files_panel_stages`：**37 条 0 红**。
