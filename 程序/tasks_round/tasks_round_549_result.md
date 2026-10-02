# R549｜结构治理轮（子场景：执行）｜P0-2 剧本与分镜成果迁入发布编排器

## 本轮结论

- 轮次类型：结构治理轮（子场景：执行）。来源：`tasks_round/tasks_round_547_result.md` 的 J 节 P0-2。
- P0-2 已完成：剧本结构的正式执行路径与分镜定稿的正式发布路径都已进入 R548 的 `stage_execution_service.publish_stage_text()` 编排入口。
- R182 可执行债务由 **16 项减至 15 项**；P0-3 仍负责媒体、交付、首帧等非剧本文本成果的迁移。

## 改动文件清单

| 文件 | 改动 | 保持的语义 |
|---|---|---|
| `script_contract.py` | `write_structured_script()` 接受仅供上层注入的可选发布器；默认既有调用仍按原逻辑保存。 | 源文件约束、目标命名、空正文拒绝和 `artifact_lineage` 记录不变；发布器失败不会执行来源登记。 |
| `stage_exec.py` | 剧本结构的 `write_structured_script` 动作注入 `publish_stage_text`。 | L3 仍委托 L0 剧本契约；不产生 L0→L3 的逆向依赖，也不改变阶段完成事件。 |
| `storyboard_final.py` | 定稿 JSON 在既有双文件发布服务外先经统一编排器校验、原子发布；双文件服务继续作为索引更新回调。 | `assets.json` 双索引、既有 `publish_final_bundle()` 回滚以及 `_record_lineage()` 的来源关系保持原有顺序与恢复语义。 |

## 发布与恢复语义

1. 剧本结构：L3 执行器将已通过 Editor 复审的正文交给统一入口；入口先校验、原子替换，再调用 L0 的来源关系登记。登记失败时入口恢复结构剧本，且该动作不返回成功。
2. 分镜定稿：L3 在写出 `episode.json` 前进行原有 `validate_episode()` 校验；写入后调用既有双文件发布服务更新 `assets.json` 并复核。任一索引/复核失败时，统一入口恢复主成果，既有双文件服务恢复其两份 JSON；来源登记不会执行。
3. 没有添加 UI、阶段、数据格式或完成事件；未修改分层登记、对外默认调用或用户项目数据。

## 验证

| 命令 | 结果 |
|---|---|
| `python -m unittest tests.test_script_structure tests.test_stage_wiring tests.architecture.test_structured_script_write_boundary tests.architecture.test_final_bundle_boundary` | 34/34 通过，覆盖剧本正式执行、分镜定稿、血缘顺序及双文件发布边界。 |
| `python smoke_test.py --affected script_structure storyboard` | 10 个相关测试文件通过，无红灯。维护记录增量写入受运行环境权限限制而提示，但门禁明确判为不影响结果。 |
| `python smoke_test.py` | 默认冒烟 8/8 通过。 |
| `python smoke_test.py --architecture` | 架构门禁 95/95 通过，无新增红点。 |

全量安全回归本轮未重复运行，历史基线为 3,230 条；本轮默认、定向、架构三类相关门禁均达标。

## 自检

- 只改 3 个生产模块，符合结构治理轮上限。
- 未改变分层登记：L0 不导入 L3；L3 以回调注入方式调用既有 L0 契约。
- 未改对外默认调用、用户数据、阶段完成契约或新增功能。
