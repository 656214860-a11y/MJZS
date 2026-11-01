# R482 结构治理：白模预演媒体发布服务化

## 轮次结论

- 本轮是结构治理轮：白模预演 UI 不再直接复制用户媒体或发布预演记录。
- 三个基线均通过：定向 51/51、架构 78/78、默认冒烟 8/8、全量 3,200/3,200。
- `project_status.md` 欠账减少一处 L4 正式写入边界；后续仍需扫描其他遗留页面。

## 完成内容

- `white_model_service.import_previs_media()` 统一校验镜头编号、格式和非空，以临时副本校验后原子发布白模视频或工程，并更新预演记录；源文件始终保留。
- `white_model_service.save_previs_notes()` 接管备注记录保存；`white_model.py` 仅保留文件选择、界面状态与服务调用。
- 新增白模导入 UI→服务静态边界及服务行为回归；将既有 `test_delivery_import_boundary.py` 补入 `AGENTS.md` 第 5 节自检表。

## 验证

- `tests.test_previs` 与 `tests.architecture.test_white_model_import_boundary`：51/51 通过。
- `smoke_test.py --architecture`：78/78 通过。
- `smoke_test.py`：8/8 通过。
- `unittest discover -f -q`：3,200/3,200 通过，耗时 538.7 秒。
