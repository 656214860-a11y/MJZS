# R645｜结构治理轮：04 资产管理页面拆分

## 开工三问与验证档位

1. 本轮是结构治理轮：执行 R630 报告 K-6.1，用户指定唯一入口为「04 资产管理」主页面。
2. 测试已跑：聚焦回归 8/8、默认冒烟 8/8 通过；按已声明档位未单独运行 `--affected`、`--architecture`，全量安全自检为 3350 条、19 个既存红文件，因此三个基线未全过。
3. `project_status.md` 的既有欠账未减少；本轮只拆分单个页面，不处理历史红项。

## 范围锁定

来源：`tasks_round/tasks_round_630_result.md` 的 K-6.1。唯一处理 `Desktop.asset_page()`／`Desktop.assets()` 的非 Tk 状态逻辑；不拆其它页面，不改资产删除、导入、项目数据格式或页面控件命令。

## 验证前单测

`D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_asset_page_controller`

```text
Ran 3 tests in 0.000s
OK
```

## 改动文件清单

- `asset_page_controller.py`：新增无 Tk 的 `AssetPageController`，仅承载资产类别筛选、勾选初始化、已导入判定与批量目标选择。
- `desktop.py`：04 资产管理页改为调用控制器；Tk 控件构造、按钮命令、删除与导入动作仍在 `Desktop` 中。
- `tests/test_asset_page_controller.py`：新增三条控制器回归。
- `tests/architecture/_layers.py`、`tests/architecture/test_migrated_ui_boundaries.py`、`architecture.md`：登记该 L3 控制器及其无 Tk、无项目数据写入边界。

未改动资产删除、导入、项目数据格式、其它页面或用户项目目录。

## 新增回归与兼容回归

新增控制器回归断言：角色类别仅返回 `CHAR_` 行且只为未导入项默认勾选；当前类别内全选与已导入判定正确；勾选行优先于高亮行，未勾选时回退高亮行。

在拆分后发现既有 `AssetDeleteTests` 测试桩未设置 `asset_kind`，已把表格批量入口固定按 `all` 构造控制器，保持原先“表中行集决定选择”的语义。

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B -m unittest tests.test_asset_page_controller tests.test_cell_menu.AssetDeleteTests
........
Ran 8 tests in 0.366s
OK
```

## 验证结果

声明档位：本轮改动涉及 6 个模块，按分级规则执行“默认冒烟 + 全量安全自检”，跳过 `--affected` 与 `--architecture`，理由是新增 L3 控制器并同时调整 L3/L4 边界登记、测试与架构契约，改动超过 4 个模块。

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B smoke_test.py
通过：8 项
失败：0 项
```

```text
D:\漫剧制作助手\运行环境\Python\python.exe -B run_selftests.py --all --safe
完整原始日志：D:\漫剧制作助手\程序\维护记录\r645_safe_all.log
共 3350 条用例，968.0 秒；19 个文件有红
```

全量安全自检的 19 个红文件为：`architecture.test_platform_process_boundary`、`architecture.test_recycle_service`、`test_copy_rules`、`test_core`、`test_hollmwood_ui_queue`、`test_idea_chat`（两组）、`test_line_endings`、`test_model_pool`、`test_pet_ui`（五组）、`test_row_targets`、`test_skills`（两组）、`test_static_names`、`test_ui_edges`。本轮资产控制器相关 `test_asset_page_controller`（3 条）、`test_cell_menu.AssetDeleteTests`（5 条）与全量内的架构迁移边界测试均通过；初次运行暴露的 `asset_kind` 兼容性问题已修正，最终失败清单不含 `test_cell_menu` 或轮次同步门禁。

因此，依任务硬判定：**[TASK_FAILED]**。失败原因是已声明的全量安全自检仍有 19 个既存失败文件，不将本轮验收为完成。

## 用户数据确认

本轮未执行任何以用户项目目录为目标的命令，未修改 `skill_config.json`、任何项目 JSON、密钥或用户资产数据。

## J 后续

- 若继续执行 R630 K-6.1，只能在用户指定下一个唯一页面后再迁移；不在本轮继续拆分 `desktop.py` 的其它页面。
- 全量安全自检的 19 个既存红项需按各自来源另立轮次处理；本轮不顺手修改。

## 自审

- 只处理了用户指定的 04 资产管理页面的非 Tk 编排逻辑。
- 资产删除、导入、项目数据和其它页面均未触碰。
- 未引入新的用户数据读写或外部依赖；L3 控制器不持有 Tk 控件。
