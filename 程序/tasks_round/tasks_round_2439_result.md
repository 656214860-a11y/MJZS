# R2439 可靠性轮：RPM 配置与无人值守认证策略

## 结论

把每模型 RPM 上限接进模型池记录，并在请求发送前按主机名限流；为无人值守直连增加“五合一认证”可开关的准入门，默认关闭、可经常量开启。

## 关键改动

- [model_pool.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/model_pool.py)
  - `FIELDS` 增加 `rpm`，模型记录可保存每分钟请求上限。
  - 新增 `wait_for_rpm(base_url, rpm)`：按主机名维护本地速率桶，发送前等待；0/空不限制。
  - `model_admission_error()` 增加 `require_certified` 参数，为真时要求最近一次五合一认证绿灯且配置版本一致。
  - 新增常量 `REQUIRE_CERTIFIED_FOR_UNATTENDED`，默认 False，保留第一方配置开关。
- [writing_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/writing_api.py)
  - `WritingRequestAdapter._call()` 读取记录 `rpm`，大于 0 时在发送前调用 `wait_for_rpm()`。
- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py)
  - 真实直连准入调用带上 `require_certified=REQUIRE_CERTIFIED_FOR_UNATTENDED`。

## 验证

- 定向 unittest：相关用例通过；`test_writing_api_output_budget` 仍因既有 `from test_writing_api import` 环境路径问题无法以单模块方式导入，不计入本轮改动。
- 架构：`test_no_circular_import` + `test_layers` 8/8 通过。

## 提交

- 已提交：`4e3657cb7d5f3e494c404d4178ae67e518662e6c`
- 分支：`codex/wip-R2439`
