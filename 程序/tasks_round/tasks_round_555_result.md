# R555｜结构治理轮（子场景：执行）｜P1-4 分镜定稿页面控制器

## 开工来源与结论

- 来源：`tasks_round/tasks_round_547_result.md` 的 J 节 **P1-4**。
- 本轮是整理轮；将 `storyboard_files.show_final()` 的定稿预览、编辑保存、选中偏好和镜头导航状态迁入无 Tk 的 `FinalStoryboardController`。页面保留 Tk 控件组装、控件更新、弹窗和事件绑定。
- R182 拆分债务由 **12 项减至 11 项**；P0-3 的既有阻塞未改变。

## 改动文件

| 文件 | 改动 |
| --- | --- |
| `storyboard_final_controller.py` | 新增 L3 无 Tk 控制器：预览读取/别名解析、选中偏好、JSON 校验后委派原子保存、镜头 ID 与当前导航状态。 |
| `storyboard_files.py` | `show_final()` 改为注入控制器；仅将控制器结果渲染到既有 Text、目录按钮与提示文本，原事件、确认弹窗和布局保持。 |
| `tests/test_storyboard_final_controller.py` | 新增无 Tk 回归：选中偏好、预览/导航状态、非法 JSON 不写入、合法编辑原子保存。 |
| `tests/architecture/_layers.py`、`tests/architecture/test_storyboard_edit_boundary.py`、`tests/architecture/test_storyboard_final_selection_boundary.py` | 登记 L2 编辑服务与 L3 控制器，并将原有“不得直接保存／选中偏好须委派”的断言迁至控制器接缝；本次测试调整因控制器契约迁移，断言未弱化。 |
| `architecture.md`、`project_status.md` | 登记控制器职责、轮次和债务余额。 |

生产模块仅 2 个：`storyboard_files.py`、`storyboard_final_controller.py`，符合“每次最多改 3 个模块”。未改用户项目数据、分层规则或既有保存／选择契约。

## 验证

| 命令 | 结果 |
| --- | --- |
| `python -m unittest tests.test_storyboard_final_controller tests.test_storyboard_edit_service tests.architecture.test_storyboard_edit_boundary tests.architecture.test_storyboard_final_selection_boundary` | 8/8 通过 |
| `python smoke_test.py --affected storyboard_final_controller final_viewer` | 15 条通过，0 红文件 |
| `python smoke_test.py` | 8/8 通过 |
| `python smoke_test.py --architecture` | 95/95 通过，无新增架构红点 |

补充：`--affected storyboard_files` 当前没有对应测试筛选别名，会被运行器判为 0 个测试文件；本轮没有修改该无关映射，故以实际新增控制器与既有定稿视图测试作为定向验收。

## 自检

- 预览、保存和导航的领域状态不再由 `show_final()` 内部字典维护；保存仍由 `storyboard_edit_service.save_edited_json()` 原子执行，选中偏好仍由 `storyboard_selection.remember_final_view()` 持久化。
- 未新增功能、未改变页面按钮、确认语义、镜头跳转行为、数据格式或目录结构。
- 自审：通过。范围、模块上限、分层与三项用户指定验证均符合要求。
