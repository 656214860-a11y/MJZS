# R593 结构治理轮结果：P0-3 视频提示迁移与闭环

## 改动文件

- `video_prompt_publication.py`：提示词 JSON、阶段文本副本和分镜索引改为可注入的关联成果整包发布；无注入调用保留既有兼容回退。
- `app.py`：手动保存、切镜自动保存向发布服务注入 `publish_stage_bundle()`。
- `video_prompt_results.py`：自动提示词结果写回向发布服务注入 `publish_stage_bundle()`。
- `tests/test_video_prompt_publication.py`、`tests/architecture/test_video_prompt_publication_boundary.py`：新增整包失败回滚和三条生产入口注入门禁。
- `tests/architecture/test_audio_import_boundary.py`、`tests/architecture/test_delivery_import_boundary.py`：冻结音频、交付入口的二进制发布器注入关系。
- `project_status.md`：关闭 P0-3 并更新债务台账。

## 迁移结果

视频提示的三条生产写入路径均通过 L3 `publish_stage_bundle()` 发布。提示词 JSON、两个用户可见文本副本和 episode 索引只会整体成功；写入或索引异常时会回滚所有本轮成果，内存 episode 也不会提前更新。

`video_prompt_publication`（L2）只接受注入发布器，未导入 `stage_execution_service`（L3）。由 UI/结果边界负责注入，分层与既有服务直调兼容性不变。

## 验证

- `python -m unittest tests.test_video_prompt_publication tests.architecture.test_video_prompt_publication_boundary tests.test_stage_execution_service tests.test_keyframe_lifecycle_service tests.test_audio_import_service tests.test_delivery_import_service`：28/28 通过。
- `python smoke_test.py --affected video_prompt_publication`：通过（定向 8/8）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

测试中的既有 `ResourceWarning` 来自历史测试文件句柄，未造成失败；R588 所记受限沙箱增量台账权限提示亦不影响应用结果。

## 债务状态

P0-3 已完成：交付（R590）、音频（R591）、首帧（R592）和视频提示（R593）均已迁入统一发布入口；字幕继续作为 R512 回归样本，不重复改造。R182 拆分债务由 2 项降为 1 项，仅余 R568/P3-2，需待 2027-03-31 兼容窗口到期后再判断可删除 facade。
