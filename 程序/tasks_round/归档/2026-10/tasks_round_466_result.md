# R466 结构治理：离线编剧任务书路径权威

## A. 范围

仅处理离线“生成编剧任务书”新增成果包的写入目录，承接 R461 的阶段路径权威扫描。

## B. 变更

- `writing.prepare()` 改由 `project_stages.writing()` 确定任务书成果包目录。
- 新任务书、技能位置、资产表、模板及参考素材继续生成在同一批次目录；旧 `writing/` 不再作为新写入目标。
- 新增静态门禁，锁定 `prepare()` 必须调用剧本准备阶段服务。

## C. 保持不变

离线按钮行为、输入校验、任务书正文、资产参考复制和 JSON 模板保持不变；不改写或删除既有历史目录。

## D. 验证

- `python -m unittest tests.test_core.ProjectsEngineTests.test_prepare_task_brief_uses_project_title tests.test_video_ui.WritingSheetExampleTests.test_the_grey_example_is_refused_at_the_door tests.architecture.test_stage_paths tests.architecture.test_writing_preparation_path_boundary`：6/6 通过。
- `python smoke_test.py --architecture`：68/68 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,169/3,169 通过（744.2 秒）。

## E. 后续

其余上下文/预算、响应式人工验收及白模真机上传仍按优化清单分批处理，其中真机上传仍需用户明确授权。
