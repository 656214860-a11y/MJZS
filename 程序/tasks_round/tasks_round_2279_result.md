# R2279 分镜页删除改走 storage_maintenance.recycle_paths()（J-回收 结构治理轮·执行）

## 来源
`tasks_round/tasks_round_2178_result.md` 候选 09 的 J-回收：「`storyboard_recycle_service` 的回收写入改走 `storage_maintenance.recycle_paths()`」（合入前全量）。

## 基线
分支 `codex/wip-R2279`，自 `codex/wip-R2276`。

## 轮次类型／三套基线／债务
结构治理轮（删除语义改动）；清掉最后一处手拼回收目录与 `rename` 搬移，「工作流任务」手拼棘轮登记表清零；无新增债务。

## 改动
- `storyboard_recycle_service.py`：`recycle_files` 的搬移改为 `recycle_paths(project, targets, '分镜页删除')`（写前计划、逐项状态、失败整批撤回均由统一入口负责）；返回值仍是批次目录。`latest_recycle_batch` 认两种清单：本轮起的 `items`（`reason=分镜页删除`）与早期 `files`，恢复仍走 `restore_recycle_batch`。
- 行为差异（如实）：批次目录名由 `<时间>_<6位>` 变为统一入口的 `自动维护_<时间>_<8位>`；清单多了 `reason/state` 字段；搬移用 `shutil.move`（原为 `rename`）。
- `tests/architecture/test_workflow_dir_ratchet.py`：登记表清空（断言未动）。

## 新增测试
`tests/test_recycle.py::test_recycle_goes_through_shared_recycler_and_restores`：回收→认出最新批次→恢复。既有断言未动。

## 测试
- 已跑（隐藏桌面）：`run_selftests.py -k recycle storyboard_files storyboard_page workflow_dir` 57 条全过；`smoke_test.py --architecture` 仅已知两项环境红。
- 未运行：`--all --safe`（删除语义改动，合入 master 前必须跑）。

## 回滚
`git revert` 本轮提交；旧 `files` 清单仍可被识别。

## 下一步
J-配置：`skill_config.json` 路径收成一个入口。
