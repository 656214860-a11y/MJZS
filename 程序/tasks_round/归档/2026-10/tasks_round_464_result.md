# R464 结构治理：手动创意发布边界

## A. 范围

承接 R462 的正式成果直写扫描，仅处理剧本准备页的手动创意另存。

## B. 变更

- `idea_chat.save_manual_creative()` 接管分类目录创建、四段式自然剧本命名与原子发布。
- `desktop.py` 只保留预置示例拦截、编辑状态和状态栏提示。
- 新增 UI→服务静态边界与服务行为回归。

## C. 保持不变

用户未改示例不落盘；同日重复仍以序号区分；正文、目录分类、文件编码和保存后的编辑器状态保持原口径。

## D. 验证

- `python -m unittest tests.test_idea_chat tests.test_ui_edges.UiEdgeTests.test_the_brief_example_never_lands_in_the_project`：63/63 通过。
- `python smoke_test.py --architecture`：66/66 通过。
- `python smoke_test.py`：8/8 通过。

## E. 后续

剩余本轮扫描目标为剪辑优化清单的保存；删除入口、上下文/预算、响应式和平台旧入口仍按 R461 路线分批处理。白模真机上传仍需用户对具体素材明确授权。
