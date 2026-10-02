# R475 结构治理轮（子场景：执行）：自动粗剪标记发布边界

## 轮次类型与范围

结构治理轮（子场景：执行），来源为 `tasks_round/tasks_round_461_result.md` E2 的剩余 UI 正式写入扫描；仅迁移自动粗剪完成标记的发布责任。

## 改动

- `edit_service.save_automatic_assemble_marker()` 统一定位后期阶段并原子发布 `自动粗剪.json`。
- `desktop.py` 的自动粗剪工作线程在成片生成后只调用该服务，不再自行创建目录或保存标记。
- 为服务行为和 UI→服务静态边界新增回归；断言未弱化。

## 验证

- 定向：`tests.test_edit_service` 与 `tests.architecture.test_edit_publication_boundary`，7/7 通过。
- `smoke_test.py --architecture`：73/73 通过。
- 默认 `smoke_test.py`：8/8 通过。
- 全量安全自检未重跑，待跨轮收口时执行。

## 三项结束检查

1. 本轮是结构治理轮（子场景：执行）。
2. 定向、架构和默认冒烟均通过；全量沿用 R473 的 3,183/3,183 已验证基线，未作为本轮新验收。
3. 项目状态的总待办未关闭，但 P0“自动粗剪标记由 UI 直写”这一独立遗留点已消除。
