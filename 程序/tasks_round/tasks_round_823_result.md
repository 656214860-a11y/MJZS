# R823 结果：字幕与视频提示词发布边界收口

## 完成项

- `subtitle_export_service.publish_srt_text()` 不再自行取得行尾写入能力；独立 L3 `subtitle_export_controller` 显式注入发布器，避开 `skill_orchestrator → skill_tools` 的静态循环风险。
- `video_prompt_publication` 的草稿／成果发布和导入事务不再直接取得文件发布、读取、回滚与目录清理能力；L3 `stage_execution_service.video_prompt_gateway()` 统一注入，应用与结果页继续只委托阶段入口。
- R821 残余调用方已收口：资产自动补全和分镜同步计划均经 `stage_execution_service` 的资产计划入口；相应测试替身也只替换真实 L3 边界。
- 修正资产页建页时强制 `update_idletasks()` 清空 Tcl 空闲队列的缺陷：该操作会在慢机上让补行定时器落入首次刷新，造成可见行数和首帧 CPU 波动。移除该强制刷新后，映射事件与既有空闲回调仍按真实可视区补齐缩略图。
- 架构统一第 3 项的 pending 由 5 降至 2，余项为 `workflow_context.py:instruction` 与 `writing.py:import_project`；未修改产品业务语义。

## 实测

```text
python smoke_test.py
通过：8 项；失败：0 项

python smoke_test.py --architecture
218 条，0 红

python run_selftests.py -k ui_edges --safe
113 条，0 红

python run_selftests.py -k asset_gating perf_baseline --safe
26 条，0 红

python run_selftests.py --all --safe
3,662 条，0 红，907.7 秒
```

## 结论

本轮完成两组发布能力的 L2→L3 注入收口，并以独立边界门禁防止回退；完整安全全量已通过，`维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 更新为 R823。测试进程销毁 Tk 根窗口后仍会输出既有 `after` 回调清理提示，但无测试失败，未在本轮扩大处理范围。
