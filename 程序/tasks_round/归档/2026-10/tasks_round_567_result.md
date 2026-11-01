# R567｜结构治理轮（子场景：执行）

## 来源与范围

- 来源：`tasks_round/tasks_round_547_result.md` J 节 P3-1——建立 facade 调用方清单、唯一所有者、淘汰日期和逾期测试，确认所有历史兼容入口均集中到 `legacy_compat` 或已声明门面。
- 应用代码仅改动 `legacy_compat.py`；未迁移、删除或改变任何兼容调用，没有修改分层、既有接口、用户项目数据或产品功能。

## 完成结果

- `legacy_compat.FACADE_MANIFEST` 成为历史兼容入口的唯一清单。五个入口均声明唯一所有者 `legacy_compat` 和淘汰日 `2027-03-31`。
- 清单由 AST 反查生产代码后登记真实调用方：`resolved_storyboard_alias → engine`、`canonical_stage_name → confirm_gates`、`optional_workflow_model_name → local_previs`、`optional_model_identity → idea_chat`、`optional_asset_counts → pet_ui`。
- 新架构门禁要求清单完整覆盖该模块全部公共兼容函数、每项只归属该门面、登记调用方与生产 AST 完全一致；新增调用、绕过门面或遗漏清单会失败。淘汰日到期后也会明确失败，要求 P3-2 删除或迁移门面。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `legacy_compat.py` | 增加唯一所有者／调用方／淘汰日期的声明式 facade 清单。 |
| `tests/architecture/test_legacy_facade_manifest.py` | 新增清单完整性、调用方反查和逾期三项架构门禁。 |
| `project_status.md`、`architecture.md` | 同步本轮、债务余额和架构基线。 |

## 验证

- `python run_selftests.py --serial -k legacy_compat legacy_facade_manifest`：8/8 通过。
- `python smoke_test.py --affected legacy_compat`：9 项通过、0 项失败；原兼容行为回归 5/5 通过。
- `python smoke_test.py`：默认冒烟 8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过，无新增红点。

## 债务状态与自审

- P3-1 完成；R182 拆分债务由 3 项减至 2 项，剩余 P0-3（已有二进制成果发布／分层阻塞）和 P3-2（在清单稳定后逐项淘汰 facade）。
- 本轮先由测试暴露并如实登记既有五个真实调用方，未将零调用误记为事实；P3-2 可按清单逐项处理，避免误删历史只读兼容路径。
