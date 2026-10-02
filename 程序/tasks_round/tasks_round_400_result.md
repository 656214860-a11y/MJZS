# 第 400 轮结果

## 完成内容

- 验证阶段配置到执行器的模型来源链：本地 Flux、DeepSeek、Codex 与自动选择的定向测试均通过。
- 只读探测本机 ComfyUI：发现 `C:\\Program Files\\Comfy Desktop\\Comfy Desktop.exe`，但应用配置的 `/system_stats` 端点返回 HTTP 502。
- 未启动 ComfyUI，未创建项目、未提交生成请求、未上传任何素材。

## 改动文件

- `project_status.md`
- `tasks_round/tasks_round_400_result.md`

## 验证

- ComfyUI 本机探测：可执行文件存在；`http://127.0.0.1:8188/system_stats` 返回 HTTP 502。
- `run_selftests.py --safe --serial -k workflow keyframe_model_service stage_model_value keyframe_comfy`：95/95 通过。
- `smoke_test.py`：8/8 通过。
