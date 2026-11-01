# R428 结构治理轮：分镜定稿发布边界

- **范围**：R418 J-1 的分镜定稿产物族，只补“发布者唯一性”契约；不改阶段完成事件、媒体复制、用户数据或其他阶段。
- **改动**：移除 `storyboard_final` 未使用的直接 JSON 写入导入；新增 `test_final_bundle_boundary.py`，要求 finalizer 导入并调用 `storyboard_storage.publish_final_bundle()`，且不得直接调用 JSON 保存接口。
- **测试**：新增测试是既有发布契约的静态保护，未弱化、删除或跳过断言；AGENTS 门禁清单与基线同步为 20 个文件、38 项。
- **验证**：定稿相关 `python -m unittest tests.architecture.test_final_bundle_boundary tests.test_final_viewer` **14/14** 通过；架构 **38/38** 通过（15.833 秒）；默认冒烟 **8/8** 通过。
- **欠账**：未减少总项；仍需其他阶段产物族分批迁移，白模真实上传继续等待用户授权。
