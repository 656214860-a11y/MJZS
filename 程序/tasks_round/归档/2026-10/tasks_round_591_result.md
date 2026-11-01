# R591 结构治理轮结果：P0-3 音频导入迁移

## 改动文件

- `audio_import_service.py`：`import_audio()` 增加可选的发布器注入；注入路径先读取并按原文件大小校验字节，再发布。
- `desktop.py`：音频导入 UI 注入 `stage_execution_service.publish_stage_bytes()`。
- `tests/test_audio_import_service.py`：新增注入式正式发布回归。
- `project_status.md`：登记本轮进度。

## 迁移结果

生产 UI 的“导入配音／音乐”已通过统一二进制发布器完成正式落盘。L2 音频服务继续拥有格式、非空、阶段目录与唯一命名规则，且在调用发布器前检查读取字节数仍等于初始源文件大小；L4 注入 L3 发布器，未产生 L2→L3 导入。

未传入发布器的调用仍走原有“临时副本 → 尺寸校验 → replace”的兼容路径。源文件不会修改。

## 验证

- `python -m unittest tests.test_audio_import_service tests.test_delivery_import_service tests.test_stage_execution_service`：11/11 通过。
- `python smoke_test.py --affected audio_import_service`：通过（定向 3/3）。
- `python smoke_test.py`：8/8 通过。
- `python smoke_test.py --architecture`：101/101 通过。

受限沙箱的增量台账权限提示不影响结果，原因和真实权限复核见 R588。

## 债务状态

P0-3 仍未完成：交付和用户音频导入已迁移；首帧替换具有“旧首帧回收且失败恢复”的额外语义，视频提示成果亦待迁入。不得因本轮的两条迁移路径提前关闭 P0-3。
