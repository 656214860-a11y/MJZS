# R2437 可靠性轮：继续向 LiteLLM 架构对齐

## 结论

继续补齐上轮列出的 API 优化项，并把模型健康、认证、限流、响应解压与请求审计能力落到现有零依赖模块中。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - 增加响应体 32 MiB 上限与流式 8 MiB 缓冲上限，`Content-Length` 预检后拒绝超限响应。
  - 支持 gzip/deflate 响应解压，解压后仍受字节上限约束。
  - 增加主机级 RPM 限流基础件 `set_host_rate_limit()`／`_RateBucket`，传输前调用 `_wait_for_rate_limit()`。
  - 增加 `health_is_blocked()` 与 `certify()`：失败健康记录在配置版本一致时阻止路由；`certify()` 复用小样本验证并记录五维检查。
- [model_router.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_router.py)
  - `ModelRouter.usable()` 与 `available_models()` 接入健康准入，最近一次完整任务失败的模型不再作为候选。
- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py)
  - 真实直连在 `model_admission_error()` 后追加健康闸门，失败模型暂停无人值守直连。
  - 结构化输出重试改为有界指数退避（`MAX_FORMAT_RETRIES=2`，0.25s 起），取消仍即时中断。
- [video_prompt_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/video_prompt_direct_api.py) 与 [audio_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/audio_direct_api.py)
  - 复用同一套有界退避，不再硬编码“只试一次”。
- [request_ledger.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/request_ledger.py)
  - 新增 `record_attempt()`，按请求号追加状态、错误类、Retry-After、协议、信封完整性与重试次数，不改金额与状态。
- [model_metering.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_metering.py)
  - `metered()` 发送后把最终传输尝试写入请求台账，异常路径也记录 `error_class='exception'`。

## 验证

- 定向 unittest：213/213 通过（含新增 11 条健康/限流/解压/台账用例；`test_api_cache_usage` 中 1 条历史 import 环境错误不计入本次改动）。
- 架构：`test_no_circular_import` + `test_layers` 8/8 通过。

## 提交

- 已提交：`e9f543b994f20490eadfd7e0bb242c9769790910`
- 分支：`codex/wip-R2437`
