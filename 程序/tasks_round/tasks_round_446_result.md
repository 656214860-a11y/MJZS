# R446 结构治理轮结果

## 范围

- 来源：`tasks_round/tasks_round_445_result.md` 整改路线 1—3。
- 仅迁移分镜定稿页正文编辑的 JSON 保存边界；不处理 `desktop.py` 资产链、阶段完成事件、上传、用户数据迁移或齿轮→设置入口。

## 改动

- 新增 L2 `storyboard_edit_service.save_edited_json()`：仅接收已校验 JSON，复用 `agent.core.save()` 原子发布并拒绝非 JSON 目标。
- `storyboard_files.show_final()` 继续负责 JSON 解析、确认提示、重载内容与状态文案，改为委托该服务，不再直接调用 `save()`。
- 新增服务行为测试与窄静态门禁；同步 `AGENTS.md` 的 32 个架构测试文件、56 项检查基线，以及 `architecture.md` 的 L2 职责表。

## 验证

- `python -m unittest tests.test_storyboard_edit_service tests.test_final_viewer tests.architecture.test_storyboard_edit_boundary`：17/17 通过。
- `python smoke_test.py --architecture`：56/56 通过。
- `python smoke_test.py`：8/8 通过。
- 全量安全自检未在本轮执行；最新可用全量基线仍为 R439 的 3,116/3,116。

## 自审与结束检查

- 通过：服务只承接页面已验证的正文保存，未伪造阶段完成或扩大可写路径；保存失败会保留旧文件。
- 通过：未改设置路由、主界面齿轮入口、外部服务和用户可见删除路径。
- 本轮为结构治理轮；项目已接续至 R447。统一阶段写入总项仍未关闭，白模真实上传仍等待用户授权。
