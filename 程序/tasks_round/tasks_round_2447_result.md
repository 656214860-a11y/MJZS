# R2447 可靠性轮：直连 API 接入模型组降级

## 结论

初步分镜、视频提示词、音频脚本的直连执行器在首选模型可重试失败时，按 `group` 字段遍历同组候选模型，成功即返回；每个候选走独立台账结算，避免跨模型误记账。

## 关键改动

- [storyboard_direct_api.py](/C:/Users/LAIBIAO/.codex/worktrees/c5b5/漫剧制作助手/程序/storyboard_direct_api.py)
  - `_Batch` 保存 `stage` 与 `group_candidates`。
  - `_ask()` 在首选流式请求可重试失败后，用 `chat_metered()` 依次尝试同组候选；取消仍即时中断，截断仍拒绝落盘。

## 验证

- 分镜/视频提示词/音频脚本直连测试 21/21 通过。

## 提交

- 已提交：`b0f4e9317c18ea14950da3b3b5371b361f32b4de`
- 分支：`codex/wip-R2447`
