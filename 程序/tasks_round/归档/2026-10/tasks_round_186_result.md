# Round 186 结果：分镜目录服务层收口

## 轮次类型

功能轮（优化清单 P0「视图 / 服务 / 适配器拆分」的分镜文件子范围）。

## 完成内容

- 将目录候选扫描后的剧本/分镜筛选、排序、来源解析、已制作剧本和已生成集数计算迁移到无 Tk 的
  `storyboard_catalog_service`。
- `storyboard_files` 仅保留同名兼容门面；删除计划与页面构建不在本轮范围内。

## 改动文件

- `storyboard_catalog_service.py`
- `storyboard_files.py`
- `project_status.md`
- `tasks_round/tasks_round_186_result.md`

## 验证

- 项目内置 Python：`-m py_compile storyboard_files.py storyboard_catalog_service.py storyboard_catalog.py` 通过。
- `-m unittest tests.test_core tests.test_file_cache tests.test_workflow`：201/201 通过。
- `smoke_test.py`：8/8 通过。

## 审查

通过：新服务不导入 Tk 或页面模块；兼容入口保留，且“传入已扫描 entries 不再重复扫描”的测试接缝未变。未修改用户项目数据或范围外页面代码。
