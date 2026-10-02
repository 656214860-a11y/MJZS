# Round 185 结果：分镜文件选择服务层收口

## 轮次类型

功能轮（优化清单 P0「视图 / 服务 / 适配器拆分」的分镜文件子范围）。

## 完成内容

- 将已选剧本/分镜的配置读取、持久化、路径去重和结构剧本同步迁移到无 Tk 的
  `storyboard_selection`。
- `storyboard_files` 保留原函数签名作为兼容门面；删除计划与 UI 构建不在本轮范围内。

## 改动文件

- `storyboard_selection.py`
- `storyboard_files.py`
- `project_status.md`
- `tasks_round/tasks_round_185_result.md`

## 验证

- 项目内置 Python：`-m py_compile storyboard_files.py storyboard_selection.py` 通过。
- `-m unittest tests.test_file_cache tests.test_workflow`：95/95 通过。
- `smoke_test.py`：8/8 通过。

## 审查

通过：服务层无 Tk 依赖，调用方继续使用原兼容入口；未修改用户项目数据或范围外页面代码。
