# R463 结构治理：手改自然剧本发布边界

## A. 范围

承接 R462 的直接写入扫描，仅处理结构页“保存修改”对自然剧本的正式发布。

## B. 变更

- `script_contract.save_natural_script()` 统一校验 Markdown 目标、自然剧本正文并原子写入。
- `desktop.py` 的结构页保存入口委托上述合同服务，不再直接写入。
- 增加服务行为和 UI→合同静态边界回归。

## C. 保持不变

页面编辑/恢复状态、保存后提示、末尾换行和原文件位置均不变；不改结构剧本生成、用户数据或其他导出入口。

## D. 验证

- `python -m unittest tests.test_script_contract tests.test_ui_edges.UiEdgeTests.test_script_structure_page_shows_source_and_output_in_separate_boxes`：45/45 通过。
- `python smoke_test.py --architecture`：65/65 通过。
- `python smoke_test.py`：8/8 通过。
- `python run_selftests.py --all --safe`：3,164/3,164 通过，741.4 秒，0 个失败文件。

## E. 风险与后续

自然剧本保存现在会拒绝结构化正文，符合既有阶段边界；后续仍有创意另存、剪辑优化清单及删除入口待逐项收敛。白模真机上传继续等待用户对具体素材授权。

## F. 测试迁移

新增测试均在既有 `tests/` 与 `tests/architecture/` 下，无搬迁、无重复模块。
