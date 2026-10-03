# R852 结果｜本地资产排队认领失败可见化

## 修复

- `native_assets._submit_job()` 在 ComfyUI 已接受 `/prompt`、但 `/drama/assets/ack` 网络失败时，继续保持“已排队、不重复提交”的安全语义。
- 该失败现在写入批次记录的 `ack_warning`，并立即经既有进度报告通道向用户说明：后续会按输出目录核对结果。

## 回归

- 新增 `test_a_failed_ack_is_visible_without_resubmitting_the_prompt`：注入回执断网，断言状态可见、记录保留原因、且 `/prompt` 仅调用一次。

`[TASK_COMPLETE]`：已收口一个网络空白路径；其余 AST 候选继续按 I/O 类型逐项裁决。
