# R2589 结果：SWE-2 T3 第二轮——volcengine/wan 计费适配器迁入 http_client
<!-- round-evidence: {"commit_base": "e521a5a6", "credential_hits": 0, "evidence_sha256": "c1d2b552bac86546", "exit": 0, "failed": 0, "passed": 56, "round": 2589, "tests": "run_selftests.py -k execution_deadline shared_adapter cloud_video http"} -->

## 类型与三问

- 类型：功能轮（调用方迁移，≤3 个/轮）。
- 测试：`run_selftests.py -k "execution_deadline shared_adapter cloud_video http"` 全绿；默认冒烟见提交证据。
- project_status 欠账：无新增。

## 交付

- `agent/volcengine.py`、`agent/wan.py` 的 `call()` 改经 `http_client.request_json()`；计费 POST 仍零重试（retries=0 默认）；`ArkRejected` 消息格式、密钥 `[REDACTED]`、图片 data-URL `[IMAGE]` 截断、网络错误抛 `URLError` 语义全部保持。
- `test_http_boundary` 白名单移除两文件（棘轮下降）。
- `test_execution_deadline` mock 的 `response.read` 改为 side_effect=[body, b'']（真实 EOF 语义；原 return_value 会让有界读取死循环到上限）。

## 验收

- 断网/超时/5xx/429 由 test_http_client 覆盖；本轮迁移行为由 test_execution_deadline、test_shared_adapter_infrastructure、test_cloud_video 回归。

## 后续

- api_endpoints._http_transport 收编评估、local_video/seedream_api/tts_api/batch_frames 迁移、platform_tools 收尾。

## 提交

- 待回填 hash。
