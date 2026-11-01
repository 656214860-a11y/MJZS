# R405 性能/资源轮结果

## 目标

完成大文本框按需加载：后台读取之外，超长剧本预览也不能一次性阻塞 Tk 主线程。

## 改动

- `script_preview_service.py`：新增 32 KiB 的预览文本分块迭代器。
- `desktop.py`：超 512 KiB 的已后台读取预览经 `after_idle` 分块投递；小预览保持即时插入，过期请求仍由既有票据丢弃。
- `tests/test_script_preview_service.py`：覆盖分块顺序与单块大小。
- `tasks_round/tasks_round_182_optimization_checklist.md`：完成大文本按需加载／分镜后台扫描总项。
- `project_status.md`：推进至 R406。

## 验证

- `python -m unittest tests.test_script_preview_service`：4/4 通过。
- `python -m py_compile desktop.py script_preview_service.py`：通过。
- `python smoke_test.py --affected script_preview_service`：9/9 通过，定向自检 4/4 通过。
- `python smoke_test.py`：8/8 通过。

## 自审

仅改变剧本结构页的大文本渲染节奏；未改变预览内容、后台读取策略、编辑语义、阶段逻辑或用户项目数据。
