# R930 UI 统一入口：图标创建审计

- 新增递归 `PhotoImage` 创建门禁：生产 UI 页面不得直接创建图标，必须使用 `IconLoader`。
- 唯一允许的实现所有者为 `ui_icons.py` 与 `asset_thumbs.py`；后者负责文件媒体缩略图缓存，不属于图标体系。
- 视频返回图标继续明确检查通过共享加载器取得。

验证：

- `python -m unittest tests.architecture.test_ui_icons_boundary`：2 条通过。
- `python smoke_test.py`：8 项通过、0 失败。
