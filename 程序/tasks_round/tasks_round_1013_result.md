# R1013 结果：收敛 TTS 项目上下文

## 变更

- `tts_api` 的整段配音复用与发布入口改为只接收 `ProjectContext`。
- `stage_execution_service` 统一构造上下文，桌面层经 L3 查询可复用的整段配音。
- 更新 TTS 与架构边界棘轮，并将 `tts_api` 从第二项待办移入 adopters。

## 验证

- `python -m unittest test_tts architecture.test_tts_publication_boundary architecture.test_project_context_boundary`：59 passed。
- `python -m py_compile tts_api.py stage_execution_service.py desktop.py`：通过。

## 提交凭据

- 实现提交：待写入。
- 凭据提交：待写入。
