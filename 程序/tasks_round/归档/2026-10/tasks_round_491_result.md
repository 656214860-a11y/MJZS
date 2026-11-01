# R491 结构治理轮：剧本重命名服务边界

## 结论

- 完成 R461 E4 的最小可验证拆分：`Desktop.writing()` 的剧本重命名不再直接调用 `Path.rename()`；`script_workspace_service.rename_script_document()` 负责项目内路径校验与实际重命名，UI 仅发起请求并刷新列表。
- 新增服务行为测试与 UI→服务 AST 边界测试。未涉及 Tk 控件、用户项目数据、删除行为或真机上传。

## 变更

- `script_workspace_service.py`：新增 `rename_script_document(project, source_path, requested_name)`，复用既有工作区路径筛选和目标命名校验，目标与源不同才执行单文件重命名。
- `desktop.py`：`rename_script()` 改为调用该服务，不再拥有文件改名操作。
- `tests/test_script_workspace_service.py`：覆盖合法项目内文件的重命名、源文件消失与内容保留。
- `tests/architecture/test_script_rename_boundary.py`：要求 UI 委托服务，且禁止该回调直接使用 `.rename()`。
- `AGENTS.md`：同轮更新架构门禁清单与基线为 50 个文件、83 个检查。

## 验证

- 定向：`python -m unittest tests.test_script_workspace_service tests.architecture.test_script_rename_boundary`，12/12 通过（0.24 秒）。
- 架构：`python smoke_test.py --architecture`，83/83 通过（19.24 秒）。
- 服务层：`python run_selftests.py --layer service --all`，1,483/1,483 通过（24.9 秒），最慢单元 23.8 秒；未触发 R488 J2 的 180 秒阈值。
- 默认冒烟：`python smoke_test.py`，8/8 通过。

## 后续

- R461 E4 尚有大型页面拆分空间；后续仅选择独立、可无 Tk 验证的热点逐项推进。
- 白模真机上传仍需用户明确授权，本轮未尝试。
