# R505 修复轮：密钥安全迁移与剧本输入布局修复

## 结论

- 模型密钥的新保存路径已统一为当前 Windows 用户的 DPAPI 加密记录；程序根目录旧 `private/.env` 已在成功迁移后清除，未回显任何密钥内容。
- 云视频新会话只保存 `key_env` 和 `key_provider=model_pool`，运行时经模型池取回 DPAPI 凭据；历史会话的 `.env` 读取仅保留只读兼容。
- 同轮修复剧本准备页点击空输入框后输入区与对话区互相触发尺寸重算的布局循环。

## 变更

1. `model_secrets.migrate_legacy_env()` 以全部条目加密成功为前置条件；加密失败回滚，旧文件删除失败则保留明文文件并报错。
2. `model_pool.save_key_env()` / `save_named_key()` 不再写 `.env`，先迁移旧文件再写 DPAPI；模型管理界面同步只走此入口。
3. `api_endpoints.configured_key()` 支持 `key_provider=model_pool`；`cloud_video` 保存会话时不再存 `project_dir` 的明文路径，`cloud_video_service` 优先从模型池读取。
4. `desktop.writing()` 在用户点击输入框时冻结展开行数，失焦才恢复，避免 `Configure` 回调循环。

## 验证

- 实际迁移后：旧明文文件不存在，检测到 9 份 DPAPI 加密记录；未读取或输出密钥值。
- `tests.test_model_pool tests.test_pet_settings tests.test_pet_llm tests.test_api tests.test_cloud_video tests.test_integration`：250/250 通过。
- `tests.test_idea_chat.SendMessageTests`：18/18 通过（含连续空闲布局稳定性回归）。
- `smoke_test.py`：8/8 通过。

## 后续

- P1：按真实 OpenAI Responses 协议使用 `max_output_tokens`，解析 `output[*].content[*].type=output_text`，验证 `input_tokens` / `output_tokens` 记账。
- P2：云视频 API Key Entry 默认掩码、仅显式短暂显示，并覆盖 Tk 回归。
