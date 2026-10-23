# R1943 结果：结构治理轮（八维度清理 · 第三批，收尾）

- 本轮类型：结构治理轮（瘦身）。分支 `codex/wip-R1943`，从 master `4ee82c27` 切出。断言未动。

## 改动及等价理由

- `ui_widgets`：删除私有别名 `_styles(master)`（函数体只是 `setup_styles(master)`），8 个调用点直接调用 `setup_styles`。全仓无外部引用 `_styles`（含 tests、动态字符串）。

## 其余维度摸底（均未改）

- 打破循环依赖：ast 建“顶层 import 图”与“含函数内延迟 import 的全图”求强连通分量，两张图均为 0 个环。1863 处延迟 import 是为懒加载／动态登记保留，不是环的遮羞布，无可拆项。
- 废弃与兼容层：`stage_config.presets()` 的无 stage 旧调用被 tests 固定；`skill_registry` 的 deprecated／replacedBy 是登记数据行为，均在用，不动。
- 替换弱类型：全仓约 2300 个公共函数无完整注解，纯注解收紧收益低且有触碰 `service_contract` 等架构门禁的风险，本批不做，留待具体契约改动时顺带。

## 测试

- `run_selftests.py -k ui_widgets ui_modern ui_batch ui_theme combobox scrollbar pet_ui`：715 条，仅 `test_pet_ui` 5 条红，与全量 `--all --safe`（R1923 树）里同一文件同为 5 条红一致，属缺外部 SKILL 文档的基线红。
- `--all --safe` 未运行。
