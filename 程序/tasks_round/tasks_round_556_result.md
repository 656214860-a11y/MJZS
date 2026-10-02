# R556｜结构治理轮（子场景：执行）｜P1-5 初步分镜文件表控制器

## 开工来源与结论

- 来源：`tasks_round/tasks_round_547_result.md` 的 J 节 **P1-5**。
- `storyboard_files.show()` 的目录扫描结果、表格选择、按钮门禁及回收/恢复操作已迁入无 Tk 的 `StoryboardPageController`。页面只保留 Treeview 渲染、滚动位置恢复、弹窗确认、状态文案和事件绑定。
- R182 拆分债务由 **11 项减至 10 项**；P0-3 的既有阻塞未改变。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `storyboard_page_controller.py` | 新增 L3 无 Tk 控制器：维护两类文件表的扫描结果与选择，派生操作按钮门禁，编排回收计划、执行和最近批次恢复。 |
| `storyboard_files.py` | `show()` 注入控制器；Tk 回调只将高亮行交给控制器、渲染返回的目录结果，并负责原有确认弹窗与控件更新。 |
| `tests/test_storyboard_page_controller.py` | 新增无 Tk 回归，覆盖刷新后的选择/门禁收敛，以及回收计划和执行均经控制器。 |
| `tests/architecture/_layers.py` | 登记新控制器为 L3，纳入既有依赖方向门禁。 |
| `architecture.md`、`project_status.md` | 更新控制器职责、当前轮次与债务余额。 |

生产模块仅 2 个：`storyboard_files.py`、`storyboard_page_controller.py`，符合三模块上限。目录枚举、选择持久化与可恢复删除仍分别经 `storyboard_catalog_service`、`storyboard_selection`、`storyboard_recycle_service`，没有变更分层、契约、数据格式或页面功能。

## 验证

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.test_storyboard_page_controller tests.test_recycle tests.test_recycle_restore tests.test_file_cache tests.architecture.test_layers` | 36/36 通过 |
| `python smoke_test.py --affected storyboard_page_controller recycle file_cache` | 5 个匹配测试文件、35 条用例通过，0 红文件 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点 |

## 自检

- 表格刷新、选择和回收操作均由可测试控制器编排；Tk 页面不再直接调用目录、选择或回收服务完成这些领域操作。
- 确认弹窗与 Treeview 绘制仍留在 UI，未新增功能或改变删除的可恢复语义。
- 自审：通过。范围、两项生产模块、分层与来源条目均符合要求；默认冒烟 8/8、架构门禁 95/95，未引入新的代码问题。
