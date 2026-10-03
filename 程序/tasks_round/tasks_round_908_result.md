# R908 B 线幽灵项目条目处置核验

- 侧栏项目树的 `<Button-3>` 绑定进入 `Desktop.project_menu()`；失效项目目录只提供“只清除失效项目登记”，回调进入 `clear_missing_project()`。
- 该路径先拒绝仍存在的目录，再仅调用 `Projects.clear_missing_registration()`；不会进入项目回收或删除流程。登记写入失败会保留条目并显示可重试原因。
- 验证：`python run_selftests.py --safe -k core`，125 条／0 红。结论：台账所列主界面右键分流已具备可执行回归证据，B-ghost-entry 收口。
