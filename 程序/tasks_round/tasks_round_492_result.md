# R492 结构治理轮：剧本工作区初始化服务化

## 结论

- 完成 R461 E4 的下一项最小拆分：`Desktop.writing()` 不再直接创建剧本准备阶段目录；`script_workspace_service.ensure_script_workspace()` 负责目录初始化并返回该工作区路径。
- 页面仍只承担控件装配与交互，目录规则集中在无 Tk 的剧本工作区服务。

## 变更与验证

- 新增 `ensure_script_workspace(project)`，仅创建 `project_stages.writing(project)` 所指向的阶段目录。
- `desktop.py` 的剧本页改为调用服务。
- 服务测试覆盖新项目下的目录创建与返回路径；现有 AST 边界测试新增 UI 委托断言。
- 定向 `tests.test_script_workspace_service` + `tests.architecture.test_script_rename_boundary`：14/14 通过（0.351 秒）。
- 架构 `smoke_test.py --architecture`：84/84 通过（12.466 秒）。

## 范围

- 未修改用户项目数据、删除流程、Tk 生命周期或白模上传。
- 下一步继续从 `desktop.py`、`storyboard_files.py`、`asset_batch.py` 中选择独立且可无 Tk 验证的热点；外部上传仍需用户授权。
