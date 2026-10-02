# Round 153 结果：当前可本地闭环的删除阻塞

类型：修复轮  
日期：2026-09-26

## 已完成

1. `app_shortcut.py` 不再直接删除 PowerShell 临时脚本，交由 `file_cache.remove_temporary_file()` 管理。
2. `engine_probe.py` 不再直接递归删除探针临时目录，交由 `file_cache.remove_temporary_tree()` 管理。
3. `projects.py` 不再直接 `os.rmdir()` 项目内部 junction；受限删除移动至 `storage_maintenance.remove_project_link_node()`，该接口只接受 junction，绝不进入其连接目标。

## 验证

- 架构删除权威：`tests.architecture.test_remove_authority` 1/1 通过。
- 存储与核心：`tests.test_storage tests.test_core` 106/106 通过。
- 默认 `smoke_test.py`：8/8 通过。

## 未完成阻塞

- 白模视频真机上传必须由用户指定已采用且已生成预演视频的镜头，并授权向目标平台上传；本轮未访问或上传用户素材。
- 全量自检的依赖层、循环依赖、路径权威等历史红灯仍需分模块收口；本轮没有放宽任何架构门禁，也不能据此宣称全量通过。

## Reviewer 结论

通过。三个删除点均被收至明确的生命周期模块；项目文件和用户素材未被删除或移动。剩余架构红灯保持可见，避免以改测试或白名单方式掩盖问题。
