# Round 187 结果：分镜目录兼容门面收敛

## 轮次类型

功能轮（优化清单 P1「旧接口兼容集中到 facade 模块」的分镜目录子范围）。

## 完成内容

- `storyboard_catalog` 改为直接导出 `storyboard_catalog_service` 和
  `storyboard_selection` 的无 Tk 实现，不再通过动态导入反向加载 `storyboard_files` 页面模块。
- 保留既有函数名与 `remember()` 语义，并在门面文档中标注旧项目路径兼容的淘汰日期。

## 改动文件

- `storyboard_catalog_service.py`
- `storyboard_catalog.py`
- `storyboard_files.py`
- `project_status.md`
- `tasks_round/tasks_round_187_result.md`

## 验证

- 项目内置 Python：受影响调用模块 `-m py_compile` 通过。
- `-m unittest tests.test_core tests.test_file_cache tests.test_workflow`：201/201 通过。
- `smoke_test.py`：8/8 通过。

## 审查

通过：领域调用不再因导入 catalog 而触发 Tk 页面依赖；兼容门面仍是唯一历史调用入口。未修改用户项目数据或范围外页面代码。
