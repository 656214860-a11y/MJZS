# R824 结果：架构统一第 3 项发布器全量接入收口

## 完成项

- `workflow_context.instruction()` 与 `request_instruction()` 不再自行发布项目接续 JSON；它们必须接收发布器。新增独立 L3 `workflow_context_controller` 统一注入正式 JSON 发布器，桌面阶段启动和直接剧本 API 回复均经该控制器刷新索引。
- `writing.import_project()` 的导入校验报告不再自行发布；L3 `stage_execution_service.import_writing_project()` 同时装配项目登记网关和报告发布器，应用页只委托该入口。
- 首次实现经循环导入门禁发现 `stage_execution_service → writing_api → stage_execution_service`；已将接续提示词职责从阶段执行器拆到独立控制器，循环解除。
- 架构统一第 3 项 pending 由 2 降至 0；路线图与基数台账均保留已迁移条目及 `baseline_pending=66` 审计基数。

## 实测

```text
python run_selftests.py -k context writing_api writing_publication_boundary unification_ratchet round_baselines layers no_circular_import --safe
68 条，0 红

python run_selftests.py --all --safe
3,663 条，0 红，879.7 秒
```

## 结论

第 3 项“L2 发布器全量接入”已满足台账清空和棘轮无命中判据。完整安全全量通过后，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 更新为 R824。Tk 根窗口销毁后存在既有 `after` 回调清理提示，但不构成失败；本轮未扩大修复范围。
