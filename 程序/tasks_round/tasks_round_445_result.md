# R445 只读诊断轮结果

## 范围与证据

- 来源：`tasks_round/tasks_round_418_result.md` J3/K 的分镜文件面板拆分路线。
- `storyboard_files.py:339` 在定稿正文编辑回调中完成 JSON 合法性校验后直接调用 `agent.core.save(path, data)`；它是该模块唯一直接写入点。
- 该面板的目录发现、选择偏好、最终查看指针与回收恢复已分别委托 `storyboard_catalog_service`、`storyboard_selection` 和 `storyboard_recycle_service`；`tests/test_final_viewer.py` 已覆盖编辑与保存的现有行为。
- `desktop.py:4771`、`:4827`、`:4845`、`:4941` 等资产管理遗留写入属于另一条多文件资产变更链，不能在分镜正文保存轮中顺带迁移。

## 整改路线

1. 下一实际轮仅为分镜文件正文编辑建立或扩展既有分镜服务的无 Tk 保存接口：接收目标路径与 JSON 对象，复用 `agent.core.save()` 的原子发布；UI 保留输入读取、合法性提示、刷新和状态文案。
2. 先补服务行为测试（合法 JSON 发布、无效/服务失败不覆盖旧文件），再将 `show_final()` 的编辑保存回调委托该接口。
3. 新增窄架构门禁：`storyboard_files.py` 的正文编辑回调不得直接调用 `save()`，必须调用该服务；不把正常编辑路径误扩展为“阶段完成”或“自动发布”。

## 边界与结论

- 未改任何 `.py`、权威文档、用户项目数据或齿轮→设置入口；按只读诊断协议未运行测试。
- 此闭环只能减少分镜文件页的 View/Service/Adapter 欠账，不足以关闭“统一阶段写入”总项；白模真实上传仍等待用户授权。
