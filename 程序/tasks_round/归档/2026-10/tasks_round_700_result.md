# R700 修复轮结果：选择项目后的查询风暴与聊天首现

## 承接说明

台账核对结论：`tasks_round_697_result.md` 在 2026-10-01 00:15 已登记，但其后 `desktop.py` 的已选项目延后建页回调由固定 1 秒改为 `after(80, show_loaded_project)`（并保留首帧 paint/tick 恢复保护）没有独立结果文件。该未登记承接改动在本轮开始时已复核：它缩短了假等待，不处理查询风暴；本轮不回退它。

当时已记录的验证为 R697 真实项目探针（2026-10-01 00:15）：`show_loaded_project` 0.322 s、首帧 1.220 s。为保持连续性，不倒填旧编号；本结果作为 R700 的开头承接说明，台账由 R699 → R700，下一轮为 R701。

## 修复

- `skill_registry.py`：增加 2 秒热查询时间片。`_fresh()` 与 `fingerprint()` 命中时直接复用已建指纹，不再调用 `_file_cache_key()`、目录枚举或拼接全量元组。根目录旧 manifest 迁移只在实例首次构建和 `scan(force=True)` 运行；`skill_panel` 既有强制扫描入口未变。
- `stage_config.py`：`synchronize()`、`get()` 以“项目配置绝对路径 + `skill_config.json` mtime + 注册表实例”为键缓存，返回值为副本；`put`、`reset`（经 `put`）、`apply_preset`（经 `put`）、`save_all` 与 workflow 写入后均失效。配置格式未改。
- `desktop.py`：模型分区键未就绪时，不再提前返回空白聊天区；先呈现不依赖键的软件示例/空会话壳，50ms 轮询保持，键回到后仍以 `_idea_view_generation` 代次重绘真实历史。

## 回归固化

- 注册表 40 次热查询不再触发 `_file_cache_key`；真实项目启动窗口计数不高于 50。
- 真实项目聊天框轮询到非空文本必须不超过 1.5 秒；保留 R697 的 `show_loaded_project <= 1.0s` 与首帧 worker 边界。
- `idea_chat_model()` 冷查在测试环境限定 `<=0.5s`。
- 原有“热加载立即发现”的验证改由面板同款 `scan(force=True)` 触发，未降低发现能力。

## 真实项目探针

对象：`D:\漫剧下载\项目\摄像头_20260930`。临时脚本曾位于 `logs/r700_startup_probe.py`，测后已删除。原始输出：

```text
project=D:\漫剧下载\项目\摄像头_20260930
idea_chat_model='' 0.000s
first_chat_visible=1.086s
file_cache_key_calls=0
```

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| 聊天首现 | 8.85 s | 1.086 s |
| `_file_cache_key` 调用 | 2,854+ | 0 |
| `model_name` 裸成本 | 1.96 s | 0.074 s（真实项目 `writing` 入口直接测量） |

## 验证

- `python -m unittest tests.test_skills.RegistryTests tests.test_skills.StageConfigTests tests.test_desktop_startup_perf`：34/34 通过。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --affected skill_registry stage_config desktop skill_panel`：9/9 通过；定向自检 0 个文件有红，桌面启动专项 5/5、SKILL 分片均通过。
- `python run_selftests.py --layer gui-short --safe --all`：1,079 条，288.1 秒；本轮关联的 `test_desktop_startup_perf`、`test_skills`、`test_idea_chat` 均通过。仅有 1 条既存非本轮红：`tests/test_asset_gating.py:587` 的 `test_kill_comfy_runs_off_the_ui_thread`，期望后台回调已更新为“已强制关闭…”，实得仍为“正在强制关闭…”。未改资产门禁模块。

## 三个基线数

- 默认冒烟：8/8 通过。
- gui-short 安全全量：1,079 条 / 155 单元，1 个既存失败文件。
- 历史全量安全基线：3,230 条（本轮按要求执行 gui-short 全量）。

[TASK_COMPLETE]
