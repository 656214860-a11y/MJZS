# R741 结果｜层级补登与越层豁免基数

## 完成内容

- `tests/architecture/_layers.py` 已覆盖当前固定扫描范围的 210 个顶层运行期模块：每项均进入 L0–L5，或进入具理由的外围工具白名单；未改任何产品模块导入。
- `broadcaster`、`asset_thumbs`、`projects` 及 13 个此前未登记的 `*_service.py` 均按真实职责及静态依赖补登。`batch_frames_tool`、Blender／Codex／控制台脚本明示为非运行期外围工具。
- 新层级门禁要求顶层模块不得漏登；`维护记录/架构统一基数.json` 的“层级”段逐项记录 38 个既存越层豁免，并同时校验扫描结果与台账一致、条目可定位、豁免数不得高于本轮基数。新越层和删台账未修源码都会失败。
- 第 3 项 L2 正式写入扫描重新定基：旧基数 37，新基数 66，差额 29；差额全部来自本轮补登后首次纳入 `LAYERS == 2` 扫描的既存模块，而非新增产品写入。

## 验证

- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：通过（新增断言后架构门禁仍全绿）。
- `python run_selftests.py -k layers unification_ratchet round_baselines --safe`：0 红。
- `python run_selftests.py --all --safe`：247 个测试文件、601 路工作单元、3,470 条用例、869.0 秒、0 个文件有红。
- 因本轮改动层级登记表，已按 AGENTS.md §5 升级完整安全全量，并将 `维护记录/测试分层基线.json` 的 `last_full_safe_all_round` 更新为 741。

## 范围说明

题述旧统计为“213 顶层／130 已登记／93 漏登”；本轮使用 `tests/architecture/_scan.py::production_files()` 的权威当前扫描范围，得到 210 个顶层运行期模块。没有为凑旧数字改变扫描范围。
