# R561｜结构治理轮（子场景：执行）

## 来源与执行项

- 来源：`tasks_round/tasks_round_547_result.md` J 节。
- 执行：P2-1——为剩余文件表实现可取消的增量目录加载与批量 UI 提交，避免大项目刷新时一次性枚举和渲染全部条目。

## 完成结果

- `script_workspace_service.iter_script_documents()` / `iter_script_document_rows()` 逐项产出剧本准备可见文件，不再要求调用方先取得完整目录结果；原 `discover_script_documents()` / `script_document_rows()` 对外行为和修改时间倒序保持不变。
- `Desktop.writing()` 的三列文件表改为每批 24 条经 `after_idle` 发现并插入；扫描结束后仍按原修改时间倒序，每次排序提交同样最多移动 24 条。
- 刷新、页面重建和销毁都使旧代次失效并取消待执行回调，不会把旧项目或旧页面的扫描结果提交给新的 Treeview。
- `storyboard_files.show()` 已有后台扫描与结果队列，本轮不重复改造其既有路径；未改变目录、选择、勾选、删除或打开文件契约。

## 改动文件

| 文件 | 变更 |
| --- | --- |
| `script_workspace_service.py` | 增加无 Tk 的逐项文件/行迭代器，并保留原完整列表 API。 |
| `desktop.py` | 三列剧本文件表改为可取消的空闲批次加载和批次排序。 |
| `tests/test_script_workspace_service.py` | 新增迭代器首项与行元数据回归；断言未弱化。 |
| `architecture.md`、`project_status.md` | 同步增量加载边界、轮次和债务状态。 |

应用代码仅改动 2 个模块，符合“最多 3 个模块”约束。

## 验证

- `python -B -m unittest tests.test_script_workspace_service`：14/14 通过。
- `python -B smoke_test.py --affected desktop script_workspace_service`：5 个测试文件、21 条用例通过。
- `python -B smoke_test.py`：默认冒烟 8/8 通过。
- `python -B smoke_test.py --architecture`：架构门禁 98/98 通过。

## 债务状态与自审

- P2-1 已完成；R182 可执行拆分债务由 8 项减至 7 项。P0-3 的既有二进制成果发布/分层阻塞不变。
- 通过：不改分层、对外契约或用户数据；未新增产品功能；应用代码改动 2 个模块；无新增架构红点。
