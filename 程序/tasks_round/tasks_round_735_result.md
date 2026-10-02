# R735 结果｜架构统一棘轮可信度与门禁清单纪律

**轮次类型：** 契约轮。本轮未改产品 `.py`，未改两处 `service_contract` 试点行为，未触碰 `AGENTS.md` 2.2 的“路径”行；既有断言未删除或弱化，只新增约束。

## 完成内容

- `test_unification_ratchet.py` 的 JSON 审计改为固定范围：顶层、`agent/`、`batch_frames_tool/`、`scripts/`、`skills/**/scripts/` 与 `skills/**/server.py`，不再从台账路径扩展范围。
- 台账第 3、4 项改为逐条 `{file, point, disposition, reason}` 记录；棘轮同时校验新增未登记项、pending 单调性、处置理由和每条记录可定位性。
- 第 3 项在 **R735** 重判：R733 的“1 个模块”来自单文件扫描；扫描范围扩至 `_layers.LAYERS` 的全部 L2 登记模块后，实际重建为 **37** 个 pending。`delivery_import_service.import_final_master()` 的 `copy2(source, target)` 已人工确认目标由 `context.stage_resolver('delivery')` 解析为正式交付阶段路径，故保留 pending。
- 第 4 项固定扫描实测 66 个命中。R735 同轮逐条定判 `storage_maintenance.py` 的删除／回收权威读点（转 `file_cache` 会自引用）、一次性迁移脚本、独立批帧工具与 Blender 模板生成器；累计 **42** 项有理由豁免，真实 pending 为 **24**。
- 新增 AGENTS 架构门禁清单集合相等断言，入口清单与实际 `tests/architecture/test_*.py` 文件完全一致；不再在文档中硬编码会过期的总数。

## 还需轮数

按每轮最多迁移 3 个模块：第 3 项 `ceil(37/3)=13` 轮，第 4 项 `ceil(24/3)=8` 轮；若并行推进，关键路径为 **13 轮**。

## 验证与三个基线

| 检查 | 结果 |
|---|---:|
| `python smoke_test.py` | 8/8 |
| `python smoke_test.py --architecture` | 134/134 |
| `python run_selftests.py -k unification_ratchet agents_md round_baselines --safe` | 14 条 / 0 红（2.8 秒） |
| `python run_selftests.py --all --safe` | 246 文件 / 600 工作单元 / 0 红（约 15 分钟） |

本轮按可判定算式 `735 − 731 = 4 ≥ 3` 触发完整安全全量；已将 `维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 写为 **735**（`last_full_safe_all_at=2026-10-01`）。R734 的 `734 − 731 = 3` 本应触发但未触发，未作为例外延后。
