# R496 结构治理轮：阶段工作区初始化服务化

## 结论

- 配音、后期和交付页面的既有编号阶段目录初始化，已从 `desktop.py` 收敛到无 Tk 的 `stage_workspace_service`。
- 服务仅经 `project_stages` 返回并创建既有目录；不发布用户成果、不启动外部程序，也不触发网络或上传。

## 变更与边界

- `ensure_audio_workspace()` 初始化音频和字幕目录；`ensure_editing_workspace()` 初始化后期目录；`ensure_delivery_workspace()` 初始化交付及导出目录。
- `Desktop.audio()`、`import_audio()`、`editing()`、`delivery()` 与 `final_import()` 保留界面、文件选择和状态职责，不再直接调用 `mkdir`。
- 新增服务行为回归与五入口 AST 边界，防止页面重新直接初始化这些阶段目录。

## 验证

- 定向服务、音频/交付既有回归与架构边界：8/8 通过（0.166 秒）。
- 编译：`desktop.py`、`stage_workspace_service.py` 通过。
- 架构门禁：86/86 通过（21.967 秒）。
- 默认冒烟：8/8 通过。

## 后续

- 继续按 R461 E4 处理可独立验证的 `desktop.py` 热点；白模真实上传仍需要用户对具体素材授权。
