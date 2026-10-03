# R887 UI 统一入口覆盖：文字层级首批迁移

- `asset_batch.py`、`asset_reference_images.py`、`asset_reference_import.py`、`cloud_assets.py` 的说明和进度标签已迁入 `DescriptionBlock`／`ProgressLabel`。
- 保留字段名、`StringVar`、布局和换行参数；不改变业务逻辑。
- 验证：上述模块语法检查通过；输入与表格门禁合计 21 条／0 红。
- 路线图文字层级项仍有其他页面待迁移，本轮不声称完成。
